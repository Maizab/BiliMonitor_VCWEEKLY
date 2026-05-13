import json
import logging
import queue
import requests
import sqlite3
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from contextlib import contextmanager

from flask import Flask, Response, request, jsonify

# ============ 配置 ============
DB_PATH = "monitor.db"
DEFAULT_INTERVAL = 30
DEFAULT_COOKIE = ""

HEADERS_TEMPLATE = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
    ),
    "Origin": "https://www.bilibili.com",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


# ============ 数据库 ============
def dict_from_row(row):
    if row is None:
        return None
    return dict(row)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT
            )"""
        )
        for k, v in [("interval", str(DEFAULT_INTERVAL)), ("cookie", DEFAULT_COOKIE)]:
            conn.execute("INSERT OR IGNORE INTO config(key, value) VALUES (?, ?)", (k, v))

        conn.execute(
            """CREATE TABLE IF NOT EXISTS videos (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                bvid          TEXT NOT NULL UNIQUE,
                title         TEXT,
                score_enabled INTEGER DEFAULT 1,
                added_at      TEXT NOT NULL
            )"""
        )

        conn.execute(
            """CREATE TABLE IF NOT EXISTS snapshots (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id     INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                timestamp    TEXT NOT NULL,
                view_count   INTEGER,
                danmaku      INTEGER,
                reply        INTEGER,
                favorite     INTEGER,
                coin         INTEGER,
                share        INTEGER,
                like_count   INTEGER,
                online_total TEXT,
                online_count TEXT,
                score_play      REAL,
                score_interact  REAL,
                score_fav       REAL,
                score_coin      REAL,
                score_like      REAL,
                score_total     REAL
            )"""
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_snap_ts ON snapshots(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_snap_vid ON snapshots(video_id)")
        conn.commit()


def get_config(key: str) -> str | None:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None


def set_config(key: str, value: str):
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO config(key, value) VALUES (?, ?)", (key, value))
        conn.commit()


def list_videos() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM videos ORDER BY id").fetchall()
        return [dict_from_row(r) for r in rows]


def add_video(bvid: str, title: str = "") -> dict | None:
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO videos (bvid, title, added_at) VALUES (?, ?, ?)",
                (bvid, title, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM videos WHERE bvid=?", (bvid,)).fetchone()
            return dict_from_row(row)
        except sqlite3.IntegrityError:
            return None


def delete_video(video_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM snapshots WHERE video_id=?", (video_id,))
        conn.execute("DELETE FROM videos WHERE id=?", (video_id,))
        conn.commit()


def update_video(video_id: int, **kwargs):
    sets = ", ".join(f"{k}=?" for k in kwargs)
    if not sets:
        return
    with get_db() as conn:
        conn.execute(f"UPDATE videos SET {sets} WHERE id=?", (*kwargs.values(), video_id))
        conn.commit()


def get_latest_snapshot(video_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM snapshots WHERE video_id=? ORDER BY timestamp DESC LIMIT 1",
            (video_id,),
        ).fetchone()
        return dict_from_row(row)


def get_snapshots(video_id: int, hours: int) -> list[dict]:
    since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        rows = conn.execute(
            """SELECT timestamp, view_count, danmaku, reply, favorite,
                      coin, share, like_count, online_total, online_count,
                      score_play, score_interact, score_fav, score_coin,
                      score_like, score_total
               FROM snapshots
               WHERE video_id=? AND timestamp >= ?
               ORDER BY timestamp ASC""",
            (video_id, since),
        ).fetchall()
        return [dict_from_row(r) for r in rows]


# ============ 得分计算 ============
def calculate_score(view, like, danmaku, comment, coin, favorite):
    if view <= 0:
        return {k: 0 for k in ["score_play", "score_interact", "score_fav", "score_coin", "score_like", "score_total"]}

    basic_view = view * 0.5 + 5000 if view > 10000 else view
    interact = comment + danmaku

    if coin > favorite and view > 0 and coin > 0:
        correction_c = (favorite ** 2 / (view * coin)) * 250
    elif view > 0:
        correction_c = (coin / view) * 250
    else:
        correction_c = 0
    correction_c = min(correction_c, 50)

    if favorite > coin and view > 0:
        correction_d = (coin / view) * 25
    elif view > 0:
        correction_d = (favorite / view) * 25
    else:
        correction_d = 0
    correction_d = min(correction_d, 1)

    denom = basic_view + favorite + interact * 20
    correction_a = ((basic_view + favorite) / denom) ** 2 if denom > 0 else 0

    if favorite > coin * 2 and view > 0 and favorite > 0:
        correction_b = (coin ** 2 / (view * favorite)) * 1000
    elif view > 0:
        correction_b = (favorite / view) * 250
    else:
        correction_b = 0
    correction_b = min(correction_b, 50)

    return {
        "score_play": round(basic_view * correction_d, 2),
        "score_interact": round(interact * correction_a * 15, 2),
        "score_fav": round(favorite * correction_b, 2),
        "score_coin": round(coin * correction_c, 2),
        "score_like": round(min(like, coin * 2), 2),
        "score_total": round(
            basic_view * correction_d
            + interact * correction_a * 15
            + favorite * correction_b
            + coin * correction_c
            + min(like, coin * 2),
            2,
        ),
    }


# ============ API 请求 ============
def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS_TEMPLATE)
    cookie_str = get_config("cookie") or ""
    if cookie_str:
        s.cookies.update({
            k.strip(): v.strip()
            for k, v in (c.split("=", 1) for c in cookie_str.split(";") if "=" in c)
        })
    return s


def fetch_video_detail(session: requests.Session, bvid: str) -> tuple[dict | None, str | None]:
    try:
        resp = session.get(
            "https://api.bilibili.com/x/web-interface/wbi/view/detail",
            params={"bvid": bvid, "need_view": "1"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data["code"] != 0:
            return None, f"code={data['code']} msg={data.get('message','')}"
        return data["data"], None
    except Exception as e:
        return None, str(e)


def fetch_online_count(session: requests.Session, bvid: str, cid: int) -> tuple[dict | None, str | None]:
    try:
        resp = session.get(
            "https://api.bilibili.com/x/player/online/total",
            params={"bvid": bvid, "cid": cid},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data["code"] != 0:
            return None, f"code={data['code']} msg={data.get('message','')}"
        return data["data"], None
    except Exception as e:
        return None, str(e)


# ============ 监控状态 ============
class MonitorState:
    def __init__(self):
        self.running = False
        self.last_fetch: str | None = None
        self.last_error: str | None = None
        self.video_cid: dict[int, int] = {}  # video_id -> cid


state = MonitorState()


class RingBufferHandler(logging.Handler):
    """将日志保留在内存环形缓冲区，供前端拉取"""

    def __init__(self, capacity: int = 200):
        super().__init__()
        self.buffer: deque[str] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord):
        import re
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        msg = re.sub(r"\x1b\[[0-9;]*m", "", record.getMessage())
        self.buffer.append(f"[{ts}] {msg}")
        broadcast("log", {"lines": [f"[{ts}] {msg}"]})

    def tail(self, n: int = 100) -> list[str]:
        items = list(self.buffer)
        return items[-n:] if len(items) > n else items


# SSE 广播
_subscribers: list[queue.Queue] = []


def broadcast(event: str, data: dict):
    for q in _subscribers[:]:
        try:
            q.put_nowait((event, data))
        except queue.Full:
            pass


_log_handler = RingBufferHandler()
_log_handler.setFormatter(logging.Formatter("%(message)s"))
_log_handler.setLevel(logging.INFO)

# 控制台输出
_console = logging.StreamHandler()
_console.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
_console.setLevel(logging.INFO)

_app_log = logging.getLogger("bili_monitor")
_app_log.addHandler(_log_handler)
_app_log.addHandler(_console)
_app_log.setLevel(logging.INFO)
_app_log.propagate = False

_werkzeug_log = logging.getLogger("werkzeug")
_werkzeug_log.addHandler(_console)
_werkzeug_log.propagate = False


def collect_video(session: requests.Session, video: dict, now: str):
    """采集单个视频数据，一次 API 调用搞定"""
    vid = video["id"]
    bvid = video["bvid"]
    score_enabled = video.get("score_enabled", 1)

    detail, err = fetch_video_detail(session, bvid)
    if detail is None:
        return False, f"{now}: [{bvid}] {err}"

    view_data = detail["View"]
    stat = view_data["stat"]

    # 缓存 cid，首次更新标题
    if vid not in state.video_cid:
        state.video_cid[vid] = view_data["cid"]
        update_video(vid, title=view_data["title"])

    # 在线人数
    online, _ = fetch_online_count(session, bvid, state.video_cid[vid])

    view = stat.get("view", 0) or 0
    like = stat.get("like", 0) or 0
    danmaku = stat.get("danmaku", 0) or 0
    reply = stat.get("reply", 0) or 0
    coin = stat.get("coin", 0) or 0
    favorite = stat.get("favorite", 0) or 0
    share = stat.get("share", 0) or 0

    if score_enabled:
        scores = calculate_score(view, like, danmaku, reply, coin, favorite)
    else:
        scores = {k: None for k in ["score_play", "score_interact", "score_fav", "score_coin", "score_like", "score_total"]}

    with get_db() as conn:
        conn.execute(
            """INSERT INTO snapshots
               (video_id, timestamp, view_count, danmaku, reply, favorite,
                coin, share, like_count, online_total, online_count,
                score_play, score_interact, score_fav, score_coin, score_like, score_total)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (vid, now, view, danmaku, reply, favorite, coin, share, like,
             online.get("total") if online else None,
             online.get("count") if online else None,
             *scores.values()),
        )
        conn.commit()

    broadcast("snapshot", {
        "video_id": vid,
        "timestamp": now,
        "view_count": view, "danmaku": danmaku, "reply": reply,
        "favorite": favorite, "coin": coin, "share": share, "like_count": like,
        "online_total": online.get("total") if online else None,
        "online_count": online.get("count") if online else None,
        "score_play": scores["score_play"], "score_interact": scores["score_interact"],
        "score_fav": scores["score_fav"], "score_coin": scores["score_coin"],
        "score_like": scores["score_like"], "score_total": scores["score_total"],
    })

    return True, None


