"""AI 面試教練 Bot — Vercel Webhook Handler (interview_trainer edition)"""
import sys, os, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import requests as req
from datetime import datetime, timedelta

from interview_trainer import (
    generate_scenario, evaluate_response, analyze_conversation,
    QUESTION_TYPES, INDUSTRIES, DIFFICULTY_LEVELS, MBTI_COACHING,
    get_daily_tip,
)
from utils import (
    load_stats, save_stats,
    load_session, save_session, clear_session,
    load_profile, save_profile,
    load_setup_session, save_setup_session, clear_setup_session,
    send_telegram,
)

app = Flask(__name__)
TOKEN = lambda: os.getenv("TELEGRAM_BOT_TOKEN")

FREE_SESSION_LIMIT = 5
UPGRADE_MSG = (
    "🎓 你已完成 {n} 次免費練習！\n\n"
    "升級 Premium 解鎖無限練習 + 詳細進度分析：\n"
    "👉 [加入等候名單](https://t.me/hkinterviewbot)（暫定 $68/月）\n\n"
    "或者繼續試用，每日送 1 次額外練習 🎁"
)

# ── 14 種行業選單 ─────────────────────────────────────────────────
SETUP_INDUSTRY_LIST = [
    ("💰", "金融/投行",    "金融／投資銀行"),
    ("💻", "科技/IT",      "科技／軟件開發"),
    ("📣", "市場/廣告",    "市場營銷／廣告"),
    ("🧩", "管理諮詢",     "管理諮詢"),
    ("🛍️", "零售/酒店",   "零售／酒店管理"),
    ("🚀", "初創",         "初創公司"),
    ("🏥", "醫療/健康科技", "醫療／藥劑／健康科技"),
    ("⚖️", "法律/合規",   "法律／合規"),
    ("👥", "人力資源",     "人力資源／招聘"),
    ("📚", "教育/培訓",    "教育／培訓"),
    ("🚚", "物流/供應鏈",  "物流／供應鏈"),
    ("🏗️", "地產/建築",  "地產／建築工程"),
    ("🎬", "傳媒/創意",   "傳媒／娛樂／創意"),
    ("🏛️", "政府/NGO",   "政府／NGO／公共服務"),
]

# MBTI 16種
MBTI_LIST = [
    "INTJ","INTP","ENTJ","ENTP",
    "INFJ","INFP","ENFJ","ENFP",
    "ISTJ","ISFJ","ESTJ","ESFJ",
    "ISTP","ISFP","ESTP","ESFP",
]


# ── 工具 ──────────────────────────────────────────────────────────

def answer_cb(cb_id, text=""):
    req.post(
        f"https://api.telegram.org/bot{TOKEN()}/answerCallbackQuery",
        json={"callback_query_id": cb_id, "text": text, "show_alert": False},
        timeout=5,
    )

def cmd(text, command):
    return text == command or text.startswith(command + " ") or text.startswith(command + "@")


# ── Stats ──────────────────────────────────────────────────────────

def record_score(qtype_name: str, score: int):
    data    = load_stats()
    scores  = data.setdefault("qtype_scores", {})
    history = scores.setdefault(qtype_name, [])
    history.append(score)
    scores[qtype_name] = history[-20:]
    data["total_sessions"] = data.get("total_sessions", 0) + 1

    today     = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    s = data.setdefault("streak", {"last_date": "", "count": 0})
    if s["last_date"] == today:
        pass
    elif s["last_date"] == yesterday:
        s["count"] += 1; s["last_date"] = today
    else:
        s["count"] = 1; s["last_date"] = today

    save_stats(data)


def check_free_limit() -> bool:
    data  = load_stats()
    total = data.get("total_sessions", 0)
    today_bonus = data.get("today_bonus_date") == datetime.now().strftime("%Y-%m-%d")
    return total < FREE_SESSION_LIMIT or today_bonus


def use_daily_bonus():
    data = load_stats()
    data["today_bonus_date"] = datetime.now().strftime("%Y-%m-%d")
    save_stats(data)


