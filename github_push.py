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

⚠️ 一次 run = 一個 commit = 一次 Vercel deployment（2026-07-02 教訓：舊版逐個檔案 PUT
會整十幾個 commit，一次 push 撞爆 Vercel 免費 plan「100 deployments/日」上限）。呢個 script
無論改幾多檔案，都係一個 tree + 一個 commit + 一次郁 ref，天生只觸發一次 build。
唔好喺短時間內連環 run，慳返 deployment 額度。

用法：
  python3 github_push.py "你的 commit message"

Token 來源：.env（GITHUB_TOKEN）→ 環境變數 GITHUB_TOKEN/GH_TOKEN → .gh-token 檔（gitignored）。
Token 只喺本機讀，唔會 print。
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

API = "https://api.github.com"
REPO = os.path.dirname(os.path.abspath(__file__))

# --- 2026-07-15 concurrent-push 事後可見警報（overlap 診斷 fix A，見
#     stephanie-personal CHANGELOG 2026-07-15）。Fail-silent，唔影響push行為，
#     remote永遠贏，本地照常上——純粹畀你事後喺log見到「可能撞咗」。 ---
_PUSH_STATE_DIR = os.path.join(os.path.dirname(REPO), "stephanie-personal", "scripts", ".push-state")
_PUSH_STATE_FILE = os.path.join(_PUSH_STATE_DIR, os.path.basename(REPO) + ".json")


def _check_concurrent_push(base_sha):
    try:
        if not os.path.isfile(_PUSH_STATE_FILE):
            return
        last = json.load(open(_PUSH_STATE_FILE))
        last_sha = last.get("last_seen_sha")
        if last_sha and last_sha != base_sha:
            print(f"⚠️ CONCURRENT-PUSH-DETECTED：remote SHA喺上個cycle之後變咗（{last_sha[:7]}→{base_sha[:7]}），可能有第二部機/session推過嘢")
    except Exception:
        pass


def _record_seen_sha(sha):
    try:
        os.makedirs(_PUSH_STATE_DIR, exist_ok=True)
        with open(_PUSH_STATE_FILE, "w") as f:
            json.dump({"last_seen_sha": sha}, f)
    except Exception:
        pass


if load_dotenv:
    load_dotenv(os.path.join(REPO, ".env"))


def run(args):
    # -c core.quotepath=false：非 ASCII（中文）檔名唔好被 octal-escape 做 "\346\...",
    # 否則 git ls-files 攞到嘅係字面 backslash-digit 文字，match 唔到真檔案，會被當刪咗。
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
        # user:token@ — the part after the colon is the token
        token = creds.split(":", 1)[1]
    elif creds and creds.startswith(_TOKEN_PREFIXES):
        # bare token@ (no username) — only treat as a token if it looks like one,
        # otherwise it's just a plain username (e.g. "auzistephanie@") and the
        # real token should come from .env / GITHUB_TOKEN / .gh-token instead
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
    return remote_token  # legacy fallback only — embedding tokens in remote URL is discouraged


def api(method, path, token, body=None):
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "github-push-script")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"❌ GitHub API {method} {path} -> {e.code}\n{e.read().decode()}")


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


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        raise SystemExit('用法：python3 github_push.py "commit message"')
    message = sys.argv[1]

    remote_token, owner, repo = parse_remote(get_remote_url())
    if not owner:
        raise SystemExit("❌ 讀唔到 remote.origin.url")
    token = get_token(remote_token)
    if not token:
        raise SystemExit("❌ 揾唔到 GitHub token（.env GITHUB_TOKEN / 環境變數 / .gh-token）")

    base = f"/repos/{owner}/{repo}/git"
    ref = api("GET", f"{base}/ref/heads/main", token)
    base_sha = ref["object"]["sha"]
    _check_concurrent_push(base_sha)
    base_tree = api("GET", f"{base}/commits/{base_sha}", token)["tree"]["sha"]
    remote = remote_tree_map(base, base_tree, token)

    local = working_files()
    local_set = set(local)

    tree, uploaded = [], 0
    for path in local:
        with open(os.path.join(REPO, path), "rb") as f:
            content = f.read()
        if remote.get(path) == git_blob_sha(content):
            continue  # 遠端已一致，唔使上
        blob = api("POST", f"{base}/blobs", token, {
            "content": base64.b64encode(content).decode(),
            "encoding": "base64",
        })
        tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        uploaded += 1

    deletions = [p for p in remote if p not in local_set]
    for path in deletions:
        tree.append({"path": path, "mode": "100644", "type": "blob", "sha": None})

    if not tree:
        print("Nothing to push — 遠端已同步。")
        _record_seen_sha(base_sha)
        return

    new_tree = api("POST", f"{base}/trees", token, {"base_tree": base_tree, "tree": tree})
    commit = api("POST", f"{base}/commits", token, {
        "message": message, "tree": new_tree["sha"], "parents": [base_sha],
    })
    api("PATCH", f"{base}/refs/heads/main", token, {"sha": commit["sha"]})

    _record_seen_sha(commit["sha"])
    print(f"✅ Pushed to GitHub — {message}")
    print(f"   {uploaded} 更新 / {len(deletions)} 刪除 · commit {commit['sha'][:7]}")


if __name__ == "__main__":
    main()
