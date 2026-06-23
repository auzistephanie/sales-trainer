"""銷售話術訓練 Bot — Telegram 對話管理、指令路由、進度追蹤。"""

import logging
import logging.handlers
import os
import sys
import re
import time
import threading
import requests
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

load_dotenv(BASE_DIR / ".env")

_log_file = BASE_DIR / "bot.log"
_handler  = logging.handlers.RotatingFileHandler(
    _log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[_handler, logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

from sales_trainer import (
    generate_scenario, evaluate_response,
    OBJECTION_TYPES, INDUSTRIES, DIFFICULTY_LEVELS,
)
from utils import (
    load_stats, save_stats,
    load_session, save_session, clear_session,
    send_telegram,
)


# ── 基礎工具 ──────────────────────────────────────────────────────

def answer_callback(cb_id: str, text: str = ""):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    requests.post(
        f"https://api.telegram.org/bot{token}/answerCallbackQuery",
        json={"callback_query_id": cb_id, "text": text, "show_alert": False},
        timeout=10,
    )


def register_commands():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    commands = [
        {"command": "practice", "description": "隨機練習一個場景"},
        {"command": "drill",    "description": "針對特定拒絕類型練習"},
        {"command": "stats",    "description": "查看進度報告"},
        {"command": "streak",   "description": "練習連續天數"},
        {"command": "tip",      "description": "今日銷售技巧"},
        {"command": "help",     "description": "指令說明"},
    ]
    requests.post(
        f"https://api.telegram.org/bot{token}/setMyCommands",
        json={"commands": commands},
        timeout=10,
    )


# ── 統計記錄 ──────────────────────────────────────────────────────

def record_score(objection_name: str, score: int):
    data    = load_stats()
    scores  = data.setdefault("objection_scores", {})
    history = scores.setdefault(objection_name, [])
    history.append(score)
    scores[objection_name] = history[-20:]          # 保留最近 20 次
    data["total_sessions"] = data.get("total_sessions", 0) + 1

    # Streak 計算
    today     = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    streak    = data.setdefault("streak", {"last_date": "", "count": 0})
    if streak["last_date"] == today:
        pass                                        # 同日唔重複計
    elif streak["last_date"] == yesterday:
        streak["count"] += 1
        streak["last_date"] = today
    else:
        streak["count"]    = 1
        streak["last_date"] = today

    save_stats(data)
    avg = sum(history) / len(history)
    return avg, len(history)


# ── Stats 報告 ────────────────────────────────────────────────────

def handle_stats():
    data   = load_stats()
    scores = data.get("objection_scores", {})
    total  = data.get("total_sessions", 0)
    streak = data.get("streak", {})

    if not scores:
        send_telegram("未有練習記錄，用 /practice 開始第一次練習！")
        return

    ranked = sorted(
        [(name, sum(sc)/len(sc), len(sc)) for name, sc in scores.items() if sc],
        key=lambda x: x[1], reverse=True
    )

    lines = [
        f"📊 我的銷售訓練進度",
        f"總練習：{total} 次  |  連續 {streak.get('count', 0)} 日\n",
        "【各拒絕類型掌握度】",
    ]
    for name, avg, count in ranked:
        filled = "█" * round(avg)
        empty  = "░" * (4 - round(avg))
        pct    = round(avg / 4 * 100)
        lines.append(f"{filled}{empty}  {name}  {pct}%（{count}次）")

    weak   = [x for x in ranked if x[1] < 2.5]
    strong = [x for x in ranked if x[1] >= 3.5]

    if weak:
        lines.append(f"\n⚠️ 薄弱項目：{', '.join(x[0] for x in weak[:3])}")
        lines.append("用 /drill 針對練習 👆")
    if strong:
        lines.append(f"\n💪 已掌握：{', '.join(x[0] for x in strong[:3])}")

    send_telegram("\n".join(lines))


# ── 今日技巧 ──────────────────────────────────────────────────────

def handle_tip():
    import random
    obj = random.choice(OBJECTION_TYPES)
    send_telegram(
        f"💡 今日銷售技巧\n\n"
        f"【處理「{obj['name']}」】\n\n"
        f"{obj['tip']}\n\n"
        f"想練習這個場景？用 /drill 揀「{obj['name']}」"
    )


# ── Drill 選單 ────────────────────────────────────────────────────

def handle_drill_menu():
    keyboard = []
    row = []
    for i, obj in enumerate(OBJECTION_TYPES):
        row.append({"text": obj["name"], "callback_data": f"drill_{obj['name']}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([{"text": "🎲 隨機場景", "callback_data": "practice_new"}])
    send_telegram("🎯 選擇你想針對練習的拒絕類型：", reply_markup={"inline_keyboard": keyboard})


# ── 練習 Session ──────────────────────────────────────────────────

def start_practice(force_objection: str = None, force_industry: str = None, difficulty: str = None):
    display, scenario = generate_scenario(force_objection, force_industry, difficulty)
    save_session({"state": "waiting_response", "scenario": scenario})
    send_telegram(display)


def handle_user_response(user_text: str):
    session = load_session()
    if not session or session.get("state") != "waiting_response":
        send_telegram("唔係練習模式。用 /practice 開始新練習！")
        return

    clear_session()
    scenario = session["scenario"]
    obj_name = scenario["objection"]["name"]

    send_telegram("🤔 AI 評估緊你嘅回應，稍等⋯⋯")
    feedback = evaluate_response(user_text, scenario)

    # 解析分數
    match = re.search(r"評分[：:]\s*([1-4])", feedback)
    score = int(match.group(1)) if match else None
    if score:
        record_score(obj_name, score)

    replay_kb = {"inline_keyboard": [[
        {"text": "🔄 再練一個",          "callback_data": "practice_new"},
        {"text": f"🎯 再練「{obj_name}」", "callback_data": f"drill_{obj_name}"},
    ]]}
    send_telegram(feedback, reply_markup=replay_kb)


# ── Callback ──────────────────────────────────────────────────────

def handle_callback(cb: dict):
    data = cb.get("data", "")

    if data == "practice_new":
        answer_callback(cb["id"], "生成新場景⋯⋯")
        threading.Thread(target=start_practice, daemon=True).start()

    elif data.startswith("drill_"):
        obj_name = data[6:]
        answer_callback(cb["id"], f"生成「{obj_name}」場景⋯⋯")
        threading.Thread(
            target=start_practice,
            kwargs={"force_objection": obj_name},
            daemon=True,
        ).start()


# ── 指令處理 ──────────────────────────────────────────────────────

def cmd(text: str, command: str) -> bool:
    return text == command or text.startswith(command + "@") or text.startswith(command + " ")


def handle_message(text: str):
    # 練習 session 中：非指令訊息 = 用戶回應
    session = load_session()
    if session and session.get("state") == "waiting_response" and not text.startswith("/"):
        log.info(f"練習回應: {text[:60]!r}")
        threading.Thread(target=handle_user_response, args=(text,), daemon=True).start()
        return

    if cmd(text, "/help") or cmd(text, "/start"):
        send_telegram(
            "🥊 銷售話術訓練機器人\n\n"
            "/practice — 隨機練習一個場景\n"
            "/practice 初級／中級／高級 — 指定難度\n"
            "/practice 保險 — 指定行業\n"
            "/drill — 針對特定拒絕類型\n"
            "/stats — 查看進度報告\n"
            "/streak — 練習連續天數\n"
            "/tip — 今日銷售技巧\n\n"
            "💡 每日練習 5 分鐘，90 日後成交率會嚇親自己"
        )
        return

    if cmd(text, "/practice"):
        parts  = text.split(maxsplit=1)
        extra  = parts[1].strip() if len(parts) > 1 else None
        diff   = extra if extra in DIFFICULTY_LEVELS else None
        ind    = extra if extra and extra not in DIFFICULTY_LEVELS else None
        send_telegram("🎯 生成練習場景⋯⋯")
        threading.Thread(
            target=start_practice,
            kwargs={"force_industry": ind, "difficulty": diff},
            daemon=True,
        ).start()
        return

    if cmd(text, "/drill"):
        handle_drill_menu()
        return

    if cmd(text, "/stats"):
        handle_stats()
        return

    if cmd(text, "/streak"):
        data   = load_stats()
        streak = data.get("streak", {})
        total  = data.get("total_sessions", 0)
        count  = streak.get("count", 0)
        emoji  = "🔥" if count >= 7 else "💪" if count >= 3 else "🌱"
        send_telegram(
            f"{emoji} 連續練習：{count} 日\n"
            f"總練習次數：{total} 次\n\n"
            f"每日練習，成交率係咁升！"
        )
        return

    if cmd(text, "/tip"):
        handle_tip()
        return


# ── 主循環 ────────────────────────────────────────────────────────

def poll():
    register_commands()
    log.info(f"Sales Trainer Bot 啟動 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    url    = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/getUpdates"
    offset = None

    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message", "callback_query"], "offset": offset}
            resp   = requests.get(url, params=params, timeout=35)
            data   = resp.json()

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                if "callback_query" in update:
                    handle_callback(update["callback_query"])
                elif "message" in update:
                    text = update["message"].get("text", "").strip()
                    if text:
                        log.info(f"收到: {text[:60]!r}")
                        handle_message(text)

        except Exception as e:
            log.error(f"Poll error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    poll()
