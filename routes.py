import hashlib
import json
import queue
import re
import secrets
import time
from datetime import datetime, timedelta
from io import BytesIO
from urllib.parse import quote

from flask import Response, request, jsonify

from config import AUTH_PASSWORD
from utils import _ts_to_iso, _normalize_ts
from database import (
    dict_from_row, get_db,
    list_videos, add_video, delete_video, update_video,
    clear_scores, recalc_scores, get_latest_snapshot, get_snapshots,
    get_saturday_ref,
    get_default_group_id, list_rule_groups, get_rule_group,
    create_rule_group, update_rule_group, delete_rule_group,
    add_rule, update_rule, delete_rule,
    upsert_uploader, sync_video_uploaders, list_uploaders_with_videos,
)
from ratelimit import (
    check_challenge_rate, record_verify_failure, clear_verify_failures,
    check_export_rate, _check_ban, _get_client_ip, _verified_ips,
)
from monitor import state, broadcast, _subscribers, _log_handler, reset_collect_times_for_group, reset_collect_time_for_video


# 已使用的 nonce 集合（防重放攻击）
_used_nonces: set[str] = set()

# BVID 格式: BV + 10位 base58 (不含 0, O, I, l)
BVID_RE = re.compile(r'^BV[1-9A-HJ-NP-Za-km-z]{10}$')


def _validate_rule_interval(rule_type: int, value: dict) -> str | None:
    """验证规则采集间隔不小于 30 秒，返回错误信息或 None"""
    if rule_type == 1:
        interval = value.get("interval", 60)
        if interval < 30:
            return "采集间隔不能小于 30 秒"
    elif rule_type == 2:
        interval = value.get("target_interval", 60)
        if interval < 30:
            return "目标采集间隔不能小于 30 秒"
    return None


