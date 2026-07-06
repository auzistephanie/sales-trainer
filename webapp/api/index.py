"""面試教練 App — Python AI API（Vercel Flask）。
純 AI 運算層：包 interview_trainer 函數，唔掂 DB／secret。
每個 request 帶 Supabase JWT，去 Supabase /auth/v1/user 驗證。
DB 讀寫喺前端用 supabase-js + RLS 做。"""
import sys, os, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "_lib"))

from flask import Flask, request, jsonify
import requests as req

from interview_trainer import (
    generate_scenario, evaluate_response,
    get_daily_tip,
    calculate_cv_health, format_cv_health_message,
    generate_salary_benchmark, parse_salary_input,
    calculate_ats_score, format_ats_message,
    generate_negotiate_response, extract_negotiate_reply, generate_negotiate_summary,
    generate_debrief,
)
from mbti_checker import MBTI_QUESTIONS, calculate_mbti, MBTI_QUICK_DESC

app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://cmtubaxlniglklmdwlzs.supabase.co")
SUPABASE_ANON = os.getenv(
    "SUPABASE_ANON_KEY",
    "sb_publishable_14eHJNNxAJC1arpj9xM58Q_2Z-EtEtG",
)


# ── auth：用 token 問 Supabase 攞 user，驗證有效性 ──────────────
def get_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1]
    try:
        r = req.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": SUPABASE_ANON},
            timeout=8,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[get_user] {e}")
    return None


def require_user():
    u = get_user()
    if not u:
        return None, (jsonify({"error": "unauthorized"}), 401)
    return u, None


def body():
    return request.get_json(silent=True) or {}


def parse_score(text: str) -> int:
    """由 evaluate_response 文字抽『評分：X／4』→ 0-100。
    容忍 markdown 星號／空格（AI 常寫成『評分：**3／4**』）。"""
    m = re.search(r"評分[:：\s\*]*([0-4])[\s\*]*[／/]\s*4", text or "")
    if m:
        return round(int(m.group(1)) / 4 * 100)
    return 70


# ── 練習 ──────────────────────────────────────────────────────
@app.route("/api/app/practice/start", methods=["POST"])
def practice_start():
    _, err = require_user()
    if err: return err
    b = body()
    import utils as _u
    _u.set_recent(b.get("recent") or {})   # 注入前端傳嚟嘅 recent（防重複）
    _display, s = generate_scenario(
        force_qtype=b.get("qtype"), force_industry=b.get("industry"),
        difficulty=b.get("difficulty"),
    )
    return jsonify({
        "question": s["qtype"]["example_q"],
        "hint": s["qtype"].get("tip"),
        "qtype": s["qtype"]["name"],
        "difficulty": s["difficulty"],
        "industry": s["industry"],
        "scenario": s,          # 完整 dict，answer 時原封送返
        "recent": _u.get_recent(),  # 更新後嘅 recent，前端存返 coach_recent_dna
    })


@app.route("/api/app/practice/answer", methods=["POST"])
def practice_answer():
    _, err = require_user()
    if err: return err
    b = body()
    scenario = b.get("scenario")
    answer = b.get("answer", "")
    profile = b.get("profile") or {}
    prof = {"mbti": profile.get("mbti")} if profile.get("mbti") else {}
    text = evaluate_response(answer, scenario, profile=prof)
    return jsonify({"score": parse_score(text), "feedback": text})


# ── 求職工具 ────────────────────────────────────────────────
@app.route("/api/app/cv/health", methods=["POST"])
def cv_health():
    _, err = require_user()
    if err: return err
    health = calculate_cv_health(body().get("cv_text", ""))
    return jsonify({"result": format_cv_health_message(health), "score": health["total"]})


@app.route("/api/app/salary", methods=["POST"])
def salary():
    _, err = require_user()
    if err: return err
    b = body()
    out = generate_salary_benchmark(
        b.get("role", ""), parse_salary_input(b.get("expected_salary", "")),
        b.get("industry", ""),
    )
    return jsonify({"result": out})


@app.route("/api/app/ats", methods=["POST"])
def ats():
    _, err = require_user()
    if err: return err
    b = body()
    res = calculate_ats_score(b.get("jd_text", ""), b.get("cv_text", ""))
    return jsonify({"result": format_ats_message(res)})


@app.route("/api/app/negotiate", methods=["POST"])
def negotiate():
    _, err = require_user()
    if err: return err
    b = body()
    text = generate_negotiate_response(
        b.get("offer_details", ""), b.get("user_message", ""),
        int(b.get("round_num", 1)), b.get("history") or [],
    )
    return jsonify({"result": text, "reply": extract_negotiate_reply(text)})


@app.route("/api/app/negotiate/summary", methods=["POST"])
def negotiate_summary():
    _, err = require_user()
    if err: return err
    b = body()
    return jsonify({"result": generate_negotiate_summary(b.get("history") or [])})


@app.route("/api/app/debrief", methods=["POST"])
def debrief():
    _, err = require_user()
    if err: return err
    b = body()
    out = generate_debrief(b.get("job_info") or {}, b.get("debrief_text", ""))
    return jsonify({"result": out})


@app.route("/api/app/tip", methods=["POST", "GET"])
def tip():
    _, err = require_user()
    if err: return err
    return jsonify({"result": get_daily_tip()})


# ── MBTI ──────────────────────────────────────────────────────
@app.route("/api/app/mbti/questions", methods=["POST", "GET"])
def mbti_questions():
    _, err = require_user()
    if err: return err
    qs = [
        {"id": q["id"], "dimension": q["dimension"],
         "question": q["question"], "a": q["a"], "b": q["b"]}
        for q in MBTI_QUESTIONS
    ]
    return jsonify({"questions": qs})


@app.route("/api/app/mbti/submit", methods=["POST"])
def mbti_submit():
    _, err = require_user()
    if err: return err
    answers = body().get("answers") or []
    res = calculate_mbti(answers)
    if not res:
        return jsonify({"error": "需要 20 個 A/B 答案"}), 400
    res["desc"] = MBTI_QUICK_DESC.get(res["mbti"], "")
    return jsonify(res)


@app.route("/api/app/health", methods=["GET"])
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=False)
