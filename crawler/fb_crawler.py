# 統一成和 IG 相同風格：today=None、先查短路、逐筆提交、登入狀態持久化
# fb_crawler.py
import os, re
from datetime import date
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from sqlalchemy.exc import IntegrityError
from playwright.async_api import async_playwright, Error as PWError
from models import FBStats

# ====== ENV ======
FB_EMAIL = os.getenv("FB_EMAIL", "")
FB_PASSWORD = os.getenv("FB_PASSWORD", "")
# FB_STORAGE_STATE_PATH = os.getenv("FB_STORAGE_STATE_PATH", "fb_storage.json")  # 建議掛 Zeabur Volume
FB_STORAGE_STATE_PATH = os.getenv("FB_STORAGE_STATE_PATH", "/data/fb_storage.json")  # 建議掛 Zeabur Volume

HEADLESS = os.getenv("FB_HEADLESS", "true").lower() != "false"  # 預設 headless



# ====== Utils ======
def get_page_name_from_url(url: str) -> str:
    """
    取粉專識別名稱：facebook.com/<page_name>/...
    """
    path = urlparse(url).path.strip("/")
    return path.split("/")[0] if path else ""


def _parse_followers_text(soup: BeautifulSoup) -> str | None:
    """
    嘗試從 <strong> 或附近文字抓追蹤數（可能含「萬」）
    """
    # 1) 先挑 <strong>（和你原本邏輯一致）
    for strong in soup.find_all("strong"):
        text = strong.get_text(strip=True).replace("\xa0", "")
        if ("人" in text) or ("萬" in text):
            return text

    # 2) 後援：找含「追蹤」「粉絲」的片段
    candidates = soup.find_all(text=re.compile(r"(追蹤|粉絲|人|萬)"))
    for c in candidates:
        t = str(c).strip()
        if re.search(r"[\d,\.]+", t):
            return t
    return None


def _followers_to_int(text: str) -> int:
    """
    '185萬人' / '1,234,567 人' / '58.7 萬' → 轉 int
    """
    if "萬" in text:
        m = re.search(r"([\d\.]+)", text)
        if m:
            return int(float(m.group(1)) * 10000)
    # 無「萬」時，抽取數字與逗號
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


# ====== Playwright Login ======
async def _new_context_with_state(p):
    """
    建立 context，若有 storage_state 檔就載入，否則乾淨 context
    """
    if os.path.exists(FB_STORAGE_STATE_PATH):
        return await p.chromium.launch_persistent_context(
            user_data_dir=None, headless=HEADLESS, storage_state=FB_STORAGE_STATE_PATH
        )
    # 無既有 state：走一般 browser/context，再登入後儲存
    browser = await p.chromium.launch(headless=HEADLESS)
    context = await browser.new_context()
    return context


async def _ensure_logged_in(context):
    """
    驗證是否已登入；未登入則用帳密登入並覆寫 storage_state
    """
    page = await context.new_page()
    # 到首頁偵測是否需要登入
    await page.goto("https://www.facebook.com/", timeout=60000)
    has_login = await page.locator("input[name='email']").count() == 0

    if not has_login:
        if not FB_EMAIL or not FB_PASSWORD:
            raise RuntimeError("FB_EMAIL / FB_PASSWORD 未設定，無法登入")
        await page.fill("input[name='email']", FB_EMAIL)
        await page.fill("input[name='pass']", FB_PASSWORD)
        await page.click("button[name='login']")
        # 等待登入完成（看不到 email 欄即視為進入）
        await page.wait_for_timeout(5000)

    # 無論是否剛登入，都把狀態寫檔（確保是最新）
    try:
        await context.storage_state(path=FB_STORAGE_STATE_PATH)
    except Exception:
        # 無法寫檔時略過，不影響流程
        pass
    return page


