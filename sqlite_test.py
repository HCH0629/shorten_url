import sqlite3

def test():
    # 連接到數據庫文件（如果不存在會創建）
    conn = sqlite3.connect('urls.db')

    # 創建一個游標對象
    cursor = conn.cursor()

    # 執行 SQL 語句
    cursor.execute('SELECT * FROM urls')
    res = cursor.fetchall()
    print(res)

    # 提交更改並關閉連接
    # conn.commit()
    conn.close()





def check_db_structure():
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    
    # 檢查資料表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='urls'")
    if not cursor.fetchone():
        print("urls 資料表不存在！")
        return
    
    # 獲取資料表結構
    cursor.execute("PRAGMA table_info(urls)")
    columns = cursor.fetchall()
    print("urls 資料表結構:")
    for col in columns:
        print(f"欄位名稱: {col[1]}, 類型: {col[2]}, 是否可為 NULL: {not col[3]}, 預設值: {col[4]}, 是否主鍵: {col[5]}")
    
    # 查看資料表中的數據
    cursor.execute("SELECT * FROM urls")
    rows = cursor.fetchall()
    print(f"\n資料表中的數據 (最多5筆):")
    if rows:
        for row in rows:
            print(row)
    else:
        print("資料表為空")
    
    conn.close()

if __name__ == "__main__":
    check_db_structure()