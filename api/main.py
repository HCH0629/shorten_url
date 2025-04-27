import os
import sqlite3
import contextlib

from fastapi import FastAPI, Request  
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from utils.logger import LoggingMiddleware, set_project_name
from api.routers import url
from api.database import db_manager, init_db

DATABASE_PATH = os.environ.get('DATABASE_PATH', 'urls.db')
PROJECT_NAME = 'REDIRT_URL'
set_project_name(PROJECT_NAME)




# FastAPI lifespan 管理器，用於應用程式啟動和關閉事件
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # API啟動時執行的程式碼
    print("API啟動")

    # 初始化 database
    init_db()
    yield
    
    # API關閉時執行的程式碼
    print("API關閉")

    # 關閉時清理 SQLAlchemy
    if db_manager.engine:
        print("關閉資料庫引擎連接池")
        db_manager.engine.dispose()




# --- Create FastAPI App ---
app = FastAPI(
     title="短網址服務 API",
    description="一個用於建立和重定向短網址的 FastAPI 應用程式",
    version="1.0.0",
    lifespan=lifespan
)


# --- 速率限制設定 (Rate Limiter Setup using slowapi) ---
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter

# --- 自定義速率限制超過的處理器 ---
async def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    # 自定義處理過程
    return JSONResponse(
        status_code=429,
        content={"error": f"Rate limit exceeded. Please try again later. Reason: {exc.detail}"}
    )

# 註冊自定義的異常處理器
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_exceeded_handler)


# 將 SlowAPIMiddleware 添加到應用程式，使其生效
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(LoggingMiddleware)                   



# --- 所有 routers 集中在這邊進行管理 ---
app.include_router(url.router)



# --- Root ---
@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Redirtion URL API. Visit /docs for documentation"}

