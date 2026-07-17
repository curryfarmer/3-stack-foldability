"""tristyle.py — single source of truth for report figures (triangle / non-square tilings).

Every matplotlib renderer in the triangle track imports this so the report PNGs share one palette,
dpi, fonts, save tail, and footprint drawer. Covers all the tiling figure kinds:
  - FOLDSHEET  — the printable pattern a person folds (foldsheet_tri.make_sheet).
  - OVERLAY    — the unfolded region with the chain walks + start/end footprints (trirender,
                 render_general).
  - REFLECTION — the crease-mirror composition that carries END onto START (render_reflection).
  - TWIST      — the reduced twist-loop diagram with per-vertex sigma*gamma (render_twist).

Convention: Cartesian, origin BOTTOM-LEFT, +y UP (native matplotlib). This is the opposite of the
square track's viewer convention (+y DOWN); the two tracks never share an axis, so the difference is
intentional and spec'd in docs/guides/STYLE_SPEC.md — not a bug to unify.

This is the triangle analog of square/render/figstyle.py. The two are SEPARATE, INDEPENDENT packages
and NEVER import each other; they only agree, by hand, on the handful of shared palette hexes (a
source-level test in smoketest/test_style_parity.py enforces that agreement by parsing both files, not
by importing). tristyle imports only stdlib + matplotlib.

Backend is forced to Agg here (headless) BEFORE pyplot is imported, so importing tristyle is enough.
"""
import os
from fractions import Fraction

import matplotlib
matplotlib.use("Agg")                          # headless: no display; set before pyplot import
import matplotlib.pyplot as plt                # noqa: E402
from matplotlib.patches import Polygon, FancyArrowPatch  # noqa: E402

# ------------------------------------------------------------------ palette ----
# Shared with the square track (figstyle.py) — IDENTICAL hex, same names, enforced by
# smoketest/test_style_parity.py (source compare, no import). A/B/C chain anchors + the semantic
# crease/cut/verdict colors.
CHAIN = ["#1f77b4", "#e8820c", "#2ca02c"]      # A blue / B orange / C green (= figstyle.CHAIN[:3])
INK = "#222222"                                # text / labels / near-black borders
MNT = "#d83232"                                # crease — mountain (away)
VLY = "#3399cc"                                # crease — valley (toward you)
CUT = "#2a8f6f"                                # slit — interior cut (teal)
FOOTPRINT_EDGE = "#6f4fb0"                     # footprint / loop / reflection-arrow outline (purple)
POS = "#1a7f37"                                # +contribution label (green)
NEG = "#c0392b"                                # -contribution label (red)
FOLD_BADGE = "#1a7f48"                         # FOLD verdict (green)
JAM_BADGE = "#c0392b"                          # JAM verdict (red)
MUTED = "#444"                                 # sub-notes / secondary caption grey (shared w/ square)
# sigma = orientation-parity tile tint — UNIFIED with the square track (figstyle PARITY_RED/BLUE) so a
# triangle sheet and a square sheet tint their two-colour background identically.
PARITY_RED = "#f2c6c6"                         # sigma up (+1)   (== figstyle even (x+y))
PARITY_BLUE = "#c6d5f2"                         # sigma down (-1) (== figstyle odd  (x+y))

# Triangle-only (no square counterpart — the parity test must NOT require these to match figstyle).
# START footprint is drawn purple (FOOTPRINT_EDGE, solid) — unified with the square track; only the
# fill (faint purple) is triangle-specific, since the square start footprint carries no fill.
START_FILL = "#efeaf7"                         # START hub fill (faint purple, matches purple outline)
RIGID = "#b0b0b0"                              # rigid hub seam — keep attached, flat (NOT a cut)
TINT = ["#eaf3fb", "#fdeeee", "#eafaef"]       # per-chain faint fill (analog of square CHAIN+alpha)
TINT_UP, TINT_DN = PARITY_RED, PARITY_BLUE     # sigma up (+1) / down (-1) tile fill (unified w/ square)
GRID_EDGE = "#dddddd"                          # tile gridlines (light grey) — one value, whole track
CREASE_COL = "#b06f4f"                         # reflection mirror-axis (brown)
TILE_FILL = "#f2f3f7"                          # twist-diagram context tiles — fill
TILE_EDGE = "#d7d9e0"                          # twist-diagram context tiles — edge
# Orientation-aware END colouring (from seam_filter.tile_chirality): each END tile is painted by how it
# returns onto its START cell. proper=aligned (rotation), mirror=sides swapped, off-cell=landed wrong.
CHIR_COLOR = {"proper": "#2ca02c", "uniform": "#2ca02c", "mirror": "#e8820c", "off-cell": "#d83232"}
CHIR_TAG = {"proper": "rot", "uniform": "=", "mirror": "flip", "off-cell": "off"}

