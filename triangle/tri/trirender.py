"""trirender.py — matplotlib rendering for the triangle-lattice PoC.

Draws each triangle as a filled Polygon tinted by sigma (UP=blue/+1, DOWN=red/-1), with an
optional chain overlay (A/B/C colored + numbered centroid walks) and a footprint outline.
Palette matches the square-track figures.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trilattice as TL  # noqa: E402
import matplotlib            # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from matplotlib.patches import Polygon   # noqa: E402
from tristyle import (draw_footprints, draw_walk_arrows, save,   # noqa: E402
                      TINT_UP, TINT_DN, CHAIN, INK, VLY, MNT, GRID_EDGE, MUTED)

# OUT is mutated externally by the engine (find_example.set_outdir sets TR.OUT) -> keep it here.
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "report", "tri")


def _poly(tid):
    return [TL.vcart(v) for v in TL.tri_vertices(tid)]


def draw_lattice(ax, lat, sigma_fill=True, label_sigma=False):
    for t in lat.tris:
        fc = (TINT_UP if TL.sigma(t) > 0 else TINT_DN) if sigma_fill else "white"
        ax.add_patch(Polygon(_poly(t), closed=True, facecolor=fc, edgecolor=GRID_EDGE, lw=0.8, zorder=1))
        if label_sigma:
            cx, cy = TL.centroid(t)
            ax.text(cx, cy, "+" if TL.sigma(t) > 0 else "−", ha="center", va="center",
                    color=VLY if TL.sigma(t) > 0 else MNT, fontsize=8, zorder=3)
    ax.set_aspect("equal"); ax.axis("off")


def overlay_walk(ax, walk, color, number=True, lw=2.4, z=6):
    cents = [TL.centroid(t) for t in walk]
    xs, ys = zip(*cents)
    ax.plot(xs, ys, "-", color=color, lw=lw, solid_capstyle="round", zorder=z)
    ax.plot(xs, ys, "o", color=color, ms=4, zorder=z + 1)
    draw_walk_arrows(ax, cents, color, z=z + 1)      # per-step direction arrowheads
    if number:
        for k, (x, y) in enumerate(cents):
            ax.text(x, y, str(k), ha="center", va="center", color="white", fontsize=6,
                    zorder=z + 2, fontweight="bold")


def fill_chain(ax, walk, color, alpha=0.30):
    for t in walk:
        ax.add_patch(Polygon(_poly(t), closed=True, facecolor=color, edgecolor="none",
                             alpha=alpha, zorder=2))


def outline_footprint(ax, fp, end_fp=None):
    # START hub (purple, faint fill) + unfolded chain-END tiles (purple, dashed), A/B/C in chain order
    draw_footprints(ax, _poly, fp, end_fp, z0=3.6, labelsize=10)


def render_tiling(lat, chains, title, out_name, twist_note="", footprint=None,
                  end_footprint=None):
    """Draw a sigma-tinted lattice + A/B/C chain overlays (+ optional START/END footprints); save
    under OUT and return the PNG path."""
    fig, ax = plt.subplots(figsize=(7.6, 6.4))
    draw_lattice(ax, lat, sigma_fill=True)
    for ci, w in enumerate(chains):
        fill_chain(ax, w, CHAIN[ci % 3])
        overlay_walk(ax, w, CHAIN[ci % 3])
    if footprint:
        outline_footprint(ax, footprint, end_footprint)
    xs = [p[0] for t in lat.tris for p in _poly(t)]
    ys = [p[1] for t in lat.tris for p in _poly(t)]
    ax.set_xlim(min(xs) - 0.5, max(xs) + 2.8)
    ax.set_ylim(min(ys) - 0.5, max(ys) + 0.5)
    ax.text(max(xs) + 0.3, max(ys), title, ha="left", va="top", fontsize=12,
            fontweight="bold", color=INK)
    if twist_note:
        ax.text(max(xs) + 0.3, max(ys) - 0.9, twist_note, ha="left", va="top", fontsize=9,
                color=MUTED, family="monospace")
    return save(fig, os.path.join(OUT, out_name))
