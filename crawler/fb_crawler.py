from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from models import FBStats
import os

# ✅ 從網址取出粉專名稱
def get_page_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path.strip("/").split("/")[0]

# ✅ 爬蟲邏輯（抓追蹤數 + 寫入 DB）
async def crawl_fb(influencer_id, url, session, today):
    try:
        page_name = get_page_name_from_url(url)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # 登入 Facebook
            await page.goto("https://www.facebook.com/login")
            await page.fill('input[name="email"]', os.getenv("FB_EMAIL"))
            await page.fill('input[name="pass"]', os.getenv("FB_PASSWORD"))
            await page.keyboard.press("Enter")
            await page.wait_for_load_state('networkidle')

            # 進入粉專頁面
            await page.goto(url)
            await page.wait_for_timeout(5000)

            # 擷取粉專頁面 HTML
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            # 擷取追蹤人數
            followers_text = "0"
            for strong in soup.find_all("strong"):
                text = strong.get_text(strip=True).replace("\xa0", "")
                if "人" in text or "萬" in text:
                    followers_text = text
                    break
            # 萬字轉換與數字清理
            if "萬" in followers_text:
                followers = int(float(followers_text.replace("萬", "")) * 10000)
            else:
                followers = int("".join(filter(str.isdigit, followers_text)))
            record = FBStats(
                influencer_id=influencer_id,
                page_name=page_name,
                url=url,
                followers=followers,
                date=today
            )
            session.add(record)
            session.commit()
            print(f"✅ 成功寫入：{influencer_id}（{page_name}）")
            return {"status": "success", "platform": "FB", "followers": followers}

    except Exception as e:
        session.rollback()
        print(f"❌ 寫入 {influencer_id} 發生錯誤：{e}")

    finally:
        session.close()
