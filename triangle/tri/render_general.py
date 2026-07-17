"""render_general.py — render a 1+1+1 fold on ANY tiling module that exposes
tile_cart(tid)->[cart pts], centroid(tid)->(x,y), sigma(tid)->+-1 (e.g. righttri, scalene)."""
import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from matplotlib.patches import Polygon   # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tristyle import (draw_footprints, draw_walk_arrows, save,   # noqa: E402
                      TINT_UP, TINT_DN, CHAIN, GRID_EDGE, INK, MUTED)

# OUT is mutated externally by the engine (find_example.set_outdir sets RG.OUT) -> keep it here.
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "report", "tri")


def render(latmod, chains, footprint, title, out_name, note="", end_footprint=None,
           region=None, partners=None, end_chirality=None):
    # region defaults to the chain union (1+1+1); for 2+1 the caller passes the FULL region so the
    # rigid-domino PARTNER tiles are drawn too (else the END footprint 'B' = partners[-1] floats).
    region = set(region) if region is not None else set().union(*[set(c) for c in chains])
    # LARGE region axis (left) + figure-relative note panel (right), so the drawn pattern is big and
    # not shrunk by the text column the way the old single-axis (+3.8-unit) layout shrank it.
    fig = plt.figure(figsize=(10.6, 7.4))
    ax = fig.add_axes([0.015, 0.02, 0.70, 0.90])
    ax.set_aspect("equal"); ax.axis("off")
    axR = fig.add_axes([0.72, 0.02, 0.27, 0.90])
    axR.set_xlim(0, 1); axR.set_ylim(0, 1); axR.axis("off")
    for t in region:
        ax.add_patch(Polygon(latmod.tile_cart(t), closed=True,
                             facecolor=TINT_UP if latmod.sigma(t) > 0 else TINT_DN,
                             edgecolor=GRID_EDGE, lw=0.5, zorder=1))
    # 2+1: shade the rigid-domino partner tiles as part of the 2-chain block (strand colour, no line)
    if partners:
        for t in partners:
            ax.add_patch(Polygon(latmod.tile_cart(t), closed=True, facecolor=CHAIN[0],
                                 edgecolor="none", alpha=0.30, zorder=2))
    for ci, w in enumerate(chains):
        for t in w:
            ax.add_patch(Polygon(latmod.tile_cart(t), closed=True, facecolor=CHAIN[ci],
                                 edgecolor="none", alpha=0.30, zorder=2))
        cents = [latmod.centroid(t) for t in w]
        xs, ys = zip(*cents)
        ax.plot(xs, ys, "-o", color=CHAIN[ci], lw=2.0, ms=3, zorder=6)
        draw_walk_arrows(ax, cents, CHAIN[ci], z=6)   # per-step direction arrowheads
        for k, (x, y) in enumerate(cents):
            ax.text(x, y, str(k), ha="center", va="center", color="white", fontsize=5, zorder=7)
    # START hub (purple, faint fill) + unfolded chain-END tiles, A/B/C in chain order; END recoloured by
    # return orientation (green=proper/rotation, amber=mirror, red=off-cell) from end_chirality.
    draw_footprints(ax, latmod.tile_cart, footprint, end_footprint, z0=3.6, labelsize=10,
                    end_chirality=end_chirality)
    pts = [p for t in region for p in latmod.tile_cart(t)]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    pad = 0.5
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - pad, max(ys) + pad)
    fig.text(0.5, 0.985, title, ha="center", va="top", fontsize=12, fontweight="bold", color=INK)
    if note:
        axR.text(0.02, 0.98, note, ha="left", va="top", fontsize=8.0, family="monospace", color=MUTED)
    return save(fig, os.path.join(OUT, out_name))
