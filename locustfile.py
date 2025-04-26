# import uuid 如果需要產生的話再打開
from locust import HttpUser, task, between
from urllib.parse import quote

class UrlShorteningUser(HttpUser):
    # 在每個任務之間等待的時間（這裡設定為 1 到 3 秒之間的隨機時間）
    wait_time = between(1, 3)

    @task(1)  # 設置此任務的權重（1 代表該任務的執行頻率，2 代表該任務會被執行得更多次）
    def create_short_url(self):
        original_url = "https://www.example.com/" 
        response = self.client.post("/url/create_short_url", json={"original_url": original_url})

        # 驗證回應
        if response.status_code == 201:
            print(f"Created short URL: {response.json()['short_url']}")
        else:
            print(f"Failed to create short URL: {response.status_code}")

    @task(1)  # 設置此任務的權重
    def redirect_to_original(self):

        # 解碼 URL
        # 手動將 // 替換為 %2F%2F
        # short_url_with_encoded_slashes = short_url.replace(':', '%3A')
        # decoded_short_url = short_url_with_encoded_slashes.replace('//', '%2F%2F')

        decoded_short_url='http%3A%2F%2F53a35434'
        response = self.client.get(f"/url/redirect_to_original?short_url={decoded_short_url}")

        # 驗證回應
        if response.status_code == 302:
            print(f"Redirected to: {response.headers['Location']}")
        else:
            print(f"Failed to redirect: {response.status_code}")
