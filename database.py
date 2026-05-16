import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager

from config import _config


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
                score_total     REAL
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
        return [dict_from_row(r) for r in rows]


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
    """清空指定视频所有快照的得点数据"""
    with get_db() as conn:
        conn.execute(
            """UPDATE snapshots SET score_play=NULL, score_interact=NULL,
               score_fav=NULL, score_coin=NULL, score_like=NULL, score_total=NULL
               WHERE video_id=?""",
            (video_id,),
        )
        conn.commit()


def recalc_scores(video_id: int):
    """重新计算指定视频所有历史快照的得点"""
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


# ============ 快照查询 ============
def get_latest_snapshot(video_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM snapshots WHERE video_id=? ORDER BY timestamp DESC LIMIT 1",
            (video_id,),
        ).fetchone()
        return dict_from_row(row)


def _normalize_ts(ts_str: str, clamp_to_now: bool = False) -> str:
    """将时间戳字符串标准化为数据库格式（YYYY-MM-DD HH:MM:SS）。
    同时支持 ISO 和本地格式。可选将未来时间截断为当前时间。"""
    now = datetime.utcnow()
    try:
        s = ts_str.replace('Z', '+00:00').replace('T', ' ')
        # 截断到秒精度
        s = s[:19] if len(s) >= 19 else s
        dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
        if clamp_to_now and dt > now:
            dt = now
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        # 尝试解析带时区的 ISO 8601（如 +08:00）
        try:
            s2 = ts_str.replace('T', ' ')[:19]
            dt = datetime.strptime(s2, '%Y-%m-%d %H:%M:%S')
            # 粗略处理：若含 +08:00 偏移则减 8 小时得到 UTC
            if '+08:00' in ts_str or '+08' in ts_str:
                from datetime import timedelta
                dt = dt - timedelta(hours=8)
            if clamp_to_now and dt > now:
                dt = now
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return ts_str[:19] if len(ts_str) >= 19 else ts_str


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
                      score_like, score_total
               FROM snapshots
               WHERE {where}
               ORDER BY timestamp ASC""",
            params,
        ).fetchall()
        return [dict_from_row(r) for r in rows]


# ============ 得分计算 ============
def calculate_score(view, like, danmaku, comment, coin, favorite):
    """根据播放、点赞、弹幕、评论、硬币、收藏计算各项得点"""
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
