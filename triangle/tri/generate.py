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
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import congruence as CG       # noqa: E402  --distinct: collapse placements into congruence classes
import find_example as FE     # noqa: E402  find_first / verdict_text (the existing search entry point)
import foldgrid_tri as FG     # noqa: E402  arbitrary drawn-region ingest (--grid-file, 1+1+1 only)
import gen_testset as GT      # noqa: E402  fold_uid / _fold_record (the existing record schema)
import seam_filter as SFILT   # noqa: E402  tile_chirality (per-tile orientation read-out for the record)
import render as RENDER       # noqa: E402  render_record_json — the SAME out/<uid>/ packaging as tri-render


def find_one(tiling, decomp, K, budget=120.0, hub=None, hubs=None):
    """Search for exactly ONE closing candidate at this fixed K. Reuses find_example.find_first,
    pinned to a single K (K0=kcap=K, step=1) instead of marching a K-range. Returns
    (result, stats) where result is (lat, K, cand) or None if no closing candidate WAS FOUND within
    the hub sample and budget searched; stats is the search's gate-funnel counter dict.

    `hubs` (2+1 start-trapezoid count) and `hub` (1+1+1 ambient variant) are threaded through rather
    than pinned: this used to pass neither, so every 2+1 search ran the 1-hub default and returned
    None at K=6/K=8 where the 8-hub census finds 6 and 8 closing folds."""
    stats = {"tried": 0, "topology_pass": 0, "closure_pass": 0, "holes_filtered": 0}
    res = FE.find_first(tiling, decomp, "allow", K, 1, K, hub=hub, budget=budget, stats=stats,
                        hubs=hubs)
    return res, stats


def find_all(tiling, decomp, K, budget=120.0, hub=None, hubs=None):
    """Every closing candidate at this fixed K, not just the first. Returns (lat, cands, stats).

    Drains find_example.iter_candidates -- the same iterator find_one takes its single hit off, and
    the same gen_* the census drives -- so `--all` and the default find-first mode cannot disagree
    about what exists. This is the `sq-generate`-style full search for the triangle track; the
    exhaustive multi-K sweep with gate funnels and truncation accounting is triangle.tri.census."""
    stats = {"tried": 0, "topology_pass": 0, "closure_pass": 0, "holes_filtered": 0}
    lat, gen = FE.iter_candidates(tiling, decomp, K, hub=hub, hubs=hubs,
                                  budget=budget, stats=stats)
    return lat, list(gen), stats


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


def _write_fold(args, lat, K, cand, render=True):
    """Write one out/<uid>/<uid>.json (+ the image bundle under `render`). Returns the uid."""
    uid = GT.fold_uid(args.tiling, args.decomp, cand)
    tc = SFILT.tile_chirality(lat, cand)
    # basenames only: the actual PNG bytes are produced once, by render_record_json below, via the
    # shared render.py path (render_fold derives these same names from rec["uid"]) — no double-render.
    over_name, sheet_name = "overlay_%s.png" % uid, "foldsheet_%s.png" % uid
    rec = GT._fold_record(uid, args.tiling, args.decomp, K, None, cand, tc, FE.verdict_text(cand),
                          over_name, sheet_name)
    uid_dir = os.path.abspath(os.path.join(args.out, uid))
    os.makedirs(uid_dir, exist_ok=True)
    json_path = os.path.join(uid_dir, "%s.json" % uid)
    with open(json_path, "w") as f:
        json.dump(rec, f, indent=1)
    if render:
        print(RENDER._summary_line(uid, RENDER.render_record_json(json_path, uid, args.out)))
    return uid


