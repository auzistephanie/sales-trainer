#!/usr/bin/env python3
"""
github_push.py — 直接經 GitHub API 把整個 working tree 同步上 GitHub main。

點解唔用 git CLI：
  Sandbox 跑 `git add/commit/push` 會留低 stale `.git/index.lock` /
  `HEAD.lock`，之後所有 commit 都被擋。呢個 script 完全繞過 git CLI，
  用 GitHub Git Data API（blobs / trees / commits / refs）直接寫上 GitHub。

偵測方式（重要）：
  同 **遠端 origin/main 的實際 tree** 比對，而唔係本地 HEAD——
  計每個工作檔的 git blob sha，只上傳有差異的檔，並刪除遠端多出的檔。
  所以就算本地 git 歷史舊咗/未同步，一樣會正確同步，且可重複執行（idempotent）。

⚠️ 本地 `git status`／`git log` 唔會反映 push 狀態（2026-07-15 起，故意）：
  想知真正有冇 push 咗 → 睇 autopush.log 尾行，或者開 GitHub 睇 commit 時間。

用法：
  python3 scripts/github_push.py "你的 commit message"
  python3 scripts/github_push.py "msg" --files path/to/a.py path/to/b.md
  python3 scripts/github_push.py --check        # 開工前 preflight，唔推

Flags：
  --files a.py b.py   淨比對/上傳指定嗰幾個檔，**唔會**掃/刪其他任何遠端檔案——
                      避免其他 session／worktree 留低嘅未完成改動被順手掃上去。
  --check             Preflight：只報告本機 vs 遠端嘅差異同 remote HEAD 時間，唔推。
                      **兩部機開工前應該跑呢個**（2026-08-16 起取代 session-lock.sh）。
  --allow-deletions   放行「刪超過 3 個遠端檔」呢個閘（見下面 §閘 1）。
  --force             放行「remote SHA 變咗」呢個閘（見下面 §閘 2）。
  --no-review         跳過交叉 review gate（見下面 §閘 3）。

═══════════════════════════════════════════════════════════════════════
三道閘（2026-08-16 加，為咗兩部機 + Claude/Codex 兩個 agent 並行）
═══════════════════════════════════════════════════════════════════════
閘 1 — 刪檔閘：
  呢個 script 會刪走「遠端有、本地冇」嘅檔。兩部機經 Google Drive Mirror 同步，
  如果你部機份 copy 未 sync 完就推，另一部機啱啱新增嘅檔會被靜靜刪走。
  所以：刪超過 DELETION_LIMIT（3）個檔就停手，要 --allow-deletions 先過。

閘 2 — SHA 閘：
  `.push-state/<repo>.json` 嘅 `seen[<機名>]` 記住**本機**上次同步到嘅 remote SHA。
  今次攞到嘅 remote SHA 同本機 baseline 唔同 = 有第二部機／session 喺你之後推過，
  你手上份 base 係舊嘅 → 停手，要 --force 先過。
  ⚠️ baseline 一定要分機存：state 檔住喺 Drive 兩機共用，如果得一個共用 SHA，
  A 機推完 sync 落 B 機就會令 B 機以為自己係最新，閘完全失效。
  `--check` 只會喺「本機同遠端完全一致」時先更新 baseline。

閘 3 — 交叉 review gate：
  推之前叫「另一個 AI」睇一次 diff：Codex 推 → Claude review；Claude 推 → Codex review。
  只喺有實質 code 改動先跑（純 .md / docs/ / CHANGELOG 跳過，慳時間慳錢）。
  Reviewer 要回 VERDICT: BLOCK / WARN / PASS。BLOCK 先擋，WARN 印出照推。
  Reviewer 叫唔郁（未登入／app 冇開）→ fail-open 照推，但連續 REVIEW_FAIL_LIMIT（3）
  次失敗就轉 BLOCK，逼你去修。

全新零 commit repo：先經 Contents API 用**用家條 commit message** 種一個檔開 `main`
（`bootstrap_empty_repo`），再照正常 Git Data API 流程推其餘檔案。得一個檔嘅話
bootstrap 就係唯一嗰個 commit（唔會多開一個 chore commit）。

⚠️ **唯一已知例外**「一次 run＝一個 commit」：全新零 commit repo **同時有 >1 個檔**
要 bootstrap 嗰次，會變成 2 個 commit（bootstrap 一個 ＋ 其餘檔一個）。呢個唔係
設計選擇，係 GitHub API 硬限制——Git Data API（`POST .../git/blobs`）喺 repo
連一個 commit 都未有嗰陣會 409 "Git Repository is empty."，一定要用 Contents API
（只能一次一個檔）先種到第一個 commit。呢個情況一世人淨會撞一次（新 repo bootstrap
嗰下），跟 06-STANDARDS 例外表 catnu-app 記錄嘅做法。

Token 來源：.env（GITHUB_TOKEN）→ 環境變數 GITHUB_TOKEN/GH_TOKEN → .gh-token 檔（gitignored）。
Token 只喺本機讀，唔會 print。

備註（中文檔名）：working_files() 靠 `git ls-files`，如遇非 ASCII 檔名會被 git octal-escape，
所以呢個 script 全程用 `-c core.quotepath=false` 行 git 指令，避免 path 變成字面 "\346\..." 亂碼。
"""
import base64
import datetime
import difflib
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

