"""ui/tabs/chat_tab.py — Chat tab rendering."""
import httpx
import streamlit as st
from ui.session import active_session, save_sessions


_CHAT_CSS = """
<style>
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
  flex-direction: row-reverse !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
  [data-testid="stChatMessageContent"] {
  background: linear-gradient(135deg,#6C63FF,#5A52E8) !important;
  border-radius: 18px 4px 18px 18px !important;
  padding: 12px 16px !important;
  max-width: 72% !important;
  margin-left: auto !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
  [data-testid="stChatMessageContent"] p { color:white !important; font-size:14px !important; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"])
  [data-testid="stChatMessageContent"] {
  background:#151515 !important; border:1px solid #252525 !important;
  border-left:3px solid #00D4AA !important;
  border-radius:4px 18px 18px 18px !important;
  padding:16px 18px !important; max-width:85% !important;
  animation:fadeSlideIn 0.25s ease forwards;
}
@keyframes fadeSlideIn {
  from{opacity:0;transform:translateY(6px);}
  to{opacity:1;transform:translateY(0);}
}
[data-testid="stChatMessageAvatarUser"] {
  background:linear-gradient(135deg,#6C63FF,#5A52E8) !important; border-radius:50% !important;
}
[data-testid="stChatMessageAvatarAssistant"] {
  background:#0D1F1A !important; border:1px solid #00D4AA44 !important; border-radius:50% !important;
}
.sources-bar { display:flex;flex-wrap:nowrap;overflow-x:auto;gap:6px;padding:8px 0 4px;scrollbar-width:none; }
.sources-bar::-webkit-scrollbar{display:none;}
.source-pill {
  display:inline-flex;align-items:center;gap:4px;padding:4px 10px;
  background:#111;border:1px solid #2A2A2A;border-radius:999px;
  font-size:11px;color:#888;white-space:nowrap;text-decoration:none;
  transition:all 0.2s ease;flex-shrink:0;
}
.source-pill:hover{border-color:#6C63FF;color:#A89FFF;background:#1A1830;}

/* Mode pill buttons */
div[data-testid="stButton"]:has(button[data-testid="mode_web_academic"]) button,
div[data-testid="stButton"]:has(button[data-testid="mode_my_documents"]) button,
div[data-testid="stButton"]:has(button[data-testid="mode_all_sources"]) button {
  border-radius: 999px !important;
  font-size: 12px !important;
  font-family: 'DM Sans', sans-serif !important;
  padding: 5px 0 !important;
  transition: all 0.2s ease !important;
  border: 1px solid #2A2A2A !important;
  background: #141414 !important;
  color: #555 !important;
}
div[data-testid="stButton"]:has(button[data-testid="mode_web_academic"]) button:hover,
div[data-testid="stButton"]:has(button[data-testid="mode_my_documents"]) button:hover,
div[data-testid="stButton"]:has(button[data-testid="mode_all_sources"]) button:hover {
  border-color: #6C63FF55 !important;
  color: #A89FFF !important;
  background: #1A1830 !important;
}
</style>
"""


def _mode_active_css(active_key: str):
    """Inject CSS to highlight only the active mode button."""
    return f"""
<style>
div[data-testid="stButton"]:has(button[data-testid="{active_key}"]) button {{
  background: #1E1A3A !important;
  border: 1px solid #6C63FF !important;
  color: #A89FFF !important;
  font-weight: 600 !important;
  box-shadow: 0 0 12px #6C63FF33 !important;
}}
</style>"""