def _run_all(args):
    """--all: enumerate every closing fold at this (tiling, decomp, K) rather than stopping at the
    first. JSON per fold; PNGs only under --render, and at most --limit records on disk."""
    t0 = time.time()
    lat, cands, stats = find_all(args.tiling, args.decomp, args.K, budget=args.budget,
                                 hub=args.hub, hubs=args.hubs)
    dt = time.time() - t0
    _print_search_summary(args.decomp, stats)

    scope = ("%d start hub(s)" % (FE.DEFAULT_HUBS_21 if args.hubs is None else args.hubs)
             if args.decomp == "2plus1" else
             "ambient hub %s" % (args.hub or "(builder default)"))
    n_fold = sum(1 for c in cands if c["foldable"])
    print("all: tiling=%s decomp=%s K=%d -> %d closing fold(s), %d predicted foldable, searching %s"
          % (args.tiling, args.decomp, args.K, len(cands), n_fold, scope))
    if args.distinct:
        _, d_all, d_flat = CG.count_distinct(cands, args.tiling, FE.GEN[args.tiling]["cent"])
        print("distinct: %d closing shape(s), %d flat shape(s)  [congruence classes under the %d-fold "
              "dihedral group]" % (d_all, d_flat, CG.NFOLD[args.tiling]))
    if dt >= args.budget:
        # The enumeration was cut off, so these are LOWER BOUNDS. Saying so is the whole point:
        # an --all that quietly stops early is worse than no --all, because it looks exhaustive.
        print("  WARNING: --budget (%.0fs) was exhausted — the enumeration stopped early, so these\n"
              "  counts are lower bounds, not the complete answer. Raise --budget, or use the census."
              % args.budget)
    if len(cands) > 1 and not args.distinct:
        # Counts are PLACEMENTS. Congruent folds at different positions/orientations are separate
        # records here, and the total therefore grows with --hubs even when no new shape appears.
        print("  NB: these are placements, not distinct shapes — congruent folds at different\n"
              "  positions are counted separately. Re-run with --distinct to collapse them.")

    written = 0
    for cand in cands[:max(0, args.limit)]:
        _write_fold(args, lat, args.K, cand, render=args.render)
        written += 1
    print("wrote %d record(s) to %s%s"
          % (written, os.path.abspath(args.out),
             "" if written == len(cands) else " (--limit %d of %d)" % (args.limit, len(cands))))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="search for one closing 3-stack fold example and render its full image bundle, "
                    "OR (--grid-file) fold an exact drawn region")
    ap.add_argument("--grid-file", help="fold-grid/1 JSON: fold an EXACT drawn region "
                    "(1+1+1 / 3-stack only). Mutually exclusive with --tiling/--decomp/--K.")
    ap.add_argument("--first", action="store_true",
                    help="--grid-file: stop at the first closing fold instead of enumerating all")
    ap.add_argument("--all", action="store_true",
                    help="--tiling/--decomp/--K: enumerate EVERY closing fold instead of stopping at "
                         "the first (the sq-generate-style full search). Counts printed are exact; "
                         "records written are capped by --limit. For a multi-K sweep with gate "
                         "funnels and truncation accounting use triangle.tri.census.")
    ap.add_argument("--distinct", action="store_true",
                    help="--all: also report DISTINCT congruence classes, i.e. how many different "
                         "SHAPES the folds are. The plain counts are placements and grow with "
                         "--hubs even when no new shape appears; the distinct counts do not.")
    ap.add_argument("--limit", type=int, default=200,
                    help="--all: max fold records written to disk (default 200). The printed counts "
                         "are unaffected -- a big cell can hold 500k folds, and one directory each "
                         "is not something a CLI should do silently.")
    ap.add_argument("--render", action="store_true",
                    help="--grid-file: also write the 2-image bundle per fold (schematic + twist PNG "
                         "+ analysis JSON, via render.py); default is JSON-only")
    ap.add_argument("--tiling", choices=["equilateral", "righttri", "scalene", "hex"])
    ap.add_argument("--decomp", choices=["2plus1", "1plus1plus1"])
    ap.add_argument("--K", type=int, help="chain length")
    ap.add_argument("--out", default="out", help="output root directory (default: out/)")
    ap.add_argument("--budget", type=float, default=120.0, help="search wall-clock budget in seconds")
    ap.add_argument("--hub", help="1+1+1 ambient variant — righttri: LL/HL ; scalene: omitVM/omitMG/omitVG "
                                  "(default: the builder's, HL / omitMG). These are inequivalent "
                                  "lattices, so a variant not searched is folds not found.")
    ap.add_argument("--hubs", type=int, default=None,
                    help="2+1: distinct START trapezoids to sweep (default %d, matching the census). "
                         "Unrelated to --hub." % FE.DEFAULT_HUBS_21)
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

    if args.all:
        return _run_all(args)

    res, stats = find_one(args.tiling, args.decomp, args.K, budget=args.budget,
                          hub=args.hub, hubs=args.hubs)
    _print_search_summary(args.decomp, stats)
    if res is None:
        # Nothing further to print: _print_search_summary above has already reported the funnel
        # (tried / topology-pass / closure-pass), which is the honest account of what was searched.
        # A found/not-found search is scoped by --hubs/--hub and --budget; a *proven* answer comes
        # from the exhaustive census (triangle.tri.census) or triangle.tri.prove_obstruction.
        return 0

    lat, K, cand = res
    _write_fold(args, lat, K, cand, render=True)
    print("verdict: %s" % FE.verdict_text(cand))
    return 0


if __name__ == "__main__":
    sys.exit(main())