def register_routes(app):
    """在给定的 Flask app 上注册所有路由"""

    # ============ 认证 ============
    def verify_challenge(nonce: str, timestamp: str, response: str) -> bool:
        """验证 challenge-response 认证"""
        try:
            ts = int(timestamp)
        except (ValueError, TypeError):
            return False
        if abs(int(time.time()) - ts) > 300:
            return False
        if nonce in _used_nonces:
            return False
        expected = hashlib.sha256(f"{nonce}{timestamp}{AUTH_PASSWORD}".encode()).hexdigest()
        if not secrets.compare_digest(response, expected):
            return False
        _used_nonces.add(nonce)
        if len(_used_nonces) > 1000:
            _used_nonces.clear()
        return True

    def check_auth():
        """检查请求是否携带有效认证头"""
        if not AUTH_PASSWORD:
            return None
        nonce = request.headers.get("X-Auth-Nonce")
        timestamp = request.headers.get("X-Auth-Timestamp")
        response = request.headers.get("X-Auth-Response")
        if not all([nonce, timestamp, response]):
            return jsonify({"error": "需要密码验证"}), 401
        if not verify_challenge(nonce, timestamp, response):
            return jsonify({"error": "验证失败"}), 403
        return None

    @app.route("/auth/check")
    def api_auth_check():
        return jsonify({"protected": bool(AUTH_PASSWORD)})

    @app.route("/auth/challenge")
    def api_auth_challenge():
        limit = check_challenge_rate()
        if limit:
            return limit
        return jsonify({
            "nonce": secrets.token_hex(16),
            "timestamp": int(time.time()),
        })

    @app.route("/auth/verify", methods=["POST"])
    def api_auth_verify():
        if not AUTH_PASSWORD:
            return jsonify({"ok": True, "protected": False})
        ip = _get_client_ip()
        ban = _check_ban(ip)
        if ban:
            return ban
        data = request.get_json()
        if not data:
            return jsonify({"error": "缺少参数"}), 400
        nonce = data.get("nonce")
        timestamp = data.get("timestamp")
        response = data.get("response")
        if not all([nonce, timestamp, response]):
            return jsonify({"error": "缺少参数"}), 400
        if verify_challenge(str(nonce), str(timestamp), str(response)):
            clear_verify_failures()
            _verified_ips[ip] = time.time()
            return jsonify({"ok": True, "protected": True})
        ban = record_verify_failure()
        if ban:
            return ban
        return jsonify({"error": "密码错误"}), 403

    # ============ 规则组管理 ============
    @app.route("/rule_groups", methods=["GET", "POST"])
    def api_rule_groups():
        if request.method == "POST":
            auth_err = check_auth()
            if auth_err:
                return auth_err
            data = request.get_json()
            if not data or not data.get("name"):
                return jsonify({"error": "缺少 name"}), 400
            name = data["name"].strip()
            if not name:
                return jsonify({"error": "名称不能为空"}), 400
            group = create_rule_group(name)
            return jsonify(group)
        return jsonify(list_rule_groups())

    @app.route("/rule_groups/<int:group_id>", methods=["GET", "PUT", "DELETE"])
    def api_rule_group_detail(group_id: int):
        if request.method == "GET":
            group = get_rule_group(group_id)
            if not group:
                return jsonify({"error": "规则组不存在"}), 404
            return jsonify(group)
        auth_err = check_auth()
        if auth_err:
            return auth_err
        if request.method == "PUT":
            data = request.get_json()
            if not data or not data.get("name"):
                return jsonify({"error": "缺少 name"}), 400
            name = data["name"].strip()
            if not name:
                return jsonify({"error": "名称不能为空"}), 400
            update_rule_group(group_id, name)
            return jsonify({"ok": True})
        if request.method == "DELETE":
            try:
                moved_ids = delete_rule_group(group_id)
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            broadcast("videos", list_videos())
            # 只重置被移动的视频
            for vid in moved_ids:
                reset_collect_time_for_video(vid)
            return jsonify({"ok": True})
        return jsonify({"error": "method not allowed"}), 405

    @app.route("/rule_groups/<int:group_id>/rules", methods=["POST"])
    def api_add_rule(group_id: int):
        auth_err = check_auth()
        if auth_err:
            return auth_err
        data = request.get_json()
        if not data:
            return jsonify({"error": "缺少参数"}), 400
        rule_type = data.get("type")
        value = data.get("value")
        if rule_type is None or value is None:
            return jsonify({"error": "缺少 type 或 value"}), 400
        if rule_type not in (1, 2, 3, 4):
            return jsonify({"error": "无效的规则类型"}), 400
        # 验证采集间隔不小于 30 秒
        interval_err = _validate_rule_interval(rule_type, value)
        if interval_err:
            return jsonify({"error": interval_err}), 400
        import json
        rule = add_rule(group_id, rule_type, json.dumps(value, ensure_ascii=False))
        reset_collect_times_for_group(group_id)
        return jsonify(rule)

    @app.route("/rules/<int:rule_id>", methods=["PUT", "DELETE"])
    def api_rule_detail(rule_id: int):
        auth_err = check_auth()
        if auth_err:
            return auth_err
        if request.method == "PUT":
            data = request.get_json()
            if not data:
                return jsonify({"error": "缺少参数"}), 400
            rule_type = data.get("type")
            value = data.get("value")
            if rule_type is None or value is None:
                return jsonify({"error": "缺少 type 或 value"}), 400
            if rule_type not in (1, 2, 3, 4):
                return jsonify({"error": "无效的规则类型"}), 400
            interval_err = _validate_rule_interval(rule_type, value)
            if interval_err:
                return jsonify({"error": interval_err}), 400
            import json
            update_rule(rule_id, rule_type, json.dumps(value, ensure_ascii=False))
            # 找到该规则所属的规则组并重置
            with get_db() as conn:
                row = conn.execute("SELECT group_id FROM rules WHERE id=?", (rule_id,)).fetchone()
                if row:
                    reset_collect_times_for_group(row["group_id"])
            return jsonify({"ok": True})
        if request.method == "DELETE":
            # 先找到 group_id 再删除
            with get_db() as conn:
                row = conn.execute("SELECT group_id FROM rules WHERE id=?", (rule_id,)).fetchone()
            delete_rule(rule_id)
            if row:
                reset_collect_times_for_group(row["group_id"])
            return jsonify({"ok": True})
        return jsonify({"error": "method not allowed"}), 405

    # ============ 上传者浏览 ============
    @app.route("/uploaders")
    def api_uploaders():
        """返回按上传者分组的视频列表"""
        return jsonify(list_uploaders_with_videos())

    # ============ 视频管理 ============
    @app.route("/videos", methods=["GET", "POST"])
    def api_videos():
        if request.method == "POST":
            auth_err = check_auth()
            if auth_err:
                return auth_err
            data = request.get_json()
            if not data or not data.get("bvid"):
                return jsonify({"error": "缺少 bvid"}), 400
            bvid = data["bvid"].strip()
            if not BVID_RE.match(bvid):
                return jsonify({"error": "无效的 BV 号格式"}), 400
            result = add_video(bvid)
            if result is None:
                return jsonify({"error": "已存在或无效"}), 409
            # 立即从 Bilibili 获取详情以填充上传者/封面信息
            try:
                from bilibili import build_session, fetch_video_detail
                session = build_session()
                detail, err = fetch_video_detail(session, bvid)
                if detail and not err:
                    # 更新封面
                    pic = detail.get("pic", "") or ""
                    if pic.startswith("http://"):
                        pic = pic[5:]
                    elif pic.startswith("https://"):
                        pic = pic[6:]
                    update_video(result["id"], title=detail.get("title", ""),
                                 pubdate=detail.get("pubdate", 0) or 0, pic=pic)
                    # 同步上传者
                    owner = detail.get("owner", {})
                    staff = detail.get("staff", [])
                    if owner and owner.get("mid"):
                        upsert_uploader(owner["mid"], owner.get("name", ""), owner.get("face", ""))
                        uploaders = [{"mid": owner["mid"], "role": "owner"}]
                        for s in (staff or []):
                            if s.get("mid"):
                                upsert_uploader(s["mid"], s.get("name", ""), s.get("face", ""))
                                uploaders.append({"mid": s["mid"], "role": s.get("title", "staff")})
                        sync_video_uploaders(result["id"], uploaders)
            except Exception:
                pass  # 获取详情失败不阻塞添加流程
            state.running = True
            state.last_error = None
            broadcast("status", {
                "running": True,
                "last_fetch": _ts_to_iso(state.last_fetch) if state.last_fetch else None,
                "last_error": None,
            })
            broadcast("videos", list_videos())
            return jsonify(result)
        return jsonify(list_videos())

    @app.route("/videos/<int:video_id>", methods=["DELETE", "PATCH"])
    def api_video_detail(video_id: int):
        auth_err = check_auth()
        if auth_err:
            return auth_err
        if request.method == "DELETE":
            delete_video(video_id)
            state.video_cid.pop(video_id, None)
            if not list_videos():
                state.running = False
                state.last_fetch = None
                state.last_error = None
            broadcast("videos", list_videos())
            return jsonify({"ok": True})
        if request.method == "PATCH":
            data = request.get_json()
            if data:
                upd = {}
                if "score_enabled" in data:
                    new_val = 1 if data["score_enabled"] else 0
                    upd["score_enabled"] = new_val
                    if new_val:
                        recalc_scores(video_id)
                    else:
                        clear_scores(video_id)
                if "paused" in data:
                    upd["paused"] = 1 if data["paused"] else 0
                if "rule_group_id" in data:
                    rgid = data["rule_group_id"]
                    if rgid is not None:
                        # 验证规则组存在
                        try:
                            rgid_int = int(rgid)
                        except (ValueError, TypeError):
                            return jsonify({"error": "无效的 rule_group_id"}), 400
                        if not get_rule_group(rgid_int):
                            return jsonify({"error": "规则组不存在"}), 400
                        upd["rule_group_id"] = rgid_int
                    else:
                        upd["rule_group_id"] = get_default_group_id()
                if upd:
                    update_video(video_id, **upd)
                    reset_collect_time_for_video(video_id)
            broadcast("videos", list_videos())
            return jsonify({"ok": True})
        return jsonify({"error": "method not allowed"}), 405

    # ============ 数据查询 ============
    @app.route("/snapshots")
    def api_snapshots():
        video_id = request.args.get("video_id", type=int)
        hours = request.args.get("hours")
        start = request.args.get("start")
        end = request.args.get("end")
        if not video_id:
            return jsonify([])
        try:
            h = int(hours) if hours else None
        except (ValueError, TypeError):
            h = None
        return jsonify(get_snapshots(video_id, hours=h, start=start, end=end))

    @app.route("/latest")
    def api_latest():
        video_id = request.args.get("video_id", type=int)
        if not video_id:
            return jsonify(None)
        return jsonify(get_latest_snapshot(video_id))

    @app.route("/reference")
    def api_reference():
        """增量得点参考点：最近一个周六凌晨3点UTC附近的数据"""
        video_id = request.args.get("video_id", type=int)
        if not video_id:
            return jsonify(None)
        return jsonify(get_saturday_ref(video_id))

    @app.route("/status")
    def api_status():
        has_videos = bool(list_videos())
        return jsonify({
            "running": state.running or has_videos,
            "last_fetch": _ts_to_iso(state.last_fetch) if state.last_fetch else None,
            "last_error": state.last_error,
        })

    @app.route("/log")
    def api_log():
        return jsonify(_log_handler.tail(100))

    # ============ 导出 ============
    @app.route("/export")
    def api_export():
        limit = check_export_rate()
        if limit:
            return limit
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            return jsonify({"error": "openpyxl 未安装，请运行 pip install openpyxl"}), 500

        video_id = request.args.get("video_id", type=int)
        start = request.args.get("start", "")
        end = request.args.get("end", "")
        if not video_id:
            return jsonify({"error": "缺少 video_id"}), 400

        # 标准化时间戳并截断未来时间
        if start:
            start = _normalize_ts(start)
        if end:
            end = _normalize_ts(end, clamp_to_now=True)
        if start and end and start >= end:
            return jsonify({"error": "开始时间必须早于结束时间"}), 400

        # 查询视频信息
        with get_db() as conn:
            video = dict_from_row(conn.execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone())
        if not video:
            return jsonify({"error": "视频不存在"}), 404

        # 按时间范围查询快照
        with get_db() as conn:
            if start and end:
                rows = conn.execute(
                    """SELECT timestamp, view_count, danmaku, reply, favorite,
                              coin, share, like_count, online_total,
                              score_play, score_interact, score_fav, score_coin,
                              score_like, score_total,
                              incr_view_count, incr_danmaku, incr_reply, incr_favorite,
                              incr_coin, incr_like_count, incr_share,
                              incr_score_play, incr_score_interact, incr_score_fav,
                              incr_score_coin, incr_score_like, incr_score_total
                       FROM snapshots
                       WHERE video_id=? AND timestamp >= ? AND timestamp <= ?
                       ORDER BY timestamp ASC""",
                    (video_id, start, end),
                ).fetchall()
            elif start:
                rows = conn.execute(
                    """SELECT timestamp, view_count, danmaku, reply, favorite,
                              coin, share, like_count, online_total,
                              score_play, score_interact, score_fav, score_coin,
                              score_like, score_total,
                              incr_view_count, incr_danmaku, incr_reply, incr_favorite,
                              incr_coin, incr_like_count, incr_share,
                              incr_score_play, incr_score_interact, incr_score_fav,
                              incr_score_coin, incr_score_like, incr_score_total
                       FROM snapshots
                       WHERE video_id=? AND timestamp >= ?
                       ORDER BY timestamp ASC""",
                    (video_id, start),
                ).fetchall()
            elif end:
                rows = conn.execute(
                    """SELECT timestamp, view_count, danmaku, reply, favorite,
                              coin, share, like_count, online_total,
                              score_play, score_interact, score_fav, score_coin,
                              score_like, score_total,
                              incr_view_count, incr_danmaku, incr_reply, incr_favorite,
                              incr_coin, incr_like_count, incr_share,
                              incr_score_play, incr_score_interact, incr_score_fav,
                              incr_score_coin, incr_score_like, incr_score_total
                       FROM snapshots
                       WHERE video_id=? AND timestamp <= ?
                       ORDER BY timestamp ASC""",
                    (video_id, end),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT timestamp, view_count, danmaku, reply, favorite,
                              coin, share, like_count, online_total,
                              score_play, score_interact, score_fav, score_coin,
                              score_like, score_total,
                              incr_view_count, incr_danmaku, incr_reply, incr_favorite,
                              incr_coin, incr_like_count, incr_share,
                              incr_score_play, incr_score_interact, incr_score_fav,
                              incr_score_coin, incr_score_like, incr_score_total
                       FROM snapshots
                       WHERE video_id=?
                       ORDER BY timestamp ASC""",
                    (video_id,),
                ).fetchall()
            snapshots = [dict_from_row(r) for r in rows]

        if not snapshots:
            return jsonify({"error": "所选时间范围内无数据"}), 404

        # 客户端时区偏移（分钟），默认 0 即 UTC
        tz_offset = request.args.get("tz", 0, type=int)

        def _fmt_local_ts(ts_str):
            """将 DB 中的 UTC 时间字符串转为客户端时区用于 XLSX 展示"""
            try:
                dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                dt = dt + timedelta(minutes=tz_offset)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                return ts_str

        tz_label = f"UTC{tz_offset//60:+d}" if tz_offset % 60 == 0 else f"UTC{tz_offset/60:+.1f}"

        wb = Workbook()
        ws = wb.active
        ws.title = "视频数据"

        # 样式
        header_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4F8EF7", end_color="4F8EF7", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center")
        data_align = Alignment(horizontal="center", vertical="center")
        thin_border = Border(
            left=Side(style="thin", color="E0E0E0"),
            right=Side(style="thin", color="E0E0E0"),
            top=Side(style="thin", color="E0E0E0"),
            bottom=Side(style="thin", color="E0E0E0"),
        )

        # 信息行
        ws.merge_cells("A1:O1")
        ws["A1"] = f"视频: {video.get('title', video['bvid'])}  ({video['bvid']})"
        ws["A1"].font = Font(name="微软雅黑", size=13, bold=True)
        ws["A1"].alignment = Alignment(horizontal="left", vertical="center")

        d_start = _fmt_local_ts(start) if start else '全部'
        d_end = _fmt_local_ts(end) if end else '全部'
        ws.merge_cells("A2:O2")
        ws["A2"] = f"导出时间范围: {d_start} ~ {d_end}（{tz_label}）      导出时间: {(_fmt_local_ts(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')))}（{tz_label}）"
        ws["A2"].font = Font(name="微软雅黑", size=10, color="888888")

        # 表头
        headers = [
            "时间", "播放量", "弹幕", "评论", "收藏", "硬币", "点赞", "分享",
            "正在观看人数",
            "得点(播放)", "得点(互动)", "得点(收藏)", "得点(硬币)", "得点(点赞)", "得点(总分)",
        ]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border

        # 数据行
        for i, s in enumerate(snapshots):
            row = i + 5
            vals = [
                _fmt_local_ts(s["timestamp"]),
                s["view_count"], s["danmaku"], s["reply"], s["favorite"],
                s["coin"], s["like_count"], s["share"],
                s["online_total"],
                s.get("score_play"), s.get("score_interact"), s.get("score_fav"),
                s.get("score_coin"), s.get("score_like"), s.get("score_total"),
            ]
            for col, v in enumerate(vals, 1):
                cell = ws.cell(row=row, column=col, value=v if v is not None else "")
                cell.alignment = data_align
                cell.border = thin_border
                if col == 1:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

        # 列宽
        col_widths = [20, 12, 10, 10, 12, 10, 12, 10, 14, 13, 13, 13, 13, 13, 13]
        for i, w in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

        # 冻结表头
        ws.freeze_panes = "A5"

        # 自动筛选
        ws.auto_filter.ref = f"A4:{get_column_letter(len(headers))}{4 + len(snapshots)}"

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        def _fmt_fn_ts(ts_str):
            """将时间字符串转为文件名安全格式"""
            try:
                dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                dt = dt + timedelta(minutes=tz_offset)
                return dt.strftime('%Y%m%d_%H%M%S')
            except (ValueError, TypeError):
                return ts_str[:10].replace('-', '') if ts_str else ''

        title = video.get('title', video['bvid']) or video['bvid']
        # 去除文件名非法字符
        title = title.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
        fstart = _fmt_fn_ts(start) if start else 'begin'
        fend = _fmt_fn_ts(end) if end else 'end'
        filename = f"{title}_{fstart}_to_{fend}.xlsx"
        return Response(
            output.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
        )

    # ============ SSE 实时推送 ============
    @app.route("/stream")
    def api_stream():
        def generate():
            q = queue.Queue(maxsize=50)
            _subscribers.append(q)
            try:
                # 推送完整初始状态
                has_videos = bool(list_videos())
                payload = json.dumps({
                    "status": {
                        "running": state.running or has_videos,
                        "last_fetch": _ts_to_iso(state.last_fetch) if state.last_fetch else None,
                        "last_error": state.last_error,
                    },
                    "log": _log_handler.tail(200),
                    "videos": list_videos(),
                }, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                while True:
                    try:
                        event, data = q.get(timeout=25)
                        yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                    except queue.Empty:
                        yield ": keepalive\n\n"
            finally:
                _subscribers.remove(q)
        return Response(generate(), mimetype="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        })
