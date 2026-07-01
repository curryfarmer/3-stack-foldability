#!/usr/bin/env python3
"""render_intuition.py — STEP-BY-STEP pedagogy diagrams for the 2+1 twist writeup.

Read-only. Renders five self-explanatory PNGs that build, slowly, the intuition for WHY the
"jump-strand" reduction (Model B) correctly predicts FOLD (Tw=0) vs JAM (Tw=+/-720) for a 2+1
paper-fold pattern, and WHY tracking the domino CENTROID (Model A) fails:

  01_fold_is_reflection.png   one fold = one mirror reflection across the crease
  02_two_reflections_rotate.png two reflections compose to a rotation by twice the angle
  03_centroid_vs_jump.png     centroid leaves the lattice; the 3-jump stays on it
  04_checkerboard_sigma.png   sigma = (-1)^(x+y): unit step AND 3-jump both flip the colour
  05_funnel.png               the 6x8 non-corner 2+1 gate funnel (22180 -> 434 -> 2 jams)

All data is hardcoded; no engine or DB is touched. Conventions match the existing twist diagrams
(experimental/enumerate_twist.py): origin top-left, +y downward, integer lattice, checkerboard tint
(-1)^(x+y), Agg backend (no GUI), dpi=150.

Usage:
  python experimental/render_intuition.py                 # -> docs/research/img/twist/intro/
  python experimental/render_intuition.py --outdir DIR
"""
import argparse
import math
import os

import matplotlib
matplotlib.use("Agg")                                       # no GUI
import matplotlib.pyplot as plt                             # noqa: E402
from matplotlib.patches import Rectangle, FancyArrowPatch, Polygon  # noqa: E402

# ---- palette (matches enumerate_twist.py) -----------------------------------
BODY_C = "#1f77b4"      # kept-strand blue
JUMP_C = "#d62728"      # red — naive / Model A / 3-jump highlight
GREEN_C = "#2ca02c"     # green — Model B / good
ORANGE_C = "#e8820c"
GRID_C = "#dddddd"
PAPER_C = "#cfe3f7"     # solid paper fill (before)
GHOST_C = "#f7d8d8"     # ghost paper fill (after)
CB_DARK = "#cdd8e6"     # checkerboard (x+y) odd
CB_LIGHT = "#f4f6fb"    # checkerboard (x+y) even
INK = "#222222"

DPI = 150


# ---- small shared helpers ---------------------------------------------------

def _save(fig, out_path):
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _arrow(ax, p, q, color, lw=2.2, z=8, mut=18, ls="-"):
    ax.add_patch(FancyArrowPatch((p[0], p[1]), (q[0], q[1]), arrowstyle="-|>",
                                 mutation_scale=mut, color=color, lw=lw, ls=ls, zorder=z,
                                 shrinkA=0, shrinkB=0))


def _checker(ax, m, n, z=1):
    """Tint an m x n grid by the checkerboard colour (-1)^(x+y)."""
    for y in range(n):
        for x in range(m):
            tint = CB_LIGHT if (x + y) % 2 == 0 else CB_DARK
            ax.add_patch(Rectangle((x, y), 1, 1, facecolor=tint, edgecolor=GRID_C, lw=0.9, zorder=z))


def _topleft_axes(ax, xlim, ylim):
    """Origin top-left, +y down, equal aspect — the shared lattice convention."""
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.invert_yaxis()


# ============================================================ 01 reflection ===

