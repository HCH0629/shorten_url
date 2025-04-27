import os
from dotenv import load_dotenv
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi import HTTPException, status

# --- 載入環境變數 ---
load_dotenv()

# --- 建立 SQLite 資料庫連線 URL ---
# 使用環境變數或預設值設定 SQLite 資料庫檔案路徑
DATABASE_PATH = os.getenv('SQLITE_DATABASE_PATH', 'urls.db')
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
print(f"資料庫連線 URL: {DATABASE_URL}")



# --- SQLiteManager 類 ---
class SQLiteManager:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine: Engine = None
        self.SessionLocal = None

    def create_engine(self):
        """建立 SQLAlchemy 引擎"""
        try:
            self.engine = create_engine(
                self.database_url,
                pool_pre_ping=True,  # 先執行簡單的 SQL 查詢，檢查連線是否有效
                connect_args={"check_same_thread": False},  # 允許在不同執行緒中使用同一連線
                pool_size=10,  # 池中的連線數量
                max_overflow=20,  # 當池已滿時，最多能夠打開多少額外的連線
                pool_timeout=30,  # 每次請求連線的超時時間
            )
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            print("資料庫引擎建立成功")
        except Exception as e:
            print(f"建立資料庫引擎時發生錯誤: {e}")
            raise RuntimeError("無法建立資料庫引擎") from e


    
    def test_connection(self):
        """測試資料庫連線"""
        try:
            with self.engine.connect() as conn:
                print("連線成功")
                sql_query = text("SELECT 1")
                result = conn.execute(sql_query)
                print(f"測試查詢結果: {result.scalar_one()}")
        except Exception as e:
            print(f"測試連線失敗: {e}")



db_manager = SQLiteManager(DATABASE_URL)

try:
    db_manager.create_engine() # 載入 class 建立引擎和 SessionLocal
except RuntimeError as e:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"無法在啟動時建立資料庫引擎: {e}")


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依賴項，直接從 db_manager 取得 SessionLocal 並管理 Session"""
    if db_manager.engine is None or db_manager.SessionLocal is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="資料庫未初始化或初始化失敗"
        )

    db: Session | None = None
    try:
        db = db_manager.SessionLocal()
        yield db # 給 api 使用
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"DB Session Error: {e}")
    
    finally:
        if db is not None:
            try:
                db.close()              
            except Exception as e: # 檢查關閉時的錯誤
                return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"DB Session Error: {e}")

# --- 初始化資料庫 ---
def init_db():
    """使用 db_manager 的引擎初始化資料庫"""
    if db_manager.engine is None:
        print("引擎未初始化，無法執行 init_db")
        return
    try:
        with db_manager.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS urls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    short_url TEXT UNIQUE NOT NULL,
                    original_url TEXT NOT NULL,
                    creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expiration_date TIMESTAMP NOT NULL 
                )
            """))
            conn.execute(text('CREATE INDEX IF NOT EXISTS idx_short_url ON urls (short_url)')) 
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_expiration_date ON urls (expiration_date)"))
            conn.commit()
            print("資料庫已初始化。")
    except Exception as e:
        print(f"初始化資料庫時發生錯誤: {e}")
        raise


# 使用方式
if __name__ == "__main__":
    db_manager = SQLiteManager(DATABASE_URL)
    db_manager.create_engine()  # 建立引擎
    db_manager.test_connection()  # 測試連線