def handle_stats():
    data   = load_stats()
    scores = data.get("qtype_scores", {})
    total  = data.get("total_sessions", 0)
    streak = data.get("streak", {})

    if not scores:
        send_telegram("未有練習記錄，用 /practice 開始！")
        return

    ranked = sorted(
        [(n, sum(sc)/len(sc), len(sc)) for n, sc in scores.items() if sc],
        key=lambda x: x[1], reverse=True
    )
    profile = load_profile()
    header  = f"🎯 {profile.get('job_title','')}  🧠 {profile.get('mbti','')}" if profile else ""

    lines = ["📊 面試訓練進度"]
    if header.strip(): lines.append(header)
    lines.append(f"總練習：{total} 次  |  連續 {streak.get('count',0)} 日\n")
    lines.append("【各題型掌握度】")
    for name, avg, count in ranked:
        lines.append(f"{'█'*round(avg)}{'░'*(4-round(avg))}  {name}  {round(avg/4*100)}%（{count}次）")

    weak = [x for x in ranked if x[1] < 2.5]
    if weak:
        lines.append(f"\n⚠️ 薄弱項目：{', '.join(x[0] for x in weak[:3])}")
        lines.append("用 /drill 針對練習 👆")

    send_telegram("\n".join(lines), reply_markup={"inline_keyboard": [[
        {"text": "🎯 繼續練習", "callback_data": "practice_new"},
    ]]})


# ── Setup ────────────────────────────────────────────────────────

def send_industry_keyboard(intro=False):
    kb = []
    row = []
    for i, (icon, short, _) in enumerate(SETUP_INDUSTRY_LIST):
        row.append({"text": f"{icon} {short}", "callback_data": f"setup_ind_{i}"})
        if len(row) == 2:
            kb.append(row); row = []
    if row: kb.append(row)
    kb.append([{"text": "✏️ 自定行業", "callback_data": "setup_ind_custom"}])
    msg = "👋 歡迎！先設定背景令練習更貼近你。\n\n🏭 目標行業係？" if intro else "🏭 揀目標行業："
    send_telegram(msg, reply_markup={"inline_keyboard": kb})


def send_mbti_keyboard():
    kb = []
    for i in range(0, 16, 4):
        kb.append([{"text": t, "callback_data": f"setup_mbti_{t}"} for t in MBTI_LIST[i:i+4]])
    kb.append([{"text": "⏭️ 唔知 / 跳過", "callback_data": "setup_mbti_skip"}])
    send_telegram(
        "🧠 你嘅 MBTI？（唔知可跳過，之後 /setup 再改）\n"
        "唔識做測試？👉 https://www.16personalities.com/ch",
        reply_markup={"inline_keyboard": kb},
    )


def send_setup_done(profile, extra=""):
    send_telegram(
        f"✅ 設定完成！\n\n"
        f"🎯 目標職位：{profile.get('job_title','未設定')}\n"
        f"🏭 行業：{profile.get('industry','未設定')}\n"
        f"🧠 MBTI：{profile.get('mbti','未設定')}"
        f"{extra}\n\n"
        f"開始你嘅面試練習！",
        reply_markup={"inline_keyboard": [[{"text": "🎯 立即練習", "callback_data": "practice_new"}]]},
    )


# ── Practice ──────────────────────────────────────────────────────

def start_practice(force_qtype=None, force_industry=None, difficulty=None):
    if not check_free_limit():
        data  = load_stats()
        total = data.get("total_sessions", 0)
        send_telegram(
            UPGRADE_MSG.format(n=total),
            reply_markup={"inline_keyboard": [[
                {"text": "🎁 今日免費練習", "callback_data": "claim_bonus"},
                {"text": "📊 睇進度",       "callback_data": "show_stats"},
            ]]}
        )
        return

    profile = load_profile() or {}
    if not force_industry:
        force_industry = profile.get("industry")

    display, scenario = generate_scenario(force_qtype, force_industry, difficulty)
    save_session({"state": "waiting_response", "scenario": scenario})
    send_telegram(display)


def handle_user_response(user_text):
    session = load_session()
    if not session or session.get("state") != "waiting_response":
        send_telegram("唔係練習模式。用 /practice 開始！")
        return

    clear_session()
    scenario   = session["scenario"]
    qtype_name = scenario["qtype"]["name"]

    send_telegram("🤔 AI 評估緊你嘅回答，稍等⋯⋯")
    feedback = evaluate_response(user_text, scenario, profile=load_profile() or {})

    match = re.search(r"評分[：:]\s*([1-4])", feedback)
    if match:
        record_score(qtype_name, int(match.group(1)))

    send_telegram(feedback, reply_markup={"inline_keyboard": [
        [
            {"text": "🔄 再練一個",              "callback_data": "practice_new"},
            {"text": f"🎯 再練「{qtype_name}」", "callback_data": f"drill_{qtype_name}"},
        ],
        [
            {"text": "📊 睇進度",  "callback_data": "show_stats"},
            {"text": "💡 今日技巧", "callback_data": "show_tip"},
        ],
    ]})


