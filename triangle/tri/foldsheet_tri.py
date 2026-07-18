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
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from matplotlib.patches import Polygon   # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tri/ on path for tristyle
# Palette / dpi / save / the shared start+end footprint drawer all come from tristyle, the triangle
# track's single source of truth (the analog of the square track's figstyle). draw_footprints lived
# here historically; it now lives in tristyle so every renderer draws footprints identically.
from tristyle import (draw_footprints, draw_walk_arrows, save, DPI, TINT, MNT, VLY, CUT, RIGID,  # noqa: E402,F401
                      START_FILL, FOOTPRINT_EDGE, GRID_EDGE, INK, MUTED, CHAIN,
                      CHIR_COLOR, CHIR_TAG)


def _cent_of(poly):
    """Centroid (vertex mean) of a tile polygon — for the chain-walk foldpath overlay."""
    return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))

# OUT is mutated externally by the engine (find_example.set_outdir sets FS.OUT to redirect a campaign's
# output dir), so it MUST stay a module attribute here — do not migrate it into tristyle.
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "report", "tri")


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
# shown in the title/verdict). Chirality is COSMETIC: only an OFF-CELL arrival jams on the seam axis
# (all-mirror/mixed returns seat flat -> their live OK captions live in _draw_class_caption). Kept to
# two short lines so they fit the narrow legend panel without overflowing.
_CLASS_CAPTION = {
    "all-proper": (CHIR_COLOR["proper"], "SEAM: whole footprint ROTATED\n(one rigid motion) -> OK iff Tw=0"),
    "uniform":    (CHIR_COLOR["proper"], "SEAM: uniform tile, mirror\ninvisible -> OK iff Tw=0"),
    "off-cell":   (CHIR_COLOR["off-cell"], "SEAM: an END tile landed OFF\nits START cell -> JAM"),
    "n/a":        (MUTED, "SEAM: n/a (no footprint geom)"),
}


def _draw_class_caption(ax, lx, y, chir):
    """Draw the whole-footprint seam-class caption on the side panel at axes-fraction (lx, y); return
    the next free y. (Two-line captions -> reserve ~2 line heights.)
    Chirality is COSMETIC (confirmed 2026-07-05): all-mirror AND mixed arrivals seat flat with the
    printed START/END seam merely flipped, so both read OK — only an OFF-CELL arrival jams (see
    seam_filter._verdict). The final FOLD/JAM is the twist's (Tw=0), shown in the title/verdict."""
    klass = chir.get("klass", "n/a")
    if klass == "all-mirror":
        col, txt = CHIR_COLOR["proper"], "SEAM: mirror return seats the\nmirror-partner cells -> OK iff Tw=0"
    elif klass == "mixed":
        col, txt = CHIR_COLOR["proper"], "SEAM: mixed flips seat flat\n(printed seam flipped) -> OK iff Tw=0"
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
    ax.text(lx + sw + gap, y, lab, ha="left", va="center", fontsize=8.0, color=INK)


