# 面試訓練功能 / 狀態機 / Setup Flow

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

## 求職功能組（2026-07-01）

**CV Health Score**（`calculate_cv_health(cv_text)`，本地計算，唔需要 AI）
- Onboarding 上傳 CV 後即時顯示，4 個維度各 25 分：結構完整性／量化成就／Action Verbs／關鍵詞豐富度
- `format_cv_health_message(health)` 砌 Telegram 訊息
- 結果存入 `profile["cv_health_score"]`，做其他功能嘅 baseline

**HK Salary Benchmark**（`generate_salary_benchmark(role, expected_salary, industry)`，DeepSeek）
- Onboarding 流程：CV upload / 手動輸入職位 → 問月薪期望（`parse_salary_input()` 解析 "38k"/"$38,000" 等格式）→ 顯示市場薪酬參考 → 入 MBTI 步
- 結果存 `profile["expected_salary"]` + `profile["salary_currency"]`（固定 "HKD"）

**ATS Match Score**（`calculate_ats_score(jd_text, cv_text, keywords=None)`，DeepSeek 抽 keyword + 本地 `smart_match()`）
- Tailored CV 生成完之後自動觸發（`handle_job_tailored_cv` / `handle_jd_tailored_cv` / `_auto_add_job_from_url`）
- **計分對象＝tailored CV**：先 `flatten_cv_data(cv_data)` 攤平成純文字先計。（2026-07-25 前錯用原版 CV，見 CHANGELOG）
- **雙分數**：同一組 keyword 分別計 tailored（`ats`）同原版 CV（`base`，靠 `keywords=` 參數重用，唔會多叫一次 API）；`format_ats_message(ats, baseline_score)` 嘅 delta 係 tailored − 原版，**唔再同 `cv_health_score` 比**（兩者係唔同指標）
- `smart_match()`：完全命中 → 否則 normalize + `_ats_stem()` 詞根 + multi-word ≥70% token 命中當 match。**只改「點樣量」，唔會為谷分而改 CV 內容**
- Keyword 抽取 prompt 有 INCLUDE ONLY / EXCLUDE 兩段：只收 hard skills / 工具 / 系統 / 學歷 / 行業術語 / 核心職能；**明確排除**僱主自家 programme 品牌名（如 "EngSeeds Programme"）、合約年期、工作模式（"1-year contract"、"5-Day Work"）、公司名 / 地區 / 人工 / 福利 / 工時，以及 "good communication" 類通用廢詞。強制 `Output in ENGLISH only, exactly as written in the JD`
- `_ats_stem()`（2026-07-25 加強）：兩層剪詞尾 `ions/ion/ments/ment/ings/ing/ies/ied/ed/es/s` + 去尾 `e`，所以 coordinate / coordinated / coordinating / coordination 全部歸一做 `coordinat`，management / managing / manage → `manag`
- `smart_match()` 拆 multi-word 時濾走長度 1 嘅 token（`len(p) > 1`）：`Bachelor's degree` 會拆出 `bachelor / s / degree`，嗰個 `s` 會令命中率跌到 2/3 < 70% 而錯判 miss
- `improvement` 唔再重複列 missing 清單（上面 `⚠️` 行已經列曬），只留一句「有就話我知我幫你加返；冇嘅話唔會幫你作」——**2026-08-04 起呢句真係做嘢**：回覆會存入 `ats_followup`（job flow）／`jd_ats_followup`（JD-session flow）state，`match_confirmed_skills()` 揪出回覆入面提到邊啲 missing keyword，冇 match 到就列清單畀用戶再試，有 match 到就帶 `confirmed_extras` 重新生成 CV + 重計 ATS，回覆 before/after 分數
- 存 `job["ats_score"]` + `job["ats_baseline"]`（JD session 同樣）

**薪酬談判 Negotiate**（`/negotiate`）
- State：`negotiate_start`（等 offer details）→ `negotiate_session`（每回合 `generate_negotiate_response()` 生成 HR 回應 + 評分）
- 「結束」或 `/negotiate` → `generate_negotiate_summary(history)` 總結
- `/listjobs` 每個 job 有 `🤝 Negotiate` 按鈕（`job_negotiate_{id}`），跳過輸入 offer details 步

**面試覆盤 Debrief**（`/debrief`）
- State：`debrief_job_select`（揀已追蹤嘅工 / 跳過）→ `debrief_input`（描述面試過程）
- `generate_debrief(job_info, debrief_text)` 輸出評級 + 強項 + 改善點
- 如有連結 job，分析完自動跳出 `handle_update_status_menu()` 更新狀態

## Tailored CV — v7 格式（2026-07-03 對齊 skill）

- `generate_tailored_cv_content()` + `build_cv_docx()`（`interview_trainer.py`）已重寫，對齊 `tailored-cv-generator` skill 嘅 v7：navy heading + 底線、2-col Core Competencies table、keepNext 分頁、齊 Earlier Exp/Certs/Languages/Salary section
- 修好「削肉」ATS 問題：唔再截 CV 到 3500 字（改 9000）、prompt 明確要求「保留所有 JD 相關 keyword，tailored 版 ATS 必須 ≥ 原版」
- JSON 新增欄位：`earlier_experience` / `certifications` / `languages` / `salary`；experience 用 `title`（唔係 `role`）
- **2026-07-28：Web App 都有埋**——`webapp/api/index.py` 新增 `POST /api/app/cv/tailor`，直接 call 呢頁嘅 4 個函數（`generate_tailored_cv_content` / `generate_cover_letter_from_jd` / `build_cv_docx` / `build_cover_letter_docx`，全部原封不動搬用，冇改邏輯），CV + Cover Letter 兩份 .docx 用 base64 一齊喺 JSON 度返，前端 `TailorCvTool`（`webapp/src/screens.jsx`）解碼做 Blob 落載。之前 Web App 淨係得一句提及字眼，冇實際畫面——而家兩邊（bot／webapp）都用得到呢個功能。

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
