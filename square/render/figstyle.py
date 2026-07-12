"""figstyle.py — single source of truth for report figures (square-lattice fold patterns).

Every matplotlib renderer in the square track imports this so the report PNGs share one palette,
grid convention, legend layout, fonts, and dpi. Covers both figure kinds:
  - FOLDSHEET  — the printable pattern a person folds (base cells / footprint / creases / slits).
  - ANALYSIS   — the twist/geometry diagram with per-turn annotations + verdict.

Convention (matches the viewer / fold.py): origin TOP-LEFT, +x right, +y DOWN. Cells are integer
(x, y); cell centres are (x+0.5, y+0.5).

Consumers: square/render/render_square.py (3-stack foldsheet), square/render/render_twostack.py
(2-stack, both kinds), square/render/render_twist_2plus1.py (2+1 analysis). Triangle renderers
(triangle/tri/render_*.py) are a separate, independent package and do not import this module.

Backend is forced to Agg here (headless) BEFORE pyplot is imported, so importing figstyle is enough.
"""
import os
from fractions import Fraction

import matplotlib
matplotlib.use("Agg")                          # headless: no display; set before pyplot import
import matplotlib.pyplot as plt                # noqa: E402
from matplotlib.patches import Rectangle, FancyArrowPatch, Patch  # noqa: E402
from matplotlib.lines import Line2D            # noqa: E402

# ------------------------------------------------------------------ palette ----
# Chain / strand colors (A / B / C) — the canonical anchor shared with the tri track.
CHAIN = ["#1f77b4", "#e8820c", "#2ca02c"]      # A blue / B orange / C green
FOOTPRINT_EDGE = "#6f4fb0"                     # tromino destination outline (purple)
GRID_EDGE = "#dddddd"                          # cell gridlines (light grey)
INK = "#222222"                                # text / labels / near-black borders

# Semantic colors (creases, cuts, highlights, verdicts).
JUMP = "#d62728"                               # 3-jump (along-axis fold) highlight (red)
SEAM = "#2ca02c"                               # hub seam where chains rejoin (green)
MNT = "#d83232"                                # crease — mountain (away)
VLY = "#3399cc"                                # crease — valley (toward you)
CUT = "#2a8f6f"                                # slit — interior cut (teal)
BOUNDARY = "#222222"                           # cut-around outer silhouette
POS = "#1a7f37"                                # +contribution label (green)
NEG = "#c0392b"                                # -contribution label (red)
FOLD_BADGE = "#1a7f48"                         # FOLD verdict (green)
JAM_BADGE = "#c0392b"                          # JAM verdict (red)

# Checkerboard sigma = (-1)^(x+y) parity tint (analysis backgrounds) — red/blue by cell parity,
# standardised across every square-track analysis figure (2-stack turn diagram, 2+1 twist diagram).
PARITY_RED = "#f2c6c6"                         # even (x+y)
PARITY_BLUE = "#c6d5f2"                        # odd  (x+y)

# Shared line styles + sizes (kill the per-file drift).
DASH = (0, (4, 2))                             # one dashed style for all cut/jump dashes
DPI = 150                                      # one dpi for the whole square track
FP_LW = 2.6                                    # footprint outline width
GRID_LW = 0.8

# Fold-direction unit vectors in SCREEN coords (+y is DOWN, matching the viewer / fold.py).
ARROW = {"L": (-1, 0), "R": (1, 0), "U": (0, -1), "D": (0, 1)}


def apply_style():
    """Set the shared matplotlib rcParams once (idempotent). Call at module import of a renderer."""
    plt.rcParams.update({
        "figure.dpi": DPI,
        "savefig.dpi": DPI,
        "savefig.bbox": "tight",
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.edgecolor": INK,
        "legend.fontsize": 8,
        "legend.frameon": False,
    })


apply_style()                                  # apply on import so every consumer inherits it


# -------------------------------------------------------------- coordinates ----

def cells(seq):
    """Normalize a list of {x,y} dicts (or [x,y]/(x,y) pairs) to (x, y) int tuples."""
    out = []
    for c in seq:
        out.append((c["x"], c["y"]) if isinstance(c, dict) else (c[0], c[1]))
    return out


def chain_color(i):
    """Color for chain index i (A/B/C, wrapping)."""
    return CHAIN[i % len(CHAIN)]


# -------------------------------------------------------------------- axes -----

