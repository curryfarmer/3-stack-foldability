"""foldsheet_tri.py — printable physical fold pattern (make-sheet) for a 1+1+1 fold on any
reflection tiling (righttri / scalene). Analog of py/make_foldsheets.py for the square grid.

Edge roles (the structural part, certain):
  - CREASE (fold): an interior edge between two CONSECUTIVE tiles of the same chain.
  - SLIT (cut): any other interior edge (between chains, or non-consecutive same-chain).
  - BOUNDARY (cut around): a tile edge on the region's outer silhouette.
Mountain/Valley: accordion alternation tied to sigma (global, so consistent across chains);
M<->V is a global symmetry, so if it doesn't collapse flat, flip them all.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from matplotlib.patches import Polygon   # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "report", "tri")
TINT = ["#eaf3fb", "#fdeeee", "#eafaef"]   # faint per-chain
MNT, VLY, CUT = "#d83232", "#3399cc", "#2a8"


def make_sheet(LatClass, vcart, tile_cart, sigma, chains, footprint, title, out_name, K):
    region = sorted(set().union(*[set(c) for c in chains]))
    sub = LatClass(cells=region)
    crease = {}                                  # frozenset(a,b) -> sigma of the "from" tile
    for w in chains:
        for k in range(len(w) - 1):
            crease[frozenset((w[k], w[k + 1]))] = sigma(w[k])
    edge_owners = {}
    for t in region:
        for e in sub.edges[t]:
            edge_owners.setdefault(e, []).append(t)
    cell_chain = {t: ci for ci, w in enumerate(chains) for t in w}

    fig, ax = plt.subplots(figsize=(8.6, 7.2))
    ax.set_aspect("equal"); ax.axis("off")
    for t in region:
        ax.add_patch(Polygon(tile_cart(t), closed=True, facecolor=TINT[cell_chain[t] % 3],
                             edgecolor="#dddddd", lw=0.5, zorder=1))
    for e, owners in edge_owners.items():
        (p, q) = [vcart(v) for v in e]
        xs, ys = [p[0], q[0]], [p[1], q[1]]
        if len(owners) == 1:                     # outer boundary -> cut around
            ax.plot(xs, ys, color="#222", lw=2.4, solid_capstyle="round", zorder=6)
        elif e in crease:                        # fold line
            mv = VLY if crease[e] > 0 else MNT
            ax.plot(xs, ys, color=mv, lw=3.0, solid_capstyle="round", zorder=7)
        else:                                    # interior slit -> cut
            ax.plot(xs, ys, color=CUT, lw=2.4, dashes=(3, 2.2), solid_capstyle="round", zorder=8)
    # footprint tiles (where it folds to)
    for ci, t in enumerate(footprint):
        ax.add_patch(Polygon(tile_cart(t), closed=True, facecolor="none", edgecolor="#6f4fb0",
                             lw=2.6, zorder=9))
        cx = sum(p[0] for p in tile_cart(t)) / 3.0
        cy = sum(p[1] for p in tile_cart(t)) / 3.0
        ax.text(cx, cy, "ABC"[ci], ha="center", va="center", color="#6f4fb0", fontsize=11,
                fontweight="bold", zorder=10)

    pts = [p for t in region for p in tile_cart(t)]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    tx = max(xs) + 0.4
    ax.set_xlim(min(xs) - 0.4, tx + 4.6)
    ax.set_ylim(min(ys) - 0.4, max(ys) + 0.4)
    ax.text(tx, max(ys), title, ha="left", va="top", fontsize=13, fontweight="bold", color="#222")
    legend = [
        (VLY, "solid", "FOLD — valley (toward you)"),
        (MNT, "solid", "FOLD — mountain (away)"),
        (CUT, "dash", "SLIT — cut (interior)"),
        ("#222", "solid", "cut around outer boundary"),
        ("#6f4fb0", "solid", "footprint A/B/C (folds to this 3-tile stack)"),
    ]
    yy = max(ys) - 1.0
    for col, ls, lab in legend:
        dash = (3, 2.2) if ls == "dash" else None
        kw = dict(color=col, lw=2.8, zorder=11)
        if dash:
            kw["dashes"] = dash
        ax.plot([tx, tx + 0.5], [yy, yy], **kw)
        ax.text(tx + 0.65, yy, lab, ha="left", va="center", fontsize=8.5, color="#222")
        yy -= 0.62
    ax.text(tx, yy - 0.2,
            "K=%d, %d tiles. Cut the outer boundary + teal slits; fold every\n"
            "red/blue crease; it should collapse FLAT to the 3-tile A/B/C\n"
            "footprint stack (predicted Tw=0 = foldable). If it won't seat,\n"
            "flip ALL mountain<->valley (a global symmetry) and retry."
            % (K, len(region)), ha="left", va="top", fontsize=8, color="#555")

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, out_name)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path