API = "https://api.github.com"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── 閘門參數（想調鬆／緊改呢度）────────────────────────────────────────
DELETION_LIMIT = 3        # 閘 1：一次過刪多過咁多個遠端檔就停手
REVIEW_TIMEOUT = 300      # 閘 3：reviewer 幾多秒唔覆就當叫唔郁
REVIEW_FAIL_LIMIT = 3     # 閘 3：連續咁多次叫唔郁就由 fail-open 轉 BLOCK
REVIEW_DIFF_MAX = 120_000 # 閘 3：diff 超過咁多字就截斷（免爆 reviewer context）

# 呢啲 path 唔算「實質 code 改動」，全部改動都係呢類就跳過 review（閘 3）
DOC_ONLY_RE = re.compile(
    r"(?:^|/)(?:CHANGELOG[^/]*|CLAUDE\.md|AGENTS\.md|README[^/]*)$"
    r"|\.(?:md|markdown|txt|rst)$"
    r"|^docs/|^_to_delete/|(?:^|/)\.DS_Store$"
)

CODEX_BIN_CANDIDATES = (
    os.environ.get("CODEX_CLI_PATH"),
    "/Applications/ChatGPT.app/Contents/Resources/codex",
    shutil.which("codex"),
)


# --- 2026-07-15 concurrent-push 偵測（overlap 診斷 fix A）。
# 2026-07-31 修：舊版當 stephanie-personal 一定係隔籬 folder。
# 2026-08-16 升級：由「事後 print 警告」變成「事前 hard stop」（閘 2）。
def _resolve_personal():
    for cand in (os.environ.get("STEPHANIE_PERSONAL_DIR"),
                 os.path.expanduser("~/dev/stephanie-personal"),
                 os.path.join(os.path.dirname(REPO), "stephanie-personal")):  # legacy sibling
        if cand and os.path.isdir(cand):
            return cand
    return None


_PERSONAL = _resolve_personal()
_PUSH_STATE_DIR = os.path.join(_PERSONAL, "scripts", ".push-state") if _PERSONAL else None
_PUSH_STATE_FILE = (os.path.join(_PUSH_STATE_DIR, os.path.basename(REPO) + ".json")
                    if _PUSH_STATE_DIR else None)


