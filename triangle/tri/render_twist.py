"""render_twist.py — twist-enumeration diagram from a common engine fold record (tri-fold/1 JSON).

The triangle analog of experimental/enumerate_twist.py (square 2+1). Ingests a folds/<uid>.json,
reconstructs the twist LOOP(s), scores each with tritwist.loop_twist under the LOOP-INDEX sigma
(path_sigma — the invariant the engine uses, see docs/research/nonsquare_construction.md), and draws
the loop on tile centroids with per-vertex sigma*gamma contributions, the running total, and the
Tw=0 FOLD / Tw!=0 JAM verdict. Also prints the per-vertex table to stdout.

  2+1   : ONE reduced loop = strand + reversed(1-chain)             (chains[0] + reversed(chains[1]))
  1+1+1 : THREE theta-graph pairwise loops AB / BC / AC             (chains[i] + reversed(chains[j]))

Self-contained: only tritwist (pure twist math) + the record's `geometry` block (tile polygons ->
centroids) are used; no lattice rebuild, no search engine. gamma_k = 2*signed_turn at loop vertex k;
Tw = sum_k sigma_k * gamma_k; a closed triangle loop's Tw is a clean multiple of 360.

  python -m triangle.tri.render_twist --uid <uid> [--matrix mvp_matrix] [--out <sub>]
  python -m triangle.tri.render_twist --json report/tri/<sub>/folds/<uid>.json
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
import tritwist as TW                                    # noqa: E402  loop_twist / path_sigma

REPORT_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "report", "tri")
POS, NEG, INK = "#1a7f37", "#c0392b", "#222222"          # +contribution / -contribution / ink
LOOP_COL, TILE_FILL, TILE_EDGE = "#6f4fb0", "#f2f3f7", "#d7d9e0"
FOLD_BADGE, JAM_BADGE = "#1a7f48", "#c0392b"


def _tk(t):
    """Record geometry key for a tile id (matches gen_testset._tk)."""
    return json.dumps(list(t), separators=(",", ":"))


def _centroid_map(rec):
    """tile-key -> (cx, cy) from the record's cartesian geometry block (polygon vertex mean)."""
    out = {}
    for k, poly in rec["geometry"].items():
        out[k] = (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
    return out


def _loops(rec):
    """[(name, [tile-tuple,...]), ...] reduced twist loop(s) for this record's decomposition."""
    chains = [[tuple(t) for t in c] for c in rec["chains"]]
    if rec["decomp"] == "2plus1":
        return [("strand+rev(1-chain)", list(chains[0]) + list(reversed(chains[1])))]
    names, pairs = ("AB", "BC", "AC"), ((0, 1), (1, 2), (0, 2))
    return [(nm, list(chains[i]) + list(reversed(chains[j]))) for nm, (i, j) in zip(names, pairs)]


def _score(loop, cents):
    """tritwist.loop_twist under the loop-index sigma, with a geometry-derived centroid callable."""
    def cent(t):
        return cents[_tk(t)]
    return TW.loop_twist(loop, cent=cent, sigma=TW.path_sigma(len(loop)))


def _draw_loop(ax, rec, cents, name, loop, res):
    """Draw one twist loop: faint region tiles, the closed centroid polyline (arrowed), and each
    vertex's sigma*gamma contribution coloured by sign. Title carries the Tw verdict."""
    for k, poly in rec["geometry"].items():                 # faint context: all region tiles
        ax.add_patch(Polygon(poly, closed=True, facecolor=TILE_FILL, edgecolor=TILE_EDGE,
                             lw=0.5, zorder=1))
    pts = [cents[_tk(t)] for t in loop]
    n = len(pts)
    for k in range(n):                                      # arrowed loop edges (closed)
        p, q = pts[k], pts[(k + 1) % n]
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=11,
                                     lw=1.6, color=LOOP_COL, zorder=4,
                                     shrinkA=6, shrinkB=6, alpha=0.9))
    cum = 0.0
    gammas, sigs = res["gammas"], res["sigmas"]
    for k in range(n):
        cx, cy = pts[k]
        contrib = sigs[k] * gammas[k]
        cum += contrib
        col = POS if contrib > 0 else (NEG if contrib < 0 else INK)
        ax.plot([cx], [cy], "o", ms=5, color=col, zorder=5)
        if abs(contrib) > 1e-9:                             # label only turning vertices (gamma!=0)
            ax.text(cx, cy, "%+d" % round(contrib), ha="center", va="center", fontsize=7.5,
                    color="white", fontweight="bold", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.14", fc=col, ec="none", alpha=0.95))
    Tw = round(res["Tw"])
    badge_c = FOLD_BADGE if Tw == 0 else JAM_BADGE
    verdict = "Tw=0 FOLD" if Tw == 0 else "Tw=%+d JAM" % Tw
    ax.set_title("%s   loop len %d\nTw = %+d deg  (%s)" % (name, n, Tw, verdict),
                 fontsize=9, color=badge_c, fontweight="bold")
    pxs = [p[0] for p in pts]; pys = [p[1] for p in pts]
    for k, poly in rec["geometry"].items():
        pxs += [p[0] for p in poly]; pys += [p[1] for p in poly]
    pad = 0.4
    ax.set_xlim(min(pxs) - pad, max(pxs) + pad)
    ax.set_ylim(min(pys) - pad, max(pys) + pad)
    ax.set_aspect("equal"); ax.axis("off")


def render_twist(json_path, out_sub=None):
    """Load folds/<uid>.json and draw its twist-enumeration figure. Returns (png_path, [results])."""
    with open(json_path) as f:
        rec = json.load(f)
    uid, tiling, decomp, K = rec["uid"], rec["tiling"], rec["decomp"], rec["K"]
    cents = _centroid_map(rec)
    loops = _loops(rec)
    results = [(nm, loop, _score(loop, cents)) for nm, loop in loops]

    fig, axes = plt.subplots(1, len(loops), figsize=(5.4 * len(loops), 5.6), squeeze=False)
    for ax, (nm, loop, res) in zip(axes[0], results):
        _draw_loop(ax, rec, cents, nm, loop, res)
    tws = [round(r["Tw"]) for _, _, r in results]
    foldable = all(t == 0 for t in tws)
    fig.suptitle("TWIST — %s %s K=%d  [%s]   engine: %s   (loop-index sigma)"
                 % (tiling, "1+1+1" if decomp == "1plus1plus1" else "2+1", K, uid[:8],
                    "FOLD (all Tw=0)" if foldable else "JAM (Tw!=0)"),
                 fontsize=11, fontweight="bold",
                 color=FOLD_BADGE if foldable else JAM_BADGE, y=0.99)
    out_sub = out_sub or os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(json_path))))
    out_dir = os.path.join(REPORT_BASE, out_sub)
    os.makedirs(out_dir, exist_ok=True)
    png = os.path.join(out_dir, "twist_%s.png" % uid)
    fig.savefig(png, dpi=160, bbox_inches="tight")
    plt.close(fig)

    # stdout: per-vertex table for each loop (the numeric justification)
    print("TWIST %s %s K=%d  uid=%s" % (tiling, decomp, K, uid))
    for nm, loop, res in results:
        print("  loop %s (len %d):  Tw=%+d  Tw_index=%+d  sigma-alternates=%s"
              % (nm, len(loop), round(res["Tw"]), round(res["Tw_index"]), res["alternates"]))
        print("    %3s %-16s %8s %4s %8s %8s" % ("k", "tile", "gamma", "sig", "sig*g", "cum"))
        cum = 0.0
        for k, t in enumerate(loop):
            contrib = res["sigmas"][k] * res["gammas"][k]
            cum += contrib
            print("    %3d %-16s %8.1f %+4d %8.1f %8.1f"
                  % (k, str(t), res["gammas"][k], res["sigmas"][k], contrib, cum))
    print("  verdict: %s" % ("FOLD (all Tw=0)" if foldable else "JAM (Tw!=0)"))
    return png, results


def main():
    ap = argparse.ArgumentParser(description="twist-enumeration diagram from a tri-fold/1 JSON record")
    ap.add_argument("--uid", help="fold uid (resolves report/tri/<matrix>/folds/<uid>.json)")
    ap.add_argument("--json", help="explicit path to a folds/<uid>.json")
    ap.add_argument("--matrix", default="mvp_matrix", help="matrix subdir to resolve --uid")
    ap.add_argument("--out", help="write PNG under report/tri/<out> (default: the fold's matrix dir)")
    args = ap.parse_args()
    if args.json:
        path = args.json
    elif args.uid:
        path = os.path.join(REPORT_BASE, args.matrix, "folds", "%s.json" % args.uid)
    else:
        ap.error("give --uid or --json")
    png, _ = render_twist(path, out_sub=args.out)
    print("  -> %s" % os.path.relpath(png))


if __name__ == "__main__":
    main()
