"""Offline post-pass: collapse a census cell's stored folds into CONGRUENCE CLASSES.

Why this exists. The census counts PLACEMENTS: every candidate every start hub yields is a separate
record, and nothing anywhere dedups congruent regions sitting at different positions or orientations
(gen_testset's frozenset(region) key separates them, since it compares tile IDs). So a plotted fold
count is partly a fact about the tiling and partly a fact about how wide the sweep was -- raising
righttri 2+1 K=7 from 4 hubs to 20 takes the count 4 -> 18 while the set of distinct shapes stays at
2. A bar chart of raw counts is therefore not reproducible: it moves when --hubs moves.

Distinct counts are stable. Measured for righttri 2+1 (see find_example.DEFAULT_HUBS_21), the
distinct count saturates at 4 hubs and is flat out to 20 while the raw count keeps climbing. Plot
distinct and the figure stops depending on the sweep width.

This is a post-pass, not a re-search: the census already writes every fold's chains, and tile
centroids are pure functions of the tile ID (GEN[tiling]["cent"]), so no lattice has to be rebuilt
and no generator has to be re-run. It reads <dir>/*.jsonl.gz and writes `distinct` / `distinct_tw0`
back into the matching *.summary.json.

Usage:
    python -m triangle.tri.census_distinct results/census_v2 --jobs 8
"""
import argparse
import glob
import gzip
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from . import congruence as CG
from . import find_example as FE

NFOLD = CG.NFOLD        # re-exported: callers select cells by tiling before knowing anything else


def cell_distinct(path, tiling):
    """(records, distinct, distinct_tw0) for one .jsonl.gz, streamed straight off disk so a cell too
    large to hold in memory still counts."""
    def records():
        with gzip.open(path, "rt") as fh:
            for line in fh:
                yield json.loads(line)

    return CG.count_distinct(records(), tiling, FE.GEN[tiling]["cent"])


def _job(args):
    path, tiling = args
    t0 = time.time()
    try:
        n, d, d0 = cell_distinct(path, tiling)
        return path, n, d, d0, time.time() - t0, None
    except Exception as exc:                                  # one bad cell must not kill the sweep
        return path, 0, 0, 0, time.time() - t0, "%s: %s" % (type(exc).__name__, exc)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("census_dir", help="directory of *.jsonl.gz + *.summary.json")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true", help="report but do not rewrite summaries")
    args = ap.parse_args(argv)

    jobs = []
    for path in sorted(glob.glob(os.path.join(args.census_dir, "*.jsonl.gz"))):
        tiling = os.path.basename(path).split("_")[0]
        if tiling not in NFOLD:
            print("skip (unknown tiling): %s" % path)
            continue
        jobs.append((path, tiling))
    if not jobs:
        print("no cells found in %s" % args.census_dir)
        return 1

    print("%-46s %10s %10s %10s %7s" % ("cell", "records", "distinct", "flat", "secs"))
    rc = 0
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(_job, j): j for j in jobs}
        for fut in as_completed(futs):
            path, n, d, d0, dt, err = fut.result()
            name = os.path.basename(path).replace(".jsonl.gz", "")
            if err:
                print("%-46s ERROR %s" % (name, err))
                rc = 1
                continue
            print("%-46s %10d %10d %10d %7.0f" % (name, n, d, d0, dt))
            sys.stdout.flush()
            if args.dry_run:
                continue
            spath = path.replace(".jsonl.gz", ".summary.json")
            if not os.path.exists(spath):
                # Cell still running, or died before writing its summary. The counts above are still
                # valid for whatever is on disk, but there is no summary to attach them to.
                print("  (no summary yet: %s)" % os.path.basename(spath))
                continue
            with open(spath) as fh:
                summary = json.load(fh)
            summary["distinct"] = d
            summary["distinct_tw0"] = d0
            summary["distinct_records"] = n     # what `distinct` was computed over; != `closing` if
                                                # the jsonl was still being written when this ran
            with open(spath, "w") as fh:
                json.dump(summary, fh, indent=2)
    return rc


if __name__ == "__main__":
    sys.exit(main())
