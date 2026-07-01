"""求職 CRM — Kanban 追蹤所有求職申請，接通面試 AI。"""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from utils import load_jobs, save_jobs, load_profile
from interview_trainer import generate_job_questions, generate_job_tips

STAGE_ORDER = ["Applied", "Phone Screen", "1st Interview", "2nd Interview", "Offer", "Rejected"]

STATUS_BADGE = {
    "Applied":       "🔵",
    "Phone Screen":  "🟠",
    "1st Interview": "🟣",
    "2nd Interview": "🟣",
    "Offer":         "🟢",
    "Rejected":      "🔴",
}

KANBAN_COLS = ["Applied", "Phone Screen", "1st Interview", "2nd Interview", "Offer / Rejected"]


def days_since(applied_date: str) -> int:
    try:
        d = datetime.strptime(applied_date, "%Y-%m-%d").date()
        return (date.today() - d).days
    except Exception:
        return 0


def bucket_key(status: str) -> str:
    return "Offer / Rejected" if status in ("Offer", "Rejected") else status


def reached_stage(job: dict, stage: str) -> bool:
    idx = STAGE_ORDER.index(job.get("status", "Applied")) if job.get("status") in STAGE_ORDER else 0
    target = STAGE_ORDER.index(stage) if stage in STAGE_ORDER else 0
    return idx >= target


st.title("💼 求職 CRM")

jobs    = load_jobs()
profile = load_profile()

# ── Metrics ──────────────────────────────────────────────────────────
total = len(jobs)
interviewing = sum(1 for j in jobs if j.get("status") in ("Phone Screen", "1st Interview", "2nd Interview"))
replied = sum(1 for j in jobs if j.get("status", "Applied") != "Applied")
response_rate = f"{int(replied / total * 100)}%" if total else "—"
pending = sum(
    1 for j in jobs
    if j.get("status") == "Applied" and days_since(j.get("applied_date", "")) > 7
)
cv_health = profile.get("cv_health_score")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("總申請", total)
m2.metric("面試中", interviewing)
m3.metric("回覆率", response_rate)
m4.metric("⚠️ 待跟進", pending, help="申請超過 7 日仍未有回覆")
m5.metric("📋 CV Health", f"{cv_health}/100" if cv_health is not None else "—", help="喺 Telegram bot 上傳 CV 時計算")

st.divider()

# ── Kanban ────────────────────────────────────────────────────────────
if not jobs:
    st.info("未有申請記錄。用 Telegram bot 直接發 job link，或 `/addjob` 手動新增。")
else:
    headers = st.columns(5)
    for h, title in zip(headers, KANBAN_COLS):
        h.markdown(f"**{title}**")

    buckets: dict[str, list] = {t: [] for t in KANBAN_COLS}
    for j in jobs:
        buckets[bucket_key(j.get("status", "Applied"))].append(j)

    cols = st.columns(5)
    for col, col_title in zip(cols, KANBAN_COLS):
        with col:
            for j in buckets[col_title]:
                status = j.get("status", "Applied")
                badge = STATUS_BADGE.get(status, "⚪")
                days = days_since(j.get("applied_date", ""))
                stale = " ⚠️" if status == "Applied" and days > 7 else ""
                ats_score = j.get("ats_score")
                ats_tag = f" 📊{ats_score}" if ats_score is not None else ""
                label = f"{badge} {j.get('company', '?')} — {j.get('role', '?')}{ats_tag}{stale}"

                with st.expander(label):
                    st.caption(f"申請日：{j.get('applied_date', '—')}  ·  {days} 日前  ·  {status}")
                    if ats_score is not None:
                        st.caption(f"📊 ATS Match Score：{ats_score}/100")

                    if j.get("link"):
                        st.markdown(f"[職位連結]({j['link']})")

                    if j.get("jd"):
                        st.text_area("JD", j["jd"], height=100, disabled=True, key=f"jd_{j['id']}")

                    if j.get("cv_file"):
                        st.caption(f"📎 已發 CV：{j['cv_file']}")

                    with st.form(key=f"cv_record_{j['id']}"):
                        cv_input = st.text_input("記低發出嘅 CV 版本", value=j.get("cv_file", ""), placeholder="例：CV_TransUnion_DataAnalyst.docx")
                        if st.form_submit_button("💾 儲存"):
                            for jj in jobs:
                                if jj["id"] == j["id"]:
                                    jj["cv_file"] = cv_input
                            save_jobs(jobs)
                            st.success("已儲存")

                    st.markdown("---")
                    b1, b2, b3, b4 = st.columns(4)

                    if b1.button("📄 CV Prompt", key=f"cv_{j['id']}"):
                        prompt = (
                            f"請用 tailored-cv-generator skill 幫我生成針對以下職位的 tailored CV：\n\n"
                            f"公司：{j.get('company', '')}\n"
                            f"職位：{j.get('role', '')}\n"
                            f"JD：\n{j.get('jd', '（未提供）')}\n\n"
                            f"請根據我的 CV 重點 highlight 最相關的經驗，調整 summary 同 core competencies。"
                        )
                        st.code(prompt, language=None)

                    if b2.button("❓ 面試問題", key=f"q_{j['id']}"):
                        with st.spinner("生成中..."):
                            st.markdown(generate_job_questions(j))

                    if b3.button("💡 Key Tips", key=f"tips_{j['id']}"):
                        with st.spinner("生成中..."):
                            st.markdown(generate_job_tips(j))

                    b4.markdown("[🤖 Bot 練習](https://t.me/SalesTrainerAIBot)")

st.divider()

# ── 申請漏斗 ────────────────────────────────────────────────────────
if total:
    st.subheader("📊 申請漏斗")
    funnel_stages = ["Applied", "Phone Screen", "1st Interview", "2nd Interview", "Offer"]
    fcols = st.columns(5)
    for fc, stage in zip(fcols, funnel_stages):
        count = sum(1 for j in jobs if reached_stage(j, stage))
        pct = f"{int(count / total * 100)}%" if total else "—"
        fc.metric(stage, count, delta=pct if stage != "Applied" else None)
