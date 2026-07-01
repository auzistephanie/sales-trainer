"""求職 CRM — Kanban 追蹤所有求職申請，接通面試 AI。"""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from utils import load_jobs, save_jobs, load_profile
from interview_trainer import generate_job_questions, generate_job_tips

STAGE_ORDER = ["Applied", "Phone Screen", "1st Interview", "2nd Interview", "Offer", "Rejected"]

KANBAN_COLS = ["Applied", "Phone Screen", "1st Interview", "2nd Interview", "Offer / Rejected"]

# 每個狀態對應嘅色系：bar = 色帶／漏斗色，bg/text = badge 底色同字色
STATUS_STYLE = {
    "Applied":       {"bar": "#B4B2A9", "bg": "#F1EFE8", "text": "#444441"},
    "Phone Screen":  {"bar": "#EF9F27", "bg": "#FAEEDA", "text": "#854F0B"},
    "1st Interview": {"bar": "#7F77DD", "bg": "#EEEDFE", "text": "#3C3489"},
    "2nd Interview": {"bar": "#7F77DD", "bg": "#EEEDFE", "text": "#3C3489"},
    "Offer":         {"bar": "#639922", "bg": "#EAF3DE", "text": "#27500A"},
    "Rejected":      {"bar": "#E24B4A", "bg": "#FCEBEB", "text": "#791F1F"},
}


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


def metric_card(label: str, value: str, warn: bool = False, help_text: str | None = None) -> str:
    bg = "#FAEEDA" if warn else "#F1EFE8"
    value_color = "#854F0B" if warn else "#2C2C2A"
    label_color = "#854F0B" if warn else "#5F5E5A"
    title_attr = f' title="{help_text}"' if help_text else ""
    return (
        f'<div{title_attr} style="background:{bg}; border-radius:10px; padding:14px 16px;">'
        f'<p style="font-size:13px; color:{label_color}; margin:0 0 4px;">{label}</p>'
        f'<p style="font-size:24px; font-weight:600; margin:0; color:{value_color};">{value}</p>'
        f'</div>'
    )