def fig_fold_is_reflection(out_path):
    """A unit square of paper + a crease line; paper reflected across the crease (before solid,
    after dashed ghost, arrow). Builds: a single fold IS one mirror reflection."""
    fig, ax = plt.subplots(figsize=(8.0, 5.6))

    # crease is the vertical line x = 1 (the short edge the square folds over)
    cx = 1.0
    # BEFORE: solid unit square spanning x in [0,1], y in [0,1]
    ax.add_patch(Rectangle((0, 0), 1, 1, facecolor=PAPER_C, edgecolor=BODY_C, lw=2.6, zorder=4))
    # AFTER (ghost): reflection of that square across x = cx -> x in [1,2]
    ax.add_patch(Rectangle((1, 0), 1, 1, facecolor=GHOST_C, edgecolor=JUMP_C, lw=2.6,
                           ls=(0, (5, 3)), zorder=4))

    # crease line
    ax.plot([cx, cx], [-0.45, 1.45], color=INK, lw=3.0, zorder=6)
    ax.annotate("crease (mirror line)", (cx, -0.5), ha="center", va="bottom",
                fontsize=12, fontweight="bold", color=INK)

    # label corners + their mirror images so the reflection is unmistakable
    pts = {"A": (0, 0), "B": (0, 1)}
    for name, (px, py) in pts.items():
        mx = 2 * cx - px                                    # mirror across x = cx
        ax.plot(px, py, "o", ms=8, color=BODY_C, zorder=9)
        ax.plot(mx, py, "o", ms=8, color=JUMP_C, zorder=9)
        ax.annotate(name, (px, py), textcoords="offset points", xytext=(-16, -2),
                    fontsize=13, fontweight="bold", color=BODY_C)
        ax.annotate(name + "'", (mx, py), textcoords="offset points", xytext=(8, -2),
                    fontsize=13, fontweight="bold", color=JUMP_C)
        # the reflection arrow for each corner
        _arrow(ax, (px + 0.04, py), (mx - 0.04, py), color="#888888", lw=1.4, mut=12, z=7,
               ls=(0, (3, 2)))

    # big curved fold arrow over the top
    ax.add_patch(FancyArrowPatch((0.5, -0.28), (1.5, -0.28), arrowstyle="-|>", mutation_scale=22,
                                 color=GREEN_C, lw=2.6,
                                 connectionstyle="arc3,rad=-0.45", zorder=8))
    ax.annotate("fold over", (cx, -0.62), ha="center", fontsize=12, color=GREEN_C,
                fontweight="bold")

    ax.text(0.5, 0.5, "BEFORE", ha="center", va="center", fontsize=13, color=BODY_C,
            fontweight="bold", zorder=10)
    ax.text(1.5, 0.5, "AFTER\n(mirror image)", ha="center", va="center", fontsize=12,
            color=JUMP_C, fontweight="bold", zorder=10)

    ax.set_title("One fold = one mirror reflection across the crease.",
                 fontsize=15, fontweight="bold")
    _topleft_axes(ax, (-0.7, 2.5), (1.7, -1.0))
    ax.axis("off")
    return _save(fig, out_path)


# ===================================================== 02 two reflections =====

def _reflect(p, a, b):
    """Reflect point p across the line through a with unit-ish direction b."""
    bx, by = b
    bn = math.hypot(bx, by)
    bx, by = bx / bn, by / bn
    vx, vy = p[0] - a[0], p[1] - a[1]
    dot = vx * bx + vy * by
    # projection onto line, then mirror
    px, py = a[0] + dot * bx, a[1] + dot * by
    return (2 * px - p[0], 2 * py - p[1])


