"""ui/session.py — Session persistence with per-session PDF + generated data."""
import uuid, json, os
import streamlit as st

SESSIONS_FILE = "./ui/sessions.json"


def _new_session() -> dict:
    return {
        "id":            str(uuid.uuid4()),
        "name":          "New chat",
        "messages":      [],
        "named":         False,
        "pdf":           None,
        "mm_pages":      [],
        "revision_data": None,
    }


def _migrate(s: dict) -> dict:
    s.setdefault("pdf",           None)
    s.setdefault("mm_pages",      [])
    s.setdefault("revision_data", None)
    return s


def save_sessions():
    os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)
    with open(SESSIONS_FILE, "w") as f:
        json.dump([
            {
                "id":            s["id"],
                "name":          s["name"],
                "named":         s["named"],
                "messages":      s["messages"],
                "pdf":           s.get("pdf"),
                "mm_pages":      s.get("mm_pages", []),
                "revision_data": s.get("revision_data"),
            }
            for s in st.session_state.sessions
        ], f, indent=2)


def load_sessions() -> list:
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE) as f:
                data = json.load(f)
                if data:
                    return [_migrate(s) for s in data]
        except Exception:
            pass
    return [_new_session()]


def init_session_state():
    if "sessions"   not in st.session_state:
        st.session_state.sessions   = load_sessions()
        st.session_state.active_idx = 0
    if "active_idx" not in st.session_state:
        st.session_state.active_idx = 0


def active_session() -> dict:
    idx = min(st.session_state.active_idx, len(st.session_state.sessions) - 1)
    st.session_state.active_idx = idx
    return st.session_state.sessions[idx]


def new_chat(api_url: str = ""):
    top = st.session_state.sessions[0] if st.session_state.sessions else None
    if top and not top.get("messages") and not top.get("pdf"):
        st.session_state.active_idx = 0
        return
    st.session_state.sessions.insert(0, _new_session())
    st.session_state.active_idx = 0
    save_sessions()


def delete_session(idx: int, api_url: str = ""):
    import httpx
    try:
        httpx.delete(f"{api_url}/history/{st.session_state.sessions[idx]['id']}")
    except Exception:
        pass
    st.session_state.sessions.pop(idx)
    if not st.session_state.sessions:
        st.session_state.sessions = [_new_session()]
    st.session_state.active_idx = 0
    save_sessions()