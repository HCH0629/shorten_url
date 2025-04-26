import os
from dotenv import load_dotenv
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, Session
from fastapi import HTTPException, status

# --- 載入環境變數 ---
load_dotenv()

# --- 建立 SQLite 資料庫連線 URL ---
# 使用環境變數或預設值設定 SQLite 資料庫檔案路徑
DATABASE_PATH = os.getenv('SQLITE_DATABASE_PATH', 'urls.db')
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
print(f"資料庫連線 URL: {DATABASE_URL}")


# --- 建立 SQLAlchemy 引擎 ---
try:
    engine: Engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True, # 先執行一個簡單的 SQL 查詢，檢查連線是否有效
        connect_args={"check_same_thread": False},  # 允許在不同執行緒中使用同一連線
        pool_size=10,  # 池中的連線數量
        max_overflow=20,  # 當池已滿時，最多能夠打開多少額外的連線
        pool_timeout=30,  # 每次請求連線的超時時間
    )
    print("資料庫引擎建立成功。")
except Exception as e:
    print(f"建立資料庫引擎時發生錯誤: {e}")
    raise RuntimeError("無法建立資料庫引擎") from e


# --- 建立 Session ---
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# --- FastAPI 資料庫連線 ---
def get_db_conn() -> Generator[Session, None, None]:
    """
    FastAPI 資料庫連線，最後會將 session 關閉
    """
    db: Session | None = None
    try:
        # 從 SessionLocal 創建一個 Session 實例
        db = SessionLocal()
        # print(f"取得連線: {db}")  # 除錯訊息
        yield db  # 將連線提供給路徑操作函數或其他依賴項

    except SQLAlchemyError as e:
        # print(f"資料庫連線錯誤: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="資料庫連線錯誤"
        )
    
    except Exception as e:
        # print(f"資料庫連線期間發生未預期的錯誤: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="發生內部伺服器錯誤"
        )
    
    finally:
        if db is not None:
            try:
                db.close()  # 將 session 關閉/歸還回連線池
                # print(f"session 已關閉/歸還: {db}")  # 除錯訊息
            except SQLAlchemyError as e:
                print(f"關閉資料庫連線時發生錯誤: {e}")


if __name__ == "__main__":
    # 基本測試
    try:
        
        # 測試連線
        with engine.connect() as conn:
            print("連線成功")

            # 執行簡單查詢
            sql_query = text("SELECT 1")
            result = conn.execute(sql_query)
            print(f"測試查詢結果: {result.scalar_one()}")
            
    except Exception as e:
        print(f"測試連線失敗: {e}")