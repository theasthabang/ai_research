"""ui/tabs/revision_tab.py — Revision Notes, cleaned up."""
import httpx
import streamlit as st

_REVISION_CSS = """
<style>
.rev-topic-header {
  padding: 14px 18px;
  border-left: 3px solid #6C63FF;
  background: #111;
  border-radius: 0 10px 10px 0;
  margin-bottom: 16px;
}
.rev-topic-name {
  font-family: 'Syne', sans-serif;
  font-size: 18px; font-weight: 800; color: #F0F0F0;
}
.rev-mm-card {
  background: #111; border: 1px solid #222;
  border-radius: 12px; padding: 16px; margin-bottom: 12px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.rev-mm-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.5);
}
.rev-mm-branch-title {
  font-family: 'Syne', sans-serif;
  font-size: 13px; font-weight: 700;
  margin-bottom: 8px; padding-bottom: 6px;
}
.rev-mm-child {
  font-size: 12px; color: #888;
  padding: 3px 0 3px 10px;
  font-family: 'DM Sans', sans-serif; line-height: 1.5;
}
.rev-note-card {
  background: #0E0E0E;
  border: 1px solid #1E1E1E;
  border-left: 3px solid #00D4AA;
  border-radius: 0 10px 10px 0;
  padding: 12px 16px; margin-bottom: 8px;
  transition: border-left-color 0.2s ease, background 0.2s ease;
}
.rev-note-card:hover {
  background: #121212; border-left-color: #6C63FF;
}
.rev-note-heading {
  font-size: 11px; font-weight: 600; color: #666;
  margin-bottom: 4px; font-family: 'DM Sans', sans-serif;
  text-transform: uppercase; letter-spacing: 0.5px;
}
.rev-note-point {
  font-size: 13px; color: #DDD; line-height: 1.6;
  font-family: 'DM Sans', sans-serif;
}
.rev-empty {
  text-align: center; padding: 64px 24px;
}
.rev-empty-icon { font-size: 48px; margin-bottom: 16px; }
.rev-empty-text {
  font-family: 'DM Sans', sans-serif;
  font-size: 14px; color: #555; line-height: 1.7;
}
</style>
"""


def _fetch_documents(api_url: str) -> list:
    try:
        r = httpx.get(f"{api_url}/documents", timeout=10.0)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def _render_mini_mindmap(mindmap: dict, border_color: str = "#6C63FF"):
    center   = mindmap.get("center", "")
    branches = mindmap.get("branches", [])

    st.markdown(f"""
    <div style="text-align:center; margin-bottom:14px;">
      <span style="
        display:inline-block; padding:6px 20px;
        background:linear-gradient(135deg,#6C63FF22,#00D4AA22);
        border:1px solid {border_color}44;
        border-radius:999px; font-size:13px; font-weight:700;
        color:{border_color}; font-family:'Syne',sans-serif;
      ">{center}</span>
    </div>
    """, unsafe_allow_html=True)

    COLORS = ["#FF6B6B","#4ECDC4","#45B7D1","#96CEB4","#FFEAA7","#DDA0DD","#FF8C42","#6BCB77"]
    if not branches:
        return
    cols = st.columns(min(len(branches), 3))
    for bi, b in enumerate(branches):
        c    = b.get("color", COLORS[bi % len(COLORS)])
        nm   = b.get("name", "")
        kids = b.get("children", [])
        kids_html = "".join(
            f'<div class="rev-mm-child" style="border-left:2px solid {c}44;">• {k}</div>'
            for k in kids
        )
        with cols[bi % len(cols)]:
            st.markdown(f"""
            <div class="rev-mm-card" style="border-top:3px solid {c};">
              <div class="rev-mm-branch-title" style="color:{c}; border-bottom:1px solid {c}22;">{nm}</div>
              {kids_html}
            </div>
            """, unsafe_allow_html=True)


def _render_crisp_notes(crisp_notes: list):
    if not crisp_notes:
        return
    st.markdown("""
    <div style="font-size:10px; font-weight:700; letter-spacing:2px;
      text-transform:uppercase; color:#555; font-family:'DM Sans',sans-serif;
      margin-bottom:10px;">📝 CRISP NOTES</div>
    """, unsafe_allow_html=True)
    for note in crisp_notes:
        heading = note.get("heading", "")
        point   = note.get("point", "")
        st.markdown(f"""
        <div class="rev-note-card">
          <div class="rev-note-heading">{heading}</div>
          <div class="rev-note-point">{point}</div>
        </div>
        """, unsafe_allow_html=True)


