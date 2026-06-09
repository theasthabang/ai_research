"""ui/sidebar.py — Sidebar with smart PDF topic naming like ChatGPT."""
import re
import httpx
import streamlit as st
from ui.session import active_session, new_chat, delete_session, save_sessions

_TOPIC_MAP = {
    "os": "Operating System", "operating": "Operating System",
    "dbms": "Database Systems", "database": "Database Systems", "db": "Database Systems",
    "dsa": "Data Structures & Algorithms", "data structure": "Data Structures",
    "algo": "Algorithms", "algorithm": "Algorithms",
    "cn": "Computer Networks", "network": "Computer Networks", "networking": "Computer Networks",
    "oops": "Object Oriented Programming", "oop": "Object Oriented Programming",
    "java": "Java Programming", "python": "Python Programming",
    "c++": "C++ Programming", "cpp": "C++ Programming",
    "ml": "Machine Learning", "ai": "Artificial Intelligence",
    "artificial": "Artificial Intelligence", "machine": "Machine Learning",
    "deep": "Deep Learning", "dl": "Deep Learning",
    "nlp": "Natural Language Processing",
    "compiler": "Compiler Design", "toc": "Theory of Computation",
    "automata": "Theory of Computation", "maths": "Mathematics",
    "math": "Mathematics", "discrete": "Discrete Mathematics",
    "statistics": "Statistics", "prob": "Probability",
    "software": "Software Engineering", "se": "Software Engineering",
    "web": "Web Development", "cloud": "Cloud Computing",
    "security": "Cyber Security", "crypto": "Cryptography",
    "digital": "Digital Electronics", "electronics": "Electronics",
    "microprocessor": "Microprocessors", "embedded": "Embedded Systems",
    "signal": "Signal Processing", "image": "Image Processing",
    "chemistry": "Chemistry", "physics": "Physics", "biology": "Biology",
    "economics": "Economics", "finance": "Finance", "accounting": "Accounting",
    "management": "Management", "marketing": "Marketing",
    "history": "History", "geography": "Geography",
}

def _pdf_to_topic(filename: str) -> str:
    name = filename.lower()
    name = re.sub(r"\.pdf$", "", name)
    name = re.sub(r"\s*\(\d+\)\s*$", "", name)
    name = re.sub(r"[_\-]+", " ", name)
    name = re.sub(r"\b(full|notes|unit|chapter|part|module|lecture|lec|pg|page|slides?)\b", "", name)
    name = re.sub(r"\d+", "", name).strip()
    words = name.split()
    for i in range(len(words)):
        if i + 1 < len(words):
            bigram = words[i] + " " + words[i+1]
            if bigram in _TOPIC_MAP:
                return _TOPIC_MAP[bigram]
        if words[i] in _TOPIC_MAP:
            return _TOPIC_MAP[words[i]]
    fallback = " ".join(words).strip()
    return fallback.title() if fallback else filename.replace(".pdf", "").title()


