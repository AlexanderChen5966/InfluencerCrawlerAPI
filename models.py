from sqlalchemy import create_engine, Column, Integer, String, Text, Date, TIMESTAMP, func, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from dotenv import load_dotenv
load_dotenv()


DB_URL = os.getenv("LOCAL_DB_URL")
# DB_URL = os.getenv("POSTGRES_CONNECTION_STRING")

engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class IGStats(Base):
    __tablename__ = 'ig_stats'
    id = Column(Integer, primary_key=True)
    influencer_id = Column(String(255), nullable=False)
    username = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    followers = Column(Integer)
    following = Column(Integer)
    posts = Column(Integer)
    ct = Column(TIMESTAMP, server_default=func.now())
    date = Column(Date, nullable=False)
    __table_args__ = (
        UniqueConstraint('influencer_id', 'username', 'date', name='unique_daily_ig'),
    )

class FBStats(Base):
    __tablename__ = 'fb_stats'
    id = Column(Integer, primary_key=True)
    influencer_id = Column(String(255), nullable=False)
    page_name = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    followers = Column(Integer)
    ct = Column(TIMESTAMP, server_default=func.now())
    date = Column(Date, nullable=False)
    __table_args__ = (
        UniqueConstraint('influencer_id', 'page_name', 'date', name='unique_daily_fb'),
    )
