# CLAUDE.md — AI 面試教練 Bot

AI 生成面試場景，評估回答，追蹤進度，MBTI 個人化 coaching。DeepSeek-V3 生成，Upstash Redis 持久化，Telegram Bot 互動。

> 詳細資訊拆咗落 `docs/*.md`，按需 read_file，唔好靠記憶或猜測。

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
- `github_push.py` — push 用呢個，唔用 git CLI：`python3 github_push.py "<msg>"`

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
⚠️ Session 冇 mount stephanie-personal folder → **叫 Stephanie 連埋佢**，唔好靜靜地跳過成套制度。

## Git Push

每次改完檔案自動 push（`python3 github_push.py "<具體 commit msg>"`），唔使另外要求。
