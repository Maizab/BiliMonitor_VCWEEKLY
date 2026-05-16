import time
from collections import defaultdict

from flask import request, jsonify

from config import _config

# ============ 限流 / IP 封禁 ============
_challenge_window: dict[str, list[float]] = defaultdict(list)
_verify_failures: dict[str, list[float]] = defaultdict(list)
_banned_ips: dict[str, float] = {}
_verified_ips: dict[str, float] = {}
_export_window: dict[str, list[float]] = defaultdict(list)


def _get_client_ip() -> str:
    """获取客户端真实 IP"""
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.remote_addr or "unknown")


def _check_ban(ip: str):
    """检查 IP 是否处于封禁状态"""
    now = time.time()
    if ip in _banned_ips:
        if now < _banned_ips[ip]:
            remaining = int(_banned_ips[ip] - now)
            return jsonify({"error": f"请求过于频繁，请 {remaining} 秒后再试"}), 429
        del _banned_ips[ip]
    return None


def check_challenge_rate():
    """challenge 接口限流：窗口内超过限制则封禁 IP"""
    ip = _get_client_ip()
    ban = _check_ban(ip)
    if ban:
        return ban
    # 已通过验证的 IP 在验证窗口内免限流
    now = time.time()
    rl = _config["rate_limit"]
    if ip in _verified_ips:
        if now - _verified_ips[ip] < rl["verify_failure_window"]:
            return None
        del _verified_ips[ip]
    _challenge_window[ip] = [t for t in _challenge_window[ip] if now - t < rl["challenge_window"]]
    if len(_challenge_window[ip]) >= rl["challenge_rate"]:
        _banned_ips[ip] = now + rl["ban_duration"]
        _challenge_window.pop(ip, None)
        return jsonify({"error": f"请求过于频繁，已临时封禁 {rl['ban_duration']} 秒"}), 429
    _challenge_window[ip].append(now)
    return None


def record_verify_failure() -> tuple | None:
    """记录验证失败，超过上限则封禁 IP"""
    ip = _get_client_ip()
    now = time.time()
    rl = _config["rate_limit"]
    _verify_failures[ip] = [t for t in _verify_failures[ip] if now - t < rl["verify_failure_window"]]
    _verify_failures[ip].append(now)
    if len(_verify_failures[ip]) >= rl["verify_max_failures"]:
        _banned_ips[ip] = now + rl["ban_duration"]
        _verify_failures.pop(ip, None)
        return jsonify({"error": f"密码错误次数过多，已临时封禁 {rl['ban_duration']} 秒"}), 429
    return None


def clear_verify_failures():
    """清除当前 IP 的验证失败记录"""
    _verify_failures.pop(_get_client_ip(), None)


def check_export_rate():
    """导出接口限流：窗口内超过限制则拒绝"""
    ip = _get_client_ip()
    ban = _check_ban(ip)
    if ban:
        return ban
    now = time.time()
    rl = _config["rate_limit"]
    ew = rl["export_window"]
    er = rl["export_rate"]
    _export_window[ip] = [t for t in _export_window[ip] if now - t < ew]
    if len(_export_window[ip]) >= er:
        return jsonify({"error": f"导出请求过于频繁，请 {ew} 秒后再试"}), 429
    _export_window[ip].append(now)
    return None
