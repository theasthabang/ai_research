"""
app/mindmap_draw.py
Function: draw_mindmap_page(data: dict) -> bytes

Draws one page of the detailed mind map using matplotlib + networkx.
Returns PNG bytes suitable for st.image() in Streamlit.

Layout:
  - Canvas 20x14 inches, white background, landscape
  - Center node   : large circle, bold 14pt topic name
  - Branch nodes  : colored ovals, spread 360° around center
  - Sub-branch    : smaller rounded rectangles per branch
  - Points        : tiny 8pt text boxes under each sub-branch
  - Key facts     : yellow info box, bottom-left
  - Exam corner   : red info box, bottom-right
  - Page title    : top-center bold
  - Arrows        : center→branch→sub-branch→point
"""

import io
import math
import textwrap
from typing import List, Tuple

import matplotlib
matplotlib.use("Agg")                        # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


# ── Palette ───────────────────────────────────────────────────────────────────

BRANCH_COLORS = [
    "#FF6B6B", "#4ECDC4", "#45B7D1",
    "#96CEB4", "#FF8C42", "#DDA0DD",
]

CENTER_COLOR    = "#1D4ED8"
CENTER_TEXT     = "white"
BG_COLOR        = "white"
ARROW_COLOR     = "#94A3B8"
SUBFACT_BG      = "#1e293b"
SUBFACT_FG      = "#e2e8f0"
KEY_FACT_BG     = "#FEF9C3"   # yellow
KEY_FACT_BORDER = "#EAB308"
EXAM_BG         = "#FEE2E2"   # red-tinted
EXAM_BORDER     = "#EF4444"


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _polar(cx: float, cy: float, r: float, angle_deg: float) -> Tuple[float, float]:
    """Return cartesian coords from polar offset."""
    a = math.radians(angle_deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def _wrap(text: str, width: int = 18) -> str:
    return "\n".join(textwrap.wrap(str(text), width))


# ── Node drawing ──────────────────────────────────────────────────────────────

def _draw_circle(ax, cx, cy, r, color, text, fontsize=10, textcolor="white", bold=False):
    circle = plt.Circle((cx, cy), r, color=color, zorder=3)
    ax.add_patch(circle)
    weight = "bold" if bold else "normal"
    ax.text(cx, cy, _wrap(text, 14), ha="center", va="center",
            fontsize=fontsize, color=textcolor, fontweight=weight,
            zorder=4, multialignment="center")
    return (cx, cy)


def _draw_oval(ax, cx, cy, w, h, color, text, fontsize=9, textcolor="white"):
    ellipse = mpatches.Ellipse((cx, cy), w, h, color=color, zorder=3)
    ax.add_patch(ellipse)
    ax.text(cx, cy, _wrap(text, 16), ha="center", va="center",
            fontsize=fontsize, color=textcolor, fontweight="bold",
            zorder=4, multialignment="center")
    return (cx, cy)


def _draw_rect(ax, cx, cy, w, h, facecolor, text, fontsize=8,
               textcolor=SUBFACT_FG, edgecolor="#334155", radius=0.15):
    x, y = cx - w / 2, cy - h / 2
    box = FancyBboxPatch((x, y), w, h,
                         boxstyle=f"round,pad=0.05,rounding_size={radius}",
                         facecolor=facecolor, edgecolor=edgecolor,
                         linewidth=0.8, zorder=3)
    ax.add_patch(box)
    ax.text(cx, cy, _wrap(text, 20), ha="center", va="center",
            fontsize=fontsize, color=textcolor, zorder=4,
            multialignment="center")
    return (cx, cy)


def _draw_point_box(ax, cx, cy, w, h, text, fontsize=7):
    _draw_rect(ax, cx, cy, w, h, facecolor="#0f172a",
               text=text, fontsize=fontsize,
               textcolor="#94A3B8", edgecolor="#1e293b")


def _arrow(ax, x1, y1, x2, y2, color=ARROW_COLOR, lw=1.0):
    ax.annotate("",
        xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(
            arrowstyle="-|>",
            color=color,
            lw=lw,
            mutation_scale=10,
        ),
        zorder=2,
    )


# ── Info boxes ────────────────────────────────────────────────────────────────

def _info_box(ax, x, y, w, h, title, items: List[str],
              bg, border, title_color, item_color="#1e293b", fontsize=8):
    box = FancyBboxPatch((x, y), w, h,
                         boxstyle="round,pad=0.1,rounding_size=0.2",
                         facecolor=bg, edgecolor=border,
                         linewidth=1.5, zorder=5)
    ax.add_patch(box)
    ax.text(x + w / 2, y + h - 0.22, title,
            ha="center", va="top", fontsize=fontsize + 1,
            fontweight="bold", color=title_color, zorder=6)
    # bullet items
    line_h = (h - 0.35) / max(len(items), 1)
    for i, item in enumerate(items):
        ty = y + h - 0.38 - i * line_h
        ax.text(x + 0.12, ty,
                "• " + _wrap(item, 38),
                ha="left", va="top", fontsize=fontsize,
                color=item_color, zorder=6,
                multialignment="left")


# ── Main draw function ────────────────────────────────────────────────────────

def draw_mindmap_page(data: dict) -> bytes:
    """
    Draw one page section as a mind map.

    Expected keys in `data`:
      page_title, center_topic, branches (list), key_facts (list), exam_corner (list)

    Each branch: {name, color, sub_branches: [{name, points: [str]}]}

    Returns PNG bytes.
    """

    page_title   = data.get("page_title",   "Page")
    center_topic = data.get("center_topic", "Topic")
    branches     = data.get("branches",     [])
    key_facts    = data.get("key_facts",    [])
    exam_corner  = data.get("exam_corner",  [])

    # ── Canvas ────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(20, 14))
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 14)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # ── Page title ────────────────────────────────────────────────────────────
    ax.text(10, 13.5, page_title,
            ha="center", va="top", fontsize=15,
            fontweight="bold", color="#0f172a", zorder=6)

    # ── Center node ───────────────────────────────────────────────────────────
    CX, CY = 10.0, 7.0
    CENTER_R = 1.0
    _draw_circle(ax, CX, CY, CENTER_R, CENTER_COLOR,
                 center_topic, fontsize=13, bold=True)

    # ── Branch layout — spread 360° ───────────────────────────────────────────
    n_branches   = max(len(branches), 1)
    branch_r     = 3.6          # distance center → branch oval
    sub_r        = 2.2          # distance branch → sub-branch rect
    point_dy     = 0.55         # vertical step between point boxes

    OVAL_W, OVAL_H    = 2.2, 0.9
    SUB_W,  SUB_H     = 1.9, 0.65
    PT_W,   PT_H      = 1.75, 0.48

    for bi, branch in enumerate(branches):
        color     = branch.get("color", BRANCH_COLORS[bi % len(BRANCH_COLORS)])
        b_name    = branch.get("name", f"Branch {bi+1}")
        sub_branches = branch.get("sub_branches", [])

        # angle: spread evenly, starting from the right (0°)
        angle = 360 * bi / n_branches

        # ── Branch oval ───────────────────────────────────────────────────────
        bx, by = _polar(CX, CY, branch_r, angle)
        _draw_oval(ax, bx, by, OVAL_W, OVAL_H, color, b_name, fontsize=9)
        _arrow(ax, CX, CY, bx, by, color=color, lw=1.4)

        # ── Sub-branches ──────────────────────────────────────────────────────
        n_sub = max(len(sub_branches), 1)

        # Fan sub-branches around the branch oval (±40° spread)
        spread = min(40, 35 * (n_sub - 1))
        sub_angles = [
            angle + spread * (si - (n_sub - 1) / 2) / max(n_sub - 1, 1)
            for si in range(n_sub)
        ] if n_sub > 1 else [angle]

        for si, sub in enumerate(sub_branches):
            s_name  = sub.get("name",   f"Sub {si+1}")
            points  = sub.get("points", [])
            s_angle = sub_angles[si]

            sx, sy = _polar(bx, by, sub_r, s_angle)
            _draw_rect(ax, sx, sy, SUB_W, SUB_H, SUBFACT_BG,
                       s_name, fontsize=8, textcolor=color, edgecolor=color)
            _arrow(ax, bx, by, sx, sy, color=color, lw=0.9)

            # ── Points under sub-branch ───────────────────────────────────────
            # stack vertically below the sub-branch rect
            px_start = sy - SUB_H / 2 - PT_H / 2 - 0.08

            for pi, pt in enumerate(points):
                py = px_start - pi * (PT_H + 0.06)
                _draw_point_box(ax, sx, py, PT_W, PT_H, pt, fontsize=7)
                # thin connector line
                ax.plot([sx, sx], [sy - SUB_H / 2, py + PT_H / 2],
                        color="#334155", lw=0.5, zorder=2)

    # ── Key facts box — bottom left ───────────────────────────────────────────
    KF_X, KF_Y = 0.3, 0.2
    KF_W, KF_H = 6.5, min(3.0, 0.35 * len(key_facts) + 0.7)
    _info_box(ax, KF_X, KF_Y, KF_W, KF_H,
              title="KEY FACTS",
              items=key_facts[:6],
              bg=KEY_FACT_BG, border=KEY_FACT_BORDER,
              title_color="#713F12", item_color="#1e293b", fontsize=8)

    # ── Exam corner box — bottom right ────────────────────────────────────────
    EC_W, EC_H = 6.5, min(3.0, 0.35 * len(exam_corner) + 0.7)
    EC_X = 20 - EC_W - 0.3
    EC_Y = 0.2
    _info_box(ax, EC_X, EC_Y, EC_W, EC_H,
              title="EXAM CORNER",
              items=exam_corner[:5],
              bg=EXAM_BG, border=EXAM_BORDER,
              title_color="#991B1B", item_color="#1e293b", fontsize=8)

    # ── Export as PNG bytes ───────────────────────────────────────────────────
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130,
                bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    buf.seek(0)
    return buf.read()