def new_grid_axes(m, n, *, pad=0.3, extra_w=0.0, ticklabels=True):
    """Make (fig, ax) for an m×n grid with the viewer convention (origin top-left, +y down),
    equal aspect, integer ticks. `extra_w` widens the figure to leave room for a side legend.
    `ticklabels=False` hides the axis numbers (foldsheets: the cells + letters already locate every
    position, and the numbers would collide with the sub-notes). I/O: (m, n, ...) -> (fig, ax)."""
    fig, ax = plt.subplots(figsize=(max(4.5, m * 0.7 + 2.5 + extra_w), max(3.5, n * 0.7 + 1.6)))
    ax.set_xlim(-pad, m + pad)
    ax.set_ylim(n + pad, -pad)                 # inverted y -> +y down
    ax.set_aspect("equal")
    ax.set_xticks(range(m + 1))
    ax.set_yticks(range(n + 1))
    ax.tick_params(labelsize=6, length=0)
    if not ticklabels:
        ax.set_xticklabels([])
        ax.set_yticklabels([])
    return fig, ax


def draw_grid_cells(ax, m, n, *, checker=False):
    """Fill the base m×n grid: plain white, or a sigma=(-1)^(x+y) red/blue parity tint when
    checker=True (the same tile-parity coloring shared by every square analysis figure)."""
    for y in range(n):
        for x in range(m):
            if checker:
                fc = PARITY_RED if (x + y) % 2 == 0 else PARITY_BLUE
            else:
                fc = "white"
            ax.add_patch(Rectangle((x, y), 1, 1, facecolor=fc, edgecolor=GRID_EDGE,
                                   lw=GRID_LW, zorder=1))


def draw_footprint(ax, fp_cells, *, letters=None):
    """Outline the footprint cells (purple). If `letters` (e.g. "ABC") given, label each cell centre.
    I/O: (ax, list[(x,y)], letters=None) -> None."""
    for i, (x, y) in enumerate(cells(fp_cells)):
        ax.add_patch(Rectangle((x, y), 1, 1, facecolor="none", edgecolor=FOOTPRINT_EDGE,
                               lw=FP_LW, zorder=5))
        if letters:
            ax.text(x + 0.5, y + 0.5, letters[i % len(letters)], ha="center", va="center",
                    color=FOOTPRINT_EDGE, fontsize=11, fontweight="bold", zorder=10)


def draw_end_footprint(ax, fp_cells):
    """Outline the ENDING footprint (each chain's terminal placement cells, unioned) — dashed purple
    so it reads as the far end of the fold path, distinct from the solid starting footprint.
    I/O: (ax, list[(x,y)]) -> None."""
    for (x, y) in cells(fp_cells):
        ax.add_patch(Rectangle((x, y), 1, 1, facecolor="none", edgecolor=FOOTPRINT_EDGE,
                               lw=FP_LW, ls=DASH, zorder=5))


def draw_base_cells(ax, base, color, letter):
    """Tint a chain's base cells + drop its letter at each. I/O: (ax, list[(x,y)], color, str)."""
    for (x, y) in base:
        ax.add_patch(Rectangle((x, y), 1, 1, facecolor=color, edgecolor="none",
                               alpha=0.32, zorder=2))
        ax.text(x + 0.5, y + 0.5, letter, ha="center", va="center", color=color,
                fontsize=12, fontweight="bold", zorder=6)


def draw_fold_path(ax, path, color):
    """Draw a chain's true per-step fold path (real cell-center positions, e.g. from
    twist_jump.strand_path — physically replayed, not a fan) as a connected polyline with
    per-segment arrowheads. I/O: (ax, list[(x,y)], color) -> None."""
    for p, q in zip(path, path[1:]):
        ax.plot([p[0], q[0]], [p[1], q[1]], color=color, lw=1.6, zorder=6, alpha=0.85,
                solid_capstyle="round")
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=10,
                                     color=color, lw=0, zorder=7))


REFLECTION_SPLIT = 0.045    # perpendicular offset of each chain's half-arrow off the shared centerline