def fig_two_reflections_rotate(out_path):
    """Two mirror lines meeting at angle theta; a small arrow reflected across line 1 then line 2,
    ending rotated by 2*theta. Builds: gamma = 2 * turn (the doubled angle)."""
    fig, ax = plt.subplots(figsize=(8.2, 7.4))

    O = (0.0, 0.0)
    theta = math.radians(35.0)                              # angle between the two mirror lines
    L = 2.6
    # line 1 along +x ; line 2 at angle theta from line 1
    d1 = (math.cos(0.0), math.sin(0.0))
    d2 = (math.cos(theta), math.sin(theta))

    # draw the two mirror lines (full, both directions)
    for d, c, name in ((d1, "#7a7a7a", "mirror line 1"), (d2, "#7a7a7a", "mirror line 2")):
        ax.plot([-L * d[0], L * d[0]], [-L * d[1], L * d[1]], color=c, lw=2.4, zorder=3)
    ax.annotate("mirror line 1", (L * d1[0], L * d1[1]), textcoords="offset points",
                xytext=(6, -2), fontsize=11, color="#555555")
    ax.annotate("mirror line 2", (L * d2[0], L * d2[1]), textcoords="offset points",
                xytext=(6, 4), fontsize=11, color="#555555")

    # mark theta between the lines
    ax.annotate(r"$\theta$ = 35$\degree$", (0.95, 0.30), fontsize=13, color=INK, fontweight="bold")
    # a little arc for theta
    arc = []
    for t in [i / 30.0 * theta for i in range(31)]:
        arc.append((0.85 * math.cos(t), 0.85 * math.sin(t)))
    ax.plot([p[0] for p in arc], [p[1] for p in arc], color=INK, lw=1.4, zorder=4)

    # the moving frame: a short arrow starting at angle -45 deg from line 1
    start_ang = math.radians(-48.0)
    tip0 = (1.7 * math.cos(start_ang), 1.7 * math.sin(start_ang))

    # step 1: reflect across line 1
    tip1 = _reflect(tip0, O, d1)
    # step 2: reflect that across line 2
    tip2 = _reflect(tip1, O, d2)

    _arrow(ax, O, tip0, color=BODY_C, lw=3.0, mut=20, z=9)
    _arrow(ax, O, tip1, color=ORANGE_C, lw=3.0, mut=20, z=9, ls=(0, (5, 3)))
    _arrow(ax, O, tip2, color=GREEN_C, lw=3.0, mut=20, z=9)

    ax.annotate("start", tip0, textcoords="offset points", xytext=(8, -6), fontsize=12,
                color=BODY_C, fontweight="bold")
    ax.annotate("after reflect #1", tip1, textcoords="offset points", xytext=(8, 2), fontsize=12,
                color=ORANGE_C, fontweight="bold")
    ax.annotate("after reflect #2", tip2, textcoords="offset points", xytext=(8, 4), fontsize=12,
                color=GREEN_C, fontweight="bold")

    # the net rotation from start -> tip2 should be 2*theta = 70 deg; draw the swept arc
    a0 = math.atan2(tip0[1], tip0[0])
    a2 = math.atan2(tip2[1], tip2[0])
    # ensure we sweep the +2theta direction
    sweep = []
    n = 40
    for i in range(n + 1):
        t = a0 + (a2 - a0) * i / n
        sweep.append((1.15 * math.cos(t), 1.15 * math.sin(t)))
    ax.plot([p[0] for p in sweep], [p[1] for p in sweep], color=GREEN_C, lw=1.6,
            ls=(0, (2, 2)), zorder=6)
    midt = (a0 + a2) / 2.0
    ax.annotate(r"net turn = 2$\theta$ = 70$\degree$",
                (1.45 * math.cos(midt), 1.45 * math.sin(midt)),
                fontsize=13, color=GREEN_C, fontweight="bold", ha="left")

    ax.plot(0, 0, "o", ms=7, color=INK, zorder=10)

    ax.set_title("Two reflections compose to a rotation by TWICE the angle\n"
                 r"$\rightarrow$ this is why the turn is doubled  ($\gamma$ = 2$\cdot$turn).",
                 fontsize=14, fontweight="bold")
    # NOTE: this is an abstract angle diagram (not the lattice), so keep math +y-up.
    ax.set_xlim(-2.8, 3.4)
    ax.set_ylim(-2.4, 2.8)
    ax.set_aspect("equal")
    ax.axis("off")
    return _save(fig, out_path)


# ================================================= 03 centroid vs jump =========