def render(api_url: str):
    st.markdown(_REVISION_CSS, unsafe_allow_html=True)
    from ui.session import active_session, save_sessions

    st.markdown("""
    <div style="margin-bottom:20px;">
      <h2 style="font-family:'Syne',sans-serif; font-size:22px; font-weight:800;
        color:#F0F0F0; margin:0 0 4px;">📚 Revision Notes</h2>
      <p style="font-size:13px; color:#555; font-family:'DM Sans',sans-serif; margin:0;">
        AI-structured notes from your PDF — mind map + crisp bullet summaries.
      </p>
    </div>
    """, unsafe_allow_html=True)

    sess     = active_session()
    selected = sess.get("pdf")

    if not selected:
        st.markdown("""
        <div class="rev-empty">
          <div class="rev-empty-icon">📂</div>
          <div class="rev-empty-text">No PDF bound to this chat.<br>Upload one from the sidebar first.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    if st.button("🚀  Generate Revision Notes", type="primary",
                 use_container_width=True, key="rev_gen_btn"):
        sess["revision_data"] = None
        save_sessions()
        progress = st.progress(0, text="Starting…")
        status   = st.empty()
        try:
            progress.progress(5, text="Detecting topics…")
            status.info("🤖 Generating revision notes — this takes a minute…")
            r = httpx.post(f"{api_url}/revision-notes",
                           json={"filename": selected}, timeout=600.0)
            progress.progress(85, text="Parsing…")
            if r.status_code == 200:
                data = r.json()
                sess["revision_data"] = data
                save_sessions()
                progress.progress(100, text="Done!")
                n = len(data.get("sections", []))
                status.success(f"✅ {n} topic sections generated")
                st.rerun()
            elif r.status_code == 404:
                progress.empty(); status.error("PDF not ingested. Re-upload first.")
            else:
                progress.empty(); status.error(r.json().get("detail", "Backend error"))
        except httpx.ConnectError:
            progress.empty(); status.error("🔌 Backend offline.")
        except httpx.TimeoutException:
            progress.empty(); status.error("⏱️ Timed out. Try a smaller PDF.")
        except Exception as e:
            progress.empty(); status.error(f"⚠️ {e}")
        return

    rev_data = sess.get("revision_data")
    if not rev_data:
        st.markdown("""
        <div class="rev-empty">
          <div class="rev-empty-icon">✨</div>
          <div class="rev-empty-text">
            Click <strong style="color:#6C63FF;">Generate Revision Notes</strong> to begin.
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    sections = rev_data.get("sections", [])
    if not sections:
        st.warning("No sections found. Try regenerating.")
        return

    COLORS_CYCLE = ["#6C63FF","#00D4AA","#FF6B6B","#FFB830","#45B7D1","#DDA0DD","#FF8C42","#6BCB77"]
    topic_names  = [s.get("topic", f"Topic {i+1}") for i, s in enumerate(sections)]

    if "rev_section_idx" not in st.session_state:
        st.session_state.rev_section_idx = 0

    # Topic selector
    st.markdown("""
    <div style="font-size:10px; font-weight:700; letter-spacing:2px;
      text-transform:uppercase; color:#555; font-family:'DM Sans',sans-serif;
      margin-bottom:8px;">SELECT TOPIC</div>
    """, unsafe_allow_html=True)

    sel_idx = st.selectbox(
        "Topic", options=list(range(len(sections))),
        format_func=lambda i: topic_names[i],
        index=st.session_state.rev_section_idx,
        label_visibility="collapsed",
    )
    st.session_state.rev_section_idx = sel_idx

    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

    section = sections[sel_idx]
    topic   = section.get("topic", "")
    mindmap = section.get("mindmap", {})
    crisp   = section.get("crisp_notes", [])
    accent  = COLORS_CYCLE[sel_idx % len(COLORS_CYCLE)]

    # Topic header
    st.markdown(f"""
    <div class="rev-topic-header" style="border-left-color:{accent};">
      <div style="font-size:10px; color:{accent}88; font-family:'DM Sans',sans-serif;
        letter-spacing:1.5px; text-transform:uppercase; margin-bottom:4px;">
        Topic {sel_idx+1} of {len(sections)}
      </div>
      <div class="rev-topic-name">{topic}</div>
    </div>
    """, unsafe_allow_html=True)

    # Two-column layout — mindmap left, notes right
    col_left, col_right = st.columns([6, 4])

    with col_left:
        st.markdown("""
        <div style="font-size:10px; font-weight:700; letter-spacing:2px;
          text-transform:uppercase; color:#555; font-family:'DM Sans',sans-serif;
          margin-bottom:12px;">🗺️ TOPIC MAP</div>
        """, unsafe_allow_html=True)
        if mindmap:
            _render_mini_mindmap(mindmap, border_color=accent)
        else:
            st.markdown('<div style="color:#555; font-size:13px;">No map generated.</div>',
                        unsafe_allow_html=True)

    with col_right:
        _render_crisp_notes(crisp)