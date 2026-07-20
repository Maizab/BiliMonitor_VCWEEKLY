import time
import requests

from config import _config

# ============ B站 API 请求 ============
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


def build_session() -> requests.Session:
    """创建一个带伪装请求头的 requests Session"""
    s = requests.Session()
    s.headers.update(HEADERS_TEMPLATE)
    return s


def _retry_get(session: requests.Session, url: str, params: dict, timeout: int):
    """带重试的 GET 请求，网络/HTTP 错误时重试，次数由 config.toml [bilibili] max_retries 控制"""
    max_retries = _config["bilibili"]["max_retries"]
    last_err = None
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep(2 + attempt)  # 递增等待：2s / 3s / 4s
            resp = session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
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
    except Exception as e:
        return None, str(e)
