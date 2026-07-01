"""用 GitHub Git Data API 一次 push 全部改動 —— 只整「一個 commit」。

⚠️ 點解要噉寫（2026-07-02）：
舊版用 Contents API 逐個檔案 PUT，每個檔案 = 一個 commit，一次 run loop 晒成個 repo
= 十幾個 commit = 十幾個 Vercel deployment，好易爆 Vercel 免費 plan「100 deployments/日」上限。
新版砌一個 tree + 一個 commit + 郁一次 ref，無論改幾多檔案都只觸發「一次」Vercel build。
"""

from __future__ import annotations
import os, sys, base64, json, requests
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

TOKEN = os.getenv("GITHUB_TOKEN")
REPO  = os.getenv("GITHUB_REPO")

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}
API = f"https://api.github.com/repos/{REPO}"


def should_skip(f: Path) -> bool:
    if any(p in ("__pycache__", ".git", "node_modules") for p in f.parts):
        return True
    if f.name in (".env", ".DS_Store", "bot.log", "bot_error.log", "genre_data.json"):
        return True
    if f.name.startswith("."):
        return True
    return f.suffix in (".pyc", ".pyo", ".log")


def gh(method: str, path: str, **kw):
    r = requests.request(method, f"{API}{path}", headers=HEADERS, timeout=30, **kw)
    if r.status_code >= 300:
        print(f"❌ {method} {path}: {r.status_code} {r.text[:200]}")
        r.raise_for_status()
    return r.json()


def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else "auto update"
    if not TOKEN or not REPO:
        print("❌ GITHUB_TOKEN / GITHUB_REPO 未設定（.env）")
        sys.exit(1)

    # 1. default branch + 現時 HEAD commit / tree
    branch = gh("GET", "").get("default_branch", "main")
    ref = gh("GET", f"/git/ref/heads/{branch}")
    base_commit_sha = ref["object"]["sha"]
    base_tree_sha = gh("GET", f"/git/commits/{base_commit_sha}")["tree"]["sha"]

    # 2. 為每個檔案造 blob，砌 tree entries
    tree = []
    for f in sorted(BASE_DIR.rglob("*")):
        if not f.is_file() or should_skip(f):
            continue
        blob = gh("POST", "/git/blobs", data=json.dumps({
            "content": base64.b64encode(f.read_bytes()).decode(),
            "encoding": "base64",
        }))
        tree.append({
            "path": f.relative_to(BASE_DIR).as_posix(),
            "mode": "100644",
            "type": "blob",
            "sha": blob["sha"],
        })

    # 3. 一個 tree → 一個 commit → 郁 ref（= 一次 Vercel deploy）
    new_tree = gh("POST", "/git/trees", data=json.dumps({
        "base_tree": base_tree_sha, "tree": tree,
    }))
    new_commit = gh("POST", "/git/commits", data=json.dumps({
        "message": msg, "tree": new_tree["sha"], "parents": [base_commit_sha],
    }))
    gh("PATCH", f"/git/refs/heads/{branch}", data=json.dumps({"sha": new_commit["sha"]}))

    print(f"🎉 push 完成（單一 commit {new_commit['sha'][:7]}）：{msg}")


if __name__ == "__main__":
    main()
