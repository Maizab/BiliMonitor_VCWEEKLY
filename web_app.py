import hashlib
import json
import logging
import queue
import requests
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from contextlib import contextmanager

from flask import Flask, Response, request, jsonify

try:
    import tomllib
except ImportError:
    import tomli as tomllib

# ============ 配置 ============
DB_PATH = "monitor.db"
DEFAULT_INTERVAL = 30

# 从 config.toml 读取认证配置
def _load_auth_config():
    try:
        with open("config.toml", "rb") as f:
            cfg = tomllib.load(f)
        return cfg.get("auth", {}).get("password", "")
    except (FileNotFoundError, KeyError):
        return ""

AUTH_PASSWORD = _load_auth_config()
_used_nonces: set[str] = set()

# --- 限流 / IP 封禁 ---
_challenge_window: dict[str, list[float]] = defaultdict(list)
_verify_failures: dict[str, list[float]] = defaultdict(list)
_banned_ips: dict[str, float] = {}

CHALLENGE_RATE = 10
CHALLENGE_WINDOW = 60
VERIFY_MAX_FAILURES = 5
VERIFY_FAILURE_WINDOW = 300
BAN_DURATION = 300


def _get_client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.remote_addr or "unknown")


def _check_ban(ip: str):
    now = time.time()
    if ip in _banned_ips:
        if now < _banned_ips[ip]:
            remaining = int(_banned_ips[ip] - now)
            return jsonify({"error": f"请求过于频繁，请 {remaining} 秒后再试"}), 429
        del _banned_ips[ip]
    return None


def check_challenge_rate():
    ip = _get_client_ip()
    ban = _check_ban(ip)
    if ban:
        return ban
    now = time.time()
    _challenge_window[ip] = [t for t in _challenge_window[ip] if now - t < CHALLENGE_WINDOW]
    if len(_challenge_window[ip]) >= CHALLENGE_RATE:
        _banned_ips[ip] = now + BAN_DURATION
        _challenge_window.pop(ip, None)
        return jsonify({"error": f"请求过于频繁，已临时封禁 {BAN_DURATION} 秒"}), 429
    _challenge_window[ip].append(now)
    return None


def record_verify_failure() -> tuple | None:
    ip = _get_client_ip()
    now = time.time()
    _verify_failures[ip] = [t for t in _verify_failures[ip] if now - t < VERIFY_FAILURE_WINDOW]
    _verify_failures[ip].append(now)
    if len(_verify_failures[ip]) >= VERIFY_MAX_FAILURES:
        _banned_ips[ip] = now + BAN_DURATION
        _verify_failures.pop(ip, None)
        return jsonify({"error": f"密码错误次数过多，已临时封禁 {BAN_DURATION} 秒"}), 429
    return None