def _load_state():
    try:
        if _PUSH_STATE_FILE and os.path.isfile(_PUSH_STATE_FILE):
            with open(_PUSH_STATE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_state(**updates):
    if not _PUSH_STATE_DIR:  # S5「死咗邊個會知」：靜默失效改成出聲
        print("⚠️ push-state 寫唔到（搵唔到 stephanie-personal）— 閘 2 已停用；"
              "設環境變數 STEPHANIE_PERSONAL_DIR 指去正本即可修復")
        return
    try:
        state = _load_state()
        state.update(updates)
        os.makedirs(_PUSH_STATE_DIR, exist_ok=True)
        with open(_PUSH_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"⚠️ push-state 寫入失敗（{e}）— 閘 2 今次冇記錄")


_HOST = socket.gethostname().split(".")[0]


def _my_baseline(state=None):
    """本機上次同步到嘅 remote SHA。

    ⚠️ 一定要**分機**存（2026-08-16 修，Codex review 捉到）：
    `.push-state/` 住喺 Google Drive，兩部機共用。舊版得一個 `last_seen_sha`——
    A 機推完會將 state 更新做新 SHA 並 sync 落 B 機，B 機（working tree 仲係舊）
    再推時見到 state == remote，閘 2 就放行，照樣覆蓋 A 機啲嘢。等於冇閘。
    """
    st = _load_state() if state is None else state
    return (st.get("seen") or {}).get(_HOST)


def _record_baseline(sha):
    st = _load_state()
    seen = dict(st.get("seen") or {})
    seen[_HOST] = sha
    _save_state(seen=seen, last_seen_sha=sha)


def _agent_label():
    """[agent@機名] — 兩部機 × 兩個 agent，commit 一眼睇到邊個推。

    Codex：喺 ~/.codex/config.toml 嘅 [shell_environment_policy.set] 加
           AI_AGENT = "codex"，佢開嘅 shell 就一定帶到。
    Claude（含 Cowork 經 desktop-commander）：冇設就當 claude（佔絕大多數）。
    """
    agent = (os.environ.get("AI_AGENT") or "").strip().lower()
    if not agent:
        agent = "codex" if os.environ.get("CODEX_HOME") else "claude"
    return agent, f"[{agent}@{_HOST}]"


# ═══════════════════════════════════════════════════════════════
# 基礎（git read-only / GitHub API）
# ═══════════════════════════════════════════════════════════════
if load_dotenv:
    load_dotenv(os.path.join(REPO, ".env"))


def run(args):
    # -c core.quotepath=false：非 ASCII（中文）檔名唔好被 octal-escape。
    # 呢個 script 淨係用 git 做 read-only 操作（config get / ls-files）——唔會再
    # 寫任何 .git ref/HEAD/index，所以唔會再產生 stale lock。
    return subprocess.run(["git", "-c", "core.quotepath=false"] + args[1:],
                          cwd=REPO, capture_output=True, text=True)


def get_remote_url():
    return run(["git", "config", "--get", "remote.origin.url"]).stdout.strip()


_TOKEN_PREFIXES = ("ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_")


def parse_remote(url):
    m = re.match(r"https://(?:([^@/]+)@)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if not m:
        return None, None, None
    creds, owner, repo = m.group(1), m.group(2), m.group(3)
    token = None
    if creds and ":" in creds:
        token = creds.split(":", 1)[1]
    elif creds and creds.startswith(_TOKEN_PREFIXES):
        token = creds
    return token, owner, repo


def get_token(remote_token):
    for env in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(env):
            return os.environ[env]
    tokfile = os.path.join(REPO, ".gh-token")
    if os.path.isfile(tokfile):
        with open(tokfile) as f:
            return f.read().strip()
    return remote_token  # legacy fallback only


def api(method, path, token, body=None, ok_statuses=()):
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "github-push-script")
    try:
        # timeout=20（2026-07-16 加）：冇呢個 urlopen 會無限等，網絡一卡就永久卡死。
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in ok_statuses:
            return None  # caller handles this expected case (e.g. brand-new empty repo)
        raise SystemExit(f"❌ GitHub API {method} {path} -> {e.code}\n{e.read().decode()}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise SystemExit(f"❌ GitHub API {method} {path} -> 網絡/timeout: {e}")


def git_blob_sha(data: bytes) -> str:
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def working_files():
    # 追蹤中 + 未追蹤但唔喺 .gitignore（自動排除 node_modules/dist）；唯讀
    out = run(["git", "ls-files", "-c", "-o", "--exclude-standard"]).stdout
    seen, files = set(), []
    for p in out.splitlines():
        p = p.strip()
        if p and p not in seen and os.path.isfile(os.path.join(REPO, p)):
            seen.add(p)
            files.append(p)
    return files


def remote_tree_map(base, tree_sha, token):
    data = api("GET", f"{base}/trees/{tree_sha}?recursive=1", token)
    return {e["path"]: e["sha"] for e in data.get("tree", []) if e["type"] == "blob"}


def bootstrap_empty_repo(owner, repo, token, path, content, message):
    """GitHub Git Data API（blobs/trees/commits）喺 `main` 未存在之前乜都寫唔到——
    連 `POST .../git/blobs` 都會 409 "Git Repository is empty."。官方解法係用高一層嘅
    Contents API，佢會由一個檔自動幫你開 initial commit ＋ default branch。

    ⚠️ 2026-08-16：12 份 script 合流時由 venturenix 版做 base，漏咗呢個函數
    （catnu 版先有）。閘 3 Codex review 捉返——單靠 `ok_statuses=(404, 409)` 唔夠，
    因為 409 唔止出現喺 GET ref，POST blobs 一樣會撞。"""
    # 用**用家自己**條 message，唔好寫死 "chore: bootstrap"（2026-08-16 閘 3 捉到）：
    # 如果本機得一個檔，bootstrap 完就已經同步，之後 tree 係空 → "Nothing to push"，
    # 用家條 message 會完全冇用過，而 repo 第一個 commit 變咗個無意義嘅 chore。
    # 2026-08-16（閘 3 捉到）：path 直接拼入 URL 冇 encode，中文／空格檔名會撞
    # urllib 報錯。呢個 codebase 成日有中文檔名（見 working_files() 嘅
    # core.quotepath=false 註解），一定要 quote。safe="/" 保留路徑分隔符。
    encoded_path = urllib.parse.quote(path, safe="/")
    api("PUT", f"/repos/{owner}/{repo}/contents/{encoded_path}", token, {
        "message": message,
        "content": base64.b64encode(content).decode(),
    })


def fetch_remote_blob(base, sha, token):
    """攞返遠端一個 blob 嘅文字內容；binary 或攞唔到就 return None。"""
    try:
        data = api("GET", f"{base}/blobs/{sha}", token)
        raw = base64.b64decode(data.get("content", ""))
        return raw.decode("utf-8")
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# 閘 3 — 交叉 review gate
# ═══════════════════════════════════════════════════════════════
REVIEW_PROMPT = """你係一個 code reviewer。下面 <diff> 係另一個 AI agent 啱啱改完、準備推上 GitHub main 嘅改動。
你嘅工作：判斷有冇嘢一定要喺推之前修好。

**只有以下 4 類問題先可以判 BLOCK：**
1. Secrets 洩漏 — diff 入面有 API key／token／password／私鑰／service-account 內容
2. 刪錯檔 — 刪走咗睇落唔應該刪嘅檔（尤其係 config、migration、有人依賴嘅 module）
3. 明顯 bug — 語法錯、undefined 變數、明顯 off-by-one、會即刻 crash 嘅嘢
4. 半成品夾帶 — diff 入面有明顯係未寫完／唔屬於呢次改動主題嘅檔（TODO 佔位、空 function、
   同 commit message 完全無關嘅檔）

其他所有嘢（風格、命名、可以做得更好、缺 test、缺註解）一律 WARN，唔准 BLOCK。
睇唔明或者資料不足 → PASS，唔好靠估。

**輸出格式（嚴格）：**
第一行必須係 `VERDICT: BLOCK` 或 `VERDICT: WARN` 或 `VERDICT: PASS`。
之後最多 5 個 bullet，每個一行，講明係邊個檔、乜事、點修。用廣東話。
唔好覆述個 diff，唔好寫前言。
"""


def _codex_bin():
    for c in CODEX_BIN_CANDIDATES:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def _reviewer_cmd(reviewer):
    """→ (argv, 人睇嘅名) 或者 (None, 原因)"""
    if reviewer == "claude":
        exe = shutil.which("claude")
        if not exe:
            return None, "claude CLI 唔喺 PATH"
        return [exe, "-p", REVIEW_PROMPT], "Claude"
    exe = _codex_bin()
    if not exe:
        return None, "搵唔到 codex binary"
    return [exe, "exec", "--skip-git-repo-check", REVIEW_PROMPT], "Codex"


def build_diff(base, remote, local_paths, deletions, token):
    """整一份 unified diff（本機 vs 遠端 main）餵畀 reviewer。"""
    chunks = []
    for path in local_paths:
        full = os.path.join(REPO, path)
        try:
            with open(full, "rb") as f:
                raw = f.read()
            new_text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            chunks.append(f"--- (binary or unreadable) {path}\n")
            continue
        if remote.get(path) == git_blob_sha(raw):
            continue  # 冇改過
        old_text = fetch_remote_blob(base, remote[path], token) if path in remote else ""
        if old_text is None:
            chunks.append(f"--- (remote binary) {path}\n")
            continue
        d = difflib.unified_diff(
            old_text.splitlines(keepends=True), new_text.splitlines(keepends=True),
            fromfile=f"a/{path}", tofile=f"b/{path}", n=3,
        )
        chunks.append("".join(d))
    for path in deletions:
        chunks.append(f"--- a/{path}\n+++ /dev/null\n(整個檔被刪走)\n")
    diff = "".join(c for c in chunks if c.strip())
    if len(diff) > REVIEW_DIFF_MAX:
        diff = diff[:REVIEW_DIFF_MAX] + f"\n\n…（diff 太大，已截斷喺 {REVIEW_DIFF_MAX} 字）\n"
    return diff


def run_review(agent, diff, message):
    """→ (verdict, 報告文字)。verdict ∈ BLOCK / WARN / PASS / UNAVAILABLE"""
    reviewer = "claude" if agent == "codex" else "codex"
    argv, label = _reviewer_cmd(reviewer)
    if argv is None:
        return "UNAVAILABLE", f"{label}"
    payload = f"commit message: {message}\n\n<diff>\n{diff}\n</diff>\n"
    try:
        proc = subprocess.run(argv, input=payload, capture_output=True,
                              text=True, timeout=REVIEW_TIMEOUT, cwd="/tmp")
    except subprocess.TimeoutExpired:
        return "UNAVAILABLE", f"{label} 超過 {REVIEW_TIMEOUT}s 冇覆"
    except Exception as e:
        return "UNAVAILABLE", f"{label} 叫唔郁：{e}"
    out = (proc.stdout or "").strip()
    if proc.returncode != 0 and not out:
        err = (proc.stderr or "").strip().splitlines()
        tail = err[-1] if err else f"exit {proc.returncode}"
        return "UNAVAILABLE", f"{label} 出錯：{tail}"
    m = re.search(r"VERDICT:\s*(BLOCK|WARN|PASS)", out, re.I)
    if not m:
        return "UNAVAILABLE", f"{label} 覆咗嘢但解析唔到 VERDICT"
    return m.group(1).upper(), out


def review_gate(agent, base, remote, changed, deletions, token, message):
    """閘 3 主邏輯。→ True = 可以繼續推，False = BLOCK。

    `changed` 由 main() 計好傳入（純本機比對），確保呢個閘喺任何 GitHub 寫入之前行。
    """
    touched = list(changed) + list(deletions)
    code_changes = [p for p in touched if not DOC_ONLY_RE.search(p)]
    if not code_changes:
        print("   ⏭️  閘 3 跳過（今次全部係文檔改動，冇實質 code）")
        return True

    reviewer = "Claude" if agent == "codex" else "Codex"
    print(f"   🔍 閘 3：叫 {reviewer} review {len(code_changes)} 個 code 檔…", flush=True)
    diff = build_diff(base, remote, changed, deletions, token)
    if not diff.strip():
        print("   ⏭️  閘 3 跳過（整唔到 diff，可能全部係 binary）")
        return True

    verdict, report = run_review(agent, diff, message)
    state = _load_state()
    streak = int(state.get("review_fail_streak", 0))

    if verdict == "UNAVAILABLE":
        streak += 1
        _save_state(review_fail_streak=streak,
                    review_last_error=report,
                    review_last_error_at=datetime.datetime.now().isoformat(timespec="seconds"))
        print(f"   ⚠️  閘 3 叫唔郁 reviewer：{report}")
        if streak >= REVIEW_FAIL_LIMIT:
            print(f"   ⛔ 已經連續 {streak} 次叫唔郁 reviewer — 由 fail-open 轉 BLOCK。")
            print("      修好佢（多數係 `codex login`／`claude` 未登入），或者今次帶 --no-review。")
            return False
        print(f"   ▶️  Fail-open，照推（連續第 {streak}/{REVIEW_FAIL_LIMIT} 次；夠 "
              f"{REVIEW_FAIL_LIMIT} 次就會擋）")
        return True

    _save_state(review_fail_streak=0,
                review_last_verdict=verdict,
                review_last_at=datetime.datetime.now().isoformat(timespec="seconds"))
    body = "\n".join("      " + ln for ln in report.splitlines()[:12])
    if verdict == "BLOCK":
        print(f"   ⛔ 閘 3 BLOCK — {reviewer} 話有嘢要先修：\n{body}")
        print("      修好再推；真係要照推就帶 --no-review。")
        return False
    if verdict == "WARN":
        print(f"   ⚠️  閘 3 WARN（照推，但 {reviewer} 有意見）：\n{body}")
        return True
    print(f"   ✅ 閘 3 PASS（{reviewer}）")
    return True


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════
class Opts:
    def __init__(self):
        self.message = None
        self.files = None
        self.check = False
        self.force = False
        self.allow_deletions = False
        self.no_review = False


USAGE = ('用法：python3 scripts/github_push.py "commit message" '
         '[--files a.py …] [--allow-deletions] [--force] [--no-review]\n'
         '　　　python3 scripts/github_push.py --check')


def parse_args(argv):
    o = Opts()
    rest = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--check":
            o.check = True
        elif a == "--force":
            o.force = True
        elif a == "--allow-deletions":
            o.allow_deletions = True
        elif a == "--no-review":
            o.no_review = True
        elif a == "--files":
            # 只食到下一個 `--flag` 為止。舊版 `argv[i+1:]` + break 會將
            # `--force`／`--no-review` 當成檔名，令旗標靜靜失效（Codex review 捉到）。
            o.files = []
            j = i + 1
            while j < len(argv) and not argv[j].startswith("--"):
                if argv[j].strip():
                    o.files.append(argv[j].strip())
                j += 1
            if not o.files:
                raise SystemExit("❌ --files 後面要跟至少一個檔案路徑")
            i = j - 1
        elif a.startswith("--"):
            raise SystemExit(f"❌ 唔識嘅參數：{a}\n{USAGE}")
        else:
            rest.append(a)
        i += 1
    if o.check:
        return o
    if not rest or not rest[0].strip():
        raise SystemExit(USAGE)
    o.message = rest[0]
    return o


def _remote_head_info(owner, repo, token, sha):
    try:
        c = api("GET", f"/repos/{owner}/{repo}/commits/{sha}", token)
        d = c["commit"]["committer"]["date"]
        return f"{sha[:7]} · {d} · {c['commit']['message'].splitlines()[0][:60]}"
    except Exception:
        return sha[:7]


def do_check(owner, repo, token, base):
    """--check：開工前 preflight。唔推，只報告。"""
    agent, _ = _agent_label()
    print(f"🔎 Preflight — {os.path.basename(REPO)}（{agent}@{socket.gethostname().split('.')[0]}）")
    ref = api("GET", f"{base}/ref/heads/main", token, ok_statuses=(404, 409))
    if ref is None:
        print("   遠端係空 repo（未有 main）— 第一次 push 會 bootstrap。")
        return 0
    base_sha = ref["object"]["sha"]
    print(f"   遠端 HEAD：{_remote_head_info(owner, repo, token, base_sha)}")

    state = _load_state()
    last = _my_baseline(state)
    if last and last != base_sha:
        print(f"   ⚠️  遠端喺你上次見到之後變咗（{last[:7]} → {base_sha[:7]}）"
              f"— 另一部機／session 推過嘢。")
        print("      Google Drive sync 完未？未 sync 完就改嘢，你會覆蓋人哋。")
    elif last:
        print(f"   ✅ 遠端同 {_HOST} 上次同步嘅一樣（{last[:7]}）")
    else:
        print(f"   ℹ️  {_HOST} 未有呢個 repo 嘅 baseline。")

    base_tree = api("GET", f"{base}/commits/{base_sha}", token)["tree"]["sha"]
    remote = remote_tree_map(base, base_tree, token)
    local = working_files()
    local_set = set(local)
    modified = [p for p in local
                if remote.get(p) != git_blob_sha(open(os.path.join(REPO, p), "rb").read())]
    missing = [p for p in remote if p not in local_set]

    if not modified and not missing:
        # 完全一致 = 實證本機已經同步，可以安全更新 baseline。
        # （唔一致就唔准更新，否則 --check 會幫你抹走閘 2 個保護。）
        _record_baseline(base_sha)
        print("   ✅ 本機同遠端完全一致 — 可以安心開工（已更新 baseline）。")
        return 0
    if modified:
        print(f"   📝 本機有 {len(modified)} 個檔同遠端唔同：")
        for p in modified[:15]:
            print(f"      · {p}")
        if len(modified) > 15:
            print(f"      … 另外 {len(modified) - 15} 個")
    if missing:
        print(f"   🗑️  遠端有 {len(missing)} 個檔本機冇（如果而家推，呢啲會被刪）：")
        for p in missing[:15]:
            print(f"      · {p}")
        if len(missing) > 15:
            print(f"      … 另外 {len(missing) - 15} 個")
        if len(missing) > DELETION_LIMIT:
            print(f"      ⚠️  超過 {DELETION_LIMIT} 個 — 好大機會係 Drive 未 sync 完，"
                  f"唔好急住推，等 Drive 追返先。")
    return 0


def main():
    o = parse_args(sys.argv[1:])
    agent, prefix = _agent_label()

    remote_token, owner, repo = parse_remote(get_remote_url())
    if not owner:
        raise SystemExit("❌ 讀唔到 remote.origin.url")
    token = get_token(remote_token)
    if not token:
        raise SystemExit("❌ 揾唔到 GitHub token（.env GITHUB_TOKEN / 環境變數 / .gh-token）")

    base = f"/repos/{owner}/{repo}/git"

    if o.check:
        raise SystemExit(do_check(owner, repo, token, base))

    message = f"{prefix} {o.message}"

    # 404 = branch doesn't exist yet; 409 "Git Repository is empty." = brand-new repo.
    ref = api("GET", f"{base}/ref/heads/main", token, ok_statuses=(404, 409))
    is_empty_repo = ref is None
    if is_empty_repo:
        # 零 commit 嘅新 repo：remote tree 當空，全部檔案都係「新增」。
        # ⚠️ bootstrap 唔喺呢度做 —— 要等過晒三道閘先寫，否則閘 3 判 BLOCK
        # 都已經有個種子檔推咗上 GitHub（2026-08-16 閘 3 捉到）。
        base_sha, base_tree, remote = None, None, {}
    else:
        base_sha = ref["object"]["sha"]
        base_tree = api("GET", f"{base}/commits/{base_sha}", token)["tree"]["sha"]
        remote = remote_tree_map(base, base_tree, token)

        # ── 閘 2：SHA 閘（baseline 分機存，見 _my_baseline）──────────
        last = _my_baseline()
        if not last:
            print(f"ℹ️  閘 2：{_HOST} 未有呢個 repo 嘅 baseline（第一次推）— 今次跳過，之後就有得比")
        if last and last != base_sha and not o.force:
            print(f"⛔ 閘 2：遠端 SHA 喺 {_HOST} 上次同步之後變咗（{last[:7]} → {base_sha[:7]}）")
            print("   即係另一部機／另一個 session 喺你之後推過嘢，你手上份 base 係舊嘅。")
            print(f"   遠端 HEAD：{_remote_head_info(owner, repo, token, base_sha)}")
            print("   點做：先跑 `python3 scripts/github_push.py --check` 睇差異，")
            print("        等 Google Drive sync 完，確認你唔會覆蓋人哋嘅嘢，再帶 --force 推。")
            raise SystemExit(2)

    all_tracked = working_files()
    if o.files is None:
        local = all_tracked
    else:
        all_tracked_set = set(all_tracked)
        local, missing = [], []
        for p in o.files:
            rel = os.path.relpath(p, REPO) if os.path.isabs(p) else p
            rel = rel.replace(os.sep, "/")
            if rel in all_tracked_set:
                local.append(rel)
            else:
                missing.append(p)
        if missing:
            print(f"⚠️  以下 --files 路徑搵唔到／未追蹤／喺 .gitignore，已跳過：{', '.join(missing)}")
        if not local:
            raise SystemExit("❌ --files 指定嘅檔案全部搵唔到，冇嘢可以推")

    local_set = set(local)

    # 淨喺全量模式先掃刪除——filtered（--files）模式唔應該掂任何未列出嘅遠端檔案。
    deletions = [] if o.files is not None else [p for p in remote if p not in local_set]

    # ── 閘 1：刪檔閘 ──────────────────────────────────────────────
    if len(deletions) > DELETION_LIMIT and not o.allow_deletions:
        print(f"⛔ 閘 1：今次會刪走遠端 {len(deletions)} 個檔（上限 {DELETION_LIMIT}）")
        for p in deletions[:20]:
            print(f"     · {p}")
        if len(deletions) > 20:
            print(f"     … 另外 {len(deletions) - 20} 個")
        print("   最常見原因：Google Drive 未 sync 完，你部機仲未見到另一部機新增嘅檔。")
        print("   點做：等 Drive sync 完再跑一次；真係要刪就帶 --allow-deletions。")
        raise SystemExit(3)

    # 邊啲檔真係要上（純本機計算，零 API 寫入）——閘 3 要喺任何寫入之前睇呢批。
    changed = []
    for path in local:
        with open(os.path.join(REPO, path), "rb") as f:
            content = f.read()
        if remote.get(path) != git_blob_sha(content):
            changed.append(path)

    if not changed and not deletions:
        print("Nothing to push — 遠端已同步。")
        _record_baseline(base_sha)
        return

    # 2026-08-01：推之前一定列出檔案名單。見到唔係自己改嘅檔 → 停手（01-DISPATCH §7）。
    _names = changed + list(deletions)
    print(f"   準備推 {len(_names)} 個檔（{len(changed)} 更新 / {len(deletions)} 刪除）· {prefix}")
    for _p in _names[:15]:
        print(f"     · {_p}")
    if len(_names) > 15:
        print(f"     … 另外 {len(_names) - 15} 個")

    # ── 閘 3：交叉 review（一定要喺任何 GitHub 寫入之前）───────────
    if not o.no_review:
        if not review_gate(agent, base, remote, changed, deletions, token, o.message):
            raise SystemExit(4)

    # ══ 過晒三道閘，由呢度先開始寫 GitHub ══
    if is_empty_repo:
        # Git Data API 喺 main 未存在時乜都寫唔到（連 POST blobs 都 409），
        # 要先用 Contents API 種一個檔開 main。用家條 message 就係第一個 commit。
        with open(os.path.join(REPO, changed[0]), "rb") as f:
            bootstrap_empty_repo(owner, repo, token, changed[0], f.read(), message)
        print(f"   (空 repo 已 bootstrap，種子檔：{changed[0]})")
        base_sha = api("GET", f"{base}/ref/heads/main", token)["object"]["sha"]
        base_tree = api("GET", f"{base}/commits/{base_sha}", token)["tree"]["sha"]
        remote = remote_tree_map(base, base_tree, token)
        changed = [p for p in changed
                   if remote.get(p) != git_blob_sha(open(os.path.join(REPO, p), "rb").read())]
        if not changed:
            # 單檔 repo：bootstrap 就係唯一嗰個 commit，符合「一次 run＝一個 commit」。
            _record_baseline(base_sha)
            print(f"✅ Pushed to GitHub — {message} (首次 bootstrap，單檔)")
            print(f"   1 更新 / 0 刪除 · commit {base_sha[:7]}")
            return

    tree, uploaded = [], 0
    for path in changed:
        with open(os.path.join(REPO, path), "rb") as f:
            content = f.read()
        blob = api("POST", f"{base}/blobs", token, {
            "content": base64.b64encode(content).decode(),
            "encoding": "base64",
        })
        tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        uploaded += 1
    for path in deletions:
        tree.append({"path": path, "mode": "100644", "type": "blob", "sha": None})

    tree_body = {"tree": tree}
    if base_tree:
        tree_body["base_tree"] = base_tree
    new_tree = api("POST", f"{base}/trees", token, tree_body)

    commit_body = {"message": message, "tree": new_tree["sha"]}
    if base_sha:
        commit_body["parents"] = [base_sha]
    commit = api("POST", f"{base}/commits", token, commit_body)

    # bootstrap 之後 main 一定已經存在，兩條路都係 PATCH。
    api("PATCH", f"{base}/refs/heads/main", token, {"sha": commit["sha"]})

    _record_baseline(commit["sha"])
    print(f"✅ Pushed to GitHub — {message}" + (" (含首次 bootstrap)" if is_empty_repo else ""))
    print(f"   {uploaded} 更新 / {len(deletions)} 刪除 · commit {commit['sha'][:7]}")


if __name__ == "__main__":
    main()
