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

用法：
  python3 scripts/github_push.py "你的 commit message"

Token 來源：.env（GITHUB_TOKEN）→ 環境變數 GITHUB_TOKEN/GH_TOKEN → .gh-token 檔（gitignored）。
Token 只喺本機讀，唔會 print。

備註（中文檔名）：working_files() 靠 `git ls-files`，如遇非 ASCII 檔名會被 git octal-escape，
所以呢個 script 全程用 `-c core.quotepath=false` 行 git 指令，避免 path 變成字面 "\346\..." 亂碼。
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
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if load_dotenv:
    load_dotenv(os.path.join(REPO, ".env"))


def run(args):
    # -c core.quotepath=false：非 ASCII（中文）檔名唔好被 octal-escape 做 "\344\275..."，
    # 否則落面 path 攞到嘅係字面 backslash-digit 文字，open() 揾唔到個真檔案。
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


def api(method, path, token, body=None, ok_statuses=()):
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
        if e.code in ok_statuses:
            return None  # caller handles this expected case (e.g. brand-new empty repo)
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


def sync_local_head(commit_sha, owner, repo, token):
    """Push 成功後，fast-forward 本地 main 到啱 push 嘅 commit，
    令 git status 唔再顯示假改動（本 script 經 GitHub API 寫入、唔會 advance 本地 HEAD）。
    token 只用喺 fetch URL、唔寫入任何檔、唔 print；任何一步失敗都唔阻塞
    （已 push 上 GitHub 嘅內容唔受影響）。用 --mixed：只郁 HEAD+index，唔掂 working tree。"""
    auth_url = f"https://{token}@github.com/{owner}/{repo}.git"
    if run(["git", "fetch", auth_url, "main"]).returncode != 0:
        print("   (本地 HEAD 未同步：fetch 失敗，唔影響已 push 內容)")
        return
    # 順手更新 refs/remotes/origin/main，等 `git status` 嘅 ahead/behind 都準——
    # 唔係淨係 HEAD 啱咗但 tracking ref 舊咗，繼續呃人話「ahead N」。
    run(["git", "update-ref", "refs/remotes/origin/main", commit_sha])
    if run(["git", "reset", "--mixed", commit_sha]).returncode == 0:
        print("   本地 HEAD 已對齊 remote — git status 現時乾淨 ✨")
    else:
        print("   (本地 HEAD reset 失敗，唔影響已 push 內容)")


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        raise SystemExit('用法：python3 scripts/github_push.py "commit message"')
    message = sys.argv[1]

    remote_token, owner, repo = parse_remote(get_remote_url())
    if not owner:
        raise SystemExit("❌ 讀唔到 remote.origin.url")
    token = get_token(remote_token)
    if not token:
        raise SystemExit("❌ 揾唔到 GitHub token（.env GITHUB_TOKEN / 環境變數 / .gh-token）")

    base = f"/repos/{owner}/{repo}/git"
    # 404 = branch doesn't exist yet; 409 "Git Repository is empty." = brand-new repo,
    # zero commits — GitHub returns either depending on repo state. Both mean: bootstrap.
    ref = api("GET", f"{base}/ref/heads/main", token, ok_statuses=(404, 409))
    is_empty_repo = ref is None
    if is_empty_repo:
        base_sha, base_tree, remote = None, None, {}
    else:
        base_sha = ref["object"]["sha"]
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
        if is_empty_repo:
            print("Nothing to push — 冇任何檔案（空 repo 亦冇本地檔案可以 bootstrap）。")
            return
        print("Nothing to push — 遠端已同步。")
        sync_local_head(base_sha, owner, repo, token)
        return

    tree_body = {"tree": tree}
    if base_tree:
        tree_body["base_tree"] = base_tree
    new_tree = api("POST", f"{base}/trees", token, tree_body)

    commit_body = {"message": message, "tree": new_tree["sha"]}
    if base_sha:
        commit_body["parents"] = [base_sha]
    commit = api("POST", f"{base}/commits", token, commit_body)

    if is_empty_repo:
        # Repo has no refs at all yet — create refs/heads/main instead of PATCHing it.
        api("POST", f"{base}/refs", token, {"ref": "refs/heads/main", "sha": commit["sha"]})
    else:
        api("PATCH", f"{base}/refs/heads/main", token, {"sha": commit["sha"]})

    print(f"✅ Pushed to GitHub — {message}" + (" (首次 bootstrap)" if is_empty_repo else ""))
    print(f"   {uploaded} 更新 / {len(deletions)} 刪除 · commit {commit['sha'][:7]}")
    sync_local_head(commit["sha"], owner, repo, token)


if __name__ == "__main__":
    main()
