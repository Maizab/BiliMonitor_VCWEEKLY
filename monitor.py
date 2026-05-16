import logging
import os
import queue
import re
import threading
import time
from collections import deque
from datetime import datetime

from config import _config
from database import get_config, list_videos, update_video, calculate_score, get_db
from bilibili import build_session, fetch_video_detail, fetch_online_count

# ============ 监控状态 ============
class MonitorState:
    def __init__(self):
        self.running = False
        self.last_fetch: str | None = None
        self.last_error: str | None = None
        self.video_cid: dict[int, int] = {}  # video_id -> cid


state = MonitorState()


# ============ 日志 ============
class RingBufferHandler(logging.Handler):
    """将日志保留在内存环形缓冲区，供前端拉取"""

    def __init__(self, capacity: int = 200):
        super().__init__()
        self.buffer: deque[str] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord):
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        msg = re.sub(r"\x1b\[[0-9;]*m", "", record.getMessage())
        self.buffer.append(f"[{ts}] {msg}")
        broadcast("log", {"lines": [f"[{ts}] {msg}"]})

    def tail(self, n: int = 100) -> list[str]:
        items = list(self.buffer)
        return items[-n:] if len(items) > n else items


# ============ SSE 广播 ============
_subscribers: list[queue.Queue] = []


def broadcast(event: str, data: dict):
    """向所有 SSE 订阅者推送事件"""
    for q in _subscribers[:]:
        try:
            q.put_nowait((event, data))
        except queue.Full:
            pass


# ============ 日志初始化 ============
_log_handler = RingBufferHandler()
_log_handler.setFormatter(logging.Formatter("%(message)s"))
_log_handler.setLevel(logging.INFO)

# 控制台输出
_console = logging.StreamHandler()
_console.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
_console.setLevel(logging.INFO)

_log_dir = "logs"
os.makedirs(_log_dir, exist_ok=True)
_log_file = os.path.join(_log_dir, datetime.now().strftime("%Y%m%d_%H%M%S") + ".log")
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
_werkzeug_log.addHandler(_file_handler)
_werkzeug_log.setLevel(logging.INFO)
_werkzeug_log.propagate = False


# ============ 采集逻辑 ============
def collect_video(session, video: dict, now: str):
    """采集单个视频数据"""
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
                coin, share, like_count, online_total,
                score_play, score_interact, score_fav, score_coin, score_like, score_total)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (vid, now, view, danmaku, reply, favorite, coin, share, like,
             online.get("total") if online else None,
             *scores.values()),
        )
        conn.commit()

    broadcast("snapshot", {
        "video_id": vid,
        "timestamp": now,
        "view_count": view, "danmaku": danmaku, "reply": reply,
        "favorite": favorite, "coin": coin, "share": share, "like_count": like,
        "online_total": online.get("total") if online else None,
        "score_play": scores["score_play"], "score_interact": scores["score_interact"],
        "score_fav": scores["score_fav"], "score_coin": scores["score_coin"],
        "score_like": scores["score_like"], "score_total": scores["score_total"],
    })

    return True, None


def monitor_loop():
    """后台监控循环，定时采集所有活跃视频的数据"""
    session = None

    while True:
        try:
            interval_str = get_config("interval")
            interval = int(interval_str) if interval_str else _config["monitor"]["interval"]

            videos = list_videos()
            if not videos:
                state.running = False
                time.sleep(10)
                session = None
                continue

            state.running = True

            if session is None:
                session = build_session()

            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            errors = []
            active = [v for v in videos if not v.get("paused")]
            for i, video in enumerate(active):
                if i > 0:
                    time.sleep(1.5)  # 错开请求，避免触发 API 限流
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
            state.last_error = f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}: {e}"

        time.sleep(interval)
