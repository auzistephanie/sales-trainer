"""api/daily_check.py — Vercel cron（每日 10:00 HKT）：Job follow-up 提醒 + 逢週日求職週報"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from datetime import datetime, timedelta

from utils import load_jobs, load_stats, send_telegram

app = Flask(__name__)

STATUS_EMOJI = {
    "Applied":       "📝",
    "Phone Screen":  "📞",
    "1st Interview": "🤝",
    "2nd Interview": "🔁",
    "Offer":         "🎉",
    "Rejected":      "❌",
}
STALE_STATUSES = {"Applied", "Phone Screen"}
FOLLOWUP_DAYS  = 7


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None


def check_followups() -> int:
    jobs = load_jobs()
    now  = datetime.now()
    sent = 0
    for job in jobs:
        if job.get("status") not in STALE_STATUSES:
            continue
        snooze_until = _parse_date(job.get("snooze_until"))
        if snooze_until and now < snooze_until:
            continue
        last_touch = _parse_date(job.get("last_touch") or job.get("applied_date"))
        if not last_touch or (now - last_touch).days < FOLLOWUP_DAYS:
            continue
        emoji = STATUS_EMOJI.get(job["status"], "📝")
        days  = (now - last_touch).days
        send_telegram(
            f"🔔 Follow-up 提醒\n{emoji} *{job.get('company','')} — {job.get('role','')}*\n"
            f"狀態：{job['status']}　停留 {days} 日未郁",
            reply_markup={"inline_keyboard": [
                [{"text": "✅ 已 Follow-up", "callback_data": f"job_followup_{job['id']}"},
                 {"text": "🔄 更新狀態",      "callback_data": f"job_updatestatus_{job['id']}"}],
                [{"text": "⏰ Snooze 3 日",  "callback_data": f"job_snooze_{job['id']}"}],
            ]}
        )
        sent += 1
    return sent


def send_weekly_report():
    jobs     = load_jobs()
    now      = datetime.now()
    week_ago = now - timedelta(days=7)

    applied_week = [
        j for j in jobs
        if _parse_date(j.get("applied_date")) and _parse_date(j["applied_date"]) >= week_ago
    ]

    stats      = load_stats()
    daily_log  = stats.get("daily_log", {})
    score_log  = stats.get("score_log", [])
    status_log = stats.get("status_change_log", [])

    practice_week = sum(c for d, c in daily_log.items() if _parse_date(d) and _parse_date(d) >= week_ago)
    scores_week   = [e["score"] for e in score_log if _parse_date(e.get("date")) and _parse_date(e["date"]) >= week_ago]
    avg_week      = round(sum(scores_week) / len(scores_week), 1) if scores_week else None
    changes_week  = [e for e in status_log if _parse_date(e.get("date")) and _parse_date(e["date"]) >= week_ago]

    qtype_scores = stats.get("qtype_scores", {})
    ranked = sorted(
        [(n, sum(sc) / len(sc)) for n, sc in qtype_scores.items() if sc],
        key=lambda x: x[1],
    )
    weakest = ranked[0][0] if ranked else None

    lines = ["📊 求職週報（過去 7 日）", "", f"📝 新申請：{len(applied_week)} 份"]
    if changes_week:
        lines.append(f"🔄 狀態變化：{len(changes_week)} 次")
        for e in changes_week[-5:]:
            lines.append(f"　　{e.get('company','')} → {e.get('to','')}")
    practice_line = f"🎯 練習：{practice_week} 次"
    if avg_week is not None:
        practice_line += f"　平均分 {avg_week}/4"
    lines.append(practice_line)
    if weakest:
        lines.append(f"⚠️ 最弱題型：{weakest}")
    lines.append("\n加油！💪")

    send_telegram("\n".join(lines))


@app.route("/api/daily_check", methods=["GET", "POST"])
def daily_check():
    followups_sent = check_followups()
    is_sunday = datetime.now().weekday() == 6  # Monday=0 ... Sunday=6
    if is_sunday:
        send_weekly_report()
    return jsonify({"ok": True, "followups_sent": followups_sent, "weekly_report_sent": is_sunday})


if __name__ == "__main__":
    app.run(debug=True, port=5001)
