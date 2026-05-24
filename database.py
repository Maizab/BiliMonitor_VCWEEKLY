import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager

from config import _config


from utils import _ts_to_iso, _normalize_ts, calculate_score


def dict_from_row(row):
    """将 sqlite3.Row 转为普通字典"""
    if row is None:
        return None
    return dict(row)


@contextmanager
def get_db():
    """获取数据库连接上下文管理器"""
    conn = sqlite3.connect(_config["storage"]["db_path"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


# ============ 数据库初始化 ============
def init_db():
    """初始化数据库表结构"""
    with get_db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT
            )"""
        )
        conn.execute("INSERT OR IGNORE INTO config(key, value) VALUES (?, ?)", ("interval", str(_config["monitor"]["interval"])))

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
        # 迁移：旧版本数据库补充 paused 列
        try:
            conn.execute("ALTER TABLE videos ADD COLUMN paused INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        # 迁移：旧版本数据库补充 pubdate 列
        try:
            conn.execute("ALTER TABLE videos ADD COLUMN pubdate INTEGER DEFAULT 0")
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
                score_play      REAL,
                score_interact  REAL,
                score_fav       REAL,
                score_coin      REAL,
                score_like      REAL,
                score_total     REAL,
                incr_view_count   INTEGER,
                incr_danmaku      INTEGER,
                incr_reply        INTEGER,
                incr_favorite     INTEGER,
                incr_coin         INTEGER,
                incr_like_count   INTEGER,
                incr_share        INTEGER,
                incr_score_play      REAL,
                incr_score_interact  REAL,
                incr_score_fav       REAL,
                incr_score_coin      REAL,
                incr_score_like      REAL,
                incr_score_total     REAL
            )"""
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_snap_ts ON snapshots(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_snap_vid ON snapshots(video_id)")
        conn.commit()


# ============ 配置表 CRUD ============
def get_config(key: str) -> str | None:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None


def set_config(key: str, value: str):
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO config(key, value) VALUES (?, ?)", (key, value))
        conn.commit()


# ============ 视频管理 ============
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
        result = []
        for r in rows:
            d = dict_from_row(r)
            if d.get("last_snapshot_at"):
                d["last_snapshot_at"] = _ts_to_iso(d["last_snapshot_at"])
            result.append(d)
        return result


def add_video(bvid: str, title: str = "") -> dict | None:
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO videos (bvid, title, added_at) VALUES (?, ?, ?)",
                (bvid, title, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
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


# ============ 得点管理 ============
def clear_scores(video_id: int):
    """清空指定视频所有快照的得点及增量得点数据"""
    with get_db() as conn:
        conn.execute(
            """UPDATE snapshots SET score_play=NULL, score_interact=NULL,
               score_fav=NULL, score_coin=NULL, score_like=NULL, score_total=NULL,
               incr_score_play=NULL, incr_score_interact=NULL, incr_score_fav=NULL,
               incr_score_coin=NULL, incr_score_like=NULL, incr_score_total=NULL
               WHERE video_id=?""",
            (video_id,),
        )
        conn.commit()


def recalc_scores(video_id: int):
    """重新计算指定视频所有历史快照的得点及增量得点"""
    ref = _get_saturday_ref_raw(video_id)
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, view_count, like_count, danmaku, reply, coin, favorite,
                      share, online_total, timestamp
               FROM snapshots WHERE video_id=? ORDER BY timestamp""",
            (video_id,),
        ).fetchall()
        for r in rows:
            scores = calculate_score(
                r["view_count"] or 0, r["like_count"] or 0,
                r["danmaku"] or 0, r["reply"] or 0,
                r["coin"] or 0, r["favorite"] or 0,
            )
            # 增量得点：用增量原始数据重新算分
            if ref and r["timestamp"] > ref["timestamp"]:
                incr_view = (r["view_count"] or 0) - (ref.get("view_count") or 0)
                incr_danmaku = (r["danmaku"] or 0) - (ref.get("danmaku") or 0)
                incr_reply = (r["reply"] or 0) - (ref.get("reply") or 0)
                incr_favorite = (r["favorite"] or 0) - (ref.get("favorite") or 0)
                incr_coin = (r["coin"] or 0) - (ref.get("coin") or 0)
                incr_like = (r["like_count"] or 0) - (ref.get("like_count") or 0)
                incr_share = (r["share"] or 0) - (ref.get("share") or 0)
                incr_scores_raw = calculate_score(incr_view, incr_like, incr_danmaku, incr_reply, incr_coin, incr_favorite)
                incr_scores = {
                    "incr_score_play": incr_scores_raw["score_play"],
                    "incr_score_interact": incr_scores_raw["score_interact"],
                    "incr_score_fav": incr_scores_raw["score_fav"],
                    "incr_score_coin": incr_scores_raw["score_coin"],
                    "incr_score_like": incr_scores_raw["score_like"],
                    "incr_score_total": incr_scores_raw["score_total"],
                }
            else:
                incr_scores = {k: None for k in ["incr_score_play", "incr_score_interact", "incr_score_fav", "incr_score_coin", "incr_score_like", "incr_score_total"]}
                incr_view = incr_danmaku = incr_reply = incr_favorite = incr_coin = incr_like = incr_share = None
            conn.execute(
                """UPDATE snapshots SET score_play=?, score_interact=?,
                   score_fav=?, score_coin=?, score_like=?, score_total=?,
                   incr_view_count=?, incr_danmaku=?, incr_reply=?, incr_favorite=?,
                   incr_coin=?, incr_like_count=?, incr_share=?,
                   incr_score_play=?, incr_score_interact=?, incr_score_fav=?,
                   incr_score_coin=?, incr_score_like=?, incr_score_total=?
                   WHERE id=?""",
                (*scores.values(),
                 incr_view, incr_danmaku, incr_reply, incr_favorite,
                 incr_coin, incr_like, incr_share,
                 *incr_scores.values(),
                 r["id"]),
            )
        conn.commit()


# ============ 快照查询 ============
def get_latest_snapshot(video_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM snapshots WHERE video_id=? ORDER BY timestamp DESC LIMIT 1",
            (video_id,),
        ).fetchone()
        d = dict_from_row(row)
        if d:
            d["timestamp"] = _ts_to_iso(d["timestamp"])
        return d


def get_snapshots(video_id: int, hours: int = None, start: str = None, end: str = None) -> list[dict]:
    """查询快照数据，支持按小时数或起止时间范围查询"""
    if start:
        start = _normalize_ts(start)
    if end:
        end = _normalize_ts(end, clamp_to_now=True)
    if start and end:
        if start >= end:
            return []
        where = "video_id=? AND timestamp >= ? AND timestamp <= ?"
        params = (video_id, start, end)
    elif start:
        where = "video_id=? AND timestamp >= ?"
        params = (video_id, start)
    elif end:
        where = "video_id=? AND timestamp <= ?"
        params = (video_id, end)
    else:
        hours = hours or 24
        since = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        where = "video_id=? AND timestamp >= ?"
        params = (video_id, since)
    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT timestamp, view_count, danmaku, reply, favorite,
                      coin, share, like_count, online_total,
                      score_play, score_interact, score_fav, score_coin,
                      score_like, score_total,
                      incr_view_count, incr_danmaku, incr_reply, incr_favorite,
                      incr_coin, incr_like_count, incr_share,
                      incr_score_play, incr_score_interact, incr_score_fav,
                      incr_score_coin, incr_score_like, incr_score_total
               FROM snapshots
               WHERE {where}
               ORDER BY timestamp ASC""",
            params,
        ).fetchall()
        result = []
        for r in rows:
            d = dict_from_row(r)
            d["timestamp"] = _ts_to_iso(d["timestamp"])
            result.append(d)
        return result


# ============ 增量参考点 ============
def _get_saturday_ref_raw(video_id: int) -> dict | None:
    """内部版本：返回原始 DB 格式的参考快照，用于增量计算"""
    window = _config["score"]["increment_window"]

    now = datetime.utcnow()
    days_to_fri = (now.weekday() - 4) % 7
    candidate = now - timedelta(days=days_to_fri)
    target = candidate.replace(hour=19, minute=0, second=0, microsecond=0)
    if target > now:
        target -= timedelta(days=7)

    t_start = (target - timedelta(minutes=window)).strftime("%Y-%m-%d %H:%M:%S")
    t_end = (target + timedelta(minutes=window)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM snapshots WHERE video_id=? AND timestamp >= ? AND timestamp <= ? ORDER BY timestamp ASC",
            (video_id, t_start, t_end),
        ).fetchall()
        if not rows:
            # 若视频在参考时间之后发布，则以全零作为基准，增量=积累
            video = conn.execute("SELECT pubdate FROM videos WHERE id=?", (video_id,)).fetchone()
            if video and video["pubdate"] and video["pubdate"] > 0:
                pubdate_dt = datetime.utcfromtimestamp(video["pubdate"])
                if pubdate_dt > target:
                    return {
                        "timestamp": target.strftime("%Y-%m-%d %H:%M:%S"),
                        "view_count": 0, "danmaku": 0, "reply": 0,
                        "favorite": 0, "coin": 0, "like_count": 0, "share": 0,
                    }
            return None

        best = None
        best_diff = float("inf")
        for r in rows:
            diff = abs((datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S") - target).total_seconds())
            if diff < best_diff:
                best_diff = diff
                best = r
        return dict_from_row(best)


def get_saturday_ref(video_id: int) -> dict | None:
    """查找最近一个周六 03:00 CST 附近的快照作为增量得点参考点（API 用）"""
    d = _get_saturday_ref_raw(video_id)
    if d:
        d["timestamp"] = _ts_to_iso(d["timestamp"])
    return d


