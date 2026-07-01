# CLAUDE.md — AI 面試教練 Bot

AI 生成面試場景，評估用戶回答，追蹤掌握進度，根據 MBTI 提供個人化 coaching。DeepSeek-V3 生成，Upstash Redis 持久化，Telegram Bot 互動。

## 核心檔案
- `interview_trainer.py` — 題型池、MBTI coaching、場景生成、AI 評估、CV/薪酬/ATS/談判/覆盤所有 AI 函數
- `api/webhook.py` — **實際接單嘅版本**（Vercel webhook，見下面「Bot Runtime」）
- `bot_listener.py` — 本地 long-polling 版本，代碼結構同 `api/webhook.py` 盡量同步，但因為 Telegram webhook 已設定，實際上冇喺接單（見下面）
- `mbti_checker.py` — MBTI 20題檢測（`/mbti`）
- `utils.py` — Redis I/O、Telegram 發送
- `.env` — API keys（唔 commit）
- `github_push.py` — 用 GitHub API push（PAT in .env）：`python3 github_push.py "<commit message>"`

## 面試題型（10 種）
行為題 STAR、優缺點、職涯規劃、壓力處理、團隊衝突、領導力、為何揀我哋、薪酬談判、情境判斷、技術知識

每種有 `weight`（出現頻率）+ `example_q`（示範問題）+ `tip`（答題技巧）。

## 場景 DNA
`pick_scenario_dna()` 隨機組合：題型 × 面試官性格 × 面試輪次 × 行業，WINDOW=4 防重複。
- **面試官性格（6種）**：友善HR、冷峻技術面試官、壓力測試型、C-level高管、Panel多人面試、沉默考驗型
- **面試輪次（6種）**：電話初篩、HR面試、技術面試、Case Study、Management Round、Offer談判
- **行業（14種）**：金融/投行、科技/IT、市場/廣告、管理諮詢、零售/酒店、初創、醫療、法律、HR、教育、物流、地產、傳媒、政府/NGO

## MBTI Coaching（16種）
`MBTI_COACHING` dict，每種有：
- `strengths`：面試優勢
- `watch_out`：常見盲點
- `tip`：針對性建議

`get_mbti_context(mbti)` 生成 prompt context，inject 入 evaluate_response。

## 難度系統
- 初級：面試官友善，問題直接
- 中級：有追問，部分問題有陷阱
- 高級：面試官強硬，質疑答案

## Bot 指令
`/addjob` 新增申請記錄 · `/listjobs` 查看所有申請+狀態 · `/practice [難度]` · `/drill` 針對題型 · `/stats` 進度報告 · `/streak` 連續天數 · `/tip` 今日技巧 · `/review` 貼真實面試對話分析 · `/negotiate` 薪酬談判 role-play · `/debrief` 面試後覆盤分析 · `/setup` 設定職位+MBTI · `/mystatus` · `/mbti` MBTI 檢測 · `/help`

## Job Application Tracker（新功能 2026-06-29）
`load_jobs() / save_jobs()` in utils.py → Redis key `interview_jobs`（list of job objects）

每個 job object 欄位：`id, company, role, jd, link, applied_date, status`

Status 值：Applied / Phone Screen / 1st Interview / 2nd Interview / Offer / Rejected

`/addjob` flow（addjob session states）：
1. `addjob_company` → 輸入公司名
2. `addjob_role` → 輸入職位
3. `addjob_jd` → 貼 JD 或 /skip
4. `addjob_link` → 貼 link 或 /skip → 自動 save job，status = Applied

`/listjobs` → 顯示所有 jobs + inline keyboard（Questions / Tips / Practice / Update Status）

Inline callbacks：`job_q_{id}` / `job_tips_{id}` / `job_practice_{id}` / `job_updatestatus_{id}` / `job_status_{id}_{status}`

AI functions in interview_trainer.py：`generate_job_questions(job)` / `generate_job_tips(job)`

