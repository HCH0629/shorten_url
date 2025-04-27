import os
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, HttpUrl, field_validator
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

from dotenv import load_dotenv
load_dotenv()

MAX_URL_LENGTH = int(os.getenv('MAX_URL_LENGTH','2048'))

Base = declarative_base()

class URLInput(BaseModel):
    original_url: HttpUrl
    
    # 針對 original_url 欄位的自定義驗證邏輯
    @field_validator('original_url')
    def check_url_length(cls, v):
        if len(str(v)) > MAX_URL_LENGTH:
            raise ValueError(f"URL 過長 (最多 {MAX_URL_LENGTH} 個字元)")
        return v

class URLResponse(BaseModel):
    short_url: Optional[str] = None
    expiration_date: Optional[datetime] = None
    success: bool
    reason: Optional[str] = None


# 使用 ORM 防止 SQL INJECTION
class URL(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, index=True)
    short_url = Column(String, unique=True, index=True)
    original_url = Column(String)
    expiration_date = Column(DateTime)
    creation_date = Column(DateTime, default=datetime.utcnow)