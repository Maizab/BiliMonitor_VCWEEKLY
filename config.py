import json

try:
    import tomllib
except ImportError:
    import tomli as tomllib

# ============ 配置 ============
CONFIG_PATH = "config.toml"

_DEFAULT_CONFIG = {
    "storage": {"db_path": "monitor.db"},
    "auth": {"password": ""},
    "monitor": {"interval": 30},
    "score": {"increment_window": 10},  # 周六凌晨3点参考点的容差窗口（分钟）
    "rate_limit": {
        "challenge_rate": 10,
        "challenge_window": 60,
        "verify_max_failures": 5,
        "verify_failure_window": 300,
        "ban_duration": 300,
        "export_rate": 5,
        "export_window": 60,
    },
    "bilibili": {
        "max_retries": 3,
    },
}


def _validate_config(cfg: dict) -> dict:
    """Deep-merge user config with defaults, fixing invalid values."""
    merged = {}
    for section, defaults in _DEFAULT_CONFIG.items():
        section_cfg = cfg.get(section, {}) if isinstance(cfg.get(section), dict) else {}
        merged[section] = {}
        for key, default in defaults.items():
            val = section_cfg.get(key)
            if val is None:
                merged[section][key] = default
            elif type(val) is not type(default):
                merged[section][key] = default
            elif isinstance(default, int) and val < 1:
                merged[section][key] = default
            else:
                merged[section][key] = val
    # 特殊处理：采集间隔最小 30 秒
    if merged["monitor"]["interval"] < 30:
        merged["monitor"]["interval"] = 30
    return merged


_CONFIG_COMMENTS = {
    "storage": {
        "": "# 存储配置",
        "db_path": "# SQLite 数据库文件路径",
    },
    "auth": {
        "": "# 认证配置",
        "password": "# 密码，为空则不启用认证（单用户，前端用 SHA256(challenge) 验证）",
    },
    "monitor": {
        "": "# 采集配置",
        "interval": "# 数据采集间隔（秒），最小 30",
    },
    "score": {
        "": "# 得点计算配置",
        "increment_window": "# 增量得点参考点（周六凌晨3点）查询容差窗口（分钟）",
    },
    "rate_limit": {
        "": "# 限流与封禁配置",
        "challenge_rate": "# 60 秒内最多请求 challenge 次数",
        "challenge_window": "# challenge 限流窗口（秒）",
        "verify_max_failures": "# 验证失败次数上限",
        "verify_failure_window": "# 验证失败计数窗口（秒），超过上限则封禁",
        "ban_duration": "# 封禁时长（秒）",
        "export_rate": "# 导出窗口内最多请求次数",
        "export_window": "# 导出限流窗口（秒）",
    },
    "bilibili": {
        "": "# Bilibili API 配置",
        "max_retries": "# API 请求最大重试次数（含首次）",
    },
}


def _dump_toml(cfg: dict) -> str:
    """生成带注释的 TOML 配置文本"""
    lines = []
    for section, items in cfg.items():
        comments = _CONFIG_COMMENTS.get(section, {})
        if comments.get(""):
            lines.append(comments[""])
        lines.append(f"[{section}]")
        for key, val in items.items():
            if key in comments:
                lines.append(comments[key])
            if isinstance(val, str):
                lines.append(f"{key} = {json.dumps(val)}")
            elif isinstance(val, bool):
                lines.append(f"{key} = {str(val).lower()}")
            else:
                lines.append(f"{key} = {val}")
        lines.append("")
    return "\n".join(lines)


def _load_config() -> dict:
    """从 CONFIG_PATH 加载配置，不存在则用默认值创建。
    无效值会被自动重置为默认值。"""
    try:
        with open(CONFIG_PATH, "rb") as f:
            user_cfg = tomllib.load(f)
        need_save = False
    except FileNotFoundError:
        user_cfg = {}
        need_save = True
    merged = _validate_config(user_cfg)
    if not need_save:
        # 检查是否有被验证修正的值，有则重写配置文件
        for section, defaults in _DEFAULT_CONFIG.items():
            user_section = user_cfg.get(section, {}) if isinstance(user_cfg.get(section), dict) else {}
            for key, default in defaults.items():
                if merged[section][key] != user_section.get(key):
                    need_save = True
                    break
            if need_save:
                break
    if need_save:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(_dump_toml(merged))
    return merged


def _save_config(cfg: dict):
    """保存配置到 TOML 文件"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(_dump_toml(cfg))


# 模块加载时读取配置
_config = _load_config()
AUTH_PASSWORD = _config["auth"]["password"]
