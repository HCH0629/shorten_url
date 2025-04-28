
# 短網址 REST API

這個專案實現了一個簡單的短網址服務，包含兩個 RESTful HTTP API：一個用來創建短網址，另一個用來處理重定向。它是使用 Python (Fastapi) 開發的，數據存儲在 SQLite 中，包含速率限制、URL 驗證和自動過期功能。
整個應用程式使用 Docker 進行容器化。

## 特性

* **創建短網址**：為任何有效的原始 URL 生成一個唯一的短代碼。
* **重定向**：訪問短網址會將用戶重定向到原始 URL。
* **URL 驗證**：確保輸入的 URL 是有效的並且長度(2048 字元)在限制範圍內。
* **過期功能**：短網址在一個可配置的時間內過期（默認：30 天）。
* **速率限制**：保護 API 防止濫用。
* **容器化**：使用 Docker 方便構建和運行。
* **RESTful 設計**：遵循 REST 原則，使用適當的 HTTP 方法和狀態碼。

## API 文檔

該 API 服務於容器運行的主機根目錄下提供（例如：`http://127.0.0.1:8000`）。

---

### 1. 創建短網址

創建一個新的短網址映射。

* **URL**：`/create_short_url`
* **方法**：`POST`
* **速率限制**：每分鐘最多 60 次請求
* **請求主體**：JSON 
    ```json
    {
        "original_url": "https://example.com/"
    }
    ```
    * `original_url`（字串，必需）：要縮短的 URL。必須是有效的 URL 格式，最大長度為 2048 個字符。長度包含了 `http://` 或 `https://`，其中如果最後沒有給 `/` 它會自動補齊 。
* **透過 PODMAN**：

* **成功響應（201 Created）**：
    ```json
    {
    "short_url": "http://53e819fa",
    "expiration_date": "2025-05-25T10:20:50.424876Z",
    "success": true,
    "reason": null
    }
    ```
    * `short_url`：生成的完整短網址。
    * `expiration_date`：短網址的過期時間戳 (UTC+0)。
    * `success`：表示操作是否成功的布林值。

* **錯誤響應**：
    * `400 Bad Request`：建立 URL 時發生內部錯誤。
      ```json
      {
        "success": false,
        "reason": "建立 URL 時發生內部錯誤" // 或其他具體原因
      }
      ```
    * `422 Unprocessable Entity`：輸入無效（URL 過長、URL 格式錯誤）。
      ```json
      {
        "success": false,
        "reason": "IValue error, URL 過長 (最多 MAX_URL_LENGTH 個字元)" // 或其他具體原因
      }
      ```
    * `429 Too Many Requests`：超過速率限制。
      ```json
      {
        "success": false,
        "reason": "Rate limit exceeded: 60 per 1 minute"
      }
      ```
    * `500 Internal Server Error`：查詢過程中的伺服器端問題。
      ```json
      {
        "success": false,
        "reason": "Internal server error during URL creation"
      }
      ```

---

### 2. 重定向使用短網址

根據短代碼將用戶重定向到原始 URL。

* **URL**：`/redirect_to_original`（例如，`http://73fad922`）
* **方法**：`GET`
* **速率限制**：每分鐘最多 60 次請求
* **行為**：
    * 如果 `short_url` 有效且未過期，伺服器會返回 HTTP `302 Found` 重定向到 `original_url`。
    * 瀏覽器會自動跟隨這個重定向。

* **錯誤響應**：
    * `404 Not Found`：`short_url` 不存在。
      ```json
      // 如果通過 API 客戶端訪問，返回的響應體（瀏覽器會顯示標準的 404 頁面）
      {
        "success": false,
        "reason": "Short URL not found"
      }
      ```
    * `410 GONE`：`short_url` 已過期。
      ```json
      // 如果通過 API 客戶端訪問，返回的響應體（瀏覽器會顯示標準的 410 頁面）
      {
        "success": false,
        "reason": "Short URL was expired"
      }
      ```
    * `429 Too Many Requests`：超過速率限制。
      ```json
      {
        "success": false,
        "reason": "Rate limit exceeded: 60 per 1 minute" 
      }
      ```
    * `500 Internal Server Error`：查詢過程中的伺服器端問題。
      ```json
      {
        "success": false,
        "reason": "Internal server error"
      }
      ```

---
## 使用指南：使用 Docker Compose 運行

### 前提條件：

