"""Entry point — secrets injection + page navigation。"""

from __future__ import annotations

import os
import streamlit as st

# Inject Streamlit Cloud secrets into env vars
for _k in ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "DEEPSEEK_API_KEY"):
    if _k in st.secrets and not os.getenv(_k):
        os.environ[_k] = st.secrets[_k]

pg = st.navigation([
    st.Page("pages/求職_CRM.py",  title="求職 CRM", icon="💼"),
    st.Page("pages/1_說明.py",    title="說明",     icon="📖"),
])
pg.run()
