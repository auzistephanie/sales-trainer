"""共用工具函數：Redis I/O、Telegram 發送、session 管理。"""

import os
import requests
from pathlib import Path
from dotenv import load_dotenv
import json as _json

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

_STATS_KEY   = "sales_stats"
_SESSION_KEY = "sales_session"
_RECENT_KEY  = "sales_recent_dna"


def _redis_url():
    return os.getenv("UPSTASH_REDIS_REST_URL", "").rstrip("/")

def _redis_headers():
    return {"Authorization": f"Bearer {os.getenv('UPSTASH_REDIS_REST_TOKEN')}"}

def _redis_get(key: str):
    resp = requests.post(
        f"{_redis_url()}/",
        headers={**_redis_headers(), "Content-Type": "application/json"},
        json=["GET", key],
        timeout=10,
    )
    value = resp.json().get("result")
    return _json.loads(value) if value else None

def _redis_set(key: str, data, ex: int = None):
    cmd = ["SET", key, _json.dumps(data, ensure_ascii=False)]
    if ex:
        cmd += ["EX", ex]
    requests.post(
        f"{_redis_url()}/",
        headers={**_redis_headers(), "Content-Type": "application/json"},
        json=cmd,
        timeout=10,
    )

def _redis_del(key: str):
    requests.post(
        f"{_redis_url()}/",
        headers={**_redis_headers(), "Content-Type": "application/json"},
        json=["DEL", key],
        timeout=10,
    )


# ── Stats ─────────────────────────────────────────────────────────

def load_stats() -> dict:
    return _redis_get(_STATS_KEY) or {
        "objection_scores": {},
        "total_sessions": 0,
        "streak": {"last_date": "", "count": 0},
    }

def save_stats(data: dict):
    _redis_set(_STATS_KEY, data)


# ── Session（練習狀態，TTL 10 分鐘）──────────────────────────────

def load_session():
    return _redis_get(_SESSION_KEY)

def save_session(data: dict, ex: int = 600):
    _redis_set(_SESSION_KEY, data, ex=ex)

def clear_session():
    _redis_del(_SESSION_KEY)


# ── DNA 防重複 ────────────────────────────────────────────────────

def load_recent_dna() -> dict:
    return _redis_get(_RECENT_KEY) or {}

def save_recent_dna(data: dict):
    _redis_set(_RECENT_KEY, data)


# ── Telegram ──────────────────────────────────────────────────────

def _split_text(text: str, max_len: int = 4000) -> list:
    if len(text) <= max_len:
        return [text]
    chunks = []
    while len(text) > max_len:
        split_pos = text.rfind("\n\n", 0, max_len)
        if split_pos == -1:
            split_pos = text.rfind("\n", 0, max_len)
        if split_pos == -1:
            split_pos = max_len
        chunks.append(text[:split_pos].rstrip())
        text = text[split_pos:].lstrip()
    if text:
        chunks.append(text)
    return chunks


def send_telegram(text: str, reply_markup=None, max_retries: int = 3):
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram 設定缺失")
        return
    url    = f"https://api.telegram.org/bot{token}/sendMessage"
    chunks = _split_text(text)
    for idx, chunk in enumerate(chunks):
        payload = {"chat_id": chat_id, "text": chunk}
        if reply_markup and idx == len(chunks) - 1:
            payload["reply_markup"] = reply_markup
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(url, json=payload, timeout=15)
                if resp.ok:
                    print(f"Telegram 發送成功 chunk {idx+1}/{len(chunks)}")
                    break
                print(f"Telegram 失敗（第{attempt}次）: {resp.status_code}")
            except requests.RequestException as e:
                print(f"Telegram 異常（第{attempt}次）: {e}")