## 求職功能組（新功能 2026-07-01）

**CV Health Score**（`calculate_cv_health(cv_text)`，本地計算，唔需要 AI）
- Onboarding 上傳 CV 後即時顯示，4 個維度各 25 分：結構完整性／量化成就／Action Verbs／關鍵詞豐富度
- `format_cv_health_message(health)` 砌 Telegram 訊息
- 結果存入 `profile["cv_health_score"]`，做其他功能嘅 baseline

**HK Salary Benchmark**（`generate_salary_benchmark(role, expected_salary, industry)`，DeepSeek）
- Onboarding 流程：CV upload / 手動輸入職位 → 問月薪期望（`parse_salary_input()` 解析 "38k"/"$38,000" 等格式）→ 顯示市場薪酬參考 → 入 MBTI 步
- 結果存 `profile["expected_salary"]` + `profile["salary_currency"]`（固定 "HKD"）

**ATS Match Score**（`calculate_ats_score(jd_text, cv_text)`，DeepSeek 抽 keyword + 本地比對）
- Tailored CV 生成完之後自動觸發（`handle_job_tailored_cv` / `handle_jd_tailored_cv` / `_auto_add_job_from_url`）
- `format_ats_message(ats, cv_health_score)` 計 delta（同 onboarding 嘅 cv_health_score 比較）

**薪酬談判 Negotiate**（`/negotiate`）
- State：`negotiate_start`（等 offer details）→ `negotiate_session`（每回合 `generate_negotiate_response()` 生成 HR 回應 + 評分）
- 「結束」或 `/negotiate` → `generate_negotiate_summary(history)` 總結
- `/listjobs` 每個 job 有 `🤝 Negotiate` 按鈕（`job_negotiate_{id}`），跳過輸入 offer details 步

**面試覆盤 Debrief**（`/debrief`）
- State：`debrief_job_select`（揀已追蹤嘅工 / 跳過）→ `debrief_input`（描述面試過程）
- `generate_debrief(job_info, debrief_text)` 輸出評級 + 強項 + 改善點
- 如有連結 job，分析完自動跳出 `handle_update_status_menu()` 更新狀態

## 狀態機
Redis key `interview_session`（`load_session()`/`save_session()` in utils.py，TTL 600s）：
- `state: "waiting_response"` + `scenario` → 用戶下一條訊息視為練習回應
- `state: "waiting_review"` → 用戶下一條訊息視為面試對話記錄
- `state: "negotiate_start"` → 下一條訊息視為 offer details
- `state: "negotiate_session"` + `offer_details`/`round_num`/`history` → 談判進行中
- `state: "debrief_job_select"` → 等揀 job（或跳過）
- `state: "debrief_input"` + `job_info` → 等面試描述
- 收到回應 → DeepSeek 評估 → clear session

Redis key `interview_setup_session`（onboarding 專用，另一個獨立 session）：
- `state: "setup_cv_upload"` → 等 CV 上傳
- `state: "setup_industry_custom"` / `"setup_jobtitle"` → 手動輸入行業／職位
- `state: "setup_salary"` → 等月薪期望輸入
- `state: "setup_mbti"` → 等揀 MBTI

## Setup Flow
`/start` 提供兩條路：
- **CV 上傳**：解析 resume → 自動填 job_title/industry/education 等 + CV Health Score → 問月薪期望 → Salary Benchmark → MBTI
- **手動輸入**：揀行業（14種 inline keyboard / 自定）→ 打目標職位（文字輸入）→ 問月薪期望 → Salary Benchmark → 揀 MBTI（16種 4×4 keyboard / 跳過）

## 評分系統（1-4分）
1. 方向錯或負面印象
2. 方向對但答法唔夠有力
3. 不錯，有改善空間
4. 出色，清晰有說服力

每種題型獨立記分，`/stats` 顯示掌握度 %。