def _domino_panel(ax, title, color, mode):
    """Render one panel of the SAME along-axis domino fold (rigid 1x2 domino folding over its short
    end). mode='centroid' (Model A) or 'jump' (Model B)."""
    # the domino occupies cells (0,0)+(1,0) [a horizontal 1x2], then folds over its short RIGHT end
    # (the crease at x=2), landing on cells (2,0)+(3,0). We show that one fold.
    _checker(ax, 5, 2, z=1)

    # BEFORE domino: cells (0,0),(1,0)
    before = [(0, 0), (1, 0)]
    after = [(2, 0), (3, 0)]                                  # reflection across crease x=2
    for (cx, cy) in before:
        ax.add_patch(Rectangle((cx, cy), 1, 1, facecolor=PAPER_C, edgecolor=BODY_C, lw=2.2, zorder=4))
    for (cx, cy) in after:
        ax.add_patch(Rectangle((cx, cy), 1, 1, facecolor=GHOST_C, edgecolor="#bbbbbb", lw=1.8,
                               ls=(0, (4, 3)), zorder=3))
    # crease at x = 2
    ax.plot([2, 2], [-0.3, 2.3], color=INK, lw=2.4, zorder=6)
    ax.annotate("crease", (2, -0.34), ha="center", va="bottom", fontsize=11, color=INK,
                fontweight="bold")

    if mode == "centroid":
        # Model A: track the CENTROID of the whole domino.
        c_before = (1.0, 0.5)                                # centroid of (0,0)+(1,0): ((0.5+1.5)/2, 0.5)
        c_after = (3.0, 0.5)                                 # centroid of (2,0)+(3,0)
        # the half-integer centre dots
        for (px, py) in (c_before, c_after):
            ax.plot(px, py, "s", ms=12, color=color, zorder=9)
        # BUT in 2D folds the next domino centre is NOT collinear: the canonical Model-A step is
        # the vector (2,1) — off the axis. Show that next centre at (3,0.5)+(2,1) direction.
        nxt = (c_after[0] + 2.0, c_after[1] + 1.0)
        ax.plot(nxt[0], nxt[1], "s", ms=12, color=color, zorder=9, alpha=0.55)
        _arrow(ax, c_before, c_after, color=color, lw=2.6, mut=18, z=10)
        _arrow(ax, c_after, nxt, color=color, lw=2.6, mut=18, z=10)
        ax.annotate("centre", c_before, textcoords="offset points", xytext=(-6, 14),
                    fontsize=11, color=color, fontweight="bold", ha="center")
        ax.annotate("step = (2,1)", ((c_after[0] + nxt[0]) / 2, (c_after[1] + nxt[1]) / 2),
                    textcoords="offset points", xytext=(8, -2), fontsize=11.5, color=color,
                    fontweight="bold")
        # the off-axis angle atan(1/2)
        ax.annotate(r"angle = atan($\frac{1}{2}$) = 26.57$\degree$",
                    (0.1, 1.55), fontsize=12, color=color, fontweight="bold")
        ax.annotate(r"injects $Q$ = 2$\cdot$atan($\frac{1}{2}$) = 53.13$\degree$",
                    (0.1, 1.85), fontsize=12, color=color, fontweight="bold")
        ax.annotate("OFF-LATTICE artifact", (0.1, 2.18), fontsize=12.5, color=color,
                    fontweight="bold")
    else:
        # Model B: keep ONE cell of the domino; its TWIN fills the gap. The kept cell lands exactly
        # 3 cells away in a straight line — the clean (3,0) "3-jump", turn 0, stays axis-aligned.
        kept_before = (0.5, 0.5)                             # centre of kept cell (0,0)
        # the twin (1,0) fills the gap; kept cell reflects to (3,0)
        kept_after = (3.5, 0.5)                              # centre of cell (3,0)
        # highlight kept cells
        ax.add_patch(Rectangle((0, 0), 1, 1, facecolor="none", edgecolor=color, lw=3.4, zorder=7))
        ax.add_patch(Rectangle((3, 0), 1, 1, facecolor="none", edgecolor=color, lw=3.4,
                               ls=(0, (4, 3)), zorder=7))
        # twin cell that "fills the gap"
        ax.annotate("twin\nfills gap", (1.5, 0.5), ha="center", va="center", fontsize=10,
                    color="#666666", zorder=10)
        ax.plot(kept_before[0], kept_before[1], "o", ms=12, color=color, zorder=9)
        ax.plot(kept_after[0], kept_after[1], "o", ms=12, color=color, zorder=9)
        _arrow(ax, kept_before, kept_after, color=color, lw=2.8, mut=20, z=10)
        ax.annotate("kept cell", kept_before, textcoords="offset points", xytext=(0, 16),
                    fontsize=11, color=color, fontweight="bold", ha="center")
        ax.annotate("3-jump = (3,0):  turn = 0$\\degree$, stays axis-aligned",
                    (2.0, 1.0), textcoords="offset points", xytext=(0, 20),
                    fontsize=11.5, color=color, fontweight="bold", ha="center", va="bottom")

    ax.set_title(title, fontsize=13, fontweight="bold", color=color)
    _topleft_axes(ax, (-0.4, 5.4), (2.7, -0.7))
    ax.set_xticks(range(6))
    ax.set_yticks(range(3))
    ax.tick_params(labelsize=8)
    ax.grid(False)


