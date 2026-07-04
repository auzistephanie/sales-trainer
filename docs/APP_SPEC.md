# APP_SPEC.md — 面試教練 Web App / PWA 技術規格（Step 2）

由 Telegram bot → 真 app。目標：全功能、Google 登入、跨裝置同步。
現有 AI 邏輯（`interview_trainer.py` + `mbti_checker.py`，DeepSeek）**照用唔重寫**，只係前面加 API + 用戶系統。

> 現狀關鍵：Redis key 冇分 user（單用戶設計）。變 multi-user = 每個 key 搬去 Supabase Postgres table + `user_id` 分隔 + RLS。Telegram bot 保持運作，app 係「加建」唔係「取代」。

---

## 1. 架構

```
[React PWA 前端]  ──JWT──▶  [Vercel Python API /api/app/*]  ──▶  interview_trainer.py (DeepSeek)
      │                              │
      └── Supabase Auth (Google)     └── Supabase Postgres (進度/CV/工作/歷史)
```

| 層 | 技術 | 備註 |
|---|---|---|
| 前端 | React (Vite) SPA，PWA manifest | 手機「加到主畫面」當 app |
| 登入 | Supabase Auth — Google only | 前端拎 JWT，帶去 API |
| API | Vercel Python serverless `/api/app/*` | 每個 endpoint 包一個現有函數，驗 Supabase JWT |
| 資料 | Supabase Postgres + RLS | 每行 `user_id = auth.uid()` |
| AI | DeepSeek-V3（不變） | `interview_trainer.py` import 即用 |

---

## 2. Supabase Schema

所有 table 開 **RLS**，policy：`user_id = auth.uid()`（`profiles` 用 `id = auth.uid()`）。

### `profiles`
| 欄 | 型 | 說明 |
|---|---|---|
| id | uuid PK | = auth user id |
| email | text | |
| display_name | text | |
| mbti | text | 例 `ENFP`；null = 未做 |
| mbti_scores | jsonb | 四維得分 |
| coaching_on | bool | 是否啟用 MBTI coaching |
| created_at | timestamptz | |

### `practice_sessions`
| id uuid PK · user_id uuid FK · qtype text · industry text · difficulty text · scenario jsonb（`generate_scenario` 輸出）· status text（active/done）· created_at |

### `practice_answers`
| id uuid PK · session_id uuid FK · user_id uuid FK · question_no int · answer_text text · score int · feedback jsonb（`evaluate_response` 解析後）· created_at |

### `stats`
| user_id uuid PK · total_answered int · avg_score numeric · streak_days int · last_practice_date date · weak_types jsonb |
> streak / 平均分即時算得，但保留一行方便快速讀 + daily streak 判斷。

### `cvs`
| id uuid PK · user_id uuid FK · filename text · cv_text text · health_score int · health jsonb（`calculate_cv_health`）· created_at |

### `jobs`（工作追蹤）
| id uuid PK · user_id uuid FK · company text · role text · url text · jd_text text · status text · ats_score int · created_at |

### `negotiate_logs`
| id uuid PK · user_id uuid FK · offer_details text · round_num int · messages jsonb · created_at |

### `debrief_logs`
| id uuid PK · user_id uuid FK · job_info jsonb · debrief_text text · ai_feedback text · created_at |

### `recent_dna`
| user_id uuid PK · data jsonb |
> 對應現有 `recent_dna`，防止場景重複。

---

## 3. API endpoints（`/api/app/*`，全部驗 JWT）

| Method · Path | 包住嘅函數 | 做咩 |
|---|---|---|
| POST `/practice/start` | `generate_scenario` + `pick_scenario_dna` | 出面試場景（收 difficulty/qtype/industry），寫 `practice_sessions` |
| POST `/practice/answer` | `evaluate_response` | 評分 + feedback，寫 `practice_answers`，更新 `stats` |
| GET `/stats` | — | 讀成長曲線、連勝、最弱題型 |
| GET `/tip` | `get_daily_tip` | 每日貼士 |
| POST `/cv/health` | `parse_resume` + `calculate_cv_health` | 上載 CV → 體檢，寫 `cvs` |
| POST `/salary` | `generate_salary_benchmark` | 市場薪酬範圍 |
| POST `/ats` | `calculate_ats_score` | CV vs JD 過機率 |
| POST `/negotiate` | `generate_negotiate_response` + `..._summary` | 多回合談判演練，寫 `negotiate_logs` |
| POST `/debrief` | `generate_debrief` + `analyze_conversation` | 面試覆盤，寫 `debrief_logs` |
| GET `/mbti/questions` · POST `/mbti/submit` | `mbti_checker.py` | 20 題 → 16 型，寫 `profiles.mbti` |
| GET/POST/PATCH `/jobs` | `extract_job_from_url` 等 | 工作追蹤 CRUD |
| POST `/cv/tailor` (可選) | `generate_tailored_cv_content` + `build_cv_docx` | 生成 tailored CV .docx |

驗證：前端每個 request 帶 `Authorization: Bearer <supabase_jwt>`；API 用 Supabase secret 驗 token 攞 `user_id`，所有讀寫鎖 `user_id`。

---

## 4. 登入流程

1. 前端撳「用 Google 繼續」→ Supabase Auth 彈 Google OAuth
2. 成功後前端攞到 session（JWT）
3. 首次登入：`profiles` 無 row → 引導做 MBTI（可跳過）
4. 之後所有 API call 帶 JWT

---

## 5. 遷移 / 共存

- **Telegram bot 不動**：`api/webhook.py` 繼續行，用返 Redis。App 用 Postgres，兩邊獨立。
- 想日後打通（同一人 Telegram + App 共用進度）＝之後再加 mapping，第一版唔做。
- Redis 唔使即刻退役。

---

## 6. 要你拍板（開放決定）

1. **前端 stack**：Vite React（最輕、最快）✅ 建議 · 定 Next.js（連 SSR/SEO，較重）
2. **Vercel project**：同現有 `sales-trainer` 同一個（`/api/app/*` 加落去）· 定開新 project（前後端乾淨分離）✅ 建議新 project
3. **收費**：第一版免費、之後先加訂閱 ✅ 建議 · 定一開始就整 paywall
4. **Telegram bot**：保留（建議）· 定逐步退役
5. **網域**：先用 Vercel 免費網域 · 定你有 custom domain

---

## 7. 落實順序（Step 3 起）

1. Supabase：建 project、跑 schema migration、開 Google OAuth、set RLS
2. API：起 `/api/app/*`，逐個包函數 + JWT 驗證，用 Postman/curl 測
3. 前端：Vite React，接 auth + API，實現 mockup 各畫面
4. PWA：manifest + service worker（可加到主畫面）
5. 部署 Vercel + 用家身份跑一次全 flow 驗證
