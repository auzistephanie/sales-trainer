# AGENTS.md — 畀 Codex（同任何讀 AGENTS.md 嘅 agent）

> Claude Code 讀 `CLAUDE.md`，Codex 讀呢份。**兩份講同一套規則**，唔好只信其中一份就開工。
> 呢份只放「唔跟就會即刻整爛嘢」嘅硬規則；其餘全部指去正本，唔喺度抄（抄＝將來 drift）。

---

## 🚫 第 1 條（最重要）：**永遠唔准用 git CLI 做 push**

呢個 repo 住喺 **Google Drive Mirror** 資料夾入面。喺 Drive 上面跑 `git add` / `git commit` /
`git push` / `git fetch` / `git reset` 會留低 stale `.git/index.lock`、`HEAD.lock`、
`refs/heads/main.lock` —— 之後**所有** commit 會被擋，一卡可以卡幾十個鐘，而且好難查。

**要推嘢，一律用：**

```bash
python3 scripts/github_push.py "你嘅 commit message"
```

呢個 script 完全繞過 git CLI 寫入，用 GitHub Git Data API 直接推 main。

**Read-only 嘅 git 指令可以用**（`git ls-files`、`git config --get`、`git diff`、
`git log`）—— 但要留意：本機 `git status` / `git log` **唔反映 push 狀態**（呢套機制
故意唔郁本地 HEAD）。想知推咗未 → 睇 `stephanie-personal/scripts/autopush.log` 尾行，
或者直接查 GitHub API。**唔准用 `git status` 判斷「改咗啲乜」**，佢會顯示成個歷史分歧。

`codex review --uncommitted` 同樣理由用唔到 —— 佢靠 git 判斷改動，喺呢套機制下會攞到
一個巨型假 diff。要 review 就用 `github_push.py` 個內置 review gate（見下）。

---

## 第 2 條：一次 run ＝ 一個 commit

呢批 project 大部分接咗 Vercel，Vercel 有 **每日 100 個 deployment 上限**。
做完一批改動先推一次，唔好每改一個檔就推一次。

---

## 第 3 條：改動記錄寫 `CHANGELOG.md` **頂部**，唔好塞落 `CLAUDE.md`

- 開發史／改咗乜／點解咁改 → `CHANGELOG.md` 最頂（新嘢喺上）
- `CLAUDE.md` **硬上限 100 行 / 6KB**，只准放路由行、概覽行、現行規則
- 同一個 pattern 改超過 3 個 repo（例：全部 repo 加同一行）→ 詳情**只寫
  `stephanie-personal/CHANGELOG.md` 一次**，其他 repo 唔使逐個寫

---

## 第 4 條：清理檔案用 `mv`，唔用 `rm`

一律 `mv` 去該 repo 根目錄嘅 `_to_delete/`（全部 repo 都已經 gitignore）。
14 日後有 script 自動清。直接 `rm` 冇得反悔，而且 device bridge 根本冇 rm 權限。

改既有檔之前開唔開 `.bak`：**只喺兩種情況先開** —— ① 個檔未 push（bak 係唯一 rollback）；
② 個檔唔係 git-tracked（`.env`、secrets）。已 push 嘅 git-tracked 檔**唔使開**，git 本身就係 rollback。

---

## 第 5 條：報「完成」之前要真跑一次

改完功能，以用家身份實際行一次、貼返 output，先可以講「做完」。
「應該得」「我以為推咗」唔算完成。

推完要核實 GitHub 遠端 HEAD 真係新過你改動（private repo 記得帶 auth，否則會收到假 404）：

```bash
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/repos/<owner>/<repo>/commits/main
```

---

## 🔀 兩部機 + 兩個 agent（2026-08-16 起）

Stephanie 有兩部 Mac，兩部都經 Google Drive Mirror 同步同一批 repo，兩部都會同時
用 Claude 同 Codex。所以 `github_push.py` 有三道閘，**撞到閘唔好即刻 `--force` 衝過去**：

| 閘 | 幾時擋你 | 點做 |
|---|---|---|
| **閘 1 刪檔** | 今次會刪走遠端 >3 個檔 | 多數係 Drive 未 sync 完，你部機仲未見到另一部機新增嘅檔。**等 Drive 追返先**。真係要刪 → `--allow-deletions` |
| **閘 2 SHA** | 遠端 SHA 喺你上次見到之後變咗 | 另一部機／session 推過嘢，你手上份 base 舊咗。跑 `--check` 睇差異，確認唔會覆蓋人哋，再 `--force` |
| **閘 3 交叉 review** | 對家 AI 判咗 `BLOCK` | Codex 推 → Claude review；Claude 推 → Codex review。BLOCK 只限 4 類（secrets 洩漏／刪錯檔／明顯 bug／半成品夾帶）。修好再推，或者 `--no-review` |

**開工前跑一次 preflight**（取代舊嘅 `session-lock.sh`）：

```bash
python3 scripts/github_push.py --check
```

見到「遠端喺你上次見到之後變咗」→ 等 Google Drive sync 完先開工，否則你改嘅嘢會建喺舊 base 上面。

**收工即推，唔好留改動過夜。** 呢條係兩機並行下唯一 100% 有效嘅防線 —— 兩部機都乾淨咗，
下次開工邊部都啱。

**推之前個 script 會列出檔案名單** —— 見到唔係你改嘅檔（另一個 agent 寫緊嘅半成品），
**停手問 Stephanie**，唔好照推。

---

## 📍 其餘規則喺邊度（唔喺呢度抄）

| 你要知 | 讀邊份 |
|---|---|
| 本 repo 架構、模組、專屬 DoD | 同層 `CLAUDE.md` |
| 全 repo 共用 standards（正本） | `stephanie-personal/docs/ai-governance/06-STANDARDS.md` |
| 判斷 rubric（幾時要停低問人 R3、完成定義 R2） | `.../02-JUDGMENT.md` |
| 派工守則、夾帶事故 §7.1 | `.../01-DISPATCH.md` |
| 新 repo 裝 push kit | `stephanie-personal/docs/PUSH-SETUP.md` |
| 新機設置 | `stephanie-personal/docs/NEW-MACHINE-SETUP.md` |

**方向性決定先問，細節唔使問**（正本 02 §R3）：
- **要停低問**：不可逆 **＋** 出咗 repo（真人／客戶收到訊息、live flow 變咗、錢郁咗、刪 production 資料）
- **唔使問，做完報告就得**：可逆 ＋ 喺 repo 入面 ＋ 冇對外影響（改檔、修 bug、加 gitignore、清雜檔、事實更正）

**測試永不掂真客**：涉及 live 系統（SleekFlow／WhatsApp／CRM）嘅測試，一律用名入面有
「Testing」嘅假 contact，**唔准帶真客 email／phone／contact ID 落 live API**，就算淨係打一個 curl 都算。

**語言**：同 Stephanie 講嘢用**廣東話 + 繁體中文**。

---
*正本位置：`stephanie-personal/scripts/AGENTS.md.template`，2026-08-16 一次過派落 12 個 repo。
改規則改正本 `06-STANDARDS.md`，唔好逐個 repo 改呢份。*
