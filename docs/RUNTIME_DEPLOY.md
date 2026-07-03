# Runtime / 部署 / Push 規則

## Bot Runtime — 正式決定用 Vercel webhook（2026-07-01）

**真正接單嘅係 Vercel webhook：**
- Telegram 一個 bot 只能夠揀 **webhook** 或者 **long-polling（`getUpdates`）** 其中一種，唔可以同時用
- Webhook 設定指去 `https://sales-trainer-wheat.vercel.app/api/webhook`（`api/webhook.py`）—— 呢個係實際回覆緊 Telegram 用戶嘅版本
- **`bot_listener.py` 本地 daemon 已經停用**：LaunchAgent 由 `~/Library/LaunchAgents/com.salestrainer.bot.plist` 搬咗去 `~/Library/LaunchAgents/_disabled/com.salestrainer.bot.plist.disabled`（冇刪，想翻用就搬返去 + `launchctl load`），確保唔會下次開機自動翻生同 Telegram 打交
- **改嘢一律改 `api/webhook.py`**，`bot_listener.py` 淨係留低做 code 參考／將來想切換返 local 時嘅底稿，唔會再自動運行

## 部署 / 更新流程（Vercel）

- Push 去 GitHub main branch → Vercel 自動 rebuild + redeploy `api/webhook.py`
- **指令 menu（Telegram 個 `/` 快捷鍵清單）唔會自動更新** —— 淨係喺手動探訪 `https://sales-trainer-wheat.vercel.app/api/set_webhook` 先會執行 `setMyCommands`。**每次加/改 bot 指令之後，記得探訪呢個 URL 一次**，唔係 Telegram 個 menu 會同 code 唔同步（2026-07-01 加咗 `/negotiate` `/debrief` `/mbti` 但 menu 舊咗成日冇人發現）

## GitHub Push

- 用 GitHub Git Data API 直接 push，唔用 git CLI（避免 lock file 問題）
- 指令：`python3 github_push.py "<commit message>"`
- `.env` 需要：`GITHUB_TOKEN` + `GITHUB_REPO=auzistephanie/sales-trainer`
- **規則：每次改完檔案，Claude 必須自動 push，唔需要 Stephanie 另外要求**
- commit message 要具體描述改動（唔好用 "update files"）
- ⚠️ **一次 run = 一個 commit**（2026-07-02 重寫）：舊版用 Contents API 逐個檔案 PUT，一次 push 整十幾個 commit → 十幾個 Vercel deployment，2026-07-02 爆咗 Vercel 免費 plan「100 deployments/日」上限（`api-deployments-free-per-day`）。新版用 Git Data API 砌一個 tree + 一個 commit，無論改幾多檔案都只觸發一次 build。**唔好喺短時間內連環 push**，慳返 deployment 額度

## ⚠️ requirements.txt 唔可以有 streamlit（Vercel 500MB 限制）

- `requirements.txt` 由 **Vercel（serverless functions）同 Streamlit Cloud（求職 CRM 網頁）共用**
- **streamlit（連 pandas/pyarrow ~200MB+）只有 `job_crm.py` + `pages/` 用，`api/` 完全冇 import**
- Vercel 每個 function 都會 bundle 全份 requirements。加咗 `api/daily_check.py`（第二個 function）之後，兩個 function 各揹一份 streamlit → **541MB 爆咗 Vercel「500MB max function size」→ build failed**（2026-07-03）
- 解決：由 `requirements.txt` **移除 streamlit**。Streamlit Community Cloud 會自己 auto-provision `streamlit`（實測 log 見到 `+ streamlit==1.58.0`），網頁照跑；Vercel bundle 即刻跌返 500MB 以下
- **規則：唔好將淨係 Streamlit 用嘅重 dependency（streamlit/pandas/pyarrow…）加入 `requirements.txt`**，否則會再爆 Vercel

## 環境變數（`.env` + Vercel dashboard）

`DEEPSEEK_API_KEY` · `UPSTASH_REDIS_REST_URL` · `UPSTASH_REDIS_REST_TOKEN` · `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID` · `GITHUB_TOKEN` · `GITHUB_REPO` · `JINA_API_KEY`（optional，抓取加速）· `GOOGLE_CREDENTIALS` + `GOOGLE_DRIVE_FOLDER_ID`（optional，CV 上 Drive）
