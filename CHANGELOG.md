# 改版歷史

> 唔會自動讀入每次對話 context，需要時先 `read_file`。

- **2026-07-12**：搬機至 Google Drive Mirror——canonical 路徑由 `~/sales-trainer` 改為 `~/Desktop/Stephanie-Google Drive/dev/sales-trainer`；HEAD／`git fsck`／檔案數（3206 個）核對通過；`stephanie-personal/scripts/autopush-registry.txt` 已更新新路徑；舊 `~/sales-trainer` 已加 `_MIGRATED_TO_GOOGLE_DRIVE.txt` 標記，確認後可刪。
- **2026-07-10**：`github_push.py` 修好「push 完 `git status` 仍顯示大量假改動」——script 經 GitHub API 寫 remote、唔 advance 本地 HEAD，令 status 成日同舊 HEAD 比。Fix：push 成功後加 `sync_local_head()`（帶 token fetch + `git reset --mixed` 對齊；token 唔寫檔唔 print、失敗唔阻塞、只郁 HEAD+index）；已清殘留 `.git/index.lock` 並驗證 status 歸零。
- **2026-07-02**：求職 CRM 網頁（Streamlit）UI 重做 —— 原本淨係 default 主題 + `st.expander` + emoji 分辨狀態，冇卡片感。新版：metric 卡片化、kanban 卡加狀態色帶（灰=Applied／橙=Phone Screen／紫=Interview／綠=Offer／紅=Rejected）+ status badge、申請漏斗由純文字 metric 改做 bar chart。**新增功能**：kanban 卡直接加咗「更新狀態」selectbox，寫返同一個 Redis key `interview_jobs`，同 Telegram `/listjobs → 更新狀態` 共用同一份資料、雙向同步。用 `streamlit.testing.v1.AppTest` 實測跑過 `pages/求職_CRM.py`（連真實 Upstash 資料），確認冇 exception、metric/badge/kanban/漏斗都正常渲染先報告完成
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
