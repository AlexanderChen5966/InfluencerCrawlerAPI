# Influencer Crawler API + n8n 自動化工作流 (Zeabur 部署)

## 📖 專案簡介

`influencer-crawler-api` 是一個基於 **FastAPI** 的爬蟲 API 系統，用於抓取 **Instagram (IG)** 和 **Facebook (FB)** 網紅資料（如粉絲數、貼文數）。  
搭配 **n8n 自動化工作流**（同樣部署在 **Zeabur**），實現每日自動抓取並寫入 Zeabur 的 **PostgreSQL 資料庫**。

---
## n8n 自動化工作流運作圖示

![n8n自動化工作流運作圖示](images/n8n運作影片.gif)


---

## 🌐 系統架構

```
Zeabur
│
├── n8n (自動化工作流)
│    └── 呼叫 FastAPI `/crawl` API
│
├── FastAPI (influencer-crawler-api)
│    └── 爬取 IG/FB 並寫入 DB
│
└── PostgreSQL (Zeabur 服務)
```

![n8n自動化工作流雛形圖示](images/n8n節點雛形.jpg)


---

## 🚀 安裝與啟動 (本地測試)

### 1. 安裝套件
```bash
pip install -r requirements.txt
playwright install
```

### 2. 啟動 FastAPI 伺服器
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

啟動後可訪問：  
`http://localhost:8000/docs` (Swagger UI)

---

## ⚙️ Zeabur 環境變數設定

1. 登入 [Zeabur](https://zeabur.com) 控制台。
2. 在 `FastAPI` 服務及 `n8n` 服務中，新增以下環境變數：
```env
IG_USERNAME=你的IG帳號
IG_PASSWORD=你的IG密碼
FB_EMAIL=你的FB帳號
FB_PASSWORD=你的FB密碼
LOCAL_DB_URL=postgresql://zeabur_admin:你的密碼@postgresql-xxxx.zeabur.app:5432/postgres
TZ=Asia/Taipei
```
3. 儲存後重新部署。

---

## 📡 API 使用

### **POST /crawl**

請求格式：
```json
{
  "influencer_id": "Joeman",
  "platform": "IG",
  "url": "https://www.instagram.com/joemanweng/"
}
```

回應範例：
```json
{
  "status": "success",
  "platform": "IG",
  "influencer": "Joeman",
  "followers": 890000,
  "posts": 430
}
```

---

## 🗄 資料庫設計 (Zeabur PostgreSQL)

### `ig_stats` (Instagram)
| 欄位 | 型別 | 說明 |
|------|------|------|
| influencer_id | VARCHAR | 網紅名稱 |
| username | VARCHAR | IG 帳號 |
| url | TEXT | IG 網址 |
| followers | INT | 粉絲數 |
| following | INT | 追蹤數 |
| posts | INT | 貼文數 |
| date | DATE | 抓取日期 |

### `fb_stats` (Facebook)
| 欄位 | 型別 | 說明 |
|------|------|------|
| influencer_id | VARCHAR | 網紅名稱 |
| page_name | VARCHAR | 粉專名稱 |
| url | TEXT | FB 粉專網址 |
| followers | INT | 追蹤人數 |
| date | DATE | 抓取日期 |

---

## ⚡ n8n 自動化流程 (Zeabur)

![](images/n8n節點雛形.jpg)

### 節點設計：
1. **Schedule Trigger**  
   每天固定時間觸發流程（`TZ=Asia/Taipei` 已設定在 Zeabur）。
2. **Function (或 Edit Fields)**  
   建立網紅名單（`influencer_id`、`platform`、`url`）。
3. **Loop Over Items**  
   逐筆呼叫 API。
4. **HTTP Request**  
   呼叫 `https://你的FastAPI服務.zeabur.app/crawl`。
5. **Replace Me**  
   預留錯誤通知或結果處理。

---

## ⏰ 每日執行設定

- **n8n**  
  在 `Schedule Trigger` 節點設定：  
  - Mode = `Every Day`
  - Time = `08:00`
- Zeabur 預設為 UTC 時間，因此需設定：
  ```
  TZ=Asia/Taipei
  ```

---
