import os
import json
import logging
import uuid
from datetime import datetime
from fastapi import Request
from logging.handlers import TimedRotatingFileHandler
from starlette.responses import Response, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pathlib import Path

# 專案名稱由外部設定
PROJECT_NAME = "default_project"  # 預設值，會由 main.py 改變
logger = None  # 初始化 Logger 變數

def set_project_name(name: str):
    """ 外部設定專案名稱，並建立 Logger """
    global PROJECT_NAME, logger
    PROJECT_NAME = name

    # 獲取 Pod 名稱
    pod_name = os.getenv("POD_NAME", PROJECT_NAME)

    # 根據專案名稱建立 Logger
    logger = logging.getLogger(PROJECT_NAME)
    logger.setLevel(logging.INFO)

    # 設定 Log 檔案名稱，例如：logs\my_project_xxxx.log
    log_dir = Path(os.getenv("LOG_DIR") or "logs")
    log_dir.mkdir(exist_ok=True)
    log_filename = log_dir.joinpath(f"{pod_name}.log") # log名稱跟著pod name


    # 設定每天 00:00 產生新檔案，最多保留 365 天
    log_handler = TimedRotatingFileHandler(
        log_filename, when="midnight", interval=1, backupCount=365, encoding="utf-8"
    )


    log_handler.suffix = "%Y%m%d"  # 設定日期格式，換日或pod關閉時，自動加日期時間，此日期時間是切換LOG FILE的時間
    

    # 定義log格式
    formatter = logging.Formatter("%(message)s") # 只 show log 內容
    log_handler.setFormatter(formatter)

    # 確保 Logger 只添加一次 Handler（避免重複）
    if not logger.handlers:
        logger.addHandler(log_handler)

async def log_request(request: Request, response: Response, request_json, request_time, response_time, total_duration):
    """ 記錄 API 請求資訊，每個請求帶有 UUID """
    if logger is None:
        return  # 確保 logger 先初始化

    request_id = str(uuid.uuid4())  # 產生 UUID 作為請求唯一識別碼

    #讀取回應內容
    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk

    # 重建回應對象
    new_response = StreamingResponse(
        content=iter([response_body]),
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type
    )

    # 建立 request_data (JSON 格式) 方便 ELK 收集
    request_data  = {
        "uuid": request_id,
        "request_time": request_time, # 請求時間
        "method": request.method,
        "path": request.url.path,
        "request_json": request_json,
        "query_params": dict(request.query_params),
        "status_code": response.status_code, # 成功 : 2xx, 客戶端失敗 : 4xx, 服務端失敗 : 5xx
        "response_time": response_time, # 回應時間
        "total_duration": total_duration # 花費時間
    }


    # 轉為 JSON 字串，寫入 Log 檔案
    log_entry = json.dumps(request_data, ensure_ascii=False)
    logger.info(log_entry) # 使用 Logger 記錄
    
    
    return request_id, new_response  # 回傳 UUID，讓 API 端可以使用 如果是一個連續性的 log 可以方便查詢過程

#  自訂中介層 (Middleware) 來記錄請求
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_datetime = datetime.now()
        request_time = request_datetime.strftime('%Y-%m-%d %H:%M:%S.%f') # 紀錄請求時間

        # 若使用POST，須把request的JSON內容取出，寫入LOG
        # 若不使用POST，須把request的JSON內容取出，寫入LOG
        if request.method == 'POST' :
            request_json = await request.json()
        else :
            request_json = ""

        response = await call_next(request) # 執行api處理，詳看 notion 文檔介紹 https://www.notion.so/call_next-1e1e8a40ee9b80309076f2cc8375da85

        response_datetime = datetime.now()
        response_time = response_datetime.strftime('%Y-%m-%d %H:%M:%S.%f') # 紀錄回應時間

        total_duration = (response_datetime-request_datetime).total_seconds() # 紀錄花費時間

        request_id, new_response = await log_request(request, response, request_json, request_time, response_time, total_duration)  # 記錄請求，獲取 UUID
        new_response.headers["X-Request-ID"] = request_id  # 在回應標頭中加入 UUID
        return new_response