def clear_verify_failures():
    _verify_failures.pop(_get_client_ip(), None)
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
        conn.execute("INSERT OR IGNORE INTO config(key, value) VALUES (?, ?)", ("interval", str(DEFAULT_INTERVAL)))

        conn.execute(
            """CREATE TABLE IF NOT EXISTS videos (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                bvid          TEXT NOT NULL UNIQUE,
                title         TEXT,
                score_enabled INTEGER DEFAULT 1,
                paused        INTEGER DEFAULT 0,
                added_at      TEXT NOT NULL
            )"""
        )
        # Migration: add paused column if upgrading from older schema
        try:
            conn.execute("ALTER TABLE videos ADD COLUMN paused INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

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
        rows = conn.execute(
            """SELECT v.*,
                      COUNT(s.id) as snapshot_count,
                      MAX(s.timestamp) as last_snapshot_at
               FROM videos v
               LEFT JOIN snapshots s ON s.video_id = v.id
               GROUP BY v.id
               ORDER BY v.id"""
        ).fetchall()
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


def clear_scores(video_id: int):
    with get_db() as conn:
        conn.execute(
            """UPDATE snapshots SET score_play=NULL, score_interact=NULL,
               score_fav=NULL, score_coin=NULL, score_like=NULL, score_total=NULL
               WHERE video_id=?""",
            (video_id,),
        )
        conn.commit()


def recalc_scores(video_id: int):
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, view_count, like_count, danmaku, reply, coin, favorite
               FROM snapshots WHERE video_id=? ORDER BY timestamp""",
            (video_id,),
        ).fetchall()
        for r in rows:
            scores = calculate_score(
                r["view_count"] or 0, r["like_count"] or 0,
                r["danmaku"] or 0, r["reply"] or 0,
                r["coin"] or 0, r["favorite"] or 0,
            )
            conn.execute(
                """UPDATE snapshots SET score_play=?, score_interact=?,
                   score_fav=?, score_coin=?, score_like=?, score_total=?
                   WHERE id=?""",
                (*scores.values(), r["id"]),
            )
        conn.commit()


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
    return s


def fetch_video_detail(session: requests.Session, bvid: str) -> tuple[dict | None, str | None]:
    try:
        resp = session.get(
            "https://api.bilibili.com/x/web-interface/view",
            params={"bvid": bvid},
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

import os as _os
_log_dir = "logs"
_os.makedirs(_log_dir, exist_ok=True)
_log_file = _os.path.join(_log_dir, datetime.now().strftime("%Y%m%d_%H%M%S") + ".log")
_file_handler = logging.FileHandler(_log_file, encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
_file_handler.setLevel(logging.INFO)

_app_log = logging.getLogger("bili_monitor")
_app_log.addHandler(_log_handler)
_app_log.addHandler(_console)
_app_log.addHandler(_file_handler)
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

    stat = detail["stat"]

    # 缓存 cid，首次更新标题
    if vid not in state.video_cid:
        state.video_cid[vid] = detail["cid"]
        update_video(vid, title=detail["title"])

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

    while True:
        try:
            interval_str = get_config("interval")
            interval = int(interval_str) if interval_str else DEFAULT_INTERVAL

            videos = list_videos()
            if not videos:
                state.running = False
                time.sleep(10)
                session = None
                continue

            state.running = True

            if session is None:
                session = build_session()

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            errors = []
            active = [v for v in videos if not v.get("paused")]
            for i, video in enumerate(active):
                if i > 0:
                    time.sleep(1.5)  # stagger to avoid hammering the API
                try:
                    ok, err = collect_video(session, video, now)
                    if not ok:
                        errors.append(err)
                        _app_log.warning("FAIL %s: %s", video['bvid'], err)
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


# --- 认证 ---
def verify_challenge(nonce: str, timestamp: str, response: str) -> bool:
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


@app.route("/api/auth/check")
def api_auth_check():
    return jsonify({"protected": bool(AUTH_PASSWORD)})


@app.route("/api/auth/challenge")
def api_auth_challenge():
    limit = check_challenge_rate()
    if limit:
        return limit
    return jsonify({
        "nonce": secrets.token_hex(16),
        "timestamp": int(time.time()),
    })


@app.route("/api/auth/verify", methods=["POST"])
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
        return jsonify({"ok": True, "protected": True})
    ban = record_verify_failure()
    if ban:
        return ban
    return jsonify({"error": "密码错误"}), 403


# --- 配置 ---
@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "POST":
        auth_err = check_auth()
        if auth_err:
            return auth_err
        data = request.get_json()
        if data and "interval" in data and data["interval"]:
            val = int(data["interval"])
            set_config("interval", str(max(30, val)))
        return jsonify({"ok": True})
    return jsonify({
        "interval": int(get_config("interval") or DEFAULT_INTERVAL),
    })


# --- 视频管理 ---
@app.route("/api/videos", methods=["GET", "POST"])
def api_videos():
    if request.method == "POST":
        auth_err = check_auth()
        if auth_err:
            return auth_err
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
            if upd:
                update_video(video_id, **upd)
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
