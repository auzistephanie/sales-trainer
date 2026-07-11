"""api/daily_check.py — Vercel cron（每日 10:00 HKT）：Job follow-up 提醒 + 逢週日求職週報 + 自動搵工推送"""
import sys, os, json, uuid
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import requests as req
from datetime import datetime, timedelta

from utils import (
    load_jobs, load_stats, load_profile, send_telegram,
    _redis_get, _redis_set, _redis_del,
)

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


# ── 自動搵工推送（JobsDB scan，2026-07-03）────────────────────────

JOBSDB_SEARCH_KEYWORDS = ["education", "education coordinator", "edtech"]
MAX_JOBS_PUSHED_PER_DAY = 3
SEEN_JOBS_KEY = "seen_scanned_jobs"
SCANNED_JOB_TTL = 14 * 24 * 3600  # 14 日


def _fetch_listing_via_jina(url: str) -> str:
    """抓 JobsDB 搜尋結果頁（用 Jina Reader，連 X-With-Links-Summary 拎返職位連結）。"""
    jina_key = os.environ.get("JINA_API_KEY", "").strip()
    headers = {
        "Accept": "text/plain",
        "X-Return-Format": "markdown",
        "X-With-Links-Summary": "true",
    }
    if jina_key:
        headers["Authorization"] = f"Bearer {jina_key}"
    try:
        resp = req.get(f"https://r.jina.ai/{url}", headers=headers, timeout=45)
        if resp.ok and len(resp.text) > 200:
            return resp.text[:6000]
        print(f"[job_scan] fetch status={resp.status_code} len={len(resp.text)} url={url}")
    except Exception as e:
        print(f"[job_scan] fetch failed url={url}: {e}")
    return ""


def _load_seen_jobs() -> set:
    return set(_redis_get(SEEN_JOBS_KEY) or [])


def _save_seen_jobs(seen: set):
    _redis_set(SEEN_JOBS_KEY, list(seen)[-500:])


def _rank_and_extract_jobs(listings_text: str, profile: dict, seen: set) -> list:
    """用 DeepSeek 由掃描到嘅搜尋結果原始文字揀最啱 profile 嘅職位。"""
    from openai import OpenAI
    ai_client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
    prompt = f"""你係求職顧問。以下係 JobsDB 搜尋結果頁面嘅原始內容（可能包含多個搜尋關鍵字嘅結果，加埋頁尾嘅連結清單）。
根據呢個求職者嘅背景，揀出最啱嘅職位空缺（最多 5 個，冇夠啱嘅可以少過 5 個甚至 0 個，唔好夾硬揀）。

【求職者背景】
目標職位：{profile.get('job_title', '未設定')}
行業：{profile.get('industry', '未設定')}
期望月薪：{profile.get('expected_salary', '未設定')} {profile.get('salary_currency', '')}

【搜尋結果原始內容】
{listings_text[:12000]}

只輸出 JSON array，每個 object 要有：
- title：職位名稱
- company：公司名稱
- url：從內容嘅連結清單揀返嗰個職位最相關嘅完整連結（唔好作連結，抽唔到就留空字串）
- reason：一句話講點解啱佢

唔要任何其他文字或 markdown code block。"""
    try:
        r = ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000,
        )
        content = r.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        jobs = json.loads(content)
        if not isinstance(jobs, list):
            return []
    except Exception as e:
        print(f"[job_scan] ranking failed: {e}")
        return []

    out = []
    for j in jobs:
        if not isinstance(j, dict):
            continue
        title, company = j.get("title", "").strip(), j.get("company", "").strip()
        if not title:
            continue
        key = f"{title.lower()}|{company.lower()}"
        if key in seen:
            continue
        out.append({
            "title": title, "company": company,
            "url": j.get("url", "").strip(), "reason": j.get("reason", "").strip(),
        })
    return out


def scan_new_jobs() -> int:
    """掃 JobsDB，推最啱 profile 嘅新職位（跳過已見過嘅）。冇設定 profile 就唔掃。"""
    profile = load_profile() or {}
    if not profile.get("job_title") and not profile.get("industry"):
        return 0

    combined_text = ""
    for kw in JOBSDB_SEARCH_KEYWORDS:
        url  = f"https://hk.jobsdb.com/jobs?keywords={quote(kw)}"
        text = _fetch_listing_via_jina(url)
        if text:
            combined_text += f"\n\n=== 關鍵字：{kw} ===\n{text}"

    if not combined_text.strip():
        return 0

    seen = _load_seen_jobs()
    jobs = _rank_and_extract_jobs(combined_text, profile, seen)[:MAX_JOBS_PUSHED_PER_DAY]

    for j in jobs:
        key = f"{j['title'].lower()}|{j['company'].lower()}"
        seen.add(key)
        short_id = str(uuid.uuid4())[:8]
        _redis_set(f"scanned_job:{short_id}", j, ex=SCANNED_JOB_TTL)
        reason_line = f"\n💡 {j['reason']}" if j["reason"] else ""
        send_telegram(
            f"💼 新職位推薦\n*{j['company']}* — {j['title']}{reason_line}",
            reply_markup={"inline_keyboard": [[
                {"text": "📄 查看 + 生成 CV", "callback_data": f"scanjob_open_{short_id}"},
                {"text": "❌ 唔啱",          "callback_data": f"scanjob_skip_{short_id}"},
            ]]}
        )

    if jobs:
        _save_seen_jobs(seen)
    return len(jobs)


@app.route("/api/daily_check", methods=["GET", "POST"])
def daily_check():
    # 保護：cron 觸發須帶正確 key，防外部濫觸發（燒 API / 洗版）
    if request.args.get("key") != os.getenv("CRON_SECRET"):
        return jsonify({"ok": False}), 403
    followups_sent = check_followups()
    jobs_pushed     = scan_new_jobs()
    is_sunday = datetime.now().weekday() == 6  # Monday=0 ... Sunday=6
    if is_sunday:
        send_weekly_report()
    return jsonify({
        "ok": True, "followups_sent": followups_sent,
        "jobs_pushed": jobs_pushed, "weekly_report_sent": is_sunday,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5001)
