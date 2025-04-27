import os
import redis
from dotenv import load_dotenv
from typing import Generator, Optional
from fastapi import HTTPException, status

# --- 載入環境變數 ---
load_dotenv()


# --- Redis 設定 ---
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
print(f"Redis 設定: host={REDIS_HOST}, port={REDIS_PORT}, db={REDIS_DB}")

# --- RedisManager 類 ---
class RedisManager:
    """管理 Redis 連線的類別"""
    def __init__(self, host: str, port: int, db: int):
        self.host = host
        self.port = port
        self.db = db
        self.connection: Optional[redis.Redis] = None

    def connect(self):
        """建立並測試 Redis 連線"""
        print("建立 Redis 連線")
        try:
            self.connection = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=True # 自動解碼 bytes 為 string
            )
            # 測試連線是否成功
            self.connection.ping()
            print("Redis 連線成功。")
        except Exception as e:
            print(f"建立 Redis 連線時發生未預期錯誤: {e}")
            self.connection = None
            raise RuntimeError(f"建立 Redis 連線時發生錯誤: {e}") from e

    def get_connection(self) -> Optional[redis.Redis]:
        """獲取 Redis 連線實例"""
        return self.connection

    def close(self):
        """關閉 Redis 連線"""
        if self.connection:
            try:
                self.connection.close()
                print("Redis 連線關閉。")
                self.connection = None
            except Exception as e:
                print(f"關閉 Redis 連線時發生錯誤: {e}")

# --- 建立 RedisManager 實例 ---
redis_manager = RedisManager(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

try:
    redis_manager.connect() # 在模組載入時就建立連線
except RuntimeError as e:
    print(f"無法在啟動時建立 Redis 連線: {e}")
    # 此處 redis_manager.connection 會是 None

# --- 提供 Redis 連線的依賴函數 (使用 RedisManager) ---
def get_redis() -> Generator[Optional[redis.Redis], None, None]:
    """FastAPI 依賴項，從 RedisManager 獲取 Redis 連線實例。"""
    print("--- get_redis START ---")
    conn = redis_manager.get_connection()
    if conn is None:
        print("警告: Redis 連線不可用 (可能是啟動失敗)。")
        yield None # 返回 None，讓路由函數處理
    else:
        try:
            yield conn # 提供可用的連線

        except redis.exceptions.RedisError as e:
            print(f"get_redis 中 Redis 操作錯誤: {e}")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"快取服務錯誤: {e}") from e
        finally:
            pass

if __name__ == "__main__":
    get_redis()