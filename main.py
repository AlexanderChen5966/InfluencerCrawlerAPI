from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from models import Base, engine, Session, IGStats, FBStats
from crawler.ig_crawler import crawl_ig
from crawler.fb_crawler import crawl_fb
import os
from datetime import date

load_dotenv()
Base.metadata.create_all(engine)
app = FastAPI()

class CrawlerRequest(BaseModel):
    influencer_id: str
    platform: str
    url: str

@app.post("/crawl")
async def crawl_data(req: CrawlerRequest):
    session = Session()
    today = date.today()
    try:
        if req.platform == "IG":
            # return crawl_ig(req.influencer_id, req.url, session, today)
            return crawl_ig(req.influencer_id, req.url, session, date.today())
        elif req.platform == "FB":
            return await crawl_fb(req.influencer_id, req.url, session, today)
        else:
            return {"status": "error", "message": "平台格式錯誤"}
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        session.close()
