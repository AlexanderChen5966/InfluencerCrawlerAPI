from instagrapi import Client
from urllib.parse import urlparse
from models import IGStats
from datetime import date
import os

# ✅ 拆網址取得 IG 使用者名稱
def parse_username_from_url(instagram_url: str) -> str:
    parsed = urlparse(instagram_url)
    return parsed.path.strip("/").split("/")[0]

# ✅ 初始化 instagrapi Client（可重複使用）
def init_client() -> Client:
    cl = Client()
    username = os.getenv("IG_USERNAME")
    password = os.getenv("IG_PASSWORD")
    if not username or not password:
        raise ValueError("請在 .env 中設定 IG_USERNAME 與 IG_PASSWORD")
    cl.login(username, password)
    return cl

# ✅ 外部呼叫用函式
def crawl_ig(influencer_id, url, session, today=date.today()):
    try:
        client = init_client()
        username = parse_username_from_url(url)
        user_id = client.user_id_from_username(username)
        user = client.user_info(user_id)

        record = IGStats(
            influencer_id=influencer_id,
            username=username,
            url=url,
            followers=user.follower_count,
            following=user.following_count,
            posts=user.media_count,
            date=today
        )

        session.add(record)
        session.commit()

        return {
            "status": "success",
            "platform": "IG",
            "influencer": influencer_id,
            "username": username,
            "followers": user.follower_count,
            "posts": user.media_count
        }

    except Exception as e:
        session.rollback()
        return {"status": "error", "platform": "IG", "influencer": influencer_id, "message": str(e)}