def handle_drill_menu():
    kb = []
    row = []
    for q in QUESTION_TYPES:
        row.append({"text": q["name"], "callback_data": f"drill_{q['name']}"})
        if len(row) == 2:
            kb.append(row); row = []
    if row: kb.append(row)
    kb.append([{"text": "🎲 隨機場景", "callback_data": "practice_new"}])
    send_telegram("🎯 揀你想針對練習的題型：", reply_markup={"inline_keyboard": kb})


# ── Callback ──────────────────────────────────────────────────────

def handle_callback(cb):
    answer_cb(cb["id"])
    data = cb.get("data", "")

    if data == "practice_new":
        start_practice()

    elif data == "claim_bonus":
        use_daily_bonus()
        start_practice()

    elif data == "show_stats":
        handle_stats()

    elif data == "show_tip":
        send_telegram(f"💡 今日面試技巧\n\n{get_daily_tip()}")

    elif data == "setup_start":
        clear_setup_session()
        send_industry_keyboard(intro=False)

    elif data == "setup_ind_custom":
        save_setup_session({"state": "setup_industry_custom"})
        send_telegram("✏️ 打出你嘅目標行業（例如：航空、網絡安全、遊戲）：")

    elif data.startswith("setup_ind_"):
        idx = int(data[len("setup_ind_"):])
        if idx < len(SETUP_INDUSTRY_LIST):
            _, _, full_name = SETUP_INDUSTRY_LIST[idx]
            profile = load_profile() or {}
            profile["industry"] = full_name
            save_profile(profile)
            save_setup_session({"state": "setup_jobtitle"})
            send_telegram(f"✅ 行業：{full_name}\n\n🎯 你嘅目標職位係？（例如：Product Manager）")

    elif data.startswith("setup_mbti_"):
        mbti_val = data[len("setup_mbti_"):]
        profile  = load_profile() or {}
        if mbti_val != "skip":
            profile["mbti"] = mbti_val
            save_profile(profile)
            extra = ""
            if mbti_val in MBTI_COACHING:
                extra = f"\n\n💡 {mbti_val} 面試盲點：{MBTI_COACHING[mbti_val]['watch_out']}"
            clear_setup_session()
            send_setup_done(profile, extra=extra)
        else:
            clear_setup_session()
            send_setup_done(profile)

    elif data.startswith("drill_"):
        qtype_name = data[6:]
        start_practice(force_qtype=qtype_name)

    elif data == "review_start":
        save_session({"state": "waiting_review"})
        send_telegram(
            "📋 貼上你嘅真實面試問答記錄，AI 幫你分析失分點：\n\n"
            "（格式：面試官問：xxx\n我答：xxx）"
        )


# ── Message ───────────────────────────────────────────────────────

