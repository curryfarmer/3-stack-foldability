"""render_reflection.py — vector-reflection diagram from a common engine fold record (tri-fold/1 JSON).

Ingests a folds/<uid>.json and draws HOW the fold is a composition of crease reflections that carries
the END footprint back onto the START footprint (the "vector reflection", see
docs/research/nonsquare_construction.md). Two panels:

  LEFT  (unfolded sheet): every region tile faint; the CREASE lines (the mirror axes the fold reflects
        across) drawn dashed; the START footprint (teal, A/B/C) and the un-folded END footprint
        (purple dashed, A/B/C); an arrow from each END cell toward its START cell (the net reflection).
  RIGHT (folded): the START footprint (teal) with each END tile's FOLDED image laid on top, coloured by
        its return orientation — green=proper rotation, amber=mirror (seats flat, printed seam flipped),
        red=off-cell (the one real jam). Title = whole-footprint chirality class + engine verdict.

Reuses the engine's own reflection composition READ-ONLY: seam_filter._region_edges (crease/rigid set)
+ seam_filter._fold_tiles (foldsim reflection walk) + seam_filter.tile_chirality, and render_fold's
record->candidate restore. No engine math is edited; the folded coordinates are exactly what the gate
sees. Prints the per-tile reflection read-out to stdout.

  python -m triangle.tri.render_reflection --uid <uid> [--matrix mvp_matrix] [--out <sub>]
  python -m triangle.tri.render_reflection --json report/tri/<sub>/folds/<uid>.json
"""
import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                          # noqa: E402
from matplotlib.patches import Polygon, FancyArrowPatch  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_example as FE      # noqa: E402  build_lat / GEN (tile_cart, vcart, cent)
import render_fold as RFD      # noqa: E402  _cand_from_record
import seam_filter as SFILT    # noqa: E402  _region_edges / _fold_tiles / tile_chirality
import tristyle as TS          # noqa: E402  draw_footprints, CHIR_COLOR/CHIR_TAG, save
from tristyle import TINT, CREASE_COL, FOOTPRINT_EDGE, FOLD_BADGE, JAM_BADGE, GRID_EDGE, MUTED  # noqa: E402


def _centroid(poly):
    return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))


def _chain_of(cand):
    """tile -> chain index, for faint per-chain tinting (2+1: strand/partners=0, 1-chain=1)."""
    ci = {}
    if cand.get("decomp") == "2plus1":
        for t in cand.get("two_tris", cand["chains"][0]):
            ci[tuple(t)] = 0
        for t in cand["chains"][1]:
            ci[tuple(t)] = 1
    else:
        for k, w in enumerate(cand["chains"]):
            for t in w:
                ci[tuple(t)] = k
    return ci


def _draw_unfolded(ax, lat, cand, tile_cart, vcart, crease):
    """LEFT panel: region tiles + crease mirror axes + START/END footprints + net reflection arrows."""
    chain_of = _chain_of(cand)
    region = sorted({tuple(t) for w in cand["chains"] for t in w}
                    | {tuple(t) for t in cand.get("two_tris", [])})
    for t in region:
        ax.add_patch(Polygon(tile_cart(t), closed=True, facecolor=TINT[chain_of.get(t, 0) % 3],
                             edgecolor=GRID_EDGE, lw=0.5, zorder=1))
    for fs in crease:                                       # crease = mirror axis of each fold
        u, v = tuple(fs)
        e = lat.shared.get((u, v)) or lat.shared.get((v, u))
        if e is None:
            continue
        (p, q) = [vcart(w) for w in e]
        ax.plot([p[0], q[0]], [p[1], q[1]], color=CREASE_COL, lw=1.7, dashes=(4, 2.4),
                solid_capstyle="round", zorder=4)
    fp = [tuple(t) for t in cand["footprint"]]
    efp = [tuple(t) for t in cand["end_footprint"]]
    TS.draw_footprints(ax, tile_cart, fp, efp, z0=8.4, labelsize=11, end_chirality=None)
    for et, st in zip(efp, fp):                             # net reflection: END cell -> START cell
        pe, ps = _centroid(tile_cart(et)), _centroid(tile_cart(st))
        if (pe[0] - ps[0]) ** 2 + (pe[1] - ps[1]) ** 2 < 1e-9:
            continue                                       # already coincident (short chain) -> no arrow
        ax.add_patch(FancyArrowPatch(pe, ps, arrowstyle="-|>", mutation_scale=13, lw=1.5,
                                     color=FOOTPRINT_EDGE, zorder=10, shrinkA=7, shrinkB=7,
                                     connectionstyle="arc3,rad=0.16", alpha=0.85))
    ax.set_title("unfolded sheet — creases (brown) = mirror axes;\narrows: END footprint reflects onto START",
                 fontsize=9, color=MUTED)
    _fit(ax, [p for t in region for p in tile_cart(t)])


