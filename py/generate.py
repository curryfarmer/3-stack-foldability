#!/usr/bin/env python3
"""generate.py — CLI to run the 3-stack search and cache results as JSON.

Examples:
  python3 generate.py --m 6 --n 6
  python3 generate.py --m 6 --n 5 --decomps 2+1 --allow-non-corner
  python3 generate.py --m 6 --n 6 --force        # ignore cache, regenerate
  python3 generate.py --stacks 2 --m 6 --n 5     # RSPA 2-stack (Hamiltonian circuits)
  python3 generate.py --list                     # show the manifest

Results land in ../results/ (per-params JSON + manifest.json). A matching cached
run is reused unless --force is given.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # py/ on path
import _bootstrap  # noqa: E402,F401  (runner -> engine/, store -> storage/, + every py/ subfolder)

import runner as Runner       # noqa: E402
import twostack as TwoStack   # noqa: E402


def parse_args(argv):
    p = argparse.ArgumentParser(description="3-stack folding search → JSON cache")
    p.add_argument("--m", type=int, help="columns")
    p.add_argument("--n", type=int, help="rows")
    p.add_argument("--stacks", type=int, default=3, choices=(2, 3),
                   help="2 = RSPA Hamiltonian-circuit 2-stack; 3 = footprint/decomp 3-stack (default)")
    p.add_argument("--shapes", default="L,Rect", help="comma list: L,Rect (3-stack only)")
    p.add_argument("--decomps", default="2+1,1+1+1", help="comma list: 2+1,1+1+1")
    p.add_argument("--allow-non-corner", action="store_true")
    p.add_argument("--store-all", action="store_true",
                   help="Phase A: store EVERY covered candidate (D4-deduped) with non-destructive "
                        "gate verdicts as columns, instead of pruning to gate-survivors")
    p.add_argument("--jobs", type=int, default=None,
                   help="parallel worker processes (default 1; env FOLD_JOBS as fallback)")
    p.add_argument("--no-dedup", action="store_true", help="disable D4 dedup")
    p.add_argument("--force", action="store_true", help="regenerate even if cached")
    p.add_argument("--list", action="store_true", help="print manifest and exit")
    # SQLite run annotation + engine-vs-old-engine compare (store-all 3-stack only)
    p.add_argument("--label", help="short name stored on the SQLite run (e.g. 'twist-fix v2')")
    p.add_argument("--note", help="free-text note stored on the SQLite run (also editable in a DB browser)")
    p.add_argument("--snapshot", metavar="LABEL",
                   help="before writing, freeze the current run for these opts as a labeled snapshot, "
                        "then diff the new engine output against it by pattern_uid (keeps both runs)")
    p.add_argument("--db", metavar="PATH",
                   help="SQLite DB path (default $FOLDDB_SQLITE or results/folddb.sqlite3)")
    p.add_argument("--test", action="store_true",
                   help="use the scratch DB results/folddb.test.sqlite3 (rehearse without touching real data)")
    return p.parse_args(argv)


def build_opts(args):
    if args.stacks == 2:
        return {"m": args.m, "n": args.n, "stacks": 2, "dedup": not args.no_dedup}
    shapes = {s: (s in args.shapes.split(",")) for s in ("L", "Rect")}
    decomps = {d: (d in args.decomps.split(",")) for d in ("2+1", "1+1+1")}
    return {
        "m": args.m, "n": args.n, "stacks": 3,
        "shapes": shapes, "decomps": decomps,
        "allowNonCorner": args.allow_non_corner,
        "dedup": not args.no_dedup,
        "jobs": args.jobs,
        "storeAll": args.store_all,
    }


def _print_diff(res, snapshot_label, limit=25):
    """Print the engine-vs-snapshot pattern_uid diff from Store.snapshot_and_save()'s result."""
    if res.get("frozen_id") is None:
        print(f"  snapshot '{snapshot_label}': no prior run for these opts — nothing to diff against")
        return
    d = res["diff"]
    print(f"  diff vs snapshot '{snapshot_label}' (run {res['frozen_id']} -> {res['run_id']}): "
          f"{len(d['changed'])} verdict flips, {len(d['onlyA'])} removed, {len(d['onlyB'])} added")
    for c in d["changed"][:limit]:
        flips = ", ".join(f"{k} {v[0]}->{v[1]}" for k, v in c["deltas"].items())
        print(f"    {c['pattern_uid']}: {flips}")
    if len(d["changed"]) > limit:
        print(f"    … +{len(d['changed']) - limit} more (full diff via GET /api/compare)")


def main(argv):
    args = parse_args(argv)

    if args.list:
        # TODO(square-restructure): replace with out/<uid>/ manifest read (store.py removed)
        print("(manifest listing disabled -- store.py removed pending new out/<uid>/ JSON format)")
        return 0

    if args.m is None or args.n is None:
        print("error: --m and --n required (or use --list)", file=sys.stderr)
        return 2

    opts = build_opts(args)

    # An explicit DB target only has a place to write when this is a 3-stack store-all run (the sole
    # path that lands in SQLite). Without --store-all, --db/--test would suppress the JSON yet write no
    # DB row — a silent no-op. Fail fast instead.
    if (args.db or args.test) and not (opts["stacks"] == 3 and opts.get("storeAll")):
        print("error: --db/--test requires --store-all (only the store-all covered set has a SQLite "
              "target; gated/2-stack runs write JSON, which an explicit-DB run suppresses)",
              file=sys.stderr)
        return 2

    # Bypass the JSON cache when the engine MUST actually run: --force, --snapshot (needs fresh output
    # to diff), or an explicit --db/--test target (the point is to populate THAT database).
    if not (args.force or args.snapshot or args.db or args.test):
        # TODO(square-restructure): replace with out/<uid>/ cache lookup (store.py removed)
        cached = None
        if cached:
            print(f"cached: {cached['count']} solutions -> results/{cached['file']} "
                  f"({cached['generated']})  [use --force to regenerate]")
            return 0

    if opts["stacks"] == 2:
        solutions, ctx, err = TwoStack.run(opts)
    else:
        solutions, ctx, err = Runner.run_search(opts)  # PyPy + multiprocessing toggles
    if err:
        print(f"rejected: {err}", file=sys.stderr)
        return 1
    # An explicit DB target (--db/--test) writes ONLY that database — it does NOT touch the legacy
    # results/*.json + manifest (those are being phased out, and a scratch run must not pollute them).
    explicit_db = bool(args.db or args.test)
    # TODO(square-restructure): replace with out/<uid>/ JSON write (store.py removed)
    fname = None
    if not explicit_db:
        print("  (JSON result caching disabled -- store.py removed pending new out/<uid>/ format)")
    # Phase-A store-all also lands in the SQLite write-master (the API + live-tag write-back read it);
    # the JSON above stays the file:// / archival fallback. Gated runs stay JSON-only (legacy path).
    if opts["stacks"] == 3 and opts.get("storeAll"):
        # TODO(square-restructure): replace with out/<uid>/ JSON write (SQLite write-master removed)
        print("  (SQLite store-all persistence disabled -- store.py removed pending new output format)")
    dest = "(no persistence -- store.py removed pending new out/<uid>/ JSON format)"
    if opts["stacks"] == 2:
        foldable = sum(1 for s in solutions if s["verdict"]["foldable"])
        print(f"generated {len(solutions)} HC patterns (foldable 2-stack: {foldable}) -> {dest}")
    else:
        twist0 = sum(1 for s in solutions if s["verdict"]["twist"] is True)
        print(f"generated {len(solutions)} solutions (Tw=0 decided: {twist0}) -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
