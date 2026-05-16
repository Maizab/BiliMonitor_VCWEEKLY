import requests

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


def fetch_video_detail(session: requests.Session, bvid: str) -> tuple[dict | None, str | None]:
    """获取视频基本信息（播放量、弹幕、评论等）"""
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
    """获取视频实时在线人数"""
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
