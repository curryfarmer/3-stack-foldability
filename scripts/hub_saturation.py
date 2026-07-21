"""hub_saturation.py — how wide does the 2+1 start-hub sweep have to be before the answer stops moving?

THE PROBLEM THIS MEASURES. A 2+1 search enumerates from the `hubs` most central start trapezoids, so
every count it reports is a count *for that sweep width*. Two consequences, and they pull in opposite
directions:

  * Too narrow and the search reports FALSE ZEROS. righttri 2+1 K=6 and K=8 report "none" at one hub
    and close at four; scalene 2+1 K=8 reports none out to TWELVE hubs and yields four shapes at 20.
    A zero is evidence about the sweep until it has been rechecked wider.
  * The raw placement count never stops growing, because nothing dedups congruent folds sitting at
    different positions (righttri K=7: 4 placements at 4 hubs, 18 at 20, 24 at 32 -- all of them the
    same 2 shapes). So a raw count cannot be published; it is partly a fact about the flag.

DISTINCT counts do settle, and where they settle is the minimum honest sweep width. That is what this
prints. It is the harness behind the saturation tables in find_example.DEFAULT_HUBS_21, and it exists
so those tables are reproducible rather than hand-assembled: every cell is exactly what

    tri-generate --tiling T --decomp 2plus1 --K k --all --distinct --hubs h --limit 0

reports, driven in process so a full sweep costs one interpreter start instead of two hundred.

DO NOT read one tiling's saturation point as the rule -- it is not even monotone in K (scalene K=9
saturates at 3 hubs, K=8 needs 20).

Usage:
    python scripts/hub_saturation.py --tiling righttri --tiling scalene
    python scripts/hub_saturation.py --tiling scalene --kmin 3 --kmax 13 --hubs 1,4,20,48

TRIANGLE ONLY. Never import square.* here -- both packages ship a bare top-level `lattice`, and
importing both in one interpreter corrupts module resolution for whichever bootstrap ran second.
"""
import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "triangle"))
import _bootstrap  # noqa: E402,F401  triangle/ + triangle/tri onto sys.path

import congruence as CG    # noqa: E402
import find_example as FE  # noqa: E402

DEFAULT_HUBS = [1, 2, 3, 4, 6, 8, 12, 20, 32]


def _cell(job):
    """One (tiling, K, hubs) cell -> (job, placements, distinct, distinct_flat, truncated, secs).

    Module-level (not a closure) so it is picklable for the process pool."""
    tiling, K, hubs, budget = job
    t0 = time.time()
    _, gen = FE.iter_candidates(tiling, "2plus1", K, hubs=hubs, budget=budget, t0=t0)
    cands = list(gen)
    n, d, df = CG.count_distinct(cands, tiling, FE.GEN[tiling]["cent"])
    dt = time.time() - t0
    return job, n, d, df, dt >= budget, dt


def _table(title, Ks, hubs, pick, res, tiling, budget):
    print("\n%s" % title)
    hdr = "%-4s |" % "K" + "".join("%7s" % ("h=%d" % h) for h in hubs)
    print(hdr)
    print("-" * len(hdr))
    for K in Ks:
        cells = []
        for h in hubs:
            n, d, df, trunc, _ = res[(tiling, K, h, budget)]
            v = (n, d, df)[pick]
            cells.append("%6d%s" % (v, "*" if trunc else " "))
        print("%-4d |" % K + "".join(cells))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tiling", action="append",
                    choices=["equilateral", "righttri", "scalene", "hex"],
                    help="repeatable; default righttri + scalene")
    ap.add_argument("--kmin", type=int, default=3)
    ap.add_argument("--kmax", type=int, default=13)
    ap.add_argument("--hubs", default=",".join(str(h) for h in DEFAULT_HUBS),
                    help="comma-separated sweep widths (default %s)" % ",".join(map(str, DEFAULT_HUBS)))
    ap.add_argument("--budget", type=float, default=900.0,
                    help="per-cell wall-clock ceiling (s); an overrun is marked * and its counts are "
                         "LOWER BOUNDS, never a zero you can trust")
    ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args(argv)

    tilings = args.tiling or ["righttri", "scalene"]
    hubs = [int(h) for h in args.hubs.split(",") if h.strip()]
    Ks = list(range(args.kmin, args.kmax + 1))
    jobs = [(t, K, h, args.budget) for t in tilings for K in Ks for h in hubs]

    print("hub saturation: %d tiling(s) x %d K x %d widths = %d cells, %d jobs, %.0fs cap"
          % (len(tilings), len(Ks), len(hubs), len(jobs), args.jobs, args.budget))
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        res = {j: (n, d, df, tr, dt) for j, n, d, df, tr, dt in ex.map(_cell, jobs)}

    for tiling in tilings:
        _table("%s 2+1 - DISTINCT closing shapes  (the column that should stop moving)"
               % tiling, Ks, hubs, 1, res, tiling, args.budget)
        _table("%s 2+1 - DISTINCT flat (Tw=0) shapes" % tiling, Ks, hubs, 2, res, tiling, args.budget)
        _table("%s 2+1 - raw placements  (never saturates -- do not publish these)"
               % tiling, Ks, hubs, 0, res, tiling, args.budget)

        # The headline number: the narrowest width at which every K already shows its final count.
        final = {K: res[(tiling, K, hubs[-1], args.budget)][1] for K in Ks}
        sat = next((h for h in hubs
                    if all(res[(tiling, K, h, args.budget)][1] == final[K] for K in Ks)), None)
        print("\n-> %s saturates at %s (widest measured: %d hubs)"
              % (tiling, "%d hubs" % sat if sat else "NO measured width -- widen --hubs", hubs[-1]))
    print("\n* = budget exhausted, counts are lower bounds.   (%.0fs)" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
