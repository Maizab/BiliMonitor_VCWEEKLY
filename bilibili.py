import threading
import time

import requests

from config import _config

# ============ B站 API 请求 ============
# 2026-10-21 起，B 站给 /x/web-interface/view 这类接口加了设备标识校验：
# 请求里没有 buvid3 / buvid4 这两个 cookie 时，openresty 风控层会直接返回
#   412 Precondition Failed + 一个 HTML 错误页
#   （正文：「由于触发哔哩哔哩安全风控策略，该次访问请求被拒绝」）
# 注意这**不是**接口变更：带上 buvid 后同样的请求 100% 正常返回，跟出口 IP 无关。
#
# 所以这里做两件事：
#   1. 建立 session 时自动去取一组 buvid 种进 cookie；
#   2. 412 不再重试（重试只会加重风控），改为熔断冷却一段时间。
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
    # 真实 Chrome/Edge 一定会带这几个，缺了也是爬虫特征之一
    "sec-ch-ua": '"Chromium";v="147", "Not.A/Brand";v="24", "Microsoft Edge";v="147"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

BUVID_SPI_URL = "https://api.bilibili.com/x/frontend/finger/spi"

# 触发风控后的冷静期（秒）。冷却期内不再发请求，避免把风控喂得更死。
RISK_COOLDOWN = 600
_risk_until = 0.0
_risk_lock = threading.Lock()


class RiskControlError(Exception):
    """命中 B 站风控（412），与接口变更无关"""


def _risk_remaining() -> float:
    with _risk_lock:
        return max(0.0, _risk_until - time.time())


def _trip_risk():
    global _risk_until
    with _risk_lock:
        _risk_until = time.time() + RISK_COOLDOWN


def _reset_risk():
    global _risk_until
    with _risk_lock:
        _risk_until = 0.0


def _ensure_buvid(session: requests.Session) -> bool:
    """保证 session 里带有 buvid3/buvid4 设备标识 cookie。

    B 站对没有该 cookie 的 API 请求一律返回 412，这里先去官方接口取一组；
    取不到就退化为访问一次首页，靠 Set-Cookie 自动种上。
    """
    if session.cookies.get("buvid3"):
        return True

    try:
        resp = session.get(BUVID_SPI_URL, timeout=10)
        data = (resp.json() or {}).get("data") or {}
        if data.get("b_3"):
            session.cookies.set("buvid3", data["b_3"], domain=".bilibili.com")
        if data.get("b_4"):
            session.cookies.set("buvid4", data["b_4"], domain=".bilibili.com")
        session.cookies.set("b_nut", str(int(time.time())), domain=".bilibili.com")
    except Exception:
        pass

    if not session.cookies.get("buvid3"):
        try:
            session.get("https://www.bilibili.com/", timeout=10)
        except Exception:
            pass

    return bool(session.cookies.get("buvid3"))


def build_session() -> requests.Session:
    """创建一个带伪装请求头 + buvid 设备标识的 requests Session"""
    s = requests.Session()
    s.headers.update(HEADERS_TEMPLATE)
    _ensure_buvid(s)
    return s


def _retry_get(session: requests.Session, url: str, params: dict, timeout: int):
    """带重试的 GET 请求。

    网络错误重试，次数由 config.toml [bilibili] max_retries 控制；
    412 属于风控拦截，重试没有意义，直接熔断。
    """
    remaining = _risk_remaining()
    if remaining > 0:
        raise RiskControlError(f"风控冷却中({int(remaining)}s)，本次跳过")

    max_retries = _config["bilibili"]["max_retries"]
    last_err = None
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep(2 + attempt)  # 递增等待：2s / 3s / 4s

            resp = session.get(url, params=params, timeout=timeout)

            if resp.status_code == 412:
                # 风控拦截：多半是 buvid cookie 掉了，重新取一次，下次再试
                _trip_risk()
                session.cookies.clear()
                _ensure_buvid(session)
                raise RiskControlError("412 风控拦截（缺少 buvid 设备标识或被限流）")

            resp.raise_for_status()
            _reset_risk()
            return resp
        except RiskControlError:
            raise
        except (
            requests.ConnectionError,
            requests.Timeout,
            ConnectionError,
            requests.HTTPError,
        ) as e:
            last_err = e
    raise last_err


def fetch_video_detail(session: requests.Session, bvid: str) -> tuple[dict | None, str | None]:
    """获取视频基本信息（播放量、弹幕、评论等）"""
    try:
        resp = _retry_get(
            session,
            "https://api.bilibili.com/x/web-interface/view",
            params={"bvid": bvid},
            timeout=15,
        )
        data = resp.json()
        if data["code"] != 0:
            return None, f"code={data['code']} msg={data.get('message','')}"
        return data["data"], None
    except RiskControlError as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)


def fetch_online_count(session: requests.Session, bvid: str, cid: int) -> tuple[dict | None, str | None]:
    """获取视频实时在线人数"""
    try:
        resp = _retry_get(
            session,
            "https://api.bilibili.com/x/player/online/total",
            params={"bvid": bvid, "cid": cid},
            timeout=10,
        )
        data = resp.json()
        if data["code"] != 0:
            return None, f"code={data['code']} msg={data.get('message','')}"
        return data["data"], None
    except RiskControlError as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)
