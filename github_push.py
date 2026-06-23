"""用 GitHub API (PAT) 自動 push 更新，唔需要本地 git config。"""

import os
import sys
import base64
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

TOKEN = os.getenv("GITHUB_TOKEN")
REPO  = os.getenv("GITHUB_REPO")       # e.g. "yourusername/sales-trainer"

SKIP = {".env", "genre_data.json", "__pycache__", ".DS_Store", "bot.log",
        "*.pyc", "*.pyo"}

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


def get_sha(path: str) -> str | None:
    resp = requests.get(
        f"https://api.github.com/repos/{REPO}/contents/{path}",
        headers=HEADERS, timeout=10
    )
    if resp.status_code == 200:
        return resp.json().get("sha")
    return None


def push_file(local_path: Path, repo_path: str, commit_msg: str):
    content = base64.b64encode(local_path.read_bytes()).decode()
    sha = get_sha(repo_path)
    payload = {"message": commit_msg, "content": content}
    if sha:
        payload["sha"] = sha
    resp = requests.put(
        f"https://api.github.com/repos/{REPO}/contents/{repo_path}",
        headers=HEADERS,
        data=json.dumps(payload),
        timeout=15,
    )
    if resp.status_code in (200, 201):
        print(f"✅ {repo_path}")
    else:
        print(f"❌ {repo_path}: {resp.status_code} {resp.text[:120]}")


def should_skip(name: str) -> bool:
    return name in SKIP or name.startswith(".") or name.endswith((".pyc", ".pyo", ".log"))


def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else "auto update"
    if not TOKEN or not REPO:
        print("❌ GITHUB_TOKEN / GITHUB_REPO 未設定（.env）")
        sys.exit(1)

    for f in sorted(BASE_DIR.iterdir()):
        if f.is_file() and not should_skip(f.name):
            push_file(f, f.name, msg)

    print(f"\n🎉 push 完成：{msg}")


if __name__ == "__main__":
    main()
