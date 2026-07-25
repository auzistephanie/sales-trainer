# CLAUDE.md — AI 面試教練 Bot

AI 生成面試場景、評估回答、追蹤進度、MBTI 個人化 coaching。DeepSeek（`deepseek-v4-flash`）＋ Upstash Redis ＋ Telegram Bot；另有獨立 Web App（`webapp/`）。

> 詳細資訊拆咗落 `docs/*.md`，按需 read_file，唔好靠記憶或猜測。

## ⚙️ Standards（MANDATORY — 正本：`stephanie-personal/docs/ai-governance/06-STANDARDS.md`，改規則只改正本）

Push（`github_push.py` 永不 git CLI・HTTPS・一次 run 一 commit）・寫入分流（改動記錄 → `CHANGELOG.md` **頂部**，唔准 append 落本檔；本檔上限 100 行/6KB）・清理 mv `_to_delete/`・改舊檔先 `.bak-YYYYMMDD`・方向性決定先 preview・改完以用家身份 run 一次先報完成・governance 00–05（派 subagent 先讀 01+03；報完成前過 02 §R2；冇 mount stephanie-personal → 叫 Stephanie 連埋）。詳文＋例外表 → 正本。

## 📖 文件讀取規則（MANDATORY）

| 需要嘅資訊 | 讀邊份 |
|---|---|
| Bot Runtime（webhook vs polling）、Vercel 部署、menu sync、環境變數 | `docs/RUNTIME_DEPLOY.md` |
| 題型/場景DNA/MBTI/難度/評分/變現、求職功能組（CV Health/Salary/ATS/Negotiate/Debrief）、Tailored CV v7、狀態機、Setup flow | `docs/FEATURES.md` |
| Job Tracker、Daily Check（followup/週報/自動搵工 scan_new_jobs）、callbacks | `docs/JOBS_DAILY.md` |
| Web App（`webapp/`）schema／API 對照／onboarding flow／主題引擎 | `docs/APP_SPEC.md` |
| 改版歷史 | `CHANGELOG.md`（唔需要每次讀）|
| AI 調度/驗證/判斷制度（全 repo 共用） | 見頂部 ⚙️ Standards |

## Gotchas（估唔到／估錯會出事）

- **`api/webhook.py` 先係實際接單嗰個**；`bot_listener.py` 已停用只留參考——**改嘢一律改 `api/webhook.py`**。
- **`requirements.txt` 唔准有 streamlit**（Vercel 500MB function 上限）。Streamlit CRM 係另一個 deployment。
- **一次 run = 一個 commit**，唔好連環 push（Vercel 100 deployments/日上限）。
- **加/改 bot 指令後必須探訪** `https://sales-trainer-wheat.vercel.app/api/set_webhook` sync menu ——`setMyCommands` 唔會自動更新，唔跑用家見唔到新指令（2026-07-01 出過事）。
- **`webapp/` 係加建唔係取代**：bot + Redis 照舊運作，兩邊並存。webapp 用 Supabase（共用 project `cmtubaxlniglklmdwlzs`，table 一律 `coach_` 前綴 + RLS `user_id = auth.uid()`），Vercel project `interview-coach`（Root Directory = `webapp`）。
- `webapp/api/index.py`（Flask）**唔可以直接 import** root 嘅 `interview_trainer.py` —— 要 copy 入 `api/_lib/` + shim `utils.py` 去走 Redis/Telegram 依賴。

## 生產網址

Telegram bot https://sales-trainer-wheat.vercel.app · Web App https://interview-coach-ten-delta.vercel.app · Streamlit CRM https://sales-trainer-jatucpwszxyvoq5kpt7bav.streamlit.app · landing `/landing.html`

## ✅ 完成前檢查（本 repo 專屬 DoD；通用四格 → 02-JUDGMENT §R2）

1. 改/加 bot 指令 → 探訪 set_webhook sync menu ＋ Telegram 實見新 menu
2. 實跑驗證：Telegram bot／webapp 實際行一次相關流程先報完成，唔係「應該得」
3. Push：`python3 scripts/github_push.py "<msg>"`＋核實 GitHub HEAD（→ Standards §S1）

## Backlog（未做，記低就算）

- 語音互動模擬面試 avatar（Vidu S1 real-time 語音控制 digital human）：用家開聲同 AI 面試官即時對話練習，取代宜家文字問答。成本≈$0.0075/秒，10 分鐘 session≈$4.5。2026-07-17 諗到，未拍板做。
