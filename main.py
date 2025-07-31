# from fastapi import FastAPI
# from pydantic import BaseModel
# from dotenv import load_dotenv
# from models import Base, engine, Session, IGStats, FBStats
# from crawler.ig_crawler import crawl_ig
# from crawler.fb_crawler import crawl_fb
# import os
# from datetime import date
#
# load_dotenv()
# Base.metadata.create_all(engine)
# app = FastAPI()
#
# class CrawlerRequest(BaseModel):
#     influencer_id: str
#     platform: str
#     url: str
#
# @app.post("/crawl")
# async def crawl_data(req: CrawlerRequest):
#     session = Session()
#     today = date.today()
#     try:
#         if req.platform == "IG":
#             # return crawl_ig(req.influencer_id, req.url, session, today)
#             return crawl_ig(req.influencer_id, req.url, session, date.today())
#         elif req.platform == "FB":
#             return await crawl_fb(req.influencer_id, req.url, session, today)
#         else:
#             return {"status": "error", "message": "平台格式錯誤"}
#     except Exception as e:
#         session.rollback()
#         return {"status": "error", "message": str(e)}
#     finally:
#         session.close()


from fastapi import FastAPI
from pydantic import BaseModel
from datetime import date
from models import Session
from crawler.ig_crawler import crawl_ig, crawl_ig_batch
from crawler.fb_crawler import crawl_fb, crawl_fb_batch
import os

app = FastAPI()

# 單筆請求格式
class CrawlerRequest(BaseModel):
    influencer_id: str
    platform: str  # "IG" 或 "FB"
    url: str

# 批量請求格式
class CrawlerBatchRequest(BaseModel):
    influencers: list[dict]  # [{"influencer_id": "xxx", "platform": "IG/FB", "url": "..."}]

@app.post("/crawl")
async def crawl_data(req: CrawlerRequest):
    session = Session()
    today = date.today()
    try:
        if req.platform.upper() == "IG":
            return crawl_ig(req.influencer_id, req.url, session, today)
        elif req.platform.upper() == "FB":
            return await crawl_fb(req.influencer_id, req.url, session, today)
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
    today = date.today()
    results = []
    try:
        # 將IG和FB分開處理
        ig_items = [item for item in req.influencers if item.get("platform", "").upper() == "IG"]
        fb_items = [item for item in req.influencers if item.get("platform", "").upper() == "FB"]

        if ig_items:
            ig_results = crawl_ig_batch(ig_items, session, today)
            results.extend(ig_results)

        if fb_items:
            fb_results = await crawl_fb_batch(fb_items, session, today)
            results.extend(fb_results)

        return {"status": "success", "results": results}
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        session.close()