* 您的系統已經安裝 Docker 和 Docker Compose。如果尚未安裝，可以參考 [Docker 安裝指南](https://docs.docker.com/get-docker/) 和 [Docker Compose 安裝指南](https://docs.docker.com/compose/install/)。

### 步驟：

1. **下載專案並進入專案目錄**：
    ```bash
    git clone https://github.com/HCH0629/shorten_url
    cd shorturl-api
    ```

2. **啟動 Docker Compose**：
    使用 Docker Compose 來啟動所有必要的服務，包括應用程式和資料庫。
    ```bash
    docker-compose up -d
    ```
    * **說明**：
        * `docker-compose up -d`：在背景模式下啟動所有服務。
        * `-d`：讓容器在後台運行。

3. **檢查容器狀態**：
    確保所有服務運行正常。
    ```bash
    docker-compose ps
    ```

4. **訪問服務**：
    * 服務將在 `http://127.0.0.1:8000` 提供。
    * 您可以在瀏覽器中進行 API 測試，或者使用 `curl` 或 Postman 進行交互。

    ```bash
    curl -X 'POST' \
        'http://127.0.0.1:8000/create_short_url' \
        -H 'accept: application/json' \
        -H 'Content-Type: application/json' \
        -d '{
        "original_url": "https://example.com/"
        }'
    ```

5. **查看日誌**：
    查看容器的運行日誌，檢查是否有任何錯誤或警告。
    ```bash
    docker-compose logs -f
    ```

6. **停止服務**：
    當您不再需要服務時，使用以下命令停止所有服務：
    ```bash
    docker-compose down
    ```

### 配置文件

在專案根目錄下，您應該能看到以下配置文件：

* **docker-compose.yml**：此文件定義了服務、網絡、資料庫卷等配置。
---

## 使用指南：使用 Docker 運行

按照以下步驟使用 Docker 構建並運行短網址 API 服務。

**前提條件**：

* 您的系統上已安裝並正在執行 Docker。(如為 Windows 可直接安裝 Docker Desktop)

**步驟**：
1.  **下載 Docker Images 並啟動**：
    * 執行以下命令來啟動容器：
        ```bash
        docker run -d -p 8000:8000 --name shorturl-app \
                   -v redirt_url:/redirt_url \
                   danielhch/redirt_url:latest
        ```
    * **說明**：
        * `docker run`：創建並啟動容器。
        * `-d`：將容器運行在背景。
        * `-p 8000:8000`：將主機的 8000 端口映射到容器的 8000 端口（這是 Uvicorn 監聽的端口）。如果 8000 端口已經被使用，可以更改主機端口（例如，`-p 8001:8000`）。
        * `--name shorturl-app`：為容器分配一個名稱（名稱可以隨意取）。
        * `-v redirt_url:/redirt_url`：**（持久化數據）** 這將創建或使用一個名為 `redirt_url` 的 Docker 命名卷，並將其掛載到容器內的 `/redirt_url` 目錄。SQLite 數據庫文件 (`urls.db`) 存儲在 `/redirt_url` 目錄中，這樣即使停止並移除容器，數據仍然可以持久化。Docker 管理該卷。
        * `danielhch/redirt_url:latest`：此應用程式的名稱 (latest 為版本號，其他版本也可以使用)

4.  **訪問服務**：
    * 現在 API 服務已經運行，可以訪問 `http://127.0.0.1:8000`。
    * **API 文檔**：`http://127.0.0.1:8000/docs` 可查看此 API 相關資訊。
    * **創建短網址**：向 `http://127.0.0.1:8000/create_short_url` 發送 `POST` 請求，並附上 JSON 載荷（使用 `curl`或 Postman 其他熟悉的工具）。
        ```bash
        curl -X 'POST' \
            'http://127.0.0.1:8888/url/create_short_url' \
            -H 'accept: application/json' \
            -H 'Content-Type: application/json' \
            -d '{
            "original_url": "https://example.com/"
          }'
        ```
    * **使用短網址**：如果上面的請求返回 `{"short_url": "http://127.0.0.1:8000/qwerasdf", ...}`，可以在瀏覽器中打開 `http://127.0.0.1:8000/qwerasdf`，並將會重定向到 `https://example.com`。

5.  **查看日誌**：
    * 要查看應用程式日誌（請求、錯誤等）：
        ```bash
        docker logs shorturl-app
        ```
    * 滾動查看日誌：
        ```bash
        docker logs -f shorturl-app
        ```

6.  **停止容器**：
    * 停止正在運行的容器：
        ```bash
        docker stop shorturl-app
        ```

7.  **重啟容器**：
    * 重啟已停止的容器（它會重新使用 `redirt_url` 卷）：
        ```bash
        docker start shorturl-app
        ```

8.  **移除容器**：
    * 如果需要移除容器（請先停止容器）：
        ```bash
        docker rm shorturl-app
        ```
    * *注意：* 移除容器不會刪除命名卷（`redirt_url`）。數據仍然安全。如果不再需要數據，可以刪除該卷：`docker volume rm redirt_url`。

---


### 本機執行語法 (需先安裝相關套件和環境)
  ```bash
  uvicorn api.main:app --host 127.0.0.1 --port 8888
  ```

### 基本啟動 container
  ```bash
  docker run -d -p 8000:8000 redirt_url
  ```

### 簡單壓測 
* 測試在 60 秒後自動停止
  ```bash 
  locust -f locustfile.py --headless -u 10 -r 1 --run-time 60s --host http://127.0.0.1:8000 --html report
  ```
