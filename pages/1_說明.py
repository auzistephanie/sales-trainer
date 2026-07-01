"""說明頁：求職 CRM + AI 面試教練使用指南。"""

import streamlit as st

st.set_page_config(page_title="說明", layout="wide")
st.title("📖 使用說明")
st.caption("最後更新：2026-07-01")

# ── 系統概覽 ─────────────────────────────────────────────────────────
st.header("系統概覽")
st.markdown("""
兩個工具配合使用：

| 工具 | 用途 |
|---|---|
| **Telegram Bot** | 日常操作：send job link、練習面試、更新申請狀態 |
| **CRM 網頁（呢個 app）** | 視覺 Kanban 睇全局、撳 AI 按鈕生成面試問題 / Key Tips |
""")

st.divider()

# ── 日常求職流程 ──────────────────────────────────────────────────────
st.header("📋 日常求職流程（唔需要開 Claude）")

st.markdown("""
**Step 1 — 見到心水職位，複製 job link**

**Step 2 — 發去 Telegram Bot**

Bot 自動完成以下全部：
- 🔍 抓取頁面內容，抽出公司、職位、JD
- 💾 存入 CRM tracker（呢個網頁即時更新）
- 📝 生成 Cover Letter（直接喺 chat 睇）
- 📄 生成 Tailored CV .docx（直接下載）

**Step 3 — 有面試？**
- Bot `/listjobs` 更新申請狀態
- Bot `/practice` 練習面試問答
- 呢個網頁撳「面試問題」或「Key Tips」睇 AI 分析
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
| 直接發 job link | 全自動：存 tracker + CV + Cover Letter |
| `/addjob` | 手動新增申請（冇 link 或 link 受保護時用）|
| `/listjobs` | 查看所有申請 + 更新狀態 |
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
| `/setup` | 設定目標職位 + MBTI |
""")

st.divider()

# ── CRM 網頁功能 ──────────────────────────────────────────────────────
st.header("📊 CRM 網頁功能")

st.markdown("""
| 功能 | 說明 |
|---|---|
| **Kanban 5 欄** | Applied → Phone Screen → 1st → 2nd → Offer/Rejected |
| **頂部 Metrics** | 總申請 / 面試中 / 回覆率 / ⚠️ 待跟進（>7日未回覆）|
| **📄 CV Prompt** | 生成一段 prompt，copy 去 Claude 生成 Tailored CV |
| **❓ 面試問題** | AI 針對該職位 JD 生成 6 條最可能出現的面試題 |
| **💡 Key Tips** | AI 分析職位重點 + 面試前要 highlight 的經驗 |
| **🤖 Bot 練習** | 連結去 Telegram bot 練習 |
| **CV 版本記錄** | 記低發咗邊份 CV 去邊個職位 |
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
""")
