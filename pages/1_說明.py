"""說明頁：求職 CRM + AI 面試教練使用指南。"""

import streamlit as st

st.set_page_config(page_title="說明", layout="wide")
st.title("📖 使用說明")
st.caption("最後更新：2026-07-01")

# ── 系統概覽 ─────────────────────────────────────────────────────────
st.header("系統概覽")
st.markdown("""
兩個工具共用同一份資料（Redis），一個做嘢、一個睇數：

| 工具 | 用途 |
|---|---|
| **Telegram Bot**（`@salestraineraubot`） | 日常操作：send job link、CV 上傳、面試練習、談判 / 覆盤 role-play、更新申請狀態 |
| **CRM 網頁（呢個 app）** | 視覺 Kanban 睇全局進度、CV Health / ATS Score / 談判覆盤記錄一覽 |
""")

st.divider()

# ── 日常求職流程 ──────────────────────────────────────────────────────
st.header("📋 日常求職流程（唔需要開 Claude）")

st.markdown("""
**Step 0 — 第一次用？喺 Bot 打 `/start`**
- 上傳 CV（PDF/.docx）或手動輸入背景 → 即時攞 **CV Health Score**
- 答月薪期望 → AI 生成 **HK 市場薪酬參考**
- 揀 MBTI → 之後練習會針對你嘅性格 coaching

**Step 1 — 見到心水職位，複製 job link**

**Step 2 — 發去 Telegram Bot**

Bot 自動完成以下全部：
- 🔍 抓取頁面內容，抽出公司、職位、JD
- 💾 存入 CRM tracker（呢個網頁即時更新）
- 📝 生成 Cover Letter（直接喺 chat 睇）
- 📄 生成 Tailored CV .docx，自動上傳 Google Drive
- 📊 生成 **ATS Match Score**（同你原本 CV 比較，睇高咗定低咗）

**Step 3 — 有面試？**
- Bot `/negotiate` 練習薪酬談判 role-play，AI 扮 HR 兼評分
- 面試完用 Bot `/debrief` 貼返面試過程，AI 出評級 + 改善建議，仲會問你要唔要更新申請狀態
- Bot `/listjobs` 每張 job 卡有 Negotiate 按鈕，跳過打 offer details 直接開始
""")

st.info("⚠️ 如果 job link 受保護（例如部分 LinkedIn 頁面），Bot 會提示你改用 `/addjob` 手動輸入。")

st.divider()

# ── Bot 指令 ─────────────────────────────────────────────────────────
st.header("🤖 Telegram Bot 指令")

col1, col2 = st.columns(2)

with col1:
    st.subheader("求職追蹤")
    st.markdown("""
| 指令 | 功能 |
|---|---|
| 直接發 job link | 全自動：存 tracker + CV + Cover Letter + ATS Score |
| `/addjob` | 手動新增申請（冇 link 或 link 受保護時用）|
| `/listjobs` | 查看所有申請 + 更新狀態 + Negotiate 按鈕 |

    """)
    st.subheader("設定")
    st.markdown("""
| 指令 | 功能 |
|---|---|
| `/start` | Onboarding：CV/背景 → CV Health → 薪酬 Benchmark → MBTI |
| `/setup` | 更改目標職位 + MBTI |
| `/mystatus` | 查看目前設定 |
| `/mbti` | 20 題 MBTI 檢測 |
""")

with col2:
    st.subheader("面試練習")
    st.markdown("""
| 指令 | 功能 |
|---|---|
| `/practice` | 隨機面試練習（AI 即場評分）|
| `/practice 高級` | 指定難度練習 |
| `/drill` | 針對特定題型練習 |
| `/review` | 貼真實面試對話，AI 分析失分點 |
| `/tip` | 今日面試技巧 |
| `/stats` | 查看練習進度報告 |
""")
    st.subheader("進階工具")
    st.markdown("""
| 指令 | 功能 |
|---|---|
| `/negotiate` | 薪酬談判 role-play，每回合有 HR 回應 + 技巧評分，「結束」出總結 |
| `/debrief` | 面試後覆盤：揀已追蹤嘅工（或跳過）→ 描述面試過程 → AI 分析評級 |
""")

st.divider()

# ── CRM 網頁功能 ──────────────────────────────────────────────────────
st.header("📊 CRM 網頁功能")

st.markdown("""
| 功能 | 說明 |
|---|---|
| **Kanban 5 欄** | Applied → Phone Screen → 1st → 2nd → Offer/Rejected |
| **頂部 Metrics** | 總申請 / 面試中 / 回覆率 / ⚠️ 待跟進（>7日未回覆）/ 📋 CV Health Score |
| **目標月薪** | 顯示你喺 Bot onboarding 答嘅薪酬期望 |
| **📊 ATS Badge** | 每張 job 卡顯示同 JD 嘅 ATS Match Score |
| **📎 Tailored CV（Drive）** | Bot 生成嘅 CV 自動上傳 Google Drive，CRM 直接顯示連結 |
| **🤝 談判練習記錄** | 顯示喺呢份工練過幾多次、最近一次幾多回合 |
| **🎙️ 覆盤記錄** | 顯示最近一次 `/debrief` 嘅完整分析內容 |
| **📄 CV Prompt** | （手動替代方案）生成一段 prompt，copy 去 Claude 生成 CV——一般用唔到，因為 Bot 已經自動做晒 |
| **❓ 面試問題 / 💡 Key Tips** | AI 直接喺網頁生成，唔使開 Bot |
| **CV 版本記錄** | 手動記低發咗邊份 CV 去邊個職位（同 Drive 自動連結係兩件事）|
| **申請漏斗** | Applied → Phone Screen → … → Offer 轉化率 |
""")

st.divider()

# ── 更新記錄 ─────────────────────────────────────────────────────────
st.header("📝 更新記錄")

st.markdown("""
| 日期 | 更新 |
|---|---|
| 2026-07-01 | 初版上線：Job CRM Kanban + Telegram bot URL 自動 add job + CV + Cover Letter |
| 2026-07-01 | Streamlit Cloud 部署，Bot `/help` 加入 CRM 連結 |
| 2026-07-01 | 說明頁上線 |
| 2026-07-01 | 新增 CV Health Score、HK 薪酬 Benchmark onboarding、ATS Match Score、`/negotiate`、`/debrief`（兩個 bot 前端同步）|
| 2026-07-01 | 修正 CRM 同升級訊息入面錯咗嘅 bot 連結（改返 `@salestraineraubot`）|
| 2026-07-01 | CRM 加返 CV Health / 目標月薪 / ATS Badge / Tailored CV Drive 連結 / 談判・覆盤記錄顯示；Tailored CV 生成正式接通 Google Drive（兩個 bot 前端一致）|
""")
