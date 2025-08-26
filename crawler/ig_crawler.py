import os, json, time, random
from urllib.parse import urlparse
from datetime import date
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired, TwoFactorRequired, PleaseWaitFewMinutes
from sqlalchemy.exc import IntegrityError
from models import IGStats

# ---------- 帳號池設定 ----------
ACCOUNT_POOL = [
    {"username": os.getenv("IG_USER_1"), "password": os.getenv("IG_PASS_1")},
    {"username": os.getenv("IG_USER_2"), "password": os.getenv("IG_PASS_2")},
    # 可再新增更多帳號
]

idx = 1

while os.getenv(f"IG_USER_{idx}"):
    ACCOUNT_POOL.append({
        "username": os.getenv(f"IG_USER_{idx}"),
        "password": os.getenv(f"IG_PASS_{idx}")
    })
    idx += 1

# 建議在 Zeabur 將此目錄掛到 Persistent Storage
IG_SETTINGS_DIR = os.getenv("IG_SETTINGS_DIR", "/data/ig_settings")
# IG_SETTINGS_DIR = os.getenv("IG_SETTINGS_DIR", "ig_settings")
os.makedirs(IG_SETTINGS_DIR, exist_ok=True)


# ---------- 工具 ----------
def _settings_path(username: str) -> str:
    return os.path.join(IG_SETTINGS_DIR, f"{username}_settings.json")

def _atomic_write_settings(cl: Client, path: str):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cl.get_settings(), f)
    os.replace(tmp, path)

def parse_username_from_url(instagram_url: str) -> str:
    """
    支援 https://www.instagram.com/<username>/ 或 @username
    """
    if not instagram_url:
        raise ValueError("empty IG url")
    if instagram_url.startswith("@"):
        return instagram_url[1:].strip("/")
    parsed = urlparse(instagram_url)
    if "instagram.com" in parsed.netloc and parsed.path:
        return parsed.path.strip("/").split("/")[0]
    return instagram_url.strip("/")

def load_or_login(account: dict) -> Client | None:
    """
    嘗試用 settings 登入；失敗則刪檔重登。
    每次成功登入都覆寫最新 settings（原子寫入）
    """
    username = account["username"]
    password = account["password"]
    path = _settings_path(username)

    cl = Client()
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                cl.set_settings(json.load(f))
        cl.login(username, password)
        _atomic_write_settings(cl, path)
        return cl
    except Exception:
        # settings 可能過期/損毀 → 刪檔乾淨登入
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        cl = Client()
        try:
            cl.login(username, password)
            _atomic_write_settings(cl, path)
            return cl
        except Exception as e2:
            print(f"[IG] login failed for {username}: {e2}")
            return None

_client: Client | None = None
_last_account: dict | None = None

def _health_check(cl: Client) -> bool:
    try:
        cl.get_timeline_feed()  # 輕量 ping；過期多半在此拋 LoginRequired
        return True
    except LoginRequired:
        return False

def _get_or_refresh_client() -> Client:
    """
    延遲初始化 + 自動重登/換帳號（帳號池 fallback）
    """
    global _client, _last_account

    if _client is None:
        for acc in ACCOUNT_POOL:
            cl = load_or_login(acc)
            if cl:
                _client, _last_account = cl, acc
                return _client
        raise RuntimeError("[IG] all accounts failed to login")

    if _health_check(_client):
        return _client

    # 同帳號重登
    if _last_account:
        cl = load_or_login(_last_account)
        if cl:
            _client = cl
            return _client

    # 換帳號池
    for acc in ACCOUNT_POOL:
        if _last_account and acc["username"] == _last_account["username"]:
            continue
        cl = load_or_login(acc)
        if cl:
            _client, _last_account = cl, acc
            return _client

    raise RuntimeError("[IG] no healthy client available after refresh")

# ---------- 單筆 ----------
def crawl_ig(influencer_id: str, url: str, session, today: date | None = None):
    today = today or date.today()
    try:
        cl = _get_or_refresh_client()
        username = parse_username_from_url(url)

        # 先查（短路，避免重複寫入）
        exists = session.query(IGStats.id).filter_by(
            influencer_id=influencer_id,
            username=username,
            date=today
        ).first()
        if exists:
            return {"status": "skip", "platform": "IG", "influencer": influencer_id, "message": "duplicate for today"}

        time.sleep(random.uniform(5, 10))  # 簡單節流

        user_id = cl.user_id_from_username(username)
        user = cl.user_info(user_id)

        session.add(IGStats(
            influencer_id=influencer_id,
            username=username,
            url=url,
            followers=user.follower_count,
            following=user.following_count,
            posts=user.media_count,
            date=today
        ))
        session.commit()

        return {
            "status": "success",
            "platform": "IG",
            "influencer": influencer_id,
            "username": username,
            "followers": user.follower_count,
            "posts": user.media_count
        }

    except PleaseWaitFewMinutes:
        session.rollback()
        return {"status": "error", "platform": "IG", "influencer": influencer_id, "message": "Rate limited, retry later."}
    except (ChallengeRequired, TwoFactorRequired):
        session.rollback()
        return {"status": "error", "platform": "IG", "influencer": influencer_id, "message": "Challenge/2FA required."}
    except IntegrityError:
        session.rollback()
        return {"status": "skip", "platform": "IG", "influencer": influencer_id, "message": "unique constraint hit"}
    except LoginRequired:
        session.rollback()
        return {"status": "error", "platform": "IG", "influencer": influencer_id, "message": "Login required."}
    except Exception as e:
        session.rollback()
        return {"status": "error", "platform": "IG", "influencer": influencer_id, "message": str(e)}

# ---------- 批量 ----------
def crawl_ig_batch(influencers: list[dict], session, today: date | None = None):
    results = []
    today = today or date.today()
    for item in influencers:
        influencer_id = item.get("influencer_id")
        url = item.get("url")
        res = crawl_ig(influencer_id, url, session, today)
        results.append(res)
    return results