"""render_general.py — render a 1+1+1 fold on ANY tiling module that exposes
tile_cart(tid)->[cart pts], centroid(tid)->(x,y), sigma(tid)->+-1 (e.g. righttri, scalene)."""
import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from matplotlib.patches import Polygon   # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from foldsheet_tri import draw_footprints  # noqa: E402  shared start+end footprint highlighter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "report", "tri")
TINT = {1: "#eaf3fb", -1: "#fdeeee"}
CH = ["#1f77b4", "#e8820c", "#2ca02c"]


def render(latmod, chains, footprint, title, out_name, note="", end_footprint=None,
           region=None, partners=None):
    # region defaults to the chain union (1+1+1); for 2+1 the caller passes the FULL region so the
    # rigid-domino PARTNER tiles are drawn too (else the END footprint 'B' = partners[-1] floats).
    region = set(region) if region is not None else set().union(*[set(c) for c in chains])
    fig, ax = plt.subplots(figsize=(7.8, 6.4))
    ax.set_aspect("equal"); ax.axis("off")
    for t in region:
        ax.add_patch(Polygon(latmod.tile_cart(t), closed=True, facecolor=TINT[latmod.sigma(t)],
                             edgecolor="#bbb", lw=0.5, zorder=1))
    # 2+1: shade the rigid-domino partner tiles as part of the 2-chain block (strand colour, no line)
    if partners:
        for t in partners:
            ax.add_patch(Polygon(latmod.tile_cart(t), closed=True, facecolor=CH[0],
                                 edgecolor="none", alpha=0.30, zorder=2))
    for ci, w in enumerate(chains):
        for t in w:
            ax.add_patch(Polygon(latmod.tile_cart(t), closed=True, facecolor=CH[ci],
                                 edgecolor="none", alpha=0.30, zorder=2))
        cents = [latmod.centroid(t) for t in w]
        xs, ys = zip(*cents)
        ax.plot(xs, ys, "-o", color=CH[ci], lw=2.0, ms=3, zorder=6)
        for k, (x, y) in enumerate(cents):
            ax.text(x, y, str(k), ha="center", va="center", color="white", fontsize=5, zorder=7)
    # START hub (teal, filled) + unfolded chain-END tiles (purple, dashed), A/B/C in chain order
    draw_footprints(ax, latmod.tile_cart, footprint, end_footprint, z0=3.6, labelsize=10)
    pts = [p for t in region for p in latmod.tile_cart(t)]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    ax.set_xlim(min(xs) - 0.5, max(xs) + 3.8)
    ax.set_ylim(min(ys) - 0.5, max(ys) + 0.5)
    ax.text(max(xs) + 0.3, max(ys), title, ha="left", va="top", fontsize=12, fontweight="bold",
            color="#222")
    if note:
        ax.text(max(xs) + 0.3, max(ys) - 0.9, note, ha="left", va="top", fontsize=9,
                family="monospace", color="#444")
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, out_name)
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p