DPI = 150                                      # one dpi for the whole triangle track (was 150/160/170)


def apply_style():
    """Set the shared matplotlib rcParams once (idempotent). Called at import so every consumer
    inherits it. Mirrors figstyle.apply_style so both tracks share fonts / dpi / legend chrome."""
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


# ------------------------------------------------------------- footprints ------

def draw_footprints(ax, tile_cart, start_fp, end_fp=None, z0=8.4, labelsize=11, end_chirality=None):
    """Highlight the START footprint (purple, solid, faint fill) and the unfolded END footprint (purple,
    dashed) with A/B/C labels in
    chain order (A=chain0, B=mid, C=chain2 in BOTH). Either may be None. Generic over n-gons.
    end_chirality (seam_filter.tile_chirality dict) recolours each END tile by its return orientation:
    green=proper(rotation)/uniform, amber=mirror(flipped/sides-swapped), red=off-cell. When None, the
    END is drawn neutral purple (no orientation claim)."""
    per = (end_chirality or {}).get("per_tile") or []

    def _one(fp, fill, outline, dashes, zf, zo, zt, nudge, chir=None):
        if not fp:
            return
        for ci, t in enumerate(fp):
            pc = tile_cart(t)
            n = len(pc)
            cx = sum(p[0] for p in pc) / n
            cy = sum(p[1] for p in pc) / n
            klass = chir[ci]["klass"] if (chir and ci < len(chir)) else None
            oc = CHIR_COLOR.get(klass, outline)
            if fill is not None:
                ax.add_patch(Polygon(pc, closed=True, facecolor=fill, edgecolor="none", zorder=zf))
            kw = dict(facecolor="none", edgecolor=oc, lw=2.6, zorder=zo)
            if dashes is not None:
                kw["linestyle"] = (0, dashes)
            ax.add_patch(Polygon(pc, closed=True, **kw))
            vx, vy = pc[0]                       # nudge the label toward vertex0 so start/end don't collide
            # Scale the nudge by 3/n: tuned for triangles (n=3); on rounder n-gons (e.g. hexagons,
            # n=6) the same fraction of a single vertex's pull reads as visibly off-centre, since
            # there are more, closer-together vertices to pull toward.
            nf = nudge * min(1.0, 3.0 / n)
            ax.text(cx + nf * (vx - cx), cy + nf * (vy - cy), "ABC"[ci % 3], ha="center",
                    va="center", color=oc, fontsize=labelsize, fontweight="bold", zorder=zt,
                    bbox=dict(boxstyle="circle,pad=0.12", fc="white", ec=oc, lw=0.8, alpha=0.85))
            if klass:                            # orientation tag beside the END label (the seam verdict)
                ax.text(cx - nf * (vx - cx), cy - nf * (vy - cy), CHIR_TAG.get(klass, "?"),
                        ha="center", va="center", color=oc, fontsize=labelsize - 4, fontweight="bold",
                        zorder=zt, bbox=dict(boxstyle="round,pad=0.1", fc="white", ec=oc, lw=0.7,
                                             alpha=0.9))
    _one(start_fp, START_FILL, FOOTPRINT_EDGE, None,     z0,       z0 + 0.2, z0 + 0.3, -0.16)
    _one(end_fp,   None,       FOOTPRINT_EDGE, (4, 2.4), z0 + 0.5, z0 + 0.7, z0 + 0.9, +0.16, chir=per)


def draw_walk_arrows(ax, pts, color, *, z=7, scale=10):
    """Per-segment arrowheads for a centroid walk — the triangle analog of figstyle.draw_fold_path's
    arrow loop. Draws ONLY the arrowheads (lw=0), so a caller keeps its own polyline + node dots + step
    numbers and just overlays the direction. I/O: (ax, list[(x,y)], color) -> None."""
    for p, q in zip(pts, pts[1:]):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=scale, color=color,
                                     lw=0, zorder=z))


# ------------------------------------------------------------------ labels -----

def pi_label(deg, *, signed=True):
    """Format a turn/twist angle in degrees as a multiple of π (standardised across every triangle
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


# -------------------------------------------------------------------- save -----

def save(fig, out_path, *, dpi=DPI):
    """makedirs + savefig(tight) + close — the repeated tail in every renderer. Returns out_path."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    try:
        fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    finally:
        plt.close(fig)                         # always release the figure, even on error
    return out_path
