import os
import json
import time
import random
from instagrapi import Client
from urllib.parse import urlparse
from models import IGStats
from datetime import date

# ---------- 帳號池設定 ----------
ACCOUNT_POOL = [
    {"username": os.getenv("IG_USER_1"), "password": os.getenv("IG_PASS_1")},
    {"username": os.getenv("IG_USER_2"), "password": os.getenv("IG_PASS_2")},
    # 可再新增更多帳號
]

SETTINGS_DIR = "ig_settings"  # 存放 cookies/session 的目錄
os.makedirs(SETTINGS_DIR, exist_ok=True)

# ---------- 工具函式 ----------
def parse_username_from_url(instagram_url: str) -> str:
    parsed = urlparse(instagram_url)
    return parsed.path.strip("/").split("/")[0]

# def load_or_login(account):
#     """
#     嘗試從本地 session 檔案登入，若無則重新登入並保存 cookies
#     """
#     cl = Client()
#     settings_path = os.path.join(SETTINGS_DIR, f"{account['username']}_settings.json")
#
#     try:
#         if os.path.exists(settings_path):
#             with open(settings_path, "r") as f:
#                 cl.set_settings(json.load(f))
#             cl.login(account["username"], account["password"])
#         else:
#             cl.login(account["username"], account["password"])
#             with open(settings_path, "w") as f:
#                 json.dump(cl.get_settings(), f)
#         print(f"使用帳號 {account['username']} 登入成功")
#     except Exception as e:
#         print(f"帳號 {account['username']} 登入失敗：{e}")
#         return None
#
#     return cl

def load_or_login(account):
    """
    嘗試從本地 session 檔案登入，若無則重新登入並保存 cookies。
    若登入失敗，則刪除對應的 session 檔案。
    """
    cl = Client()
    settings_path = os.path.join(SETTINGS_DIR, f"{account['username']}_settings.json")

    try:
        if os.path.exists(settings_path):
            with open(settings_path, "r") as f:
                cl.set_settings(json.load(f))
            cl.login(account["username"], account["password"])
        else:
            cl.login(account["username"], account["password"])
            with open(settings_path, "w") as f:
                json.dump(cl.get_settings(), f)
        print(f"使用帳號 {account['username']} 登入成功")
    except Exception as e:
        print(f"帳號 {account['username']} 登入失敗：{e}")
        # 自動刪除損壞的 session 檔案
        if os.path.exists(settings_path):
            try:
                os.remove(settings_path)
                print(f"已刪除損壞的 session 檔案：{settings_path}")
            except Exception as del_err:
                print(f"刪除 session 檔案失敗：{del_err}")
        return None

    return cl


def get_client():
    """
    從帳號池中選擇可用帳號並返回 Client
    若全部失敗，則回傳 None
    """
    for account in ACCOUNT_POOL:
        client = load_or_login(account)
        if client:
            return client
    # raise RuntimeError("所有帳號登入失敗，無法取得 IG Client")
    print("所有帳號登入失敗，無法取得 IG Client")
    return None  # 不 raise

# 初始化全域 client（常駐 session）
# global_client = get_client()

# ---------- 單筆爬取 ----------
# def crawl_ig(influencer_id, url, session, today=date.today()):
#     try:
#         username = parse_username_from_url(url)
#
#         # 隨機延遲，避免短時間連續請求
#         time.sleep(random.uniform(5, 10))
#
#         user_id = global_client.user_id_from_username(username)
#         user = global_client.user_info(user_id)
#
#         record = IGStats(
#             influencer_id=influencer_id,
#             username=username,
#             url=url,
#             followers=user.follower_count,
#             following=user.following_count,
#             posts=user.media_count,
#             date=today
#         )
#         session.add(record)
#         session.commit()
#
#         return {
#             "status": "success",
#             "platform": "IG",
#             "influencer": influencer_id,
#             "username": username,
#             "followers": user.follower_count,
#             "posts": user.media_count
#         }
#
#     except Exception as e:
#         session.rollback()
#         return {
#             "status": "error",
#             "platform": "IG",
#             "influencer": influencer_id,
#             "message": str(e)
#         }

def crawl_ig(influencer_id, url, session, today=date.today()):
    try:
        client = get_client()
        if not client:
            raise Exception("無可用 IG 帳號，無法取得 client")

        username = parse_username_from_url(url)
        time.sleep(random.uniform(5, 10))  # 防止請求過快

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
        return {
            "status": "error",
            "platform": "IG",
            "influencer": influencer_id,
            "message": str(e)
        }

# ---------- 批量爬取 ----------
def crawl_ig_batch(influencers, session, today=date.today()):
    """
    批量爬取多個 influencer
    influencers: list of {"influencer_id": "xxx", "url": "..."}
    """
    results = []
    for item in influencers:
        influencer_id = item.get("influencer_id")
        url = item.get("url")
        result = crawl_ig(influencer_id, url, session, today)
        results.append(result)
    return results