## 變現機制
- 免費 5 次 session，之後提示升級（$68/月 Premium）
- 每日 bonus：免費 1 次額外練習
- `FREE_SESSION_LIMIT = 5`（bot_listener.py）

## Bot Runtime — 正式決定用 Vercel webhook（2026-07-01）

**真正接單嘅係 Vercel webhook：**
- Telegram 一個 bot 只能夠揀 **webhook** 或者 **long-polling（`getUpdates`）** 其中一種，唔可以同時用
- Webhook 設定指去 `https://sales-trainer-wheat.vercel.app/api/webhook`（`api/webhook.py`）—— 呢個係實際回覆緊 Telegram 用戶嘅版本
- **`bot_listener.py` 本地 daemon 已經停用**：LaunchAgent 由 `~/Library/LaunchAgents/com.salestrainer.bot.plist` 搬咗去 `~/Library/LaunchAgents/_disabled/com.salestrainer.bot.plist.disabled`（冇刪，想翻用就搬返去 + `launchctl load`），確保唔會下次開機自動翻生同 Telegram 打交
- **改嘢一律改 `api/webhook.py`**，`bot_listener.py` 淨係留低做 code 參考／將來想切換返 local 時嘅底稿，唔會再自動運行

**部署 / 更新流程（Vercel）：**
- Push 去 GitHub main branch → Vercel 自動 rebuild + redeploy `api/webhook.py`
- **指令 menu（Telegram 個 `/` 快捷鍵清單）唔會自動更新** —— 淨係喺手動探訪 `https://sales-trainer-wheat.vercel.app/api/set_webhook` 先會執行 `setMyCommands`。**每次加/改 bot 指令之後，記得探訪呢個 URL 一次**，唔係 Telegram 個 menu 會同 code 唔同步（好似 2026-07-01 噉，加咗 `/negotiate` `/debrief` `/mbti` 但 menu 舊咗成日都冇人發現）

## GitHub Push
- 用 GitHub API 直接 push，唔用 git CLI（避免 lock file 問題）
- 指令：`python3 github_push.py "<commit message>"`
- `.env` 需要：`GITHUB_TOKEN` + `GITHUB_REPO=auzistephanie/sales-trainer`
- **規則：每次改完檔案，Claude 必須自動 push，唔需要 Stephanie 另外要求**
- commit message 要具體描述改動（唔好用 "update files"）

