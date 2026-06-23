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
    generate_scenario, evaluate_response, evaluate_strategy,
    OBJECTION_TYPES, INDUSTRIES, DIFFICULTY_LEVELS, STRATEGIES,
)
from utils import (
    load_stats, save_stats,
    load_session, save_session, clear_session,
    load_profile, save_profile,
    load_setup_session, save_setup_session, clear_setup_session,
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
        {"command": "help",      "description": "指令說明"},
        {"command": "mystatus", "description": "查看目前設定"},
        {"command": "setup",    "description": "更改我的背景設定（行業／公司／產品）"},
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


# ── Profile Setup ─────────────────────────────────────────────────

SETUP_INDUSTRIES = [
    ("🛡️", "保險", "保險（人壽／醫療）"),
    ("🏠", "地產", "地產代理"),
    ("💰", "財務投資", "財務策劃／投資產品"),
    ("💻", "B2B/SaaS", "B2B 服務／SaaS 軟件"),
    ("📚", "培訓教育", "培訓課程／教育"),
    ("🔗", "直銷/網絡", "直銷／網絡生意"),
]


def handle_setup_start(intro: bool = True):
    """Step 1：揀行業。intro=True 顯示歡迎語。"""
    keyboard = []
    row = []
    for i, (icon, short, _) in enumerate(SETUP_INDUSTRIES):
        row.append({"text": f"{icon} {short}", "callback_data": f"setup_ind_{i}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([{"text": "✏️ 自定行業", "callback_data": "setup_ind_custom"}])
    msg = (
        "👋 先設定你嘅 Sales 背景，令練習更貼近實際工作！\n\n🏭 你主要做邊個行業？"
        if intro else
        "🏭 揀你嘅行業："
    )
    send_telegram(msg, reply_markup={"inline_keyboard": keyboard})


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


def handle_industry_menu(prompt_text: str = "🏭 揀你嘅行業："):
    """顯示行業選擇 inline keyboard。"""
    keyboard = []
    row = []
    icons = ["🛡️", "🏠", "💰", "💻", "📚", "🔗"]
    short_names = ["保險", "地產", "財務投資", "B2B/SaaS", "培訓教育", "直銷/網絡"]
    for i, (icon, short) in enumerate(zip(icons, short_names)):
        row.append({"text": f"{icon} {short}", "callback_data": f"industry_pick_{i}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    send_telegram(prompt_text, reply_markup={"inline_keyboard": keyboard})


# ── 練習 Session ──────────────────────────────────────────────────

def build_strategy_keyboard():
    """生成策略選擇 inline keyboard。"""
    keyboard = []
    row = []
    for s in STRATEGIES:
        row.append({"text": s["label"], "callback_data": f"strategy_{s['key']}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([{"text": "✏️ 自由輸入", "callback_data": "strategy_freetext"}])
    return {"inline_keyboard": keyboard}


def start_practice(force_objection: str = None, force_industry: str = None, difficulty: str = None):
    # 用 profile 行業（除非明確指定）
    if not force_industry:
        profile = load_profile()
        force_industry = profile.get("industry")
    display, scenario = generate_scenario(force_objection, force_industry, difficulty)
    save_session({"state": "waiting_strategy", "scenario": scenario})
    send_telegram(display, reply_markup=build_strategy_keyboard())


def handle_strategy_pick(strategy_key: str):
    """處理用戶揀咗策略 button。"""
    session = load_session()
    if not session or session.get("state") not in ("waiting_strategy", "waiting_response"):
        send_telegram("唔係練習模式。用 /practice 開始新練習！")
        return

    scenario = session["scenario"]
    obj_name = scenario["objection"]["name"]
    clear_session()

    if strategy_key == "freetext":
        # 切換到自由輸入模式
        save_session({"state": "waiting_response", "scenario": scenario})
        send_telegram("✏️ 好，直接打出你嘅回應 ⬇️")
        return

    send_telegram("🤔 AI 評估緊你嘅策略選擇，稍等⋯⋯")
    feedback = evaluate_strategy(strategy_key, scenario, profile=load_profile())

    # 解析分數
    match = re.search(r"策略評估[：:]\s*([1-4])", feedback)
    score = int(match.group(1)) if match else None
    if score:
        record_score(obj_name, score)

    replay_kb = {"inline_keyboard": [
        [
            {"text": "🔄 再練一個",           "callback_data": "practice_new"},
            {"text": f"🎯 再練「{obj_name}」", "callback_data": f"drill_{obj_name}"},
        ],
        [
            {"text": "🏭 換行業",             "callback_data": "practice_change_industry"},
            {"text": "📊 睇進度",             "callback_data": "show_stats"},
        ],
    ]}
    send_telegram(feedback, reply_markup=replay_kb)


def handle_user_response(user_text: str):
    session = load_session()
    if not session or session.get("state") != "waiting_response":
        send_telegram("唔係練習模式。用 /practice 開始新練習！")
        return

    clear_session()
    scenario = session["scenario"]
    obj_name = scenario["objection"]["name"]

    send_telegram("🤔 AI 評估緊你嘅回應，稍等⋯⋯")
    feedback = evaluate_response(user_text, scenario, profile=load_profile())

    # 解析分數
    match = re.search(r"評分[：:]\s*([1-4])", feedback)
    score = int(match.group(1)) if match else None
    if score:
        record_score(obj_name, score)

    replay_kb = {"inline_keyboard": [
        [
            {"text": "🔄 再練一個",          "callback_data": "practice_new"},
            {"text": f"🎯 再練「{obj_name}」", "callback_data": f"drill_{obj_name}"},
        ],
        [
            {"text": "🏭 換行業",            "callback_data": "practice_change_industry"},
            {"text": "📊 睇進度",            "callback_data": "show_stats"},
        ],
    ]}
    send_telegram(feedback, reply_markup=replay_kb)


# ── Callback ──────────────────────────────────────────────────────

def handle_callback(cb: dict):
    data = cb.get("data", "")

    if data == "practice_new":
        answer_callback(cb["id"], "生成新場景⋯⋯")
        # 沿用偏好行業
        stats = load_stats()
        preferred = stats.get("preferred_industry")
        threading.Thread(
            target=start_practice,
            kwargs={"force_industry": preferred},
            daemon=True,
        ).start()

    elif data == "setup_ind_custom":
        answer_callback(cb["id"])
        save_setup_session({"state": "setup_industry_custom"})
        send_telegram("✏️ 打出你嘅行業（例如：美容、網絡行銷、汽車）：")

    elif data.startswith("setup_ind_"):
        idx = int(data[len("setup_ind_"):])
        if idx < len(SETUP_INDUSTRIES):
            _, _, full_name = SETUP_INDUSTRIES[idx]
            profile = load_profile()
            profile["industry"] = full_name
            save_profile(profile)
            stats = load_stats()
            stats["preferred_industry"] = full_name
            save_stats(stats)
            answer_callback(cb["id"], f"✅ {full_name}")
            save_setup_session({"state": "setup_company"})
            send_telegram(f"✅ 行業：{full_name}\n\n🏢 你係邊間公司 / 機構做嘅？（直接打名）")
        else:
            answer_callback(cb["id"], "出錯，請再試")

    elif data == "do_setup":
        answer_callback(cb["id"])
        clear_setup_session()
        handle_setup_start(intro=False)

    elif data == "practice_change_industry":
        answer_callback(cb["id"])
        handle_industry_menu("🔄 換行業——揀新嘅行業：")

    elif data.startswith("industry_pick_"):
        idx = int(data[len("industry_pick_"):])
        industry_list = [
            "保險（人壽／醫療）",
            "地產代理",
            "財務策劃／投資產品",
            "B2B 服務／SaaS 軟件",
            "培訓課程／教育",
            "直銷／網絡生意",
        ]
        chosen = industry_list[idx] if idx < len(industry_list) else None
        if chosen:
            stats = load_stats()
            stats["preferred_industry"] = chosen
            save_stats(stats)
            answer_callback(cb["id"], f"已選：{chosen}")
            threading.Thread(
                target=start_practice,
                kwargs={"force_industry": chosen},
                daemon=True,
            ).start()
        else:
            answer_callback(cb["id"], "揀取失敗，請再試")

    elif data == "show_stats":
        answer_callback(cb["id"])
        handle_stats()

    elif data.startswith("strategy_"):
        strategy_key = data[len("strategy_"):]
        answer_callback(cb["id"], "評估緊⋯⋯" if strategy_key != "freetext" else "自由輸入模式")
        threading.Thread(
            target=handle_strategy_pick,
            args=(strategy_key,),
            daemon=True,
        ).start()

    elif data.startswith("drill_"):
        obj_name = data[6:]
        answer_callback(cb["id"], f"生成「{obj_name}」場景⋯⋯")
        stats = load_stats()
        preferred = stats.get("preferred_industry")
        threading.Thread(
            target=start_practice,
            kwargs={"force_objection": obj_name, "force_industry": preferred},
            daemon=True,
        ).start()


# ── 指令處理 ──────────────────────────────────────────────────────

def cmd(text: str, command: str) -> bool:
    return text == command or text.startswith(command + "@") or text.startswith(command + " ")


def handle_message(text: str):
    # Setup session 中：非指令訊息 = 填寫公司 / 產品
    setup = load_setup_session()
    if setup and not text.startswith("/"):
        state = setup.get("state")
        if state == "setup_industry_custom":
            profile = load_profile()
            profile["industry"] = text.strip()
            save_profile(profile)
            stats = load_stats()
            stats["preferred_industry"] = text.strip()
            save_stats(stats)
            save_setup_session({"state": "setup_company"})
            send_telegram(f"✅ 行業：{text.strip()}\n\n🏢 你係邊間公司 / 機構做嘅？（直接打名）")
            return
        if state == "setup_company":
            profile = load_profile()
            profile["company"] = text.strip()
            save_profile(profile)
            save_setup_session({"state": "setup_product"})
            send_telegram(f"✅ 公司：{text.strip()}\n\n📦 你主要賣咩產品或服務？（直接打出來）")
            return
        elif state == "setup_product":
            profile = load_profile()
            profile["product"] = text.strip()
            save_profile(profile)
            clear_setup_session()
            send_telegram(
                f"✅ 設定完成！\n\n"
                f"🏭 行業：{profile.get('industry', '')}\n"
                f"🏢 公司：{profile.get('company', '')}\n"
                f"📦 產品：{text.strip()}\n\n"
                f"用 /practice 開始練習！"
            )
            return

    # 練習 session 中：非指令訊息 = 用戶回應
    session = load_session()
    if session and session.get("state") in ("waiting_response", "waiting_strategy") and not text.startswith("/"):
        log.info(f"練習回應: {text[:60]!r}")
        # waiting_strategy 狀態下直接打字，視作自由輸入回應
        if session.get("state") == "waiting_strategy":
            session["state"] = "waiting_response"
            save_session(session)
        threading.Thread(target=handle_user_response, args=(text,), daemon=True).start()
        return

    if cmd(text, "/setup"):
        clear_setup_session()
        handle_setup_start(intro=False)
        return

    if cmd(text, "/help") or cmd(text, "/start"):
        profile = load_profile()
        if not profile.get("industry"):
            handle_setup_start(intro=True)
            return
        send_telegram(
            "🥊 銷售話術訓練機器人\n\n"
            "/practice — 隨機練習一個場景\n"
            "/practice 初級／中級／高級 — 指定難度\n"
            "/drill — 針對特定拒絕類型\n"
            "/stats — 查看進度報告\n"
            "/streak — 練習連續天數\n"
            "/tip — 今日銷售技巧\n"
            "/setup — 更改我的背景設定\n\n"
            "💡 每日練習 5 分鐘，90 日後成交率會嚇親自己"
        )
        return

    if cmd(text, "/practice"):
        profile = load_profile()
        if not profile.get("industry"):
            handle_setup_start(intro=True)
            return

        parts = text.split(maxsplit=1)
        extra = parts[1].strip() if len(parts) > 1 else None
        diff  = extra if extra in DIFFICULTY_LEVELS else None

        industry = profile.get("industry")
        send_telegram(
            f"🎯 生成練習場景⋯⋯",
            reply_markup={"inline_keyboard": [[
                {"text": "⚙️ 改設定", "callback_data": "do_setup"},
            ]]}
        )
        threading.Thread(
            target=start_practice,
            kwargs={"difficulty": diff},
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

    if cmd(text, "/mystatus"):
        stats    = load_stats()
        industry = stats.get("preferred_industry", "未設定")
        total    = stats.get("total_sessions", 0)
        streak   = stats.get("streak", {}).get("count", 0)
        send_telegram(
            f"⚙️ 我的設定\n\n"
            f"🏭 偏好行業：{industry}\n"
            f"📊 總練習次數：{total}\n"
            f"🔥 連續天數：{streak}\n\n"
            f"換行業：用 /practice 然後撳「🔄 換行業」"
        )
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