def render(api_url: str) -> str:
    with st.sidebar:

        # ── Logo ─────────────────────────────────────────────────────────
        st.markdown("""
        <div style="padding:24px 20px 8px;">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
            <div style="width:32px;height:32px;border-radius:10px;
              background:linear-gradient(135deg,#6C63FF,#00D4AA);
              display:flex;align-items:center;justify-content:center;
              font-size:16px;flex-shrink:0;">🔬</div>
            <div>
              <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:16px;
                background:linear-gradient(90deg,#6C63FF,#00D4AA);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                line-height:1.2;">Research Helper</div>
              <div style="font-size:10px;color:#555;letter-spacing:1.5px;
                text-transform:uppercase;font-family:'DM Sans',sans-serif;">AI-Powered</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── New Chat ──────────────────────────────────────────────────────
        st.markdown('<div style="padding:0 12px 4px;">', unsafe_allow_html=True)
        if st.button("＋  New Chat", use_container_width=True, type="primary", key="new_chat_btn"):
            new_chat(api_url)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div style="height:1px;background:#1E1E1E;margin:8px 0;"></div>',
                    unsafe_allow_html=True)

        # ── Chat history — show topic name, no pdf icon, like ChatGPT ────
        st.markdown("""
        <div style="padding:4px 20px 6px;">
          <span style="font-size:10px;font-weight:600;letter-spacing:2px;
            text-transform:uppercase;color:#555;font-family:'DM Sans',sans-serif;">CHATS</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <style>
        div[data-testid="stSidebar"] .sess-active > div > button {
            background:#1E1A3A !important; border:1px solid #6C63FF55 !important;
            color:#A89FFF !important; font-weight:500 !important;
            border-radius:8px !important; font-size:13px !important;
            font-family:'DM Sans',sans-serif !important; text-align:left !important;
        }
        div[data-testid="stSidebar"] .sess-idle > div > button {
            background:transparent !important; border:1px solid transparent !important;
            color:#666 !important; font-weight:400 !important;
            border-radius:8px !important; font-size:13px !important;
            font-family:'DM Sans',sans-serif !important; text-align:left !important;
        }
        div[data-testid="stSidebar"] .sess-idle > div > button:hover {
            background:#161616 !important; border-color:#2A2A2A !important; color:#CCC !important;
        }
        div[data-testid="stSidebar"] .sess-del > div > button {
            background:transparent !important; border:none !important;
            color:#333 !important; font-size:11px !important;
            padding:6px !important; border-radius:6px !important;
        }
        div[data-testid="stSidebar"] .sess-del > div > button:hover {
            color:#FF4757 !important; background:#1A0808 !important;
        }
        </style>
        """, unsafe_allow_html=True)

        for i, s in enumerate(st.session_state.sessions):
            is_active = (i == st.session_state.active_idx)
            # Show topic name from PDF if available, else session name
            display_name = (
                _pdf_to_topic(s["pdf"]) if s.get("pdf") else s["name"]
            )
            dot   = "●" if is_active else "○"
            label = f"{dot}  {display_name[:26]}"
            wrap  = "sess-active" if is_active else "sess-idle"

            col_btn, col_del = st.columns([5, 1])
            with col_btn:
                st.markdown(f'<div class="{wrap}">', unsafe_allow_html=True)
                if st.button(label, key=f"sess_{s['id']}", use_container_width=True):
                    st.session_state.active_idx = i
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            with col_del:
                st.markdown('<div class="sess-del">', unsafe_allow_html=True)
                if st.button("✕", key=f"del_{s['id']}"):
                    delete_session(i, api_url)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div style="height:1px;background:#1E1E1E;margin:10px 0;"></div>',
                    unsafe_allow_html=True)

        # ── PDF Upload ────────────────────────────────────────────────────
        st.markdown("""
        <div style="padding:4px 20px 8px;">
          <span style="font-size:10px;font-weight:600;letter-spacing:2px;
            text-transform:uppercase;color:#555;font-family:'DM Sans',sans-serif;">
            📄  DOCUMENT</span>
        </div>
        """, unsafe_allow_html=True)

        sess = active_session()

        if sess.get("pdf"):
            topic = _pdf_to_topic(sess["pdf"])
            st.markdown(f"""
            <div style="margin:0 12px 10px;padding:8px 12px;
              background:#0D1A14;border-left:2px solid #00D4AA55;border-radius:0 6px 6px 0;">
              <div style="font-size:10px;color:#00D4AA88;font-family:'DM Sans',sans-serif;
                letter-spacing:1px;text-transform:uppercase;margin-bottom:2px;">Active</div>
              <div style="font-size:12px;color:#AAD8CC;font-family:'DM Sans',sans-serif;">
                {topic}</div>
            </div>
            """, unsafe_allow_html=True)

        ufile = st.file_uploader(
            "Drop PDF here or click to browse",
            type=["pdf"], label_visibility="visible", key="pdf_uploader",
        )
        if ufile:
            st.markdown('<div style="margin:4px 12px 0;">', unsafe_allow_html=True)
            if st.button("🚀  Ingest PDF", use_container_width=True, type="primary"):
                with st.spinner("Indexing document…"):
                    try:
                        r = httpx.post(
                            f"{api_url}/ingest",
                            files={"file": (ufile.name, ufile.getvalue(), "application/pdf")},
                            timeout=60.0,
                        )
                        if r.status_code == 201:
                            chunks = r.json().get("chunks_added", 0)
                            s2 = active_session()
                            s2["pdf"]           = ufile.name
                            s2["mm_pages"]      = []
                            s2["revision_data"] = None
                            if not s2.get("named"):
                                s2["name"]  = _pdf_to_topic(ufile.name)
                                s2["named"] = True
                            save_sessions()
                            st.success(f"✅ {chunks} chunks indexed")
                            st.rerun()
                        else:
                            st.error(r.json().get("detail", "Failed"))
                    except Exception as e:
                        st.error(f"Backend unreachable: {e}")
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div style="height:1px;background:#1E1E1E;margin:10px 0;"></div>',
                    unsafe_allow_html=True)

        # ── Clear chat ────────────────────────────────────────────────────
        st.markdown('<div style="padding:0 12px 16px;">', unsafe_allow_html=True)
        if st.button("🗑️  Clear Current Chat", use_container_width=True):
            s3 = active_session()
            try:
                httpx.delete(f"{api_url}/history/{s3['id']}")
            except Exception:
                pass
            s3["messages"]      = []
            s3["name"]          = "New chat"
            s3["named"]         = False
            s3["mm_pages"]      = []
            s3["revision_data"] = None
            save_sessions()
            st.toast("✓ Chat cleared")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    if "search_mode" not in st.session_state:
        st.session_state.search_mode = "my_documents"   # default = My Documents
    return st.session_state.search_mode