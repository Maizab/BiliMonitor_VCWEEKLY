"""规则引擎：根据视频关联的规则组计算下次采集时间。

后端统一使用 UTC 时间。前端负责将用户本地时区转换为 UTC 后存储。
"""

import calendar
import json
from datetime import datetime, timedelta

from database import get_rules_for_group


def evaluate_condition(value_json: dict, snapshot: dict | None) -> bool:
    """评估 Type 2 条件：检查快照中的指标值是否落在指定区间内。"""
    if snapshot is None:
        return False

    metric = value_json.get("metric", "")
    actual = snapshot.get(metric)
    if actual is None:
        return False

    try:
        actual = float(actual)
    except (ValueError, TypeError):
        return False

    min_val = value_json.get("min_value")
    max_val = value_json.get("max_value")

    if min_val is not None:
        try:
            if actual < float(min_val):
                return False
        except (ValueError, TypeError):
            pass

    if max_val is not None:
        try:
            if actual > float(max_val):
                return False
        except (ValueError, TypeError):
            pass

    return True


def _next_daily_occurrence(now_epoch: float, time_str: str) -> float:
    """从 now_epoch 起下一个 time_str (HH:MM, UTC) 的 epoch 时间。"""
    h, m = map(int, time_str.split(":"))
    dt = datetime.utcfromtimestamp(now_epoch)
    target = dt.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= dt:
        target += timedelta(days=1)
    return calendar.timegm(target.timetuple())


def _next_weekly_occurrence(now_epoch: float, day_of_week: int, time_str: str) -> float:
    """从 now_epoch 起下一个周几 (0=Mon UTC...6=Sun UTC) time_str (HH:MM, UTC) 的 epoch 时间。"""
    h, m = map(int, time_str.split(":"))
    dt = datetime.utcfromtimestamp(now_epoch)
    target = dt.replace(hour=h, minute=m, second=0, microsecond=0)
    days_ahead = (day_of_week - dt.weekday()) % 7
    if days_ahead == 0 and target <= dt:
        days_ahead = 7
    target += timedelta(days=days_ahead)
    return calendar.timegm(target.timetuple())


def compute_next_collect(
    video: dict, now_epoch: float, last_snapshot: dict | None
) -> float:
    """返回该视频下次应采集的 epoch 时间。"""
    group_id = video.get("rule_group_id")
    if not group_id:
        return now_epoch + 60

    rules = get_rules_for_group(group_id)
    if not rules:
        return now_epoch + 60

    candidates: list[float] = []

    for rule in rules:
        try:
            value = json.loads(rule["value"])
        except (json.JSONDecodeError, KeyError):
            continue

        rt = rule["rule_type"]

        if rt == 1:
            interval = value.get("interval", 60)
            candidates.append(now_epoch + max(interval, 30))

        elif rt == 2:
            if evaluate_condition(value, last_snapshot):
                interval = value.get("target_interval", 60)
                candidates.append(now_epoch + max(interval, 30))

        elif rt == 3:
            time_str = value.get("time", "00:00")
            candidates.append(_next_daily_occurrence(now_epoch, time_str))

        elif rt == 4:
            dow = value.get("day_of_week", 4)
            time_str = value.get("time", "19:00")
            candidates.append(_next_weekly_occurrence(now_epoch, dow, time_str))

    return min(candidates) if candidates else (now_epoch + 60)