def make_sheet(LatClass, vcart, tile_cart, sigma, chains, footprint, title, out_name, K,
               verdict_note=None, crease_override=None, end_footprint=None, rigid_override=None,
               end_chirality=None, walk_chains=None, chrome=True):
    # chrome=True (default): full printable sheet — title band + side panel (legend + physical notes).
    # chrome=False: BARE model only — no title, no legend, no notes; the pattern fills the figure. Used
    # for report montages that carry their own per-panel title (report_examples / tri montage builders).
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
    if chrome:
        fig = plt.figure(figsize=(12.0, 8.2))
        ax = fig.add_axes([0.015, 0.02, 0.66, 0.90])
        axL = fig.add_axes([0.69, 0.02, 0.30, 0.90])      # side panel, own 0..1 coordinate system
        axL.set_xlim(0, 1); axL.set_ylim(0, 1); axL.axis("off")
    else:                                                 # bare model: pattern fills the whole figure
        fig = plt.figure(figsize=(8.0, 8.0))
        ax = fig.add_axes([0.01, 0.01, 0.98, 0.98])
        axL = None
    ax.set_aspect("equal"); ax.axis("off")
    for t in region:
        ax.add_patch(Polygon(tile_cart(t), closed=True, facecolor=TINT[cell_chain[t] % 3],
                             edgecolor=GRID_EDGE, lw=0.5, zorder=1))
    for e, owners in edge_owners.items():
        (p, q) = [vcart(v) for v in e]
        xs, ys = [p[0], q[0]], [p[1], q[1]]
        if len(owners) == 1:                     # outer boundary -> cut around
            ax.plot(xs, ys, color=INK, lw=2.4, solid_capstyle="round", zorder=6)
        elif e in crease:                        # fold line (mountain/valley by COLOR)
            valley = crease[e] > 0
            mv = VLY if valley else MNT
            ax.plot(xs, ys, color=mv, lw=3.0, solid_capstyle="round", zorder=7)
        elif e in rigid:                         # rigid hub seam -> keep attached, flat (NOT a cut)
            ax.plot(xs, ys, color=RIGID, lw=1.4, solid_capstyle="round", zorder=5)
        else:                                    # interior slit -> cut
            ax.plot(xs, ys, color=CUT, lw=2.4, dashes=(3, 2.2), solid_capstyle="round", zorder=8)
    # fold path: each chain's centroid walk (the order its tiles are visited) with per-step arrowheads
    # and step numbers — the "with foldpath" half of the unified schematic (analog of the square
    # foldsheet's draw_fold_path). walk_chains carries the ORDERED walks (the sheet `chains` may be a
    # sorted set, e.g. the 2+1 domino); drawn only when supplied so a bare crease sheet is unchanged.
    if walk_chains is not None:
        for ci, w in enumerate(walk_chains):
            cents = [_cent_of(tile_cart(t)) for t in w]
            if not cents:
                continue
            xs, ys = zip(*cents)
            ax.plot(xs, ys, "-", color=CHAIN[ci % 3], lw=1.8, solid_capstyle="round", zorder=6, alpha=0.9)
            ax.plot(xs, ys, "o", color=CHAIN[ci % 3], ms=3, zorder=6.1)
            draw_walk_arrows(ax, cents, CHAIN[ci % 3], z=6.2)
            for k, (x, y) in enumerate(cents):
                ax.text(x, y, str(k), ha="center", va="center", color="white", fontsize=5, zorder=7)
    # START hub (purple, faint fill) + unfolded chain-END tiles, A/B/C in chain order. END tiles are
    # recoloured by return orientation (green=proper/rotation, amber=mirror, red=off-cell) from
    # end_chirality — the orientation-aware replacement for the old S/L END length tags.
    draw_footprints(ax, tile_cart, footprint, end_footprint, z0=8.4, labelsize=11,
                    end_chirality=end_chirality)
    # side-length tags (S/M/L) on the START hub's real seams only (reference for the by-eye check).
    # The END tags are DROPPED: length is a reflection invariant, so an END length tag reads "match"
    # even on a real mirror — the END orientation colour (above) is the correct START<->END signal.
    lmap = _len_class_map(tile_cart, footprint)
    _draw_seam_tags(ax, sub, vcart, footprint, lmap, FOOTPRINT_EDGE, 9.2)

    # tight region limits: the pattern now fills its own axis instead of sharing it with the legend.
    pts = [p for t in region for p in tile_cart(t)]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    pad = 0.4
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - pad, max(ys) + pad)

    # title spans the full sheet width; legend + notes live on the side panel (axL, figure-relative).
    # Skipped entirely for a bare model (chrome=False) — the montage supplies its own per-panel title.
    if chrome:
        fig.text(0.5, 0.985, title, ha="center", va="top", fontsize=13, fontweight="bold", color=INK)
        lx, y, lh = 0.02, 0.985, 0.040
        legend = [
            (VLY, "solid", "FOLD — valley (toward you)"),
            (MNT, "solid", "FOLD — mountain (away)"),
            (CUT, "dash", "SLIT — cut (interior)"),
            ("#222", "solid", "cut around outer boundary"),
            (RIGID, "solid", "rigid — keep attached, flat (hub)"),
            (FOOTPRINT_EDGE, "fill", "START footprint A/B/C (the hub)"),
        ]
        if end_chirality:
            legend += [
                (CHIR_COLOR["proper"], "endcol", "END aligned: proper rotation = FOLD"),
                (CHIR_COLOR["mirror"], "endcol", "END mirror: sides swapped = JAM"),
                (CHIR_COLOR["off-cell"], "endcol", "END off-cell: wrong cell = JAM"),
            ]
        else:
            legend.append((FOOTPRINT_EDGE, "endfp", "END footprint A/B/C (fold onto hub)"))
        legend.append((INK, "text", "S L = START hub seam side-length"))
        for col, ls, lab in legend:
            _legend_row(axL, lx, y, col, ls, lab)
            y -= lh
        if end_chirality:                        # name the whole-footprint rigid-motion class
            y = _draw_class_caption(axL, lx, y, end_chirality)
        verdict = verdict_note or "predicted Tw=0 = foldable"
        axL.text(lx, y - 0.015,
                 "K=%d, %d tiles. Cut the outer boundary + green slits\n"
                 "(leave grey hub seams attached); fold every red/blue\n"
                 "crease (red=mountain, blue=valley); the chains accordion\n"
                 "so the END footprint lands on the START hub (purple) as a\n"
                 "3-stack (%s). If it won't seat, flip ALL\n"
                 "mountain<->valley (a global symmetry) and retry."
                 % (K, len(region), verdict), ha="left", va="top", fontsize=7.5, color=MUTED)

    return save(fig, os.path.join(OUT, out_name))
