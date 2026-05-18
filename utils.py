from datetime import datetime, timedelta


# ============ 时间工具 ============
def _ts_to_iso(ts):
    """将 DB 中的 UTC 时间字符串转为 ISO 8601 UTC 格式，前端才能正确识别为 UTC"""
    if not ts:
        return ts
    return ts.replace(' ', 'T') + 'Z'


def _normalize_ts(ts_str: str, clamp_to_now: bool = False) -> str:
    """将时间戳字符串标准化为数据库格式（YYYY-MM-DD HH:MM:SS）。
    同时支持 ISO 和本地格式。可选将未来时间截断为当前时间。"""
    now = datetime.utcnow()
    try:
        s = ts_str.replace('Z', '+00:00').replace('T', ' ')
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
            if '+08:00' in ts_str or '+08' in ts_str:
                dt = dt - timedelta(hours=8)
            if clamp_to_now and dt > now:
                dt = now
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return ts_str[:19] if len(ts_str) >= 19 else ts_str


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
