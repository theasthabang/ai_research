"""
ui/tabs/mindmap_tab.py
Real radial mind map SVG — like the reference images:
  • Center circle with topic name
  • Branches radiate outward at even angles
  • Each branch has a colored pill node
  • Text box beside each branch showing sub-topics + points
  • Straight lines with dot connectors (Dribbble reference style)
"""
import math
import httpx
import streamlit as st

BRANCH_COLORS = [
    "#FF6B6B","#4ECDC4","#45B7D1","#96CEB4",
    "#DDA0DD","#FF8C42","#6BCB77","#FFEAA7",
]

_CSS = """
<style>
.mm-page-label {
  font-size:10px; color:#555; letter-spacing:2.5px;
  text-transform:uppercase; font-family:'DM Sans',sans-serif; margin-bottom:4px;
  text-align:center;
}
.mm-title {
  font-family:'Syne',sans-serif; font-size:20px;
  font-weight:800; color:#F0F0F0; text-align:center; margin-bottom:18px;
}
.mm-nav-counter {
  font-family:'Syne',sans-serif; font-size:14px;
  font-weight:700; color:#F0F0F0; text-align:center;
}
.mm-facts-row { display:flex; gap:12px; margin-top:18px; }
.mm-fact-box  { flex:1; border-radius:10px; padding:12px 14px; }
.mm-fact-title{
  font-size:10px; font-weight:700; letter-spacing:1.5px;
  text-transform:uppercase; margin-bottom:8px; font-family:'Syne',sans-serif;
}
.mm-fact-item {
  font-size:12px; font-family:'DM Sans',sans-serif;
  color:#CCC; padding:3px 0; line-height:1.5;
  display:flex; gap:6px; align-items:flex-start;
}
</style>
"""


# ─── SVG builder ──────────────────────────────────────────────────────────────