def draw_reflection(ax, seed, segs, passed):
    """Overlay the reflection gate for one shared-crease pair. The seed crease is drawn as one
    directed arrow (tinted by pass/fail — this IS the crease arrow in the starting foldsheet, oriented
    per Fold._crease_segment's +x/+y tangent convention). Each chain's reflected image segment
    (Fold.reflection_verdict's own segI/segJ — coincident on PASS) is drawn as a short half-width arrow
    offset to its own side of the centerline, so both chains stay visible instead of one hiding the
    other when they land on the identical segment.
    segs = list of (color, seg) with seg = ((x0,y0),(x1,y1)). I/O: (ax, seg, list, bool) -> None."""
    badge = FOLD_BADGE if passed else JAM_BADGE
    ax.add_patch(FancyArrowPatch(seed[0], seed[1], arrowstyle="-|>", mutation_scale=13,
                                 lw=3.0, color=badge, zorder=8, alpha=0.9))
    n = len(segs)
    for k, (color, (p, q)) in enumerate(segs):
        dx, dy = q[0] - p[0], q[1] - p[1]
        perp = (-dy, dx)                                    # unit perp (segs are axis-aligned, unit length)
        off = REFLECTION_SPLIT * (2 * k - (n - 1))          # spread each half to its own side, symmetric
        pk = (p[0] + perp[0] * off, p[1] + perp[1] * off)
        qk = (q[0] + perp[0] * off, q[1] + perp[1] * off)
        ax.add_patch(FancyArrowPatch(pk, qk, arrowstyle="-|>", mutation_scale=9, lw=1.8,
                                     color=color, ls=DASH, zorder=9, alpha=0.95))


# ------------------------------------------------------------------ legend -----

def line_handle(color, label, *, lw=2.4, ls="-"):
    """A Line2D legend handle (creases, strands, boundaries)."""
    return Line2D([], [], color=color, lw=lw, ls=ls, label=label)


def patch_handle(color, label, *, alpha=0.32, edgecolor=None):
    """A filled-swatch legend handle (base cells, footprint)."""
    return Patch(facecolor=color, edgecolor=edgecolor or color, alpha=alpha, label=label)


def legend_panel(ax, handles, *, loc="upper left", anchor=(1.01, 1.0)):
    """Place the canonical side legend (right of the axes, frameless). One builder so every variant
    matches. I/O: (ax, list[handle], ...) -> Legend."""
    return ax.legend(handles=handles, loc=loc, bbox_to_anchor=anchor)


# -------------------------------------------------------------------- angles ---

def pi_label(deg, *, signed=True):
    """Format a turn/twist angle in degrees as a multiple of π (standardised across every square
    analysis figure, replacing raw degree labels). E.g. 180 -> "+1π", -360 -> "-2π",
    90 -> "+1/2π", 0 -> "0". I/O: (degrees: float) -> str."""
    frac = Fraction(deg / 180).limit_denominator(12)
    if frac == 0:
        return "0"
    sign = "+" if frac > 0 else "-"
    frac = abs(frac)
    body = "π" if frac == 1 else (f"{frac.numerator}/{frac.denominator}π" if frac.denominator != 1
                                        else f"{frac.numerator}π")
    return f"{sign}{body}" if signed else body


# ----------------------------------------------------------------- verdict -----

_GATE_ORDER = [("arithmetic", "arith"), ("exitFootprint", "exit"), ("parity", "par"),
               ("vectorParity", "vpar"), ("reflection", "refl"), ("twist", "twist")]


def verdict_line(verdict):
    """One-line gate summary: ✓/✗/–(undecided) per gate. I/O: (verdict dict) -> str."""
    bits = []
    for key, label in _GATE_ORDER:
        v = verdict.get(key)
        bits.append(f"{label}={'–' if v is None else ('✓' if v else '✗')}")
    return "  ".join(bits)


def verdict_badge(foldable):
    """(text, color) for a FOLD/JAM/untested badge. I/O: (bool|None) -> (str, color)."""
    if foldable is None:
        return "untested", "#888888"
    return ("FOLD", FOLD_BADGE) if foldable else ("JAM", JAM_BADGE)


def draw_subnotes(ax, lines):
    """Stack monospace sub-notes (chain detail, verdict line) below the axes. I/O: (ax, list[str])."""
    y = -0.02
    for text in lines:
        ax.text(0.5, y, text, transform=ax.transAxes, ha="center", va="top",
                fontsize=7, color="#444", family="monospace")
        y -= 0.07


# -------------------------------------------------------------------- save -----

def save(fig, out_path, *, dpi=DPI):
    """makedirs + savefig(tight) + close — the repeated tail in every renderer. Returns out_path."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    try:
        fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    finally:
        plt.close(fig)                         # always release the figure, even on error
    return out_path
