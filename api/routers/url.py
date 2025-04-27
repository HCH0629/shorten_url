import os
import secrets
import string
import redis
from typing import Optional 
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from sqlalchemy.orm import Session
from api import models
from api.database import get_db
from api.cache import get_redis, REDIS_CACHE_TTL 

from dotenv import load_dotenv
load_dotenv()

DEFAULT_EXPIRATION_DAYS = int(os.getenv('DEFAULT_EXPIRATION_DAYS','30'))
SHORT_CODE_LENGTH = int(os.getenv('SHORT_CODE_LENGTH','8'))


# --- 短代碼生成 ---
def generate_short_code(length=SHORT_CODE_LENGTH, db_conn: Session = Depends(get_db)):
    """
    生成一個唯一的隨機短代碼（資料庫連線進行檢查)
    """
    tmp = 0 # 避免有重複short url造成無限迴圈
    while tmp < 10:
        # 簡單快速生成唯一的短碼
        characters = string.ascii_letters + string.digits
        short_code = ''.join(secrets.choice(characters) for _ in range(length))
        
        short_url = f'http://{short_code}'

        # 查找有沒有生成的短碼，使否有重複 使用 ORM 查詢資料
        result = db_conn.query(models.URL).filter(models.URL.short_url == short_url).first()

        tmp += 1
        if result is None:
            return short_url

router = APIRouter(
    prefix="/url",
    tags=["Url"]
)



@router.post("/create_short_url", response_model=models.URLResponse, status_code=status.HTTP_201_CREATED, description='依據原網址建立短網址')
async def create_short_url(
    url_input: models.URLInput, 
    db_conn: Session  = Depends(get_db),
    redis_conn: Optional[redis.Redis] = Depends(get_redis)
    ):

    try:
        # 建構短 URL        
        short_url = generate_short_code(db_conn=db_conn)

        # 計算過期時間 (30天後)
        expiration_date = datetime.now(timezone.utc) + timedelta(days=DEFAULT_EXPIRATION_DAYS)

        # 將 HttpUrl 轉換為字串
        original_url_str = str(url_input.original_url)
        

        # 創建 Url 實例並將資料插入資料庫 
        new_url = models.URL(
            short_url=short_url,
            original_url=original_url_str,
            expiration_date=expiration_date
        )

        db_conn.add(new_url)  # 添加實例到會話
        db_conn.commit()  # 提交變更


        # --- 寫入快取 ---
        if redis_conn:
            try:
                # 使用 set 方法，key 是 short_url，value 是 original_url
                # ex=REDIS_CACHE_TTL 設定 Redis 中的過期時間 (秒)
                redis_conn.set(short_url, original_url_str, ex=REDIS_CACHE_TTL)
                # print(f"快取寫入成功: {short_url} -> {original_url_str} (TTL: {REDIS_CACHE_TTL}s)")
            except redis.RedisError as e:
                # 如果快取寫入失敗，只記錄錯誤，不影響主要流程，在不使用 docker compose 也可以正常運行
                print(f"Redis 快取寫入失敗 ({short_url}): {e}")
        else:
            print(f"Redis 連線不可用，未寫入快取 ({short_url})")


        return models.URLResponse(
            success=True,
            original_url=url_input,
            short_url=short_url,
            expiration_date=expiration_date
        )
    
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "reason": "建立 URL 時發生內部錯誤"} 
            # content={"success": False, "reason": str(e)} # 內部觀察錯誤原因使用
        )



@router.get("/redirect_to_original", description='重新定向到原網址')
async def redirect_to_original(
    short_url: str, 
    db_conn: Session  = Depends(get_db),
    redis_conn: Optional[redis.Redis] = Depends(get_redis)
   ):
    

    # --- 1. 檢查快取 ---
    print(f"檢查快取: {short_url}")
    if redis_conn:
        try:
            cached_original_url = redis_conn.get(short_url)
            if cached_original_url:
                print(f"快取命中: {short_url}")
                # 直接從快取重定向
                return RedirectResponse(status_code=status.HTTP_302_FOUND, url=cached_original_url)
            else:
                print(f"快取未命中: {short_url}")
        except redis.RedisError as e:
            print(f"讀取 Redis 快取錯誤 ({short_url}): {e}")
            # 快取讀取失敗，繼續往下查詢資料庫

    else:
        print(f"Redis 連線不可用，跳過快取檢查 ({short_url})")

    # --- 2. 快取未命中或 Redis 不可用，查詢資料庫 ---
    
    print(f"從資料庫查找: {short_url}")
    try:
        url_data = db_conn.query(models.URL).filter(models.URL.short_url == short_url).first()

        # --- 3. 處理資料庫查詢結果 ---
        if not url_data:
            print(f"資料庫未找到: {short_url}")
            return HTMLResponse(content="<html><body><h1>404 - Short URL not found</h1></body></html>", status_code=status.HTTP_404_NOT_FOUND)

        # --- 4. 資料庫找到，獲取資料 ---
        original_url = url_data.original_url
        expiration_date = url_data.expiration_date # 這是從 DB 來的 datetime 物件或字串
        print(f"資料庫找到: {short_url} -> {original_url}, DB Expires: {expiration_date}")


        # --- 5. 將從資料庫找到的結果寫入快取 ---
        if redis_conn:
            try:
                redis_conn.set(short_url, original_url, ex=REDIS_CACHE_TTL)
                print(f"資料庫結果已寫入快取: {short_url} (TTL: {REDIS_CACHE_TTL}s)")
            except redis.RedisError as e:
                print(f"警告：寫入 Redis 快取失敗 ({short_url}): {e}")


        # 查找短碼 使用 ORM 查詢資料
        url_data = db_conn.query(models.URL).filter(models.URL.short_url == short_url).first()

        # 檢查是否存在
        if not url_data:
            # 改成用 HTMLResponse
            return HTMLResponse(content="<html><body><h1>404 - Short URL not found </h1></body></html>",status_code=status.HTTP_404_NOT_FOUND)
            # return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"success": False, "reason": "短網址未找到"})
            
        
        # 從 URL 實例中獲取原始網址和過期時間
        original_url = url_data.original_url
        expiration_date = url_data.expiration_date


        # 將 expiration_date 轉換為 datetime 物件
        if isinstance(expiration_date, str):
            expiration_date = datetime.fromisoformat(expiration_date.replace("Z", "+00:00"))  # 處理 Z 時區標記
        
        # 獲取當下時間，不過先暫時不處理時區問題 -> 晚點再回來處理 應該要使用 pytz
        current_time = datetime.now()
        
        # 檢查是否過期
        if current_time > expiration_date:
            # 改成用 HTMLResponse
            return HTMLResponse(content="<html><body><h1>410 - Short URL was expired </h1></body></html>",status_code=status.HTTP_410_GONE)
            # return JSONResponse(status_code=status.HTTP_410_GONE, content={"success": False, "reason": "短網址已過期"})
        
        
        # 成功返回訊息
        else:
            return RedirectResponse(status_code=status.HTTP_302_FOUND, url=original_url)
        
    except Exception as e:
        return HTMLResponse(content="<html><body><h1>500 - 系統錯誤 </h1></body></html>",status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"success": False, "reason": f"系統錯誤: {str(e)}"})