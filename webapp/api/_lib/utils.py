"""Web app 用嘅精簡 utils shim。
interview_trainer.py 只 import 呢三個；app 版本唔用 Redis / Telegram。
場景防重複（recent_dna）改為每 request 由前端傳入 → 用 contextvar 傳遞 →
generate_scenario 內部 load/save 都指返呢個 contextvar，最後 API 讀返傳畀前端存 Postgres。
contextvar 令每個 request 隔離，唔會 warm-instance 撞。"""
import contextvars

_recent = contextvars.ContextVar("coach_recent_dna", default=None)


def load_recent_dna() -> dict:
    v = _recent.get()
    return dict(v) if v else {}


def save_recent_dna(data: dict):
    _recent.set(dict(data) if data else {})


def set_recent(data: dict):
    """API 喺 request 開始時注入前端傳嚟嘅 recent。"""
    _recent.set(dict(data) if data else {})


def get_recent() -> dict:
    """API 喺 generate 之後讀返更新咗嘅 recent，傳畀前端存。"""
    v = _recent.get()
    return dict(v) if v else {}


def send_telegram(*args, **kwargs):
    pass