def _confidence_badge(conf: dict) -> str:
    sc = conf.get("score", 5)
    reason = conf.get("reason", "")
    if   sc >= 8: bg,fg,dot,label = "#0A1F14","#00D4AA","#00D4AA",f"High · {sc}/10"
    elif sc >= 5: bg,fg,dot,label = "#1E1600","#FFB830","#FFB830",f"Medium · {sc}/10"
    else:         bg,fg,dot,label = "#1E0808","#FF4757","#FF4757",f"Low · {sc}/10"
    return (
        f'<div style="margin-bottom:12px;display:flex;align-items:center;gap:8px;">'
        f'<span style="background:{bg};color:{fg};border:1px solid {dot}44;border-radius:999px;'
        f'padding:3px 12px;font-size:11px;font-weight:600;font-family:\'DM Sans\',sans-serif;'
        f'display:inline-flex;align-items:center;gap:5px;">'
        f'<span style="width:6px;height:6px;border-radius:50%;background:{dot};display:inline-block;"></span>'
        f'{label}</span>'
        f'<span style="font-size:11px;color:#555;font-family:\'DM Sans\',sans-serif;">{reason[:80]}</span>'
        f'</div>'
    )


def _sources_html(sources: list) -> str:
    if not sources:
        return ""
    pills = ""
    for s in sources[:8]:
        if s.startswith("http"):
            domain = s.split("/")[2].replace("www.", "")
            pills += f'<a href="{s}" target="_blank" class="source-pill"><span style="opacity:.6;">🔗</span> {domain}</a>'
        else:
            short = s[:30] + ("…" if len(s) > 30 else "")
            pills += f'<span class="source-pill">📄 {short}</span>'
    return f'<div class="sources-bar">{pills}</div>'


def render(search_mode: str, api_url: str):
    st.markdown(_CHAT_CSS, unsafe_allow_html=True)

    if "search_mode" not in st.session_state:
        st.session_state.search_mode = "my_documents"

    sess = active_session()

    st.markdown(
        f'<h2 style="font-family:\'Syne\',sans-serif;font-size:20px;font-weight:700;'
        f'color:#F0F0F0;margin:0 0 16px;padding:0;">{sess["name"]}</h2>',
        unsafe_allow_html=True,
    )

    for msg in sess["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

    # ── Mode pills — color-only active highlight, no text label ──────────────
    active = st.session_state.search_mode
    st.markdown(_mode_active_css(f"mode_{active}"), unsafe_allow_html=True)

    _, c1, c2, c3, _ = st.columns([1, 2, 2, 2, 1])
    clicked = None
    with c1:
        if st.button("🌐 Web + Academic", key="mode_web_academic", use_container_width=True):
            clicked = "web_academic"
    with c2:
        if st.button("📄 My Documents",   key="mode_my_documents", use_container_width=True):
            clicked = "my_documents"
    with c3:
        if st.button("✦ All Sources",     key="mode_all_sources",  use_container_width=True):
            clicked = "all_sources"

    if clicked:
        st.session_state.search_mode = clicked
        st.rerun()

    # ── Chat input ────────────────────────────────────────────────────────────
    user_input = st.chat_input("Ask anything about your research topic…")
    if not user_input:
        return

    current_mode = st.session_state.get("search_mode", "all_sources")

    if not sess["named"]:
        sess["name"]  = user_input.strip()[:40]
        sess["named"] = True
        save_sessions()

    sess["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        ph = st.empty()
        with st.spinner("Researching…"):
            try:
                r = httpx.post(
                    f"{api_url}/chat",
                    json={"query": user_input, "session_id": sess["id"], "mode": current_mode},
                    timeout=300.0,
                )
                if r.status_code == 200:
                    data    = r.json()
                    answer  = data.get("answer", "")
                    sources = data.get("sources", [])
                    conf    = data.get("confidence")
                    badge   = _confidence_badge(conf) if conf else ""
                    src_bar = _sources_html(sources)
                    full    = f"{badge}{answer}"
                    if src_bar:
                        full += f"<br>{src_bar}"
                    ph.markdown(full, unsafe_allow_html=True)
                    sess["messages"].append({"role": "assistant", "content": full})
                    save_sessions()
                else:
                    ph.error(f"API error {r.status_code}: {r.text}")
            except httpx.ConnectError:
                ph.error("🔌 Backend offline — is uvicorn running?")
            except Exception as e:
                ph.error(f"⚠️ {e}")