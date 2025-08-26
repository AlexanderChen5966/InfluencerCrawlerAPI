from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from models import Base, engine, Session  # 你現有的 models.py 裡應該有 Base、engine、Session
from sqlalchemy import text

from crawler.ig_crawler import crawl_ig, crawl_ig_batch
from crawler.fb_crawler import crawl_fb, crawl_fb_batch

app = FastAPI()

@app.on_event("startup")
def init_db():
    # 一次性建立缺少的資料表（不會覆蓋既有資料）
    Base.metadata.create_all(bind=engine)


# 單筆請求格式
class CrawlerRequest(BaseModel):
    influencer_id: str
    platform: str  # "IG" 或 "FB"
    url: str

# 批量請求格式
class CrawlerBatchRequest(BaseModel):
    influencers: list[dict]  # [{"influencer_id": "xxx", "platform": "IG/FB", "url": "..."}]

@app.get("/health")
def health():
    """
    DB 健康檢查：
    - 成功：回 200，{"status":"ok","db":"up"}
    - 失敗：回 503，{"status":"fail","db":"down","error": "..."}
    """
    session = Session()
    try:
        session.execute(text("SELECT 1"))
        return {"status": "ok", "db": "up"}
    except Exception as e:
        # 也可在這裡加 logging
        raise HTTPException(status_code=503, detail={"status": "fail", "db": "down", "error": str(e)})
    finally:
        session.close()


@app.post("/crawl")
async def crawl_data(req: CrawlerRequest):
    session = Session()
    # today = date.today()
    try:
        if req.platform.upper() == "IG":
            return crawl_ig(req.influencer_id, req.url, session, None)
        elif req.platform.upper() == "FB":
            return await crawl_fb(req.influencer_id, req.url, session, None)
        else:
            return {"status": "error", "message": "平台格式錯誤"}
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        session.close()

@app.post("/crawl_batch")
async def crawl_batch(req: CrawlerBatchRequest):
    """
    批量爬取，支援 IG 和 FB
    """
    session = Session()
    # today = date.today()
    results = []
    try:
        # 將IG和FB分開處理
        fb_items = [item for item in req.influencers if item.get("platform", "").upper() == "FB"]
        ig_items = [item for item in req.influencers if item.get("platform", "").upper() == "IG"]

        if fb_items:
            fb_results = await crawl_fb_batch(fb_items, session, None)
            results.extend(fb_results)

        if ig_items:
            ig_results = crawl_ig_batch(ig_items, session, None)
            results.extend(ig_results)


        return {"status": "success", "results": results}
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        session.close()

