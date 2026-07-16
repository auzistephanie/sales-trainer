# CLAUDE.md — AI 面試教練 Bot

AI 生成面試場景，評估回答，追蹤進度，MBTI 個人化 coaching。DeepSeek-V3 生成，Upstash Redis 持久化，Telegram Bot 互動。

> 詳細資訊拆咗落 `docs/*.md`，按需 read_file，唔好靠記憶或猜測。

## ✍️ 寫入分流（MANDATORY — 想更新本檔前先讀）

- **改動記錄／開發史** → root `CHANGELOG.md` **頂部**，唔准 append 落本檔；本檔硬上限 **100 行／6KB**
- 本檔只准改：路由行、現行規則本身變咗。完整分流表 → `stephanie-personal/docs/ai-governance/04-MAINTENANCE.md` §0


## 📖 文件讀取規則（MANDATORY）

| 需要嘅資訊 | 讀邊份 |
|---|---|
| Bot Runtime（webhook vs polling）、Vercel 部署、menu sync、GitHub push 規則、requirements.txt 禁 streamlit、環境變數 | `docs/RUNTIME_DEPLOY.md` |
| 題型/場景DNA/MBTI/難度/評分/變現、求職功能組（CV Health/Salary/ATS/Negotiate/Debrief）、Tailored CV v7、狀態機、Setup flow | `docs/FEATURES.md` |
| Job Tracker、Daily Check（followup/週報/自動搵工 scan_new_jobs）、callbacks | `docs/JOBS_DAILY.md` |
| 改版歷史 | `CHANGELOG.md`（唔需要每次讀）|
| AI 調度/驗證/判斷制度（全 repo 共用） | `stephanie-personal/docs/ai-governance/`（見下）|

## 核心檔案

- `interview_trainer.py` — 題型池、MBTI coaching、場景生成、AI 評估、CV/薪酬/ATS/談判/覆盤所有 AI 函數
- `api/webhook.py` — **實際接單嘅版本**（Vercel webhook）；`bot_listener.py` 已停用，只留參考——**改嘢一律改 `api/webhook.py`**
- `api/daily_check.py` — 每日 10:00 HKT 由 cron-job.org 觸發（followup 提醒/週報/自動搵工）
- `mbti_checker.py` — MBTI 20題檢測（`/mbti`）· `utils.py` — Redis I/O、Telegram 發送
- `job_crm.py` + `pages/` — Streamlit 求職 CRM（https://sales-trainer-jatucpwszxyvoq5kpt7bav.streamlit.app）
- `github_push.py` — push 用呢個，唔用 git CLI：`python3 github_push.py "<msg>"`（裝機步驟正本 → `stephanie-personal/docs/PUSH-SETUP.md`）
- `landing.html` — 復古滾動旅程 landing page（Vercel 靜態，`/landing.html`）
- `webapp/` — **真 App（Web/PWA）**：Vite React 前端 + Flask AI API，Google 登入，跨裝置同步。詳見 `docs/APP_SPEC.md`

## Web App（webapp/，Telegram bot 之外嘅獨立產品）

- 由 Telegram bot → 真 app，**加建唔取代**，bot + Redis 照舊運作。
- 前端 `webapp/src/`（Vite React），API `webapp/api/index.py`（Flask，包 `interview_trainer.py`，copy 入 `api/_lib/` + shim `utils.py` 去走 Redis/Telegram）。
- **登入**：Supabase Auth（Google only）。**資料**：Supabase Postgres，共用 project `cmtubaxlniglklmdwlzs`，所有 table `coach_` 前綴 + RLS（`user_id = auth.uid()`）。**AI**：DeepSeek 不變。
- 部署：Vercel **新 project** `interview-coach`（git auto-deploy），Root Directory = `webapp`，env 要 `DEEPSEEK_API_KEY`。**生產網址 https://interview-coach-ten-delta.vercel.app**。schema/API 對照見 `docs/APP_SPEC.md`。
- **首次登入 onboarding**：`coach_profiles.onboarded=false` 觸發 → 可跳過 MBTI（真 20 題）→ 可跳過 upload CV → 設 `onboarded=true`。gate 喺 `App.jsx`，畫面喺 `screens.jsx`（`Onboarding`/`MbtiQuiz`/`CvStep`）。MBTI endpoint 用 `api/_lib/mbti_checker.py`。
- PWA：`webapp/public/` 有 `icon-192/512.png` + `sw.js`（真可安裝）。
- **花磚視覺 + 主題**：Login 用滿版八角星花磚 + 浮紙卡（`screens.jsx` `Login` + `huazhuan.jsx` `StarBg`）；內頁用色塊 header + 菱格花磚帶（`c-head` + `DiamondBand`）。主題引擎 `theme.js`（4 preset `brick/forest/indigo/ochre` + 自選 accent），套色寫 CSS 變數落 `.app` root（`themeVars`），設定喺 Profile `ThemePicker`，存 `coach_profiles.theme` + `custom_accent_color`（照 travel app 套法）。

## Bot 指令

`/addjob` · `/listjobs` · `/practice [難度]` · `/drill` · `/stats` · `/streak` · `/tip` · `/review` · `/negotiate` · `/debrief` · `/setup` · `/mystatus` · `/mbti` · `/help`

（加/改指令後：同步更新上面呢行 + 探訪 set_webhook sync menu，見下面保命規則 1）

## ⚠️ 三條保命規則（詳情 `docs/RUNTIME_DEPLOY.md`）

1. 加/改 bot 指令後**必須探訪** `https://sales-trainer-wheat.vercel.app/api/set_webhook` sync menu
2. **一次 run = 一個 commit**，唔好連環 push（Vercel 100 deployments/日上限）
3. `requirements.txt` **唔准有 streamlit**（Vercel 500MB function 上限）

## AI 制度（全 repo 共用正本）

正本：`stephanie-personal/docs/ai-governance/`（00 診斷 · 01 調度守則 · 02 判斷 rubric · 03 派工模板 · 04 維護協議 · 05 給未來 session 的信）。
決定咗要派 subagent（門檻見 01 §1，唔係乜都派）先讀 01+03；報「完成」前過一次 02 §R2。
⚠️ Session 冇 mount stephanie-personal folder（REQUIRED core folder，唔係 optional）→ **叫 Stephanie 連埋佢**，唔好靜靜地跳過成套制度。

## Git Push

每次改完檔案自動 push（`python3 github_push.py "<具體 commit msg>"`），唔使另外要求。
