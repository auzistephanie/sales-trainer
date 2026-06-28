# CLAUDE.md — AI 面試教練 Bot

AI 生成面試場景，評估用戶回答，追蹤掌握進度，根據 MBTI 提供個人化 coaching。DeepSeek-V3 生成，Upstash Redis 持久化，Telegram Bot 互動。

## 核心檔案
- `interview_trainer.py` — 題型池、MBTI coaching、場景生成、AI 評估
- `bot_listener.py` — Telegram 後台服務（狀態機、指令路由）
- `utils.py` — Redis I/O、Telegram 發送
- `.env` — API keys（唔 commit）
- `github_push.py` — 用 GitHub API push（PAT in .env）：`python3 github_push.py "<commit message>"`
- `sales_trainer.py` — 舊銷售版本（保留備份，唔再使用）

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
`/practice [難度]` · `/drill` 針對題型 · `/stats` 進度報告 · `/streak` 連續天數 · `/tip` 今日技巧 · `/review` 貼真實面試對話分析 · `/setup` 設定職位+MBTI · `/mystatus` · `/help`

## 狀態機
Redis key `sales_session`（TTL 600s）：
- `state: "waiting_response"` + `scenario` → 用戶下一條訊息視為練習回應
- `state: "waiting_review"` → 用戶下一條訊息視為面試對話記錄
- 收到回應 → DeepSeek 評估 → clear session

## Setup Flow
1. 揀行業（14種 inline keyboard / 自定）
2. 打目標職位（文字輸入）
3. 揀 MBTI（16種 4×4 keyboard / 跳過）

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

## 自動化
- 執行：`python3 bot_listener.py`（常駐）
- LaunchAgent plist：`com.salestrainer.bot.plist`

## GitHub Push
- 用 GitHub API 直接 push，唔用 git CLI（避免 lock file 問題）
- 指令：`python3 github_push.py "<commit message>"`
- `.env` 需要：`GITHUB_TOKEN` + `GITHUB_REPO=auzistephanie/sales-trainer`
- **規則：每次改完檔案，Claude 必須自動 push，唔需要 Stephanie 另外要求**
- commit message 要具體描述改動（唔好用 "update files"）

## 改版歷史
- **2026-06-23**：初版創建，銷售話術訓練，10 種拒絕類型
- **2026-06-28**：重大 pivot — 改為 AI 面試教練，新增 14 種行業、MBTI 16種 coaching、變現 credit 系統