## 改版歷史
- **2026-06-23**：初版創建，銷售話術訓練，10 種拒絕類型
- **2026-06-28**：重大 pivot — 改為 AI 面試教練，新增 14 種行業、MBTI 16種 coaching、變現 credit 系統
- **2026-06-29**：新增 Job Application Tracker — /addjob, /listjobs, AI 面試問題、Key Tips、status tracking（Applied/Phone Screen/Interview/Offer/Rejected）
- **2026-07-01**：CV Health Score、HK Salary Benchmark onboarding、ATS Match Score（Tailored CV 生成後自動顯示）、`/negotiate` 薪酬談判 role-play、`/debrief` 面試後覆盤分析。`bot_listener.py` 同步補齊 CV 上傳基建（之前得 `api/webhook.py` 有）。詳見 `FEATURE_SPEC.md`
- **2026-07-01**：發現 `bot_listener.py`（local polling）同 Vercel webhook 一直喺度衝突 —— Telegram webhook 已設定，真正接單嘅係 `api/webhook.py`，`bot_listener.py` 嘅 `getUpdates` 一直畀 Telegram reset。順手發現指令 menu 淨係喺手動探訪 `/api/set_webhook` 先會更新，補做咗一次同步
- **2026-07-01**：正式決定唔用 local —— 停咗 `bot_listener.py` 嘅 LaunchAgent（搬去 `_disabled/`），Vercel webhook 做唯一 runtime
- **2026-07-01**：停用 5 次免費練習限制（Stephanie 自用）—— `check_free_limit()` 改為直接 return True，`api/webhook.py` + `bot_listener.py` 同步；`FREE_SESSION_LIMIT`/`UPGRADE_MSG` 同舊 logic 留底註解，日後想開返俾其他用戶隨時復原
- **2026-07-02**：修 JobsDB 抓取失敗 —— 根因係 `fetch_jd_via_jina()`（`api/webhook.py`）`X-No-Cache:true`（強制慢 render）+ `timeout=15`（JobsDB 冷 render 成日過 15s，實測有條要 16.2s）。改為移除 X-No-Cache、`X-Return-Format=markdown`、`timeout=45`、加一次 retry、支援 optional `JINA_API_KEY`（有就用，加速 16.2s→1.5s + 鬆 rate limit）。⚠️ **Vercel 側要喺 dashboard 加環境變數 `JINA_API_KEY` 先生效**（`.env` 只影響 local）
- **2026-07-02**：升級 CV / Cover Letter 質素 —— `generate_tailored_cv_content()` + `generate_cover_letter_from_jd()`（`interview_trainer.py`）搬入 `tailored-cv-generator` skill 嘅 CRITICAL RULES：唔准作假、鎖公司名/職稱/日期、ATS keyword tailoring、core competencies 6→8-12、bullets 3→4、summary 唔提學歷/語言、temperature 收緊（CV 0.4→0.3、CL 0.6→0.35）
- **2026-07-02**：修 CV/CL 實測 4 個問題 ——
  1. **公司/職位變鬼字**（"Skip to content @ Markdown Content"）：`handle_url_message` 之前用「Jina 頭 10 行最短句」亂估，估中咗 Jina 導航文字。新增 `clean_jd_text()`（清 Title:/URL Source:/Markdown Content:/導航）+ `extract_company_role()`（DeepSeek 乾淨抽 company/role）取代亂估
  2. **Cover letter 太長**：280 字 → ~150 字（2 段，`max_tokens` 900→500），實測 138 字
  3. **Education 印 placeholder**（"not specified in CV"）：prompt 禁止填 placeholder、搵唔到就返 `[]`；`build_cv_docx` 加 `_valid_edu()` filter，冇有效學歷就唔印個 section
  4. **Drive fallback 訊息突兀**：「（Drive 未設定，直接傳送）」→「✅ Tailored CV 已生成！」
  - ⚠️ **Google Drive 上傳**：bot（Vercel）同 CV skill（Cowork）係兩套獨立系統。bot 要上 Drive 須喺 `.env` + Vercel 加 `GOOGLE_CREDENTIALS`（service account JSON）+ `GOOGLE_DRIVE_FOLDER_ID`；未設定就直接 Telegram 傳檔（`utils.upload_to_drive` fallback）
- **2026-07-02**：開通 bot Drive 上傳 —— service account `cv-uploader@just-clover-487108-a0`、folder `1QMBJwdWBknIMVHxIDZs7i7u9oy0SQ6JY`（同 CV skill 共用）。加入 local `.env`（gitignored）。個 folder 係 **Shared Drive**，`utils.upload_to_drive` 之前冇 `supportsAllDrives=True` 會 404 File not found，已補上並實測上傳成功。⚠️ **Vercel dashboard 要自己加 `GOOGLE_CREDENTIALS`（單行 JSON）+ `GOOGLE_DRIVE_FOLDER_ID` 先會喺正式 bot 生效**

## 環境變數（`.env` + Vercel dashboard）
`DEEPSEEK_API_KEY` · `UPSTASH_REDIS_REST_URL` · `UPSTASH_REDIS_REST_TOKEN` · `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID` · `GITHUB_TOKEN` · `GITHUB_REPO` · `JINA_API_KEY`（optional，抓取加速）· `GOOGLE_CREDENTIALS` + `GOOGLE_DRIVE_FOLDER_ID`（optional，CV 上 Drive）
