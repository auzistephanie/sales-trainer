"""共用工具函數：Redis I/O、Telegram 發送、session 管理。"""

from __future__ import annotations
import os
import requests
from pathlib import Path
from dotenv import load_dotenv
import json as _json

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

_STATS_KEY   = "interview_stats"
_SESSION_KEY = "interview_session"
_RECENT_KEY  = "interview_recent_dna"

# 動態 chat_id（webhook 每次 request 開頭設定）
_current_chat_id: str | None = None

def set_current_chat_id(chat_id):
    global _current_chat_id
    _current_chat_id = str(chat_id)


def _redis_url():
    return os.getenv("UPSTASH_REDIS_REST_URL", "").rstrip("/")

def _redis_headers():
    return {"Authorization": f"Bearer {os.getenv('UPSTASH_REDIS_REST_TOKEN')}"}

def _redis_get(key: str):
    resp = requests.post(
        f"{_redis_url()}/",
        headers={**_redis_headers(), "Content-Type": "application/json"},
        json=["GET", key], timeout=10,
    )
    value = resp.json().get("result")
    return _json.loads(value) if value else None

def _redis_set(key: str, data, ex: int = None):
    cmd = ["SET", key, _json.dumps(data, ensure_ascii=False)]
    if ex: cmd += ["EX", ex]
    requests.post(f"{_redis_url()}/",
        headers={**_redis_headers(), "Content-Type": "application/json"},
        json=cmd, timeout=10)

def _redis_del(key: str):
    requests.post(f"{_redis_url()}/",
        headers={**_redis_headers(), "Content-Type": "application/json"},
        json=["DEL", key], timeout=10)

# ── Stats ─────────────────────────────────────────────────────────

def load_stats() -> dict:
    return _redis_get(_STATS_KEY) or {"qtype_scores": {}, "total_sessions": 0, "streak": {"last_date": "", "count": 0}}

def save_stats(data: dict): _redis_set(_STATS_KEY, data)


# ── Session ───────────────────────────────────────────────────────

def load_session(): return _redis_get(_SESSION_KEY)
def save_session(data: dict, ex: int = 600): _redis_set(_SESSION_KEY, data, ex=ex)
def clear_session(): _redis_del(_SESSION_KEY)


# ── DNA 防重複 ────────────────────────────────────────────────────

def load_recent_dna() -> dict: return _redis_get(_RECENT_KEY) or {}
def save_recent_dna(data: dict): _redis_set(_RECENT_KEY, data)


# ── Profile / Setup Session ───────────────────────────────────────

def load_profile() -> dict: return _redis_get("interview_profile") or {}
def save_profile(data: dict): _redis_set("interview_profile", data)

def load_setup_session() -> dict: return _redis_get("interview_setup_session") or {}
def save_setup_session(data: dict): _redis_set("interview_setup_session", data, ex=600)
def clear_setup_session(): _redis_del("interview_setup_session")


# ── CV 全文儲存 ───────────────────────────────────────────────────

def load_cv_text() -> str: return _redis_get("interview_cv_text") or ""
def save_cv_text(text: str): _redis_set("interview_cv_text", text)


# ── JD Session（link/text → Cover Letter / CV 流程）──────────────

def load_jd_session() -> dict: return _redis_get("interview_jd_session") or {}
def save_jd_session(data: dict): _redis_set("interview_jd_session", data, ex=900)
def clear_jd_session(): _redis_del("interview_jd_session")


# ── Job Application Tracker ───────────────────────────────────────

def load_jobs() -> list: return _redis_get("interview_jobs") or []
def save_jobs(data: list): _redis_set("interview_jobs", data)

def load_addjob_session() -> dict: return _redis_get("interview_addjob_session") or {}
def save_addjob_session(data: dict): _redis_set("interview_addjob_session", data, ex=600)
def clear_addjob_session(): _redis_del("interview_addjob_session")


# ── Telegram ──────────────────────────────────────────────────────

def _split_text(text: str, max_len: int = 4000) -> list:
    if len(text) <= max_len: return [text]
    chunks = []
    while len(text) > max_len:
        pos = text.rfind("\n\n", 0, max_len)
        if pos == -1: pos = text.rfind("\n", 0, max_len)
        if pos == -1: pos = max_len
        chunks.append(text[:pos].rstrip()); text = text[pos:].lstrip()
    if text: chunks.append(text)
    return chunks

def upload_to_drive(file_bytes: bytes, filename: str) -> str:
    """Upload .docx to Google Drive, return shareable link. Returns '' on failure."""
    import json as _j2, io as _io2
    creds_raw = os.getenv("GOOGLE_CREDENTIALS", "")
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    if not creds_raw or not folder_id:
        print("upload_to_drive: missing GOOGLE_CREDENTIALS or GOOGLE_DRIVE_FOLDER_ID")
        return ""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload
        creds = service_account.Credentials.from_service_account_info(
            _j2.loads(creds_raw),
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        svc = build("drive", "v3", credentials=creds)
        meta = {"name": filename, "parents": [folder_id]}
        media = MediaIoBaseUpload(
            _io2.BytesIO(file_bytes),
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        f = svc.files().create(body=meta, media_body=media, fields="id").execute()
        fid = f.get("id")
        svc.permissions().create(fileId=fid, body={"type": "anyone", "role": "reader"}).execute()
        return f"https://drive.google.com/file/d/{fid}/view"
    except Exception as e:
        print(f"upload_to_drive failed: {e}")
        return ""


def send_document(file_bytes: bytes, filename: str, caption: str = ""):
    """Send a file (e.g. .docx) to the current Telegram chat (fallback)."""
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = _current_chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    url  = f"https://api.telegram.org/bot{token}/sendDocument"
    data = {"chat_id": chat_id}
    if caption: data["caption"] = caption
    try:
        requests.post(url, data=data, files={"document": (filename, file_bytes)}, timeout=30)
    except requests.RequestException as e:
        print(f"send_document 失敗: {e}")


def send_telegram(text: str, reply_markup=None, max_retries: int = 3):
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    # 優先用動態 chat_id（webhook），fallback 去 env var（本地 polling）
    chat_id = _current_chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(f"Telegram 設定缺失 token={bool(token)} chat_id={chat_id}")
        return
    url    = f"https://api.telegram.org/bot{token}/sendMessage"
    chunks = _split_text(text)
    for idx, chunk in enumerate(chunks):
        payload = {"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"}
        if reply_markup and idx == len(chunks) - 1:
            payload["reply_markup"] = reply_markup
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(url, json=payload, timeout=15)
                if resp.ok: break
                # Markdown 解析錯誤時 fallback 純文字
                if resp.status_code == 400:
                    payload.pop("parse_mode", None)
                    resp2 = requests.post(url, json=payload, timeout=15)
                    if resp2.ok: break
                print(f"Telegram 失敗（第{attempt}次）: {resp.status_code} {resp.text[:100]}")
            except requests.RequestException as e:
                print(f"Telegram 異常（第{attempt}次）: {e}")