# ====== 單筆 ======
async def crawl_fb(influencer_id: str, url: str, session, today: date | None = None):
    today = today or date.today()
    page_name = get_page_name_from_url(url)

    # 先查短路（避免重複）
    exists = session.query(FBStats.id).filter_by(
        influencer_id=influencer_id, page_name=page_name, date=today
    ).first()
    if exists:
        return {"status": "skip", "platform": "FB", "influencer": influencer_id, "message": "duplicate for today"}

    try:
        async with async_playwright() as p:
            # 1) context & login（自動復原）
            try:
                context = await _new_context_with_state(p)
                page = await _ensure_logged_in(context)
            except Exception:
                # state 可能壞掉 → 刪檔、重建 context 再試一次
                try:
                    if os.path.exists(FB_STORAGE_STATE_PATH):
                        os.remove(FB_STORAGE_STATE_PATH)
                except Exception:
                    pass
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=None, headless=HEADLESS
                )
                page = await _ensure_logged_in(context)

            # 2) 前往粉專並解析
            await page.goto(url, timeout=60000)
            await page.wait_for_timeout(5000)
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            text = _parse_followers_text(soup) or ""
            followers = _followers_to_int(text)

            # 3) 寫 DB（逐筆提交）
            session.add(FBStats(
                influencer_id=influencer_id,
                page_name=page_name,
                url=url,
                followers=followers,
                date=today
            ))
            session.commit()

            await context.close()
            return {"status": "success", "platform": "FB", "influencer": influencer_id, "followers": followers}

    except IntegrityError:
        session.rollback()
        return {"status": "skip", "platform": "FB", "influencer": influencer_id, "message": "unique constraint hit"}
    except (PWError, Exception) as e:
        session.rollback()
        return {"status": "error", "platform": "FB", "influencer": influencer_id, "message": str(e)}


# ====== 批量 ======
async def crawl_fb_batch(influencers: list[dict], session, today: date | None = None):
    today = today or date.today()
    results = []
    try:
        async with async_playwright() as p:
            # 準備共用 context/page（減少重覆登入）
            try:
                context = await _new_context_with_state(p)
                page = await _ensure_logged_in(context)
            except Exception:
                try:
                    if os.path.exists(FB_STORAGE_STATE_PATH):
                        os.remove(FB_STORAGE_STATE_PATH)
                except Exception:
                    pass
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=None, headless=HEADLESS
                )
                page = await _ensure_logged_in(context)

            for item in influencers:
                influencer_id = item.get("influencer_id")
                url = item.get("url")
                page_name = get_page_name_from_url(url)

                # 先查短路
                exists = session.query(FBStats.id).filter_by(
                    influencer_id=influencer_id, page_name=page_name, date=today
                ).first()
                if exists:
                    results.append({"status": "skip", "platform": "FB", "influencer": influencer_id,
                                    "message": "duplicate for today"})
                    continue

                try:
                    await page.goto(url, timeout=60000)
                    await page.wait_for_timeout(5000)
                    html = await page.content()
                    soup = BeautifulSoup(html, "html.parser")

                    text = _parse_followers_text(soup) or ""
                    followers = _followers_to_int(text)

                    session.add(FBStats(
                        influencer_id=influencer_id,
                        page_name=page_name,
                        url=url,
                        followers=followers,
                        date=today
                    ))
                    session.commit()

                    results.append({"status": "success", "platform": "FB", "influencer": influencer_id,
                                    "followers": followers})
                except IntegrityError:
                    session.rollback()
                    results.append({"status": "skip", "platform": "FB", "influencer": influencer_id,
                                    "message": "unique constraint hit"})
                except (PWError, Exception) as e:
                    session.rollback()
                    results.append(
                        {"status": "error", "platform": "FB", "influencer": influencer_id, "message": str(e)})

            await context.close()
        return results

    except Exception as e:
        session.rollback()
        # 一律回傳 list，避免 main.py 的 extend 壞掉
        return [{"status": "error", "platform": "FB", "message": str(e)}]