def handle_message(text):
    # Setup flow
    setup = load_setup_session()
    if setup and not text.startswith("/"):
        state = setup.get("state")

        if state == "setup_industry_custom":
            profile = load_profile() or {}
            profile["industry"] = text.strip()
            save_profile(profile)
            save_setup_session({"state": "setup_jobtitle"})
            send_telegram(f"✅ 行業：{text.strip()}\n\n🎯 你嘅目標職位係？")
            return

        if state == "setup_jobtitle":
            profile = load_profile() or {}
            profile["job_title"] = text.strip()
            save_profile(profile)
            save_setup_session({"state": "setup_mbti"})
            send_mbti_keyboard()
            return

        if state == "setup_mbti":
            mbti_input = text.strip().upper()
            if mbti_input in MBTI_COACHING:
                profile = load_profile() or {}
                profile["mbti"] = mbti_input
                save_profile(profile)
                clear_setup_session()
                extra = f"\n\n💡 {mbti_input} 面試盲點：{MBTI_COACHING[mbti_input]['watch_out']}"
                send_setup_done(profile, extra=extra)
            else:
                send_telegram("請從鍵盤揀選 MBTI，或者打「跳過」")
            return

    # Practice / Review session
    session = load_session()
    state   = session.get("state", "") if session else ""

    if state == "waiting_response" and not text.startswith("/"):
        handle_user_response(text)
        return

    if state == "waiting_review" and not text.startswith("/"):
        clear_session()
        profile = load_profile() or {}
        send_telegram("🔍 AI 分析緊你嘅面試對話，稍等⋯⋯")
        result = analyze_conversation(text, profile)
        send_telegram(result, reply_markup={"inline_keyboard": [[
            {"text": "🎯 繼續練習", "callback_data": "practice_new"},
        ]]})
        return

    # Commands
    if cmd(text, "/start") or cmd(text, "/help"):
        profile = load_profile()
        if not profile or (not profile.get("job_title") and not profile.get("industry")):
            send_industry_keyboard(intro=True)
            return
        send_telegram(
            "🎓 AI 面試教練\n\n"
            "/practice — 隨機面試練習\n"
            "/practice 初級／中級／高級 — 指定難度\n"
            "/drill — 針對特定題型練習\n"
            "/review — 貼真實面試答案，AI 分析\n"
            "/stats — 我的進度\n"
            "/streak — 練習連續天數\n"
            "/tip — 今日面試技巧\n"
            "/setup — 更改設定\n"
            "/mystatus — 我的設定\n\n"
            "💡 每日練習 10 分鐘，面試表現明顯提升"
        )
        return

    if cmd(text, "/setup"):
        clear_setup_session()
        send_industry_keyboard(intro=False)
        return

    if cmd(text, "/practice"):
        profile = load_profile()
        if not profile or (not profile.get("job_title") and not profile.get("industry")):
            send_industry_keyboard(intro=True)
            return
        parts = text.split(maxsplit=1)
        extra = parts[1].strip() if len(parts) > 1 else None
        diff  = extra if extra in DIFFICULTY_LEVELS else None
        send_telegram("🎯 生成面試場景⋯⋯")
        start_practice(difficulty=diff)
        return

    if cmd(text, "/drill"):
        handle_drill_menu()
        return

    if cmd(text, "/review"):
        save_session({"state": "waiting_review"})
        send_telegram(
            "📋 貼上你嘅真實面試問答記錄，AI 幫你分析失分點：\n\n"
            "（格式：面試官問：xxx\n我答：xxx）"
        )
        return

    if cmd(text, "/stats"):
        handle_stats()
        return

    if cmd(text, "/streak"):
        data   = load_stats()
        streak = data.get("streak", {})
        count  = streak.get("count", 0)
        total  = data.get("total_sessions", 0)
        emoji  = "🔥" if count >= 7 else "💪" if count >= 3 else "🌱"
        send_telegram(
            f"{emoji} 連續練習：{count} 日\n"
            f"總練習次數：{total} 次\n\n"
            f"每日練習，面試信心係咁升！"
        )
        return

    if cmd(text, "/tip"):
        send_telegram(f"💡 今日面試技巧\n\n{get_daily_tip()}")
        return

    if cmd(text, "/mystatus"):
        profile = load_profile() or {}
        data    = load_stats()
        total   = data.get("total_sessions", 0)
        streak  = data.get("streak", {}).get("count", 0)
        mbti    = profile.get("mbti", "未設定")
        note    = ""
        if profile.get("mbti") and profile["mbti"] in MBTI_COACHING:
            note = f"\n💡 面試盲點：{MBTI_COACHING[profile['mbti']]['watch_out']}"
        send_telegram(
            f"⚙️ 我的設定\n\n"
            f"🎯 目標職位：{profile.get('job_title','未設定')}\n"
            f"🏭 行業：{profile.get('industry','未設定')}\n"
            f"🧠 MBTI：{mbti}{note}\n\n"
            f"📊 總練習：{total} 次  🔥 連續：{streak} 日\n\n"
            f"更改設定：/setup",
            reply_markup={"inline_keyboard": [[{"text": "🎯 開始練習", "callback_data": "practice_new"}]]}
        )
        return

    # 未知輸入：引導
    profile = load_profile()
    if not profile or (not profile.get("job_title") and not profile.get("industry")):
        send_industry_keyboard(intro=True)
    else:
        send_telegram(
            "輸入 /practice 開始練習，/help 睇所有指令 😊",
            reply_markup={"inline_keyboard": [[{"text": "🎯 開始練習", "callback_data": "practice_new"}]]}
        )


# ── Routes ────────────────────────────────────────────────────────

@app.route("/api/webhook", methods=["POST"])
def webhook():
    update = request.json or {}
    if "callback_query" in update:
        handle_callback(update["callback_query"])
    elif "message" in update:
        text = update["message"].get("text", "").strip()
        if text:
            handle_message(text)
    return jsonify({"ok": True})


@app.route("/api/set_webhook", methods=["GET"])
def set_webhook():
    """部署後訪問呢個 URL 自動設定 Telegram webhook。"""
    host = request.host_url.rstrip("/")
    url  = f"{host}/api/webhook"
    resp = req.post(
        f"https://api.telegram.org/bot{TOKEN()}/setWebhook",
        json={"url": url, "allowed_updates": ["message", "callback_query"]},
        timeout=10,
    )
    return jsonify({"webhook_url": url, "telegram_response": resp.json()})


@app.route("/", methods=["GET"])
def health():
    return "AI Interview Coach Bot ✅", 200


if __name__ == "__main__":
    app.run(debug=False)