def _polar(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def _wrap_text(text, max_chars=22):
    """Split text into lines of max_chars."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > max_chars:
            if cur: lines.append(cur.strip())
            cur = w
        else:
            cur += " " + w
    if cur: lines.append(cur.strip())
    return lines[:3]


def _text_block(x, y, lines, color, anchor="middle", size=10.5, bold=False):
    """Return SVG <text> with tspans for each line."""
    lh = 14
    total_h = len(lines) * lh
    start_y = y - total_h / 2 + lh / 2
    weight = "700" if bold else "400"
    parts = []
    for i, line in enumerate(lines):
        parts.append(
            f'<tspan x="{x:.1f}" dy="{0 if i == 0 else lh}">{line}</tspan>'
        )
    return (
        f'<text x="{x:.1f}" y="{start_y:.1f}" text-anchor="{anchor}" '
        f'font-family="DM Sans, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{color}">'
        + "".join(parts) + "</text>"
    )


def _build_mindmap_svg(page: dict) -> str:
    center_topic = page.get("center_topic", "Topic")
    branches     = page.get("branches", [])
    n            = len(branches)
    if n == 0:
        return '<svg width="800" height="500"><text x="400" y="250" text-anchor="middle" fill="#555">No data</text></svg>'

    W, H  = 900, 580
    cx, cy = W / 2, H / 2
    BRANCH_R  = 195   # center → branch pill
    BOX_GAP   = 52    # branch pill → text box edge

    parts = []

    # ── Background ────────────────────────────────────────────────────────
    parts.append(f'<rect width="{W}" height="{H}" fill="#0D0D0D" rx="16"/>')

    # Subtle radial glow
    parts.append(
        '<radialGradient id="glow" cx="50%" cy="50%" r="35%">'
        '<stop offset="0%" stop-color="#6C63FF" stop-opacity="0.1"/>'
        '<stop offset="100%" stop-color="#0D0D0D" stop-opacity="0"/>'
        '</radialGradient>'
        f'<rect width="{W}" height="{H}" fill="url(#glow)"/>'
    )

    # ── Defs ──────────────────────────────────────────────────────────────
    parts.append(
        '<defs>'
        '<filter id="cshadow" x="-40%" y="-40%" width="180%" height="180%">'
        '<feDropShadow dx="0" dy="0" stdDeviation="10" flood-color="#6C63FF" flood-opacity="0.45"/>'
        '</filter>'
        '</defs>'
    )

    # ── Branches ──────────────────────────────────────────────────────────
    for bi, branch in enumerate(branches):
        color        = branch.get("color", BRANCH_COLORS[bi % len(BRANCH_COLORS)])
        bname        = branch.get("name", "")
        sub_branches = branch.get("sub_branches", [])
        angle        = 360 * bi / n - 90   # start top, go clockwise

        bx, by = _polar(cx, cy, BRANCH_R, angle)
        is_right = bx >= cx

        # Line: center edge → branch pill edge
        # Start point on center circle boundary
        lx1, ly1 = _polar(cx, cy, 46, angle)
        # End point on branch pill boundary (pill half-width ~40)
        pill_r = 18
        lx2, ly2 = _polar(cx, cy, BRANCH_R - pill_r - 2, angle)

        parts.append(
            f'<line x1="{lx1:.1f}" y1="{ly1:.1f}" x2="{lx2:.1f}" y2="{ly2:.1f}" '
            f'stroke="{color}" stroke-width="1.8" stroke-opacity="0.55" '
            f'stroke-dasharray="0"/>'
        )

        # Dot on line midpoint
        mx, my = (lx1 + lx2) / 2, (ly1 + ly2) / 2
        parts.append(
            f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="3" '
            f'fill="{color}" opacity="0.7"/>'
        )

        # ── Branch pill node ──────────────────────────────────────────────
        pill_w = max(len(bname) * 7.2 + 24, 80)
        pill_h = 32
        parts.append(
            f'<rect x="{bx - pill_w/2:.1f}" y="{by - pill_h/2:.1f}" '
            f'width="{pill_w:.1f}" height="{pill_h}" rx="16" '
            f'fill="{color}28" stroke="{color}" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{bx:.1f}" y="{by + 4:.1f}" text-anchor="middle" '
            f'font-family="Syne, sans-serif" font-size="11" font-weight="700" '
            f'fill="{color}">{bname[:20]}</text>'
        )

        # ── Text box beside branch pill ───────────────────────────────────
        # Build content lines: all sub-branch names + their points
        content_lines = []
        for sb in sub_branches[:3]:
            sbname = sb.get("name", "")
            content_lines.append(("sub", sbname, color))
            for pt in sb.get("points", [])[:2]:
                content_lines.append(("pt", pt, "#888"))

        if not content_lines:
            continue

        box_line_h   = 15
        box_padding  = 10
        box_h        = len(content_lines) * box_line_h + box_padding * 2
        box_w        = 160
        box_x_offset = pill_w / 2 + BOX_GAP

        if is_right:
            box_x = bx + box_x_offset
            anchor = "start"
            text_x = box_x + box_padding
            line_x2 = box_x
        else:
            box_x = bx - box_x_offset - box_w
            anchor = "start"
            text_x = box_x + box_padding
            line_x2 = box_x + box_w

        box_y = by - box_h / 2

        # Connector line: pill edge → box edge
        conn_x1 = bx + (pill_w / 2 if is_right else -pill_w / 2)
        parts.append(
            f'<line x1="{conn_x1:.1f}" y1="{by:.1f}" '
            f'x2="{line_x2:.1f}" y2="{by:.1f}" '
            f'stroke="{color}" stroke-width="1" stroke-opacity="0.35"/>'
        )

        # Box background
        parts.append(
            f'<rect x="{box_x:.1f}" y="{box_y:.1f}" '
            f'width="{box_w}" height="{box_h:.1f}" rx="8" '
            f'fill="#161616" stroke="{color}" stroke-width="0.8" stroke-opacity="0.3"/>'
        )

        # Box text content
        cur_y = box_y + box_padding + 10
        for kind, txt, fg in content_lines:
            is_sub = (kind == "sub")
            prefix = "▸ " if is_sub else "  • "
            fw     = "600" if is_sub else "400"
            fs     = "10.5" if is_sub else "9.5"
            label  = (prefix + txt)[:30]
            parts.append(
                f'<text x="{text_x:.1f}" y="{cur_y:.1f}" '
                f'font-family="DM Sans, sans-serif" font-size="{fs}" '
                f'font-weight="{fw}" fill="{fg}">{label}</text>'
            )
            cur_y += box_line_h

    # ── Center circle ──────────────────────────────────────────────────────
    CR = 46
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{CR + 6}" '
        f'fill="#6C63FF18" stroke="#6C63FF" stroke-width="1.5" stroke-opacity="0.4"/>'
    )
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{CR}" fill="#1D4ED8" filter="url(#cshadow)"/>'
    )

    # Center label
    c_lines = _wrap_text(center_topic, 11)
    lh      = 13
    start_y = cy - (len(c_lines) - 1) * lh / 2
    for li, line in enumerate(c_lines):
        parts.append(
            f'<text x="{cx}" y="{start_y + li * lh + 4:.1f}" '
            f'text-anchor="middle" font-family="Syne, sans-serif" '
            f'font-size="11" font-weight="800" fill="white">{line}</text>'
        )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;border-radius:16px;">'
        + "".join(parts) + "</svg>"
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fetch_documents(api_url: str) -> list:
    try:
        r = httpx.get(f"{api_url}/documents", timeout=10.0)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def _render_page(page: dict, page_num: int, total: int):
    title = page.get("page_title", f"Section {page_num}")
    key_facts   = page.get("key_facts", [])
    exam_corner = page.get("exam_corner", [])

    # Header
    st.markdown(
        f'<div class="mm-page-label">Page {page_num} of {total}</div>'
        f'<div class="mm-title">{title}</div>',
        unsafe_allow_html=True,
    )

    # SVG mind map — full width
    svg = _build_mindmap_svg(page)
    st.markdown(
        f'<div style="background:#0D0D0D;border:1px solid #1E1E1E;border-radius:16px;'
        f'padding:4px;overflow:hidden;">{svg}</div>',
        unsafe_allow_html=True,
    )

    # Facts row below map
    if key_facts or exam_corner:
        facts_html = '<div class="mm-facts-row">'
        if key_facts:
            items = "".join(
                f'<div class="mm-fact-item">'
                f'<span style="color:#FFB830;flex-shrink:0;">📌</span>{f}'
                f'</div>'
                for f in key_facts[:5]
            )
            facts_html += (
                f'<div class="mm-fact-box" style="background:#141200;border:1px solid #FFB83033;">'
                f'<div class="mm-fact-title" style="color:#FFB830;">Key Facts</div>{items}</div>'
            )
        if exam_corner:
            items = "".join(
                f'<div class="mm-fact-item">'
                f'<span style="color:#FF4757;flex-shrink:0;">🎯</span>{t}'
                f'</div>'
                for t in exam_corner[:4]
            )
            facts_html += (
                f'<div class="mm-fact-box" style="background:#140A0A;border:1px solid #FF475733;">'
                f'<div class="mm-fact-title" style="color:#FF4757;">Exam Corner</div>{items}</div>'
            )
        facts_html += '</div>'
        st.markdown(facts_html, unsafe_allow_html=True)


# ─── Main render ──────────────────────────────────────────────────────────────

def render(api_url: str):
    st.markdown(_CSS, unsafe_allow_html=True)

    if "mm_page_idx" not in st.session_state:
        st.session_state.mm_page_idx = 0

    from ui.session import active_session, save_sessions
    sess = active_session()

    st.markdown("""
    <div style="margin-bottom:20px;">
      <h2 style="font-family:'Syne',sans-serif;font-size:22px;font-weight:800;
        color:#F0F0F0;margin:0 0 4px;">🗺️ Visual Mind Map</h2>
      <p style="font-size:13px;color:#555;font-family:'DM Sans',sans-serif;margin:0;">
        Radial mind map generated section-by-section from your PDF.
      </p>
    </div>
    """, unsafe_allow_html=True)

    selected = sess.get("pdf")
    if not selected:
        st.markdown("""
        <div style="text-align:center;padding:64px 24px;">
          <div style="font-size:48px;margin-bottom:16px;">📂</div>
          <div style="font-size:14px;color:#555;font-family:'DM Sans',sans-serif;">
            No PDF bound. Upload one from the sidebar.
          </div>
        </div>""", unsafe_allow_html=True)
        return

    ingested = _fetch_documents(api_url)
    doc_map  = {d["filename"]: d for d in ingested}
    if selected not in doc_map:
        st.warning(f"'{selected}' not found — please re-ingest.")
        return

    pdf_pages = doc_map[selected].get("pages_count", 10)

    if st.button("🚀  Generate Mind Map", type="primary",
                 use_container_width=True, key="mm_gen_btn"):
        sess["mm_pages"]             = []
        st.session_state.mm_page_idx = 0
        save_sessions()
        progress = st.progress(0, text="Connecting…")
        status   = st.empty()
        try:
            progress.progress(5, text="Sending to AI…")
            status.info("🤖 Analysing PDF — please wait…")
            r = httpx.post(
                f"{api_url}/detailed-mindmap",
                json={"filename": selected, "total_pages": pdf_pages},
                timeout=600.0,
            )
            progress.progress(80, text="Building map…")
            if r.status_code == 200:
                pages = r.json().get("pages", [])
                if not pages:
                    progress.empty(); status.error("No pages returned. Try re-ingesting.")
                else:
                    sess["mm_pages"] = pages
                    save_sessions()
                    progress.progress(100, text="Done!")
                    status.success(f"✅ {len(pages)} sections ready")
                    st.rerun()
            elif r.status_code == 404:
                progress.empty(); status.error("PDF not ingested yet.")
            else:
                progress.empty(); status.error(r.json().get("detail", "Backend error"))
        except httpx.ConnectError:
            progress.empty(); status.error("🔌 Backend offline.")
        except httpx.TimeoutException:
            progress.empty(); status.error("⏱️ Timed out. Try a smaller PDF.")
        except Exception as e:
            progress.empty(); status.error(f"⚠️ {e}")
        return

    pages = sess.get("mm_pages", [])
    if not pages:
        st.markdown("""
        <div style="text-align:center;padding:48px 24px;">
          <div style="font-size:48px;margin-bottom:16px;">✨</div>
          <div style="font-size:14px;color:#555;font-family:'DM Sans',sans-serif;">
            Click <strong style="color:#6C63FF;">Generate Mind Map</strong> to begin.
          </div>
        </div>""", unsafe_allow_html=True)
        return

    n_pages = len(pages)
    idx     = st.session_state.mm_page_idx

    # Status strip
    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;
      background:#0D1F18;border:1px solid #00D4AA22;border-radius:10px;
      padding:10px 16px;margin-bottom:16px;">
      <span style="font-size:12px;color:#00D4AA;font-family:'DM Sans',sans-serif;">
        ✦ {n_pages} sections ready</span>
      <span style="font-size:11px;color:#444;font-family:'DM Sans',sans-serif;">{selected}</span>
    </div>
    """, unsafe_allow_html=True)

    # Navigation
    nl, nm, nr = st.columns([1, 2, 1])
    with nl:
        if st.button("◀  Prev", disabled=(idx == 0),
                     use_container_width=True, key="mm_prev"):
            st.session_state.mm_page_idx -= 1; st.rerun()
    with nm:
        st.markdown(f'<div class="mm-nav-counter">Page {idx+1} / {n_pages}</div>',
                    unsafe_allow_html=True)
    with nr:
        if st.button("Next  ▶", disabled=(idx == n_pages - 1),
                     use_container_width=True, key="mm_next"):
            st.session_state.mm_page_idx += 1; st.rerun()

    with st.expander("🗂️  Jump to section", expanded=False):
        jump_cols = st.columns(min(n_pages, 8))
        for i, pg in enumerate(pages):
            with jump_cols[i % 8]:
                marker = "🟣" if i == idx else "⬜"
                if st.button(f"{marker}{i+1}", key=f"mm_jump_{i}",
                             help=pg.get("page_title",""), use_container_width=True):
                    st.session_state.mm_page_idx = i; st.rerun()

    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
    _render_page(pages[idx], idx + 1, n_pages)

    # Download
    st.markdown('<div style="height:16px;"></div>', unsafe_allow_html=True)
    base = selected.replace(".pdf","").replace(" ","_")

    def _all_text():
        lines = [f"MIND MAP — {selected}", "="*60]
        for i, pg in enumerate(pages, 1):
            lines += [f"\n--- Page {i}: {pg.get('page_title','')} ---",
                      f"Topic: {pg.get('center_topic','')}"]
            for b in pg.get("branches",[]):
                lines.append(f"\n  [{b.get('name','')}]")
                for sb in b.get("sub_branches",[]):
                    lines.append(f"    > {sb.get('name','')}")
                    for pt in sb.get("points",[]):
                        lines.append(f"      • {pt}")
            if pg.get("key_facts"):
                lines.append("\n  KEY FACTS:")
                lines += [f"    • {f}" for f in pg["key_facts"]]
            if pg.get("exam_corner"):
                lines.append("\n  EXAM CORNER:")
                lines += [f"    • {t}" for t in pg["exam_corner"]]
        return "\n".join(lines)

    st.download_button(
        "📥  Download All Pages (Text)", data=_all_text(),
        file_name=f"mindmap_{base}_all.txt",
        mime="text/plain", use_container_width=True,
    )