"""
ui/chat_app.py — Main Streamlit entry point.
Run with:  streamlit run ui/chat_app.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from ui.session import init_session_state
from ui.sidebar import render as render_sidebar
from ui.tabs    import chat_tab, mindmap_tab, revision_tab

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="AI Research Helper", page_icon="🔬", layout="wide")
st.markdown("""
<style>
section[data-testid="stSidebar"]{min-width:260px!important;max-width:300px!important}
.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 8px 20px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

init_session_state()
search_mode = render_sidebar(API_URL)

# Tab order: Chat | Revision Notes | Mind Map
tab_chat, tab_rev, tab_mm = st.tabs(["💬 Chat", "📚 Revision Notes", "🗺️ Mind Map"])

with tab_chat:
    chat_tab.render(search_mode, API_URL)

with tab_rev:
    revision_tab.render(API_URL)        # Revision Notes tab

with tab_mm:
    mindmap_tab.render(API_URL)         # Mind Map tab