def fig_centroid_vs_jump(out_path):
    """Two side-by-side panels of the SAME along-axis domino fold. LEFT = naive centroid (Model A),
    RIGHT = jump-strand (Model B)."""
    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.2))
    _domino_panel(axes[0], "naive / Model A:  track the CENTROID", JUMP_C, "centroid")
    _domino_panel(axes[1], "jump-strand / Model B:  keep ONE cell", GREEN_C, "jump")
    fig.suptitle("Same fold, two ways to track it: the centroid leaves the lattice; "
                 "the 3-jump stays on it.", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _save(fig, out_path)


# ================================================= 04 checkerboard sigma =======

def fig_checkerboard_sigma(out_path):
    """A 6x4 grid tinted by (-1)^(x+y); overlay a kept-strand doing a unit step and a 3-jump, mark
    sigma = +/-1 at each cell, show BOTH flip the colour."""
    m, n = 6, 4
    fig, ax = plt.subplots(figsize=(9.6, 6.8))
    _checker(ax, m, n, z=1)

    # sigma = (-1)^(x+y) label at every cell centre
    for y in range(n):
        for x in range(m):
            s = 1 if (x + y) % 2 == 0 else -1
            ax.annotate(f"{'+1' if s > 0 else '-1'}", (x + 0.5, y + 0.5), ha="center", va="center",
                        fontsize=10, color="#7a7a7a", zorder=3)

    def cc(cx, cy):
        return (cx + 0.5, cy + 0.5)

    # unit step: (0,0) -> (1,0). colour +1 -> -1 (flips)
    a, b = (0, 0), (1, 0)
    _arrow(ax, cc(*a), cc(*b), color=BODY_C, lw=3.0, mut=20, z=9)
    for (cx, cy), lab in ((a, "+1"), (b, "-1")):
        ax.add_patch(Rectangle((cx, cy), 1, 1, facecolor="none", edgecolor=BODY_C, lw=3.0, zorder=6))
    ax.annotate("unit step (1,0)\ncolour flips +1 -> -1", cc(0.5, 0),
                textcoords="offset points", xytext=(0, 40), fontsize=11.5, color=BODY_C,
                fontweight="bold", ha="center")

    # 3-jump: (2,2) -> (5,2). colour also flips (x+y parity changes by 3 = odd)
    a2, b2 = (2, 2), (5, 2)
    _arrow(ax, cc(*a2), cc(*b2), color=JUMP_C, lw=3.0, mut=20, z=9, ls=(0, (5, 3)))
    for (cx, cy) in (a2, b2):
        ax.add_patch(Rectangle((cx, cy), 1, 1, facecolor="none", edgecolor=JUMP_C, lw=3.0,
                               ls=(0, (4, 3)), zorder=6))
    # sigma at a2=(2,2): (2+2)=4 even -> +1 ; b2=(5,2): 7 odd -> -1
    ax.annotate("3-jump (3,0)\ncolour flips +1 -> -1", cc(3.5, 2),
                textcoords="offset points", xytext=(0, -44), fontsize=11.5, color=JUMP_C,
                fontweight="bold", ha="center")

    ax.set_title(r"$\sigma$ = (-1)$^{(x+y)}$: every unit step AND every 3-jump flips the "
                 "checkerboard colour.", fontsize=14, fontweight="bold")
    _topleft_axes(ax, (-0.4, m + 0.4), (n + 0.6, -0.6))
    ax.set_xticks(range(m + 1))
    ax.set_yticks(range(n + 1))
    ax.tick_params(labelsize=8)
    return _save(fig, out_path)


# ============================================================= 05 funnel =======

def fig_funnel(out_path):
    """Horizontal funnel of the 6x8 non-corner 2+1 filter funnel. Counts are HARDCODED and must
    not change."""
    # (label, count)  — gate stages, top to bottom
    stages = [
        ("covered", 22180),
        ("exit-footprint", 1109),
        ("parity", 644),
        ("reflection (survivors)", 434),
    ]
    # terminal split of the 434 reflection-survivors
    fold_n, jam_n = 432, 2

    fig, ax = plt.subplots(figsize=(11.0, 6.4))

    maxc = stages[0][1]
    bar_h = 0.62
    y = 0
    yticks, ylabels = [], []
    colors = ["#9ecae1", "#6baed6", "#4292c6", "#2171b5"]
    for i, (name, cnt) in enumerate(stages):
        w = cnt / maxc
        ax.add_patch(Rectangle((0, y - bar_h / 2), w, bar_h, facecolor=colors[i],
                               edgecolor="#08306b", lw=1.4, zorder=4))
        ax.annotate(f"{cnt:,}", (w, y), textcoords="offset points", xytext=(10, 0),
                    va="center", fontsize=13, fontweight="bold", color=INK, zorder=6)
        yticks.append(y)
        ylabels.append(name)
        y -= 1

    # terminal split bars (FOLD vs JAM) drawn from the reflection-survivor width
    surv_w = stages[-1][1] / maxc
    fy = y
    fold_w = fold_n / maxc
    jam_w = jam_n / maxc
    ax.add_patch(Rectangle((0, fy - bar_h / 2), fold_w, bar_h, facecolor=GREEN_C,
                           edgecolor="#0b5e0b", lw=1.4, zorder=4))
    ax.annotate(f"FOLD (Tw=0): {fold_n}", (fold_w, fy), textcoords="offset points", xytext=(10, 0),
                va="center", fontsize=13, fontweight="bold", color=GREEN_C, zorder=6)
    yticks.append(fy)
    ylabels.append("twist -> FOLD")
    y -= 1

    jy = y
    # make the 2-jam bar visible with a minimum width
    jam_draw_w = max(jam_w, 0.012)
    ax.add_patch(Rectangle((0, jy - bar_h / 2), jam_draw_w, bar_h, facecolor=JUMP_C,
                           edgecolor="#7a1010", lw=1.4, zorder=5))
    ax.annotate(f"JAM (Tw != 0): {jam_n}", (jam_draw_w, jy), textcoords="offset points",
                xytext=(10, 0), va="center", fontsize=13, fontweight="bold", color=JUMP_C, zorder=6)
    yticks.append(jy)
    ylabels.append("twist -> JAM")

    # bracket showing 434 splits into 432 + 2 (placed well right of the terminal labels)
    bx = 0.62
    ax.annotate("", xy=(bx, fy), xytext=(bx, jy),
                arrowprops=dict(arrowstyle="-", color="#888888", lw=1.2))
    ax.annotate("434 = 432 + 2", (bx + 0.02, (fy + jy) / 2), va="center", fontsize=11,
                color="#555555", rotation=90, ha="left")

    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels, fontsize=12)
    ax.set_xlim(0, 1.35)
    ax.set_xticks([])
    ax.set_ylim(jy - 0.8, 0.8)
    for spine in ("top", "right", "bottom"):
        ax.spines[spine].set_visible(False)
    ax.set_title("Each gate cuts the field: 22,180 candidates -> 434 survive -> "
                 "twist catches the last 2 jams.", fontsize=14, fontweight="bold")
    fig.tight_layout()
    return _save(fig, out_path)


# ================================================================= main ========

def main():
    p = argparse.ArgumentParser(description="Render the 2+1 twist intuition PNGs (read-only).")
    p.add_argument("--outdir", default=os.path.join(os.path.dirname(os.path.dirname(
                       os.path.abspath(__file__))), "docs", "research", "img", "twist", "intro"),
                   help="output directory (default: docs/research/img/twist/intro)")
    ns = p.parse_args()
    out = ns.outdir
    os.makedirs(out, exist_ok=True)

    jobs = [
        ("01_fold_is_reflection.png", fig_fold_is_reflection),
        ("02_two_reflections_rotate.png", fig_two_reflections_rotate),
        ("03_centroid_vs_jump.png", fig_centroid_vs_jump),
        ("04_checkerboard_sigma.png", fig_checkerboard_sigma),
        ("05_funnel.png", fig_funnel),
    ]
    for fname, fn in jobs:
        path = os.path.join(out, fname)
        fn(path)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
