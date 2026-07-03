# Job Tracker / Daily Check / 自動搵工

## Job Application Tracker（2026-06-29）

`load_jobs() / save_jobs()` in utils.py → Redis key `interview_jobs`（list of job objects）

每個 job object 欄位：`id, company, role, jd, link, applied_date, status, last_touch, snooze_until`

Status 值：Applied / Phone Screen / 1st Interview / 2nd Interview / Offer / Rejected

`/addjob` flow（addjob session states）：
1. `addjob_company` → 輸入公司名
2. `addjob_role` → 輸入職位
3. `addjob_jd` → 貼 JD 或 /skip
4. `addjob_link` → 貼 link 或 /skip → 自動 save job，status = Applied

`/listjobs` → 顯示所有 jobs + inline keyboard（Questions / Tips / Practice / Update Status）

Inline callbacks：`job_q_{id}` / `job_tips_{id}` / `job_practice_{id}` / `job_updatestatus_{id}` / `job_status_{id}_{status}`

AI functions in interview_trainer.py：`generate_job_questions(job)` / `generate_job_tips(job)`

## Daily Check — Follow-up 提醒 + 求職週報（2026-07-03）

`api/daily_check.py` — 獨立 Vercel serverless function，⚠️ **唔用 Vercel 內建 cron**（`vercel.json` 冇 `crons` 設定，2026-07-02 已移除），改用外部服務 **cron-job.org** 每日 10:00 HKT 打 `https://sales-trainer-wheat.vercel.app/api/daily_check`（endpoint 冇加 auth，GET/POST 都得）。`vercel.json` 仍然要喺 catch-all rewrite 之前加一條 `/api/daily_check` → 自己嘅明確 rewrite，否則會俾 `/(.*) → /api/webhook` 嗰條吞晒。

**Follow-up 提醒**（`check_followups()`）：status 係 Applied / Phone Screen 嘅 job，`last_touch`（冇就用 `applied_date`）超過 7 日冇郁 → 推 Telegram，附 3 個掣：
- `job_followup_{id}` → 重置 `last_touch` = 今日
- `job_updatestatus_{id}` → 沿用 `/listjobs` 現有嘅 update status 選單
- `job_snooze_{id}` → 設 `snooze_until` = 今日+3日，喺嗰日之前唔會再提醒

`job_status_` callback（更新狀態）而家會自動更新 `last_touch` + 清走 `snooze_until`，並將轉態記錄寫入 `interview_stats` Redis key 嘅 `status_change_log`（list，上限200項）。

**求職週報**（`send_weekly_report()`，淨係逢星期日先發）：
- 過去 7 日新申請數（睇 `applied_date`）
- 過去 7 日狀態變化（`status_change_log`）
- 過去 7 日練習次數 + 平均分（`interview_stats` 新增嘅 `daily_log`{日期:次數} 同 `score_log`[{date,qtype,score}]，喺 `record_score()` 寫入，`daily_log` 保留 60 日）
- 最弱題型（跨全部歷史 `qtype_scores` 揀平均分最低嗰個，同 `/stats` 用同一套邏輯）

**自動搵工推送**（`scan_new_jobs()`，同一個 daily_check 內一齊跑）：
- 搜尋關鍵字 `JOBSDB_SEARCH_KEYWORDS = ["education", "education coordinator", "edtech"]`（Stephanie 2026-07-03 揀嘅，想改直接改呢個 list）
- 用 Jina Reader 抓 `https://hk.jobsdb.com/jobs?keywords=<關鍵字>`（`X-With-Links-Summary: true` 攞埋職位連結），冇 `profile.job_title`/`industry` 就唔掃
- DeepSeek 對住 profile 揀最啱嘅職位（最多 `MAX_JOBS_PUSHED_PER_DAY=3`），dedup 用 Redis `seen_scanned_jobs`（title+company 組合，上限 500 個）
- 每個推薦存 `scanned_job:{short_id}`（TTL 14 日），Telegram 推送附 2 個掣：
  - `scanjob_open_{id}` → 直接call現有嘅 `handle_url_message(url)`，等於自己貼咗個 link，會出返 Cover Letter / Tailored CV / 加入追蹤 嗰個選單
  - `scanjob_skip_{id}` → 淨係刪走個 scanned_job 記錄
- ⚠️ 風險：JobsDB 改版／加強反爬會令 Jina 抓唔到嘢，`scan_new_jobs()` 靜靜地回傳 0（唔會報錯，但都唔會推嘢）——如果幾日都冇推薦，check下係咪呢度斷咗
