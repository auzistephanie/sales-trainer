"""Web app 用嘅精簡 utils shim。
interview_trainer.py 只 import 呢三個；app 版本唔用 Redis / Telegram，
場景防重複改為每次隨機（recent 由前端／Postgres 管，AI 層唔需要）。"""


def load_recent_dna() -> dict:
    return {}


def save_recent_dna(data: dict):
    pass


def send_telegram(*args, **kwargs):
    pass