def _draw_folded(ax, lat, cand, tile_cart, folded, chir):
    """RIGHT panel: START footprint (purple) with each END tile's FOLDED image overlaid, coloured by
    return orientation (proper/mirror/off-cell)."""
    fp = [tuple(t) for t in cand["footprint"]]
    efp = [tuple(t) for t in cand["end_footprint"]]
    TS.draw_footprints(ax, tile_cart, fp, None, z0=6.0, labelsize=11)     # START target only
    per = chir.get("per_tile") or []
    allpts = [p for t in fp for p in tile_cart(t)]
    for i, et in enumerate(efp):
        ev = folded.get(tuple(et))
        klass = per[i]["klass"] if i < len(per) else None
        col = TS.CHIR_COLOR.get(klass, MUTED)
        if ev is None:                                     # off-cell / unreached: draw at unfolded spot
            ev = tile_cart(et)
        ax.add_patch(Polygon(ev, closed=True, facecolor=col, edgecolor=col, lw=1.8, alpha=0.32,
                             zorder=9))
        ax.add_patch(Polygon(ev, closed=True, facecolor="none", edgecolor=col, lw=2.2, zorder=10))
        cx, cy = _centroid(ev)
        ax.text(cx, cy, "%s\n%s" % ("ABC"[i % 3], TS.CHIR_TAG.get(klass, "?")), ha="center",
                va="center", color=col, fontsize=9, fontweight="bold", zorder=11)
        allpts += list(ev)
    klass = chir.get("klass", "n/a")
    ok = chir.get("ok")
    badge = "FOLD" if ok else "JAM"
    ax.set_title("folded: END images on START — class '%s'\nseam gate: %s (%s)"
                 % (klass, badge, "cosmetic; only off-cell jams" if ok else chir.get("detail", "")),
                 fontsize=9, color=FOLD_BADGE if ok else JAM_BADGE, fontweight="bold")
    _fit(ax, allpts)


def _fit(ax, pts, pad=0.4):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - pad, max(ys) + pad)
    ax.set_aspect("equal"); ax.axis("off")


def render_reflection(json_path, out_sub=None):
    """Load folds/<uid>.json and draw its vector-reflection figure. Returns (png_path, chirality)."""
    with open(json_path) as f:
        rec = json.load(f)
    uid, tiling, decomp, K = rec["uid"], rec["tiling"], rec["decomp"], rec["K"]
    if tiling == "equilateral" and decomp == "1plus1plus1":
        raise SystemExit("equilateral 1+1+1 emits a solver rec (no chain footprint geometry to fold); "
                         "render_reflection targets the general reflection path (righttri/scalene/hex + all 2+1)")
    lat = FE.build_lat(tiling, decomp, K)
    cand = RFD._cand_from_record(rec, lat, K)
    region, crease, rigid, anchor = SFILT._region_edges(lat, cand)
    folded = SFILT._fold_tiles(lat, region, crease, rigid, anchor, region)
    chir = SFILT.tile_chirality(lat, cand)
    g = FE.GEN[tiling]
    tile_cart, vcart = g["tile_cart"], g["vcart"]

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12.6, 6.2))
    _draw_unfolded(axL, lat, cand, tile_cart, vcart, crease)
    _draw_folded(axR, lat, cand, tile_cart, folded, chir)
    fig.suptitle("VECTOR REFLECTION — %s %s K=%d  [%s]"
                 % (tiling, "1+1+1" if decomp == "1plus1plus1" else "2+1", K, uid[:8]),
                 fontsize=12, fontweight="bold", y=1.0)
    out_sub = out_sub or os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(json_path))))
    out_dir = os.path.join(FE._REPORT_BASE, out_sub)
    os.makedirs(out_dir, exist_ok=True)
    png = os.path.join(out_dir, "reflect_%s.png" % uid)
    TS.save(fig, png)

    print("REFLECTION %s %s K=%d  uid=%s  class=%s  verdict=%s"
          % (tiling, decomp, K, uid, chir.get("klass"), "FOLD" if chir.get("ok") else "JAM"))
    for i, p in enumerate(chir.get("per_tile") or []):
        print("  %s: klass=%-8s same_cell=%s proper=%s" %
              (p["label"], p["klass"], p.get("same_cell"), p.get("proper")))
    print("  -> %s" % os.path.relpath(png))
    return png, chir


def main():
    ap = argparse.ArgumentParser(description="vector-reflection diagram from a tri-fold/1 JSON record")
    ap.add_argument("--uid", help="fold uid (resolves report/tri/<matrix>/folds/<uid>.json)")
    ap.add_argument("--json", help="explicit path to a folds/<uid>.json")
    ap.add_argument("--matrix", default="mvp_matrix", help="matrix subdir to resolve --uid")
    ap.add_argument("--out", help="write PNG under report/tri/<out> (default: the fold's matrix dir)")
    args = ap.parse_args()
    if args.json:
        path = args.json
    elif args.uid:
        path = os.path.join(FE._REPORT_BASE, args.matrix, "folds", "%s.json" % args.uid)
    else:
        ap.error("give --uid or --json")
    render_reflection(path, out_sub=args.out)


if __name__ == "__main__":
    main()
