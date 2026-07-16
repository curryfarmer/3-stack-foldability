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

Alternatively, ingest an EXACT drawn region (a fold-grid/1 file: arbitrary connected set of a tiling's
base cells) and write a tri-fold/1 record per closing 1+1+1 fold (JSON always; --render also writes the
overlay/foldsheet/twist/reflect PNGs, so the S7 orchestrator has the worker render its own engine code).
1+1+1 / 3-stack only; --grid-file is mutually exclusive with the flags above:

  python generate.py --grid-file my_region.json            # enumerate every closing fold of the region
  python generate.py --grid-file my_region.json --first    # stop at the first closing fold
  python generate.py --grid-file my_region.json --render   # also write the PNG bundle per fold
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_example as FE     # noqa: E402  find_first / verdict_text (the existing search entry point)
import foldgrid_tri as FG     # noqa: E402  arbitrary drawn-region ingest (--grid-file, 1+1+1 only)
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


def _run_grid_file(args):
    """Ingest an arbitrary drawn region (fold-grid/1 JSON) and write one tri-fold/1 record per closing
    1+1+1 fold that covers EXACTLY the region. JSON always; PNGs only under --render (overlay/foldsheet/
    twist/reflect via the shared render.py path -- the S7 orchestrator passes --render so the worker,
    not the orchestrator, renders engine code). The embedded geometry lets a consumer render engine-free
    later too. Exit 0 even when the region admits no closing fold (a valid obstruction, mirroring the
    no-example search path)."""
    with open(args.grid_file) as f:
        spec = json.load(f)
    if spec.get("schema") != "fold-grid/1":
        raise ValueError("grid-file schema must be 'fold-grid/1', got %r" % spec.get("schema"))
    tiling = spec.get("tiling")
    if tiling not in FG.TILINGS:
        raise ValueError("grid-file tiling must be one of %s, got %r"
                         % (", ".join(FG.TILINGS), tiling))
    stacks = spec.get("stacks", [3])
    if stacks != [3]:
        raise ValueError("triangle grid ingest is 3-stack / 1+1+1 only; `stacks` must be [3], got %r"
                         % (stacks,))
    lat = FG.build_lattice(tiling, spec.get("cells", []))   # validates the region (raises ValueError)
    K = len(lat.tris) // 3
    records = FG.enumerate_folds(lat, tiling, first=args.first)
    n_fold = sum(1 for r in records if r["foldable"])
    print("grid-file: tiling=%s |S|=%d K=%d -> %d closing fold(s), %d predicted foldable%s"
          % (tiling, len(lat.tris), K, len(records), n_fold, " (--first)" if args.first else ""))
    for rec in records:
        uid = GT.fold_uid(tiling, "1plus1plus1", rec)
        tc = SFILT.tile_chirality(lat, rec)
        verdict = FE.verdict_text(rec)
        over_name, sheet_name = "overlay_%s.png" % uid, "foldsheet_%s.png" % uid
        full = GT._fold_record(uid, tiling, "1plus1plus1", K, None, rec, tc, verdict,
                               over_name, sheet_name)
        uid_dir = os.path.abspath(os.path.join(args.out, uid))
        os.makedirs(uid_dir, exist_ok=True)
        json_path = os.path.join(uid_dir, "%s.json" % uid)
        with open(json_path, "w") as f:
            json.dump(full, f, indent=1)
        if args.render:
            RENDER.render_record_json(json_path, uid, args.out)
        print("  wrote %s/%s.json  %s%s" % (uid, uid, verdict, "  +PNGs" if args.render else ""))
    if not records:
        print("no closing 1+1+1 fold covers this region "
              "(a valid outcome -- the region may admit no 3-stack closure)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="search for one closing 3-stack fold example and render its full image bundle, "
                    "OR (--grid-file) fold an exact drawn region")
    ap.add_argument("--grid-file", help="fold-grid/1 JSON: fold an EXACT drawn region "
                    "(1+1+1 / 3-stack only). Mutually exclusive with --tiling/--decomp/--K.")
    ap.add_argument("--first", action="store_true",
                    help="--grid-file: stop at the first closing fold instead of enumerating all")
    ap.add_argument("--render", action="store_true",
                    help="--grid-file: also write the overlay/foldsheet/twist/reflect PNG bundle per fold "
                         "(via render.py); default is JSON-only")
    ap.add_argument("--tiling", choices=["equilateral", "righttri", "scalene", "hex"])
    ap.add_argument("--decomp", choices=["2plus1", "1plus1plus1"])
    ap.add_argument("--K", type=int, help="chain length")
    ap.add_argument("--out", default="out", help="output root directory (default: out/)")
    ap.add_argument("--budget", type=float, default=120.0, help="search wall-clock budget in seconds")
    args = ap.parse_args(argv)

    if args.grid_file:
        conflicts = [n for n, v in (("--tiling", args.tiling), ("--decomp", args.decomp),
                                    ("--K", args.K)) if v is not None]
        if conflicts:
            ap.error("--grid-file is mutually exclusive with %s" % ", ".join(conflicts))
        return _run_grid_file(args)

    missing = [n for n, v in (("--tiling", args.tiling), ("--decomp", args.decomp),
                              ("--K", args.K)) if v is None]
    if missing:
        ap.error("the following arguments are required: %s (or use --grid-file)" % ", ".join(missing))

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
