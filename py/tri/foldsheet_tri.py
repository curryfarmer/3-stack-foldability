"""foldsheet_tri.py — printable physical fold pattern (make-sheet) for a 1+1+1 fold on any
reflection tiling (righttri / scalene). Analog of py/make_foldsheets.py for the square grid.

Edge roles (the structural part, certain):
  - CREASE (fold): an interior edge between two CONSECUTIVE tiles of the same chain.
  - RIGID (keep attached, flat): an interior edge inside the START footprint trapezoid (its tiles
    stay coplanar as the fold anchor), plus any caller-supplied rigid edges (2+1: the domino-internal
    edge). The END trapezoid is NOT rigid: its tiles are independent chain ends that only meet after
    folding, so their mutual seams are SLITS (cut) — matches the foldsim gate (edges_* rigid = START
    hub + domino only). The sheet stays one connected piece via the start hub + creased chains.
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
RIGID = "#b0b0b0"   # faint grey: keep-attached, flat (the rigid hub trapezoids — NOT a cut)
# Two footprints: the START hub (where the chains begin) and the unfolded chain-END tiles. They are
# distinct regions on the flat sheet (chain ends are K steps from the hub); the END trapezoid folds
# onto the START hub, so comparing the two makes the edge-type (long/short seam) relationship visible.
START_OUTLINE, START_FILL = "#1b9e9e", "#e3f4f4"   # teal: start hub, filled
END_OUTLINE = "#6f4fb0"                            # purple: unfolded chain-end tiles, dashed (no fill)


def draw_footprints(ax, tile_cart, start_fp, end_fp=None, z0=8.4, labelsize=11):
    """Highlight the START footprint (teal, filled) and the unfolded END footprint (purple, dashed)
    with A/B/C labels in chain order (A=chain0, B=mid, C=chain2 in BOTH). Either may be None.
    Generic over n-gons (3 for triangles, 6 for hexagons); centroid = mean of tile vertices."""
    def _one(fp, fill, outline, dashes, zf, zo, zt, nudge):
        if not fp:
            return
        for ci, t in enumerate(fp):
            pc = tile_cart(t)
            cx = sum(p[0] for p in pc) / len(pc)
            cy = sum(p[1] for p in pc) / len(pc)
            if fill is not None:
                ax.add_patch(Polygon(pc, closed=True, facecolor=fill, edgecolor="none", zorder=zf))
            kw = dict(facecolor="none", edgecolor=outline, lw=2.6, zorder=zo)
            if dashes is not None:
                kw["linestyle"] = (0, dashes)
            ax.add_patch(Polygon(pc, closed=True, **kw))
            vx, vy = pc[0]                       # nudge the label toward vertex0 so start/end don't collide
            ax.text(cx + nudge * (vx - cx), cy + nudge * (vy - cy), "ABC"[ci % 3], ha="center",
                    va="center", color=outline, fontsize=labelsize, fontweight="bold", zorder=zt,
                    bbox=dict(boxstyle="circle,pad=0.12", fc="white", ec=outline, lw=0.8, alpha=0.85))
    _one(start_fp, START_FILL, START_OUTLINE, None,     z0,       z0 + 0.2, z0 + 0.3, -0.16)
    _one(end_fp,   None,       END_OUTLINE,   (4, 2.4), z0 + 0.5, z0 + 0.7, z0 + 0.9, +0.16)


def _len_class_map(tile_cart, fp):
    """Rounded-edge-length -> 'S'/'M'/'L' using the DISTINCT side lengths of the footprint's tiles.
    Empty for edge-uniform tiles (equilateral / hex), so their sheets get no seam tags."""
    lens = set()
    for t in fp:
        pc = tile_cart(t)
        n = len(pc)
        for i in range(n):
            x1, y1 = pc[i]
            x2, y2 = pc[(i + 1) % n]
            lens.add(round(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5, 4))
    order = sorted(lens)
    if len(order) <= 1:
        return {}
    names = {2: ["S", "L"], 3: ["S", "M", "L"]}.get(len(order),
                                                    ["s%d" % i for i in range(len(order))])
    return {order[i]: names[i] for i in range(len(order))}


def _draw_seam_tags(ax, sub, vcart, fp, lmap, color, z):
    """Tag each INTERNAL footprint seam (adjacent pair) with its side-length class S/M/L, so the
    short-short/long-long (righttri) or all-sides (scalene) START<->END match is verifiable by eye.
    Slit seams (non-adjacent end tiles, e.g. the END binding) have no shared edge -> no tag."""
    if not lmap or not fp:
        return
    fpt = [tuple(t) for t in fp]
    for i in range(len(fpt)):
        for j in range(i + 1, len(fpt)):
            t, u = fpt[i], fpt[j]
            e = sub.shared.get((t, u)) or sub.shared.get((u, t))
            if e is None:
                continue
            (p, q) = [vcart(v) for v in e]
            mx, my = (p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0
            L = round(((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2) ** 0.5, 4)
            ax.text(mx, my, lmap.get(L, "?"), ha="center", va="center", fontsize=7.5, color=color,
                    fontweight="bold", zorder=z,
                    bbox=dict(boxstyle="round,pad=0.1", fc="white", ec=color, lw=0.7, alpha=0.9))


def make_sheet(LatClass, vcart, tile_cart, sigma, chains, footprint, title, out_name, K,
               verdict_note=None, crease_override=None, end_footprint=None, rigid_override=None):
    region = sorted(set().union(*[set(c) for c in chains]))
    sub = LatClass(cells=region)
    if crease_override is not None:              # caller supplies the fold-edge set directly
        crease = crease_override                 # (e.g. 2+1: ribbon hinges + 1-chain creases)
    else:
        crease = {}                              # shared-edge (vertex keys) -> sigma of "from" tile
        for w in chains:
            for k in range(len(w) - 1):
                crease[sub.shared[(w[k], w[k + 1])]] = sigma(w[k])
    # RIGID seams = interior edges inside the START footprint trapezoid PLUS any caller-supplied
    # rigid edges (2+1: each domino's internal edge — a domino is one rigid 2-tile unit, drawn grey
    # not folded). The start hub/domino stay flat rigid, so these are "keep attached" (NOT cut).
    # The END trapezoid is NOT glued: its tiles are the ends of independent chains (1+1+1) or the
    # domino-end vs 1-chain-end (2+1) that only meet AFTER folding — gluing them would over-constrain
    # the sheet into a different (non-closing on hex/eq) object than the fold the gate validated. It
    # is drawn outline-only (draw_footprints). This keeps the sheet's rigid set == foldsim edges_*[1].
    rigid = set(rigid_override) if rigid_override else set()
    for fp in (footprint,):
        if not fp:
            continue
        fpt = [tuple(t) for t in fp]
        for i in range(len(fpt)):
            for j in range(i + 1, len(fpt)):
                t, u = fpt[i], fpt[j]
                if u in sub.adj.get(t, ()) and (t, u) in sub.shared:
                    rigid.add(sub.shared[(t, u)])
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
        elif e in crease:                        # fold line (mountain/valley by COLOR)
            valley = crease[e] > 0
            mv = VLY if valley else MNT
            ax.plot(xs, ys, color=mv, lw=3.0, solid_capstyle="round", zorder=7)
        elif e in rigid:                         # rigid hub seam -> keep attached, flat (NOT a cut)
            ax.plot(xs, ys, color=RIGID, lw=1.4, solid_capstyle="round", zorder=5)
        else:                                    # interior slit -> cut
            ax.plot(xs, ys, color=CUT, lw=2.4, dashes=(3, 2.2), solid_capstyle="round", zorder=8)
    # START hub (teal, filled) + unfolded chain-END tiles (purple, dashed) — A/B/C in chain order
    draw_footprints(ax, tile_cart, footprint, end_footprint, z0=8.4, labelsize=11)
    # side-length tags (S/M/L) on each footprint's internal seams — makes the START<->END side match
    # verifiable at a glance (short-short/long-long etc.). Empty for uniform tiles (eq/hex).
    lmap = _len_class_map(tile_cart, footprint)
    _draw_seam_tags(ax, sub, vcart, footprint, lmap, START_OUTLINE, 9.2)
    _draw_seam_tags(ax, sub, vcart, end_footprint or [], lmap, END_OUTLINE, 9.4)

    pts = [p for t in region for p in tile_cart(t)]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    tx = max(xs) + 0.4
    ax.set_xlim(min(xs) - 0.4, tx + 4.6)
    # extend the y-axis downward so the title + 6 legend rows + 4-line verdict block fit even when
    # the region itself is short (small 2+1 sheets) -- otherwise the legend glyphs clip off-axis.
    legend_bottom = max(ys) - 1.0 - 0.62 * 8 - 2.4
    ax.set_ylim(min(min(ys) - 0.4, legend_bottom), max(ys) + 0.4)
    ax.text(tx, max(ys), title, ha="left", va="top", fontsize=13, fontweight="bold", color="#222")
    legend = [
        (VLY, "solid", "FOLD — valley (toward you)"),
        (MNT, "solid", "FOLD — mountain (away)"),
        (CUT, "dash", "SLIT — cut (interior)"),
        ("#222", "solid", "cut around outer boundary"),
        (RIGID, "solid", "rigid — keep attached, flat (hub trapezoids)"),
        (START_OUTLINE, "fill", "START footprint A/B/C (the hub)"),
        (END_OUTLINE, "endfp", "END footprint A/B/C (chain ends, fold onto hub)"),
        ("#222", "text", "S/M/L = seam side-length: START & END tags must match"),
    ]
    yy = max(ys) - 1.0
    for col, ls, lab in legend:
        if ls == "fill":
            ax.add_patch(Polygon([(tx, yy - 0.12), (tx + 0.5, yy - 0.12), (tx + 0.5, yy + 0.12),
                                  (tx, yy + 0.12)], closed=True, facecolor=START_FILL,
                                 edgecolor=col, lw=2.0, zorder=11))
        elif ls == "endfp":
            ax.add_patch(Polygon([(tx, yy - 0.12), (tx + 0.5, yy - 0.12), (tx + 0.5, yy + 0.12),
                                  (tx, yy + 0.12)], closed=True, facecolor="none",
                                 edgecolor=col, lw=2.0, linestyle=(0, (4, 2.4)), zorder=11))
        elif ls == "text":
            ax.text(tx + 0.25, yy, "S L", ha="center", va="center", fontsize=7.5, color=col,
                    fontweight="bold", zorder=11,
                    bbox=dict(boxstyle="round,pad=0.1", fc="white", ec=col, lw=0.7, alpha=0.9))
        else:
            dash = (3, 2.2) if ls == "dash" else None
            kw = dict(color=col, lw=2.8, zorder=11)
            if dash:
                kw["dashes"] = dash
            ax.plot([tx, tx + 0.5], [yy, yy], **kw)
        ax.text(tx + 0.65, yy, lab, ha="left", va="center", fontsize=8.5, color="#222")
        yy -= 0.62
    verdict = verdict_note or "predicted Tw=0 = foldable"
    ax.text(tx, yy - 0.2,
            "K=%d, %d tiles. Cut the outer boundary + green slits (leave grey hub seams\n"
            "attached); fold every red/blue crease (red=mountain, blue=valley); the chains\n"
            "accordion so the END footprint (purple) lands on the START hub (teal) as a 3-stack\n"
            "(%s). If it won't seat, flip ALL mountain<->valley (a global symmetry) and retry."
            % (K, len(region), verdict), ha="left", va="top", fontsize=8, color="#555")

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, out_name)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path