st.markdown(
    """
    <style>
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; }
    .block-container { padding-top: 2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

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
m1.markdown(metric_card("總申請", str(total)), unsafe_allow_html=True)
m2.markdown(metric_card("面試中", str(interviewing)), unsafe_allow_html=True)
m3.markdown(metric_card("回覆率", response_rate), unsafe_allow_html=True)
m4.markdown(
    metric_card("⚠️ 待跟進", str(pending), warn=pending > 0, help_text="申請超過 7 日仍未有回覆"),
    unsafe_allow_html=True,
)
m5.markdown(
    metric_card("📋 CV Health", f"{cv_health}/100" if cv_health is not None else "—", help_text="喺 Telegram bot 上傳 CV 時計算"),
    unsafe_allow_html=True,
)

if profile.get("expected_salary"):
    st.caption(f"🎯 目標月薪：${profile['expected_salary']} {profile.get('salary_currency', 'HKD')}")

st.divider()

# ── Kanban ────────────────────────────────────────────────────────────
if not jobs:
    st.info("未有申請記錄。用 Telegram bot 直接發 job link，或 `/addjob` 手動新增。")
else:
    buckets: dict[str, list] = {t: [] for t in KANBAN_COLS}
    for j in jobs:
        buckets[bucket_key(j.get("status", "Applied"))].append(j)

    cols = st.columns(5)
    for col, col_title in zip(cols, KANBAN_COLS):
        header_style = STATUS_STYLE.get(col_title, STATUS_STYLE["Applied"])
        with col:
            st.markdown(
                f'<div style="border-left:3px solid {header_style["bar"]}; padding:2px 0 2px 8px; margin-bottom:10px;">'
                f'<p style="font-size:13px; font-weight:600; margin:0; color:{header_style["text"]};">'
                f'{col_title}（{len(buckets[col_title])}）</p></div>',
                unsafe_allow_html=True,
            )
            for j in buckets[col_title]:
                status = j.get("status", "Applied")
                style = STATUS_STYLE.get(status, STATUS_STYLE["Applied"])
                days = days_since(j.get("applied_date", ""))
                stale = status == "Applied" and days > 7
                ats_score = j.get("ats_score")

                with st.container(border=True):
                    st.markdown(
                        f'<p style="font-size:14px; font-weight:600; margin:0 0 2px;">{j.get("company", "?")}</p>'
                        f'<p style="font-size:12px; color:#5F5E5A; margin:0 0 6px;">{j.get("role", "?")}</p>',
                        unsafe_allow_html=True,
                    )

                    badges = f'<span style="font-size:11px; background:{style["bg"]}; color:{style["text"]}; padding:1px 8px; border-radius:6px;">{status}</span>'
                    if ats_score is not None:
                        badges += (
                            f' <span style="font-size:11px; background:#EAF3DE; color:#27500A; '
                            f'padding:1px 8px; border-radius:6px; margin-left:4px;">📊 ATS {ats_score}</span>'
                        )
                    if stale:
                        badges += (
                            ' <span style="font-size:11px; background:#FCEBEB; color:#791F1F; '
                            'padding:1px 8px; border-radius:6px; margin-left:4px;">⚠️ 超過 7 日</span>'
                        )
                    st.markdown(badges, unsafe_allow_html=True)
                    st.caption(f"申請日：{j.get('applied_date', '—')} · {days} 日前")

                    with st.expander("詳情"):
                        if j.get("link"):
                            st.markdown(f"[職位連結]({j['link']})")

                        if j.get("jd"):
                            st.text_area("JD", j["jd"], height=100, disabled=True, key=f"jd_{j['id']}")

                        if j.get("cv_drive_link"):
                            st.markdown(f"📎 [Tailored CV（Drive）]({j['cv_drive_link']})")

                        if j.get("cv_file"):
                            st.caption(f"📎 已發 CV：{j['cv_file']}")

                        negotiate_log = j.get("negotiate_log") or []
                        if negotiate_log:
                            latest = negotiate_log[-1]
                            st.caption(f"🤝 談判練習：{len(negotiate_log)} 次（最近 {latest['date']}，{latest['rounds']} 回合）")

                        debrief_log = j.get("debrief_log") or []
                        if debrief_log:
                            st.caption(f"🎙️ 覆盤分析：{len(debrief_log)} 次（最近 {debrief_log[-1]['date']}）")
                            st.text_area(
                                "最近一次覆盤內容", debrief_log[-1]["result"],
                                height=120, disabled=True, key=f"debrief_{j['id']}",
                            )

                        with st.form(key=f"cv_record_{j['id']}"):
                            cv_input = st.text_input(
                                "記低發出嘅 CV 版本", value=j.get("cv_file", ""),
                                placeholder="例：CV_TransUnion_DataAnalyst.docx",
                            )
                            if st.form_submit_button("💾 儲存"):
                                for jj in jobs:
                                    if jj["id"] == j["id"]:
                                        jj["cv_file"] = cv_input
                                save_jobs(jobs)
                                st.success("已儲存")

                    b1, b2, b3, b4 = st.columns(4)

                    if b1.button("📄", key=f"cv_{j['id']}", help="CV Prompt", use_container_width=True):
                        prompt = (
                            f"請用 tailored-cv-generator skill 幫我生成針對以下職位的 tailored CV：\n\n"
                            f"公司：{j.get('company', '')}\n"
                            f"職位：{j.get('role', '')}\n"
                            f"JD：\n{j.get('jd', '（未提供）')}\n\n"
                            f"請根據我的 CV 重點 highlight 最相關的經驗，調整 summary 同 core competencies。"
                        )
                        st.code(prompt, language=None)

                    if b2.button("❓", key=f"q_{j['id']}", help="面試問題", use_container_width=True):
                        with st.spinner("生成中..."):
                            st.markdown(generate_job_questions(j))

                    if b3.button("💡", key=f"tips_{j['id']}", help="Key Tips", use_container_width=True):
                        with st.spinner("生成中..."):
                            st.markdown(generate_job_tips(j))

                    b4.link_button(
                        "🤖", "https://t.me/salestraineraubot",
                        help="Bot 練習", use_container_width=True,
                    )

                    with st.form(key=f"status_form_{j['id']}"):
                        sc1, sc2 = st.columns([4, 1])
                        new_status = sc1.selectbox(
                            "更新狀態", STAGE_ORDER,
                            index=STAGE_ORDER.index(status) if status in STAGE_ORDER else 0,
                            key=f"status_sel_{j['id']}", label_visibility="collapsed",
                        )
                        if sc2.form_submit_button("✓", help="更新狀態", use_container_width=True):
                            for jj in jobs:
                                if jj["id"] == j["id"]:
                                    jj["status"] = new_status
                            save_jobs(jobs)
                            st.success(f"已更新為 {new_status}")
                            st.rerun()

st.divider()

# ── 申請漏斗 ────────────────────────────────────────────────────────
if total:
    st.subheader("📊 申請漏斗")
    funnel_stages = ["Applied", "Phone Screen", "1st Interview", "2nd Interview", "Offer"]
    counts = [sum(1 for j in jobs if reached_stage(j, s)) for s in funnel_stages]
    max_count = counts[0] if counts[0] else 1

    bars_html = (
        '<div style="display:flex; align-items:flex-end; gap:10px; height:120px; '
        'background:#F1EFE8; border-radius:10px; padding:16px;">'
    )
    for stage, count in zip(funnel_stages, counts):
        pct = int(count / total * 100) if total else 0
        height_pct = max(int(count / max_count * 100), 4) if max_count else 4
        bar_color = STATUS_STYLE.get(stage, STATUS_STYLE["Applied"])["bar"]
        bars_html += (
            '<div style="flex:1; display:flex; flex-direction:column; align-items:center; '
            'justify-content:flex-end; height:100%;">'
            f'<div style="background:{bar_color}; width:100%; border-radius:4px 4px 0 0; height:{height_pct}%;"></div>'
            f'<p style="font-size:11px; color:#5F5E5A; margin:6px 0 0;">{stage}</p>'
            f'<p style="font-size:12px; font-weight:600; margin:0;">{count} · {pct}%</p>'
            '</div>'
        )
    bars_html += '</div>'
    st.markdown(bars_html, unsafe_allow_html=True)
