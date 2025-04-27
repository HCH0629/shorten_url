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
from api.cache import get_redis 

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
        expiration_date = datetime.now() + timedelta(days=DEFAULT_EXPIRATION_DAYS)

        # 將 HttpUrl 轉換為字串
        original_url_str = str(url_input.original_url)

        
        # 創建 Url 實例並將資料插入資料庫 
        new_url = models.URL(
            short_url=short_url,
            original_url=original_url_str,
            expiration_date=expiration_date
        )

        db_conn.add(new_url)
        db_conn.commit()


        # --- 寫入 Redis ---
        if redis_conn:
            try:
                # 使用 set 方法，key 是 short_url，value 是 original_url
                remaining_seconds = int((expiration_date - datetime.now()).total_seconds())
                
                # 因為 ex 一定要是正整數 所以這邊再多一個判斷
                if remaining_seconds > 0:
                    redis_conn.set(short_url, original_url_str, ex=remaining_seconds)

            except redis.RedisError as e:
                # 如果 Redis 寫入失敗，只記錄錯誤，不影響主要流程，在不使用 Redis 也可以正常運行
                print(f"Redis 寫入失敗 {e}")
        else:
            print(f"未寫入快取")


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
    try:
        # --- 檢查 Redis ---
        if redis_conn:
            try:
                cached_original_url = redis_conn.get(short_url)
                if cached_original_url:
                    print(f"Redis 有: {short_url}")
                    # 直接從 Redis 重定向
                    return RedirectResponse(status_code=status.HTTP_302_FOUND, url=cached_original_url)
                else:
                    print(f"Redis 未出現: {short_url}")

            except redis.RedisError as e:
                print(f"讀取 Redis 快取錯誤 ({short_url}): {e}")
                # Redis 讀取失敗，繼續往下查詢資料庫

        else:
            print(f"跳過 Redis 檢查")

    
        # --- Redis 未出現或 Redis 不可用，查詢資料庫 ---
        # 查找短碼 使用 ORM 查詢資料
        url_data = db_conn.query(models.URL).filter(models.URL.short_url == short_url).first()

        # 檢查是否存在
        if not url_data:
            return HTMLResponse(content="<html><body><h1>404 - Short URL not found</h1></body></html>", status_code=status.HTTP_404_NOT_FOUND)

        # 從 URL 實例中獲取原始網址和過期時間
        original_url = url_data.original_url
        expiration_date = url_data.expiration_date
        
        # 將從資料庫找到的結果寫入快取，如果 redis 不明原因暫時損毀後，可以再次寫回 (但目前實際上 如果 redis 遇到意外 shutdown 以現在的 code 是要直接重啟 pod or container)
        if redis_conn:
            
            try:
                remaining_seconds = int((expiration_date - datetime.now()).total_seconds())
                
                if remaining_seconds > 0:
                    redis_conn.set(short_url, original_url, ex=remaining_seconds)

            except redis.RedisError as e:
                # 如果快取寫入失敗，只記錄錯誤，不影響主要流程，在不使用 Redis 也可以正常運行
                print(f"Redis 快取寫入失敗 ({short_url}): {e}")

        

        
        # 獲取當下時間，先暫時不處理時區問題
        current_time = datetime.now()
        
        # 檢查是否過期 (這邊建議先把 F12 -> network -> 停用快取勾起來)
        if current_time > expiration_date:
            return HTMLResponse(content="<html><body><h1>410 - Short URL was expired </h1></body></html>",status_code=status.HTTP_410_GONE)
        
        
        # 成功返回訊息
        else:
            return RedirectResponse(status_code=status.HTTP_302_FOUND, url=original_url)
        
    except Exception as e:
        return HTMLResponse(content="<html><body><h1>500 - 系統錯誤 </h1></body></html>",status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)