def monitor_loop():
    session = None
    last_cookie = None

    while True:
        try:
            interval_str = get_config("interval")
            interval = int(interval_str) if interval_str else DEFAULT_INTERVAL

            videos = list_videos()
            if not videos:
                state.running = False
                time.sleep(10)
                session = None
                last_cookie = None
                continue

            state.running = True

            current_cookie = get_config("cookie") or ""
            if session is None or current_cookie != last_cookie:
                session = build_session()
                last_cookie = current_cookie

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            errors = []
            for video in videos:
                try:
                    ok, err = collect_video(session, video, now)
                    if not ok:
                        errors.append(err)
                        _app_log.warning("FAIL %s: %s", video['bvid'], err)
                        if "风控校验失败" in err:
                            _app_log.warning("HINT 建议在设置中填写或更新已登录的 Cookie")
                    else:
                        _app_log.info("OK   %s", video['bvid'])
                except Exception as e:
                    errors.append(f"{now}: [{video['bvid']}] {e}")
                    _app_log.error("ERR  %s: %s", video['bvid'], e)

            state.last_fetch = now
            state.last_error = "; ".join(errors) if errors else None
            broadcast("status", {
                "running": state.running,
                "last_fetch": state.last_fetch,
                "last_error": state.last_error,
            })

        except Exception as e:
            state.last_error = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {e}"

        time.sleep(interval)


# ============ Flask ============
app = Flask(__name__)


# --- 配置 ---
@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "POST":
        data = request.get_json()
        if data:
            if "interval" in data and data["interval"]:
                set_config("interval", str(int(data["interval"])))
            if "cookie" in data:
                c = data["cookie"].strip()
                if c == "clear":
                    set_config("cookie", "")
                elif c:
                    set_config("cookie", c)
        return jsonify({"ok": True})
    return jsonify({
        "interval": int(get_config("interval") or DEFAULT_INTERVAL),
        "has_cookie": bool(get_config("cookie")),
    })


# --- 视频管理 ---
@app.route("/api/videos", methods=["GET", "POST"])
def api_videos():
    if request.method == "POST":
        data = request.get_json()
        if not data or not data.get("bvid"):
            return jsonify({"error": "bvid required"}), 400
        bvid = data["bvid"].strip()
        result = add_video(bvid)
        if result is None:
            return jsonify({"error": "已存在或无效"}), 409
        state.running = True
        state.last_error = None
        broadcast("status", {
            "running": True,
            "last_fetch": state.last_fetch,
            "last_error": None,
        })
        return jsonify(result)
    return jsonify(list_videos())


@app.route("/api/videos/<int:video_id>", methods=["DELETE", "PATCH"])
def api_video_detail(video_id: int):
    if request.method == "DELETE":
        delete_video(video_id)
        state.video_cid.pop(video_id, None)
        if not list_videos():
            state.running = False
            state.last_fetch = None
            state.last_error = None
        return jsonify({"ok": True})
    if request.method == "PATCH":
        data = request.get_json()
        if data and "score_enabled" in data:
            update_video(video_id, score_enabled=1 if data["score_enabled"] else 0)
        return jsonify({"ok": True})
    return jsonify({"error": "method not allowed"}), 405


# --- 数据 ---
@app.route("/api/snapshots")
def api_snapshots():
    video_id = request.args.get("video_id", type=int)
    hours = request.args.get("hours", "24")
    if not video_id:
        return jsonify([])
    return jsonify(get_snapshots(video_id, int(hours)))


@app.route("/api/latest")
def api_latest():
    video_id = request.args.get("video_id", type=int)
    if not video_id:
        return jsonify(None)
    return jsonify(get_latest_snapshot(video_id))


@app.route("/api/status")
def api_status():
    has_videos = bool(list_videos())
    return jsonify({
        "running": state.running or has_videos,
        "last_fetch": state.last_fetch,
        "last_error": state.last_error,
    })


@app.route("/api/log")
def api_log():
    return jsonify(_log_handler.tail(100))


@app.route("/api/stream")
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
                    "last_fetch": state.last_fetch,
                    "last_error": state.last_error,
                },
                "log": _log_handler.tail(200),
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


def main():
    init_db()
    threading.Thread(target=monitor_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()
