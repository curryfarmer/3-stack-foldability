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
# Orientation-aware END colouring (the actual fix): each END tile is painted by how it returns onto its
# START cell, from seam_filter.tile_chirality (single source of truth = the gate). This replaces the
# orientation-BLIND S/L seam-length tags, which read "match" on a real mirror because length is a
# reflection invariant. proper=aligned (a->a, b->b sides map through), mirror=sides swapped (short seam
# onto long), off-cell=landed wrong. Tag glyph next to A/B/C makes the per-tile verdict readable.
CHIR_COLOR = {"proper": "#2ca02c", "uniform": "#2ca02c", "mirror": "#e8820c", "off-cell": "#d83232"}
CHIR_TAG = {"proper": "rot", "uniform": "=", "mirror": "flip", "off-cell": "off"}


def draw_footprints(ax, tile_cart, start_fp, end_fp=None, z0=8.4, labelsize=11, end_chirality=None):
    """Highlight the START footprint (teal, filled) and the unfolded END footprint with A/B/C labels in
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
    _one(start_fp, START_FILL, START_OUTLINE, None,     z0,       z0 + 0.2, z0 + 0.3, -0.16)
    _one(end_fp,   None,       END_OUTLINE,   (4, 2.4), z0 + 0.5, z0 + 0.7, z0 + 0.9, +0.16, chir=per)


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


# whole-footprint rigid-motion class -> compact physical caption for the side panel (seam_filter.klass).
# SEAM-axis captions only. seam OK is NECESSARY-not-sufficient (the twist has the final FOLD/JAM say,
# shown in the title/verdict); seam BAD is AUTHORITATIVE (a mirror/rearrangement JAMs regardless of Tw).
# Kept to two short lines so they fit the narrow legend panel without overflowing.
_CLASS_CAPTION = {
    "all-proper": ("#2ca02c", "SEAM: whole footprint ROTATED\n(one rigid motion) -> OK iff Tw=0"),
    "uniform":    ("#2ca02c", "SEAM: uniform tile, mirror\ninvisible -> OK iff Tw=0"),
    "all-mirror": ("#e8820c", "SEAM: 3 tiles FLIPPED about\ndifferent axes -> JAM (rearrange)"),
    "mixed":      ("#d83232", "SEAM: MIXED flips, tiles\nrearranged -> JAM"),
    "off-cell":   ("#d83232", "SEAM: an END tile landed OFF\nits START cell -> JAM"),
    "n/a":        ("#777777", "SEAM: n/a (no footprint geom)"),
}


def _draw_class_caption(ax, lx, y, chir):
    """Draw the whole-footprint seam-class caption on the side panel at axes-fraction (lx, y); return
    the next free y. (Two-line captions -> reserve ~2 line heights.)
    all-mirror splits on the gate verdict: EXEMPT tiles (asymmetric/scalene: mirror seats the
    mirror-partner cell) read OK; ENFORCED tiles (isosceles/righttri: equal sides swap) read JAM —
    the 2026-07-02 physical fold of the righttri single-reflection case confirmed the mismatch."""
    klass = chir.get("klass", "n/a")
    if klass == "all-mirror" and chir.get("ok"):
        col, txt = "#2ca02c", "SEAM: mirror return seats the\nmirror-partner cells -> OK iff Tw=0"
    elif klass == "all-mirror" and chir.get("single_motion"):
        col, txt = "#e8820c", "SEAM: whole footprint REFLECTED\n(single mirror): equal sides swap -> JAM"
    else:
        col, txt = _CLASS_CAPTION.get(klass, _CLASS_CAPTION["n/a"])
    ax.text(lx, y - 0.008, txt, ha="left", va="top", fontsize=7.4, color=col, fontweight="bold")
    return y - 0.085


def _legend_row(ax, lx, y, col, ls, lab):
    """One legend row (swatch + label) at axes-fraction (lx, y) on the side panel (0..1 coords)."""
    sw, gap = 0.10, 0.03
    if ls == "fill":
        ax.add_patch(Polygon([(lx, y - 0.011), (lx + sw, y - 0.011), (lx + sw, y + 0.011),
                              (lx, y + 0.011)], closed=True, facecolor=START_FILL,
                             edgecolor=col, lw=2.0, zorder=11))
    elif ls in ("endfp", "endcol"):
        ax.add_patch(Polygon([(lx, y - 0.011), (lx + sw, y - 0.011), (lx + sw, y + 0.011),
                              (lx, y + 0.011)], closed=True, facecolor="none",
                             edgecolor=col, lw=2.0, linestyle=(0, (4, 2.4)), zorder=11))
    elif ls == "text":
        ax.text(lx + sw / 2, y, "S L", ha="center", va="center", fontsize=7.5, color=col,
                fontweight="bold", zorder=11,
                bbox=dict(boxstyle="round,pad=0.1", fc="white", ec=col, lw=0.7, alpha=0.9))
    else:
        kw = dict(color=col, lw=2.8, zorder=11, solid_capstyle="round")
        if ls == "dash":
            kw["dashes"] = (3, 2.2)
        ax.plot([lx, lx + sw], [y, y], **kw)
    ax.text(lx + sw + gap, y, lab, ha="left", va="center", fontsize=8.0, color="#222")


def make_sheet(LatClass, vcart, tile_cart, sigma, chains, footprint, title, out_name, K,
               verdict_note=None, crease_override=None, end_footprint=None, rigid_override=None,
               end_chirality=None):
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

    # Two panels: a LARGE region axis (most of the sheet) so the drawn pattern is big + legible, and a
    # figure-relative side panel for the title/legend/notes. The old single-axis layout reserved a
    # fixed ~5-data-unit legend column to the right of the region, which shrank compact patterns
    # (worst on scalene) into the corner; splitting the axes decouples pattern size from legend size.
    fig = plt.figure(figsize=(12.0, 8.2))
    ax = fig.add_axes([0.015, 0.02, 0.66, 0.90])
    ax.set_aspect("equal"); ax.axis("off")
    axL = fig.add_axes([0.69, 0.02, 0.30, 0.90])          # side panel, own 0..1 coordinate system
    axL.set_xlim(0, 1); axL.set_ylim(0, 1); axL.axis("off")
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
    # START hub (teal, filled) + unfolded chain-END tiles, A/B/C in chain order. END tiles are
    # recoloured by return orientation (green=proper/rotation, amber=mirror, red=off-cell) from
    # end_chirality — the orientation-aware replacement for the old S/L END length tags.
    draw_footprints(ax, tile_cart, footprint, end_footprint, z0=8.4, labelsize=11,
                    end_chirality=end_chirality)
    # side-length tags (S/M/L) on the START hub's real seams only (reference for the by-eye check).
    # The END tags are DROPPED: length is a reflection invariant, so an END length tag reads "match"
    # even on a real mirror — the END orientation colour (above) is the correct START<->END signal.
    lmap = _len_class_map(tile_cart, footprint)
    _draw_seam_tags(ax, sub, vcart, footprint, lmap, START_OUTLINE, 9.2)

    # tight region limits: the pattern now fills its own axis instead of sharing it with the legend.
    pts = [p for t in region for p in tile_cart(t)]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    pad = 0.4
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - pad, max(ys) + pad)

    # title spans the full sheet width; legend + notes live on the side panel (axL, figure-relative).
    fig.text(0.5, 0.985, title, ha="center", va="top", fontsize=13, fontweight="bold", color="#222")
    lx, y, lh = 0.02, 0.985, 0.040
    legend = [
        (VLY, "solid", "FOLD — valley (toward you)"),
        (MNT, "solid", "FOLD — mountain (away)"),
        (CUT, "dash", "SLIT — cut (interior)"),
        ("#222", "solid", "cut around outer boundary"),
        (RIGID, "solid", "rigid — keep attached, flat (hub)"),
        (START_OUTLINE, "fill", "START footprint A/B/C (the hub)"),
    ]
    if end_chirality:
        legend += [
            ("#2ca02c", "endcol", "END aligned: proper rotation = FOLD"),
            ("#e8820c", "endcol", "END mirror: sides swapped = JAM"),
            ("#d83232", "endcol", "END off-cell: wrong cell = JAM"),
        ]
    else:
        legend.append((END_OUTLINE, "endfp", "END footprint A/B/C (fold onto hub)"))
    legend.append(("#222", "text", "S L = START hub seam side-length"))
    for col, ls, lab in legend:
        _legend_row(axL, lx, y, col, ls, lab)
        y -= lh
    if end_chirality:                            # name the whole-footprint rigid-motion class
        y = _draw_class_caption(axL, lx, y, end_chirality)
    verdict = verdict_note or "predicted Tw=0 = foldable"
    axL.text(lx, y - 0.015,
             "K=%d, %d tiles. Cut the outer boundary + green slits\n"
             "(leave grey hub seams attached); fold every red/blue\n"
             "crease (red=mountain, blue=valley); the chains accordion\n"
             "so the END footprint lands on the START hub (teal) as a\n"
             "3-stack (%s). If it won't seat, flip ALL\n"
             "mountain<->valley (a global symmetry) and retry."
             % (K, len(region), verdict), ha="left", va="top", fontsize=7.5, color="#555")

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, out_name)
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return path
