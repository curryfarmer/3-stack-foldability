"""generate.py — tri-generate CLI: search for ONE closing 3-stack fold example at a fixed
(tiling, decomp, K) and package it exactly like `render.py` would (out/<uid>/<uid>.json +
overlay/foldsheet/twist/reflect PNGs).

Reuses the existing search machinery — find_example.find_first (pinned to a single K instead of
marching a K-range) drives the same physical-closure-gated generators (gen_111 / gen_21 / gen_eq)
that find_example.py / gen_testset.py already use; gen_testset.fold_uid / _fold_record build the
same self-contained tri-fold/1 record schema gen_testset.py writes. No new search algorithm here.

Not finding a closing example at the given (tiling, decomp, K) is a normal, CORRECT outcome for
some inputs (e.g. equilateral 1+1+1 is a proven obstruction at every K) — this prints a message
and exits 0, not an error.

  python generate.py --tiling righttri --decomp 1plus1plus1 --K 16
  python generate.py --tiling equilateral --decomp 1plus1plus1 --K 10 --out /tmp/tri_out
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_example as FE     # noqa: E402  find_first / verdict_text (the existing search entry point)
import gen_testset as GT      # noqa: E402  fold_uid / _fold_record (the existing record schema)
import seam_filter as SFILT   # noqa: E402  tile_chirality (per-tile orientation read-out for the record)
import render as RENDER       # noqa: E402  render_record_json — the SAME out/<uid>/ packaging as tri-render


def find_one(tiling, decomp, K, budget=120.0):
    """Search for exactly ONE closing candidate at this fixed K. Reuses find_example.find_first,
    pinned to a single K (K0=kcap=K, step=1) instead of marching a K-range. Returns
    (result, stats) where result is (lat, K, cand) or None if no closing candidate exists at this
    K (a valid, meaningful outcome); stats is the search's gate-funnel counter dict."""
    stats = {"tried": 0, "topology_pass": 0, "closure_pass": 0, "holes_filtered": 0}
    res = FE.find_first(tiling, decomp, "allow", K, 1, K, hub=None, budget=budget, stats=stats)
    return res, stats


def _print_search_summary(decomp, stats):
    parts = ["%d candidate(s) tried" % stats["tried"]]
    if decomp == "2plus1":
        parts.append("%d passed topology/exit" % stats["topology_pass"])
    parts.append("%d passed the physical closure (reflection) gate" % stats["closure_pass"])
    if stats["holes_filtered"]:
        parts.append("%d holes-filtered" % stats["holes_filtered"])
    print("search: " + ", ".join(parts))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="search for one closing 3-stack fold example and render its full image bundle")
    ap.add_argument("--tiling", required=True, choices=["equilateral", "righttri", "scalene", "hex"])
    ap.add_argument("--decomp", required=True, choices=["2plus1", "1plus1plus1"])
    ap.add_argument("--K", type=int, required=True, help="chain length")
    ap.add_argument("--out", default="out", help="output root directory (default: out/)")
    ap.add_argument("--budget", type=float, default=120.0, help="search wall-clock budget in seconds")
    args = ap.parse_args(argv)

    res, stats = find_one(args.tiling, args.decomp, args.K, budget=args.budget)
    _print_search_summary(args.decomp, stats)
    if res is None:
        print("no closing example found for tiling=%s decomp=%s K=%d "
              "(this can be a correct, proven obstruction — e.g. equilateral 1+1+1 never closes —"
              " not necessarily a search failure)" % (args.tiling, args.decomp, args.K))
        return 0

    lat, K, cand = res
    uid = GT.fold_uid(args.tiling, args.decomp, cand)
    verdict = FE.verdict_text(cand)
    tc = SFILT.tile_chirality(lat, cand)
    # basenames only: the actual PNG bytes are produced once, below, via the shared render.py path
    # (render_fold.render_fold derives these exact same names from rec["uid"]) — no double-rendering.
    over_name, sheet_name = "overlay_%s.png" % uid, "foldsheet_%s.png" % uid
    rec = GT._fold_record(uid, args.tiling, args.decomp, K, None, cand, tc, verdict, over_name, sheet_name)

    uid_dir = os.path.abspath(os.path.join(args.out, uid))
    os.makedirs(uid_dir, exist_ok=True)
    json_path = os.path.join(uid_dir, "%s.json" % uid)
    with open(json_path, "w") as f:
        json.dump(rec, f, indent=1)

    written = RENDER.render_record_json(json_path, uid, args.out)
    print(RENDER._summary_line(uid, written))
    print("verdict: %s" % verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
