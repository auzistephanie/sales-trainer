# CLAUDE.md — 銷售話術訓練機器人

AI 生成銷售拒絕場景，評估用戶回應，追蹤掌握進度。DeepSeek-V3 生成，Upstash Redis 持久化，Telegram Bot 互動。

## 核心檔案
- `sales_trainer.py` — 場景生成、AI 評估、反對類型池
- `bot_listener.py` — Telegram 後台服務（狀態機、指令路由）
- `utils.py` — Redis I/O、Telegram 發送
- `.env` — API keys（唔 commit）
- `github_push.py` — 用 GitHub API push（PAT in .env）：`python3 github_push.py "<commit message>"`

## 反對類型（10 種）
價格太貴、要考慮下、有比較、唔需要、冇時間、唔信任、要問老婆、時機未到、有現有供應商、要研究下

每種有 `weight`（出現頻率）+ `client_line`（客戶原話）+ `tip`（處理技巧）。

## 場景 DNA
`pick_scenario_dna()` 隨機組合：反對類型 × 客戶性格 × 銷售場景 × 行業，WINDOW=4 防重複。
- **客戶性格池（8種）**：慳家算數、忙碌不耐、比較分析、冷淡懷疑、拖延逃避、情緒搖擺、強勢主導、沉默保守
- **銷售場景（8種）**：冷電話開場、跟進 warm lead、現場 demo 後、報價後反應、續約談判等
- **行業（6種）**：保險、地產、企業 SaaS、零售消費品、金融投資、教育培訓

## 難度系統
- 初級：單一拒絕、配合型客戶、提示多
- 中級：多重拒絕、中立客戶、提示少
- 高級：連環拒絕、強勢客戶、無提示

## Bot 指令
`/practice [難度/行業]` 隨機練習 · `/drill` 針對類型 · `/stats` 進度報告 · `/streak` 連續天數 · `/tip` 今日技巧 · `/help`

## 狀態機
Redis key `sales_session`（TTL 600s）：
- `state: "waiting_response"` + `scenario` → 用戶下一條訊息視為練習回應
- 收到回應 → DeepSeek 評估 → clear session

## 評分系統（1-4分）
1. 完全唔識應對
2. 基本方向對，但力度不足
3. 處理得當，可以更強
4. 教科書級回應

每種反對類型獨立記分，`/stats` 顯示各類型掌握度 %。

## 自動化
- 執行：`python3 bot_listener.py`（常駐）
- LaunchAgent plist 可按 daily-novel 模式設置

## 改版歷史
- **2026-06-23**：初版創建，10 種拒絕類型、8 種客戶性格、狀態機練習流程
