"""Store-all K-census over the non-square tilings: every closing candidate, every gate stage.

Replaces the deleted `py/tri/k_stress.py` (commit 0750f15), whose outputs survive under
`report/tri/k-stress/` but which nothing in the repo could regenerate or extend. Differences:

  * STORE-ALL. Every closing candidate is written to a .jsonl, not a ~30-uid sample. The 2+1 records
    keep `strand`/`partners`/`one_chain` separately (not fused into `chains`), so the
    dual-decomposition question -- can this rigid domino ribbon be re-read as two twin monomino
    chains? -- is answerable later as an offline post-pass with no re-search.
  * FUNNEL. The per-gate counters are persisted, so "why is 2+1 so much rarer than 1+1+1" can be
    answered by WHERE candidates die, not just by the surviving count.
  * PARALLEL. Cells (tiling, decomp, K) are independent -> one process each. The triangle stack had
    no parallelism at all; the square side has had --jobs for a while.
  * HONEST TRUNCATION. A cell that hits the wall-clock cap is written with truncated=true rather
    than silently reported as a smaller exhaustive count. Every K=18 row in the old census is in
    fact truncated, which is how the published tables drifted from the on-disk ones.

The search itself is NOT reimplemented: this drives find_example.gen_111 / gen_21 / gen_eq, the same
XVAL-guarded generators the rest of the stack uses, and consumes them to exhaustion instead of
stopping at the first hit.

Usage:
    python -m triangle.tri.census --all --jobs 20
    python -m triangle.tri.census --tiling righttri --decomp 2plus1 --kmin 3 --kmax 8
"""
import argparse
import gzip
import itertools
import json
import os
import subprocess
import sys
import time
import traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed

from . import find_example as FE

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUTDIR = os.path.join(REPO, "results", "census")

TILINGS = ["equilateral", "righttri", "scalene", "hex"]
DECOMPS = ["1plus1plus1", "2plus1"]

CAP_SEC = 3600.0          # per-cell wall-clock ceiling; overrun -> truncated=true
# Per-cell resident-memory ceiling. Measured peaks with the lazy enumerators are ~165 MB for the
# heaviest cell (scalene 1+1+1 K=18, 108572 closers) and 64 MB for the honeycomb cell that used to
# exhaust the machine, so 1 GB is ~6x headroom. Concurrency is derived from this (see safe_jobs), so
# do not inflate it "to be safe" -- that just throttles the sweep.
CAP_RSS_MB = 1024
CAP_RECORDS = 2_000_000   # per-cell record ceiling; overrun -> truncated=true (disk guard)
CHECK_EVERY = 2000        # records between resource checks (RSS polling is not free)

# 2+1 START hubs to sweep. A "hub" is a distinct start trapezoid -- a different mid tile AND/OR a
# different arm pair -- so hubs are genuinely different starting configurations, not translations of
# one. Shared with the CLI (see find_example.DEFAULT_HUBS_21) so "the CLI found none" and "the census
# counted zero" mean the same thing.
#
# WAS 8, matching gen_testset. That was too narrow: 8 central hubs reach only 4 of righttri's 8 hub
# classes, so the counts it produced were undercounts, not censuses (righttri 2+1 K=4 reads 5 at 8
# hubs and 12 at 20). Counts from this file are therefore NOT comparable with the pre-2026-07-21
# k-stress tables or with figures built off them -- compare `hubs` in the summary first, which is
# why that field now exists. (1+1+1's analogue is HUBS_111 below -- a discrete variant, not a count.)
HUBS_21 = FE.DEFAULT_HUBS_21

# 1+1+1 START-hub variants to sweep, per tiling. Unlike 2+1's `hubs` (a COUNT of central start
# trapezoids) a 1+1+1 hub is a discrete AMBIENT variant: build_ambient_right/scalene lay a different
# arm pair around the mid tile, and on a tiling whose tile has unequal sides those ambients are
# genuinely inequivalent, not translations of one another. The census used to build only the
# builder's default (righttri HL, scalene omitMG), so every published 1+1+1 count was a
# single-variant undercount -- righttri LL alone adds 14 flat folds at K=14 (40 -> 54). hex and
# equilateral have no variant: their builders take no hub.
HUBS_111 = {"righttri": ["LL", "HL"], "scalene": ["omitVM", "omitMG", "omitVG"]}

_GIT_COMMIT = ...          # sentinel: not probed yet (None is a legitimate "not a checkout" answer)


def _git_commit():
    """Short HEAD sha of the tree that produced this summary, or None outside a checkout. Provenance
    is not decoration here: these counts are SWEEP-dependent, and fixing the hub coverage moved
    published numbers (righttri 2+1 K=4: 5 -> 12), so a summary that cannot say which code and which
    sweep width produced it cannot be compared with another one. Probed once per process."""
    global _GIT_COMMIT
    if _GIT_COMMIT is ...:
        try:
            out = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                                 capture_output=True, text=True, timeout=30)
            _GIT_COMMIT = out.stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            _GIT_COMMIT = None
    return _GIT_COMMIT

# Funnel stages, in gate order, per decomposition. The two ladders are not identical -- 1+1+1 fuses
# the exit-footprint and parity gates into the enumerator (a candidate failing either is never
# generated) whereas 2+1 tests exit_ok on a materialised triple -- so they are reported separately
# and only the shared tail (closure -> twist) is compared directly.
FUNNEL_111 = ["exit_fp_all", "exit_fp_parity", "exit_fp_reach", "cand", "exit_pass",
              "routed", "closure_pass"]
FUNNEL_21 = ["strands", "partner_sets", "partner_clean", "tried", "topology_pass", "closure_pass"]


_RSS_WARNED = False   # _rss_mb logs a probe failure at most once per process (see below)


def _rss_mb():
    """Resident memory of THIS process, in MB. Returns 0.0 only when NO probe is available on the
    platform (guard then no-ops); a genuinely broken probe (a wrong ctypes signature) is NOT swallowed
    -- it surfaces as ArgumentError so the RSS ceiling can't be silently disabled by a code bug.

    The census OOMed the machine outright on its first run: the walk enumerators used to materialise
    every path into a list, and 20 workers doing that on the honeycomb exhausted RAM. The enumerators
    are lazy now, but a hard per-worker ceiling is the thing that turns "the box dies" into "one cell
    is marked truncated", so it stays regardless."""
    global _RSS_WARNED
    try:
        import ctypes
        import ctypes.wintypes as wt

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        # argtypes are NOT optional here: without them ctypes marshals the pseudo-handle (-1) as a
        # 32-bit int on a 64-bit build, the call fails, and the guard silently reports 0 MB forever.
        gpmi = ctypes.windll.psapi.GetProcessMemoryInfo
        gpmi.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
        gpmi.restype = wt.BOOL
        cur = ctypes.windll.kernel32.GetCurrentProcess
        cur.restype = wt.HANDLE

        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        if gpmi(cur(), ctypes.byref(pmc), pmc.cb):
            return pmc.WorkingSetSize / (1024.0 * 1024.0)
    except (OSError, AttributeError, ValueError, ImportError) as e:
        # Real probe/platform failures only: psapi/ctypes.wintypes unavailable, non-Windows (no
        # windll), a failed WinAPI call. A wrong ctypes SIGNATURE raises ctypes.ArgumentError, which
        # is deliberately NOT caught -- that is a code bug and must surface, not silently zero out the
        # RSS ceiling. Log once (per process) so a genuine probe outage is visible but not spammed.
        if not _RSS_WARNED:
            _RSS_WARNED = True
            print("  _rss_mb: RSS probe unavailable (%s: %s); RSS ceiling disabled this run"
                  % (type(e).__name__, e), flush=True)
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except (ImportError, OSError):
        return 0.0


def _norm(cand, decomp):
    """One yielded candidate -> a flat JSON record. gen_eq wraps its payload in `rec`; gen_111 and
    gen_21 are already flat. Tile ids are tuples/lists depending on the lattice -> coerce to lists."""
    def tiles(seq):
        return [list(t) for t in seq]

    if decomp == "2plus1":
        return {
            "strand": tiles(cand["strand"]),
            "partners": tiles(cand["partners"]),
            "one_chain": tiles(cand["one_chain"]),
            "two_tris": tiles(cand["two_tris"]),
            "footprint": tiles(cand["footprint"]),
            "end_footprint": tiles(cand["end_footprint"]),
            "tw": cand["tw"],
            "foldable": bool(cand["foldable"]),
        }
    rec = cand.get("rec")                       # equilateral 1+1+1 comes through gen_eq
    if rec is not None:
        return {
            "chains": [tiles(c) for c in rec["chains"]],
            "footprint": tiles(rec["footprint"]),
            "end_footprint": tiles(rec["end_footprint"]),
            "tw": rec["tw"],
            "foldable": bool(rec["foldable"]),
            "holes": rec.get("holes"),
        }
    return {
        "chains": [tiles(c) for c in cand["chains"]],
        "footprint": tiles(cand["footprint"]),
        "end_footprint": tiles(cand["end_footprint"]),
        "tw": cand["tw"],
        "foldable": bool(cand["foldable"]),
    }


def run_cell(tiling, decomp, K, cap=CAP_SEC, outdir=OUTDIR, hubs=HUBS_21,
             cap_rss=CAP_RSS_MB, cap_records=CAP_RECORDS):
    """Exhaust one (tiling, decomp, K) cell. Returns the summary dict; writes .jsonl.gz + .summary.json.

    A cell stops early -- truncated=true, never a silent short count -- on any of three ceilings:
    wall clock (`cap`), resident memory (`cap_rss`), or records written (`cap_records`). The reason
    is recorded in `stop`."""
    t0 = time.time()
    stats = Counter({"tried": 0, "topology_pass": 0, "closure_pass": 0, "holes_filtered": 0})

    variants = None                              # 1+1+1 only; recorded as provenance below
    if decomp == "2plus1":
        # equilateral 2+1 routes here too (gen_eq delegates to gen_21 for the unified domino model),
        # but gen_eq's signature has no `hubs`, so call gen_21 directly to sweep them.
        it = FE.gen_21(tiling, K, hubs=hubs, stats=stats, budget=cap, t0=t0)[1]
    elif tiling == "equilateral":
        it = FE.gen_eq(decomp, K, stats=stats, budget=cap, t0=t0)[1]
    else:
        # Every inequivalent ambient variant, chained into ONE cell -- a census cell means "all
        # closing folds at this (tiling, decomp, K)", and a variant never built is a missing fold,
        # not a duplicate. Lazily: the chain builds each ambient only when the previous is drained.
        # `cap`/`t0` are shared, so the cell's ceilings still bound the variants COMBINED (an
        # overrun mid-variant is flagged truncated exactly as before, not silently short).
        variants = HUBS_111.get(tiling, [None])
        it = itertools.chain.from_iterable(
            FE.gen_111(tiling, K, hub=h, stats=stats, budget=cap, t0=t0)[1] for h in variants)

    os.makedirs(outdir, exist_ok=True)
    stem = "%s_%s_K%d" % (tiling, decomp, K)
    jsonl_path = os.path.join(outdir, stem + ".jsonl.gz")

    closing = tw0 = 0
    spectrum = Counter()
    truncated = False
    stop = None
    peak_rss = _rss_mb()
    # gzip: the first sweep put 900 MB on disk before it died, most of it in three K=18 cells. These
    # records are highly repetitive tile ids, so gzip is ~10x and costs little against the DFS.
    with gzip.open(jsonl_path, "wt") as fh:
        for cand in it:
            closing += 1
            rec = _norm(cand, decomp)
            key = tuple(rec["tw"]) if isinstance(rec["tw"], list) else rec["tw"]
            spectrum[str(key)] += 1
            if rec["foldable"]:
                tw0 += 1
            fh.write(json.dumps(rec) + "\n")

            if closing % CHECK_EVERY:
                continue
            rss = _rss_mb()
            peak_rss = max(peak_rss, rss)
            if rss > cap_rss:
                truncated, stop = True, "rss>%dMB" % cap_rss
            elif closing >= cap_records:
                truncated, stop = True, "records>=%d" % cap_records
            elif (time.time() - t0) > cap:
                truncated, stop = True, "time>%.0fs" % cap
            if truncated:
                break

    # The ENUMERATORS honour `cap` internally and stop yielding the moment (time - t0) > cap -- the
    # SAME threshold this consumer's in-loop check uses (see above), on the SAME t0/clock (budget=cap,
    # t0=t0 were passed straight through). From the consumer side a budget cut and a natural exhaustion
    # both look like a finished iterator, so a cut-off cell would otherwise be written out as an
    # exhaustive census with a short count -- the silent truncation that corrupted the previous
    # k-stress tables. We therefore flag truncated iff the elapsed time actually EXCEEDED the cap,
    # which is exactly the enumerator's own cutoff condition -- NOT a "near the cap" fudge: a cell that
    # exhausted at 0.99*cap ran out of candidates on its own and is a real census, not a lower bound.
    # (Matching `> cap` is the closest a consumer can get to natural-vs-cutoff without a cut flag
    # threaded back from the enumerator itself.)
    dt = time.time() - t0
    if not truncated and dt > cap:
        truncated, stop = True, "time>%.0fs (enumerator cut)" % cap

    summary = {
        "tiling": tiling, "decomp": decomp, "K": K,
        "closing": closing, "tw0": tw0,
        # Provenance -- WHICH SWEEP produced these counts. Without it a summary is uncomparable:
        # `closing` is a function of the hub sample, not of (tiling, decomp, K) alone, and the
        # figures built off these files stamp this in their caption.
        "hubs": hubs if decomp == "2plus1" else None,
        "hub_variants": variants,
        "git_commit": _git_commit(),
        # The CEILINGS, not just `stop`. A truncated count is a lower bound whose value depends on
        # the cap that produced it, and the previous sweep ran hex at 900s and everything else at
        # 3600s -- so its cells were not mutually comparable and nothing on disk said so.
        "caps": {"sec": cap, "rss_mb": cap_rss, "records": cap_records},
        "truncated": truncated, "stop": stop, "dt": round(dt, 1),
        "peak_rss_mb": round(peak_rss),
        "funnel": {k: stats[k] for k in (FUNNEL_21 if decomp == "2plus1" else FUNNEL_111)},
        "spectrum": dict(spectrum),
        "jsonl": os.path.relpath(jsonl_path, REPO),
    }
    with open(os.path.join(outdir, stem + ".summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    return summary


def _worker(cell):
    """Run one census cell in a child process -> summary dict. MemoryError is EXPECTED (a big cell can
    legitimately exhaust RAM) and is turned into a truncated record so the sweep continues. Every OTHER
    exception is a real bug and is deliberately left to SURFACE: the parent records it as an error cell
    and the ERRORED banner groups it by signature (see main), so a systematic bug shows up as many
    identical errors instead of being laundered here into one 'error' stub indistinguishable from a
    single flaky cell."""
    tiling, decomp, K, cap, outdir, hubs, cap_rss, cap_records = cell
    try:
        return run_cell(tiling, decomp, K, cap=cap, outdir=outdir, hubs=hubs,
                        cap_rss=cap_rss, cap_records=cap_records)
    except MemoryError:
        # one cell exhausting RAM must not take the sweep (or the machine) down with it
        return {"tiling": tiling, "decomp": decomp, "K": K, "closing": 0, "tw0": 0,
                "truncated": True, "stop": "MemoryError", "dt": 0, "peak_rss_mb": None,
                "funnel": {}, "spectrum": {}, "jsonl": None}


def safe_jobs(requested, cap_rss=CAP_RSS_MB, headroom_mb=4096):
    """Cap concurrency by RAM, not by core count. Peak sweep memory is roughly jobs x cap_rss, so on a
    24-core box `--jobs 20` at 3 GB/cell wants 60 GB and the machine dies -- which is exactly what
    happened on the first run. Leave `headroom_mb` for the OS and everything else."""
    try:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        ms = MS()
        ms.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
        avail_mb = ms.ullAvailPhys / (1024.0 * 1024.0)
    except Exception:
        return requested                       # cannot measure -> trust the operator
    budget = max(1, int((avail_mb - headroom_mb) // cap_rss))
    return max(1, min(requested, budget))


def plan_cells(tilings, decomps, kmin, kmax, cap, outdir, even_111=True, hubs=HUBS_21,
               cap_rss=CAP_RSS_MB, cap_records=CAP_RECORDS):
    """1+1+1 is enumerated at EVEN K only by default: the k-even criterion puts every flat fold at
    even sub-chain length, and the big 1+1+1 cells are the expensive ones. 2+1 is enumerated at
    every K -- it is cheap (tens of closers per family, all K combined) and the on-disk scalene 2+1
    census records flat folds at K=11, which an even-only sweep would silently miss."""
    cells = []
    for t in tilings:
        for d in decomps:
            for K in range(kmin, kmax + 1):
                if d == "1plus1plus1" and even_111 and K % 2:
                    continue
                cells.append((t, d, K, cap, outdir, hubs, cap_rss, cap_records))
    # biggest-first: long cells start early so they overlap the short tail
    cells.sort(key=lambda c: (-c[2], c[0]))
    return cells


def _write_index(outdir, done):
    """Write results/census/index.json from the collected per-cell summaries; return (ok, errs).
    Called from a finally so a mid-sweep abort (a wedged pool, a KeyboardInterrupt) still leaves an
    index of the cells that DID finish rather than nothing on disk."""
    ok = [s for s in done if "error" not in s]
    ok.sort(key=lambda s: (s["tiling"], s["decomp"], s["K"]))
    errs = [s for s in done if "error" in s]
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "index.json"), "w") as fh:
        json.dump({"cells": ok, "errors": errs}, fh, indent=2)
    return ok, errs


def _err_sig(tb):
    """Last non-empty line of a traceback string (the 'ExceptionType: message') -> used to GROUP error
    cells so a systematic bug (many cells, one signature) is distinguishable from a single flaky cell."""
    lines = [ln for ln in tb.strip().splitlines() if ln.strip()]
    return lines[-1].strip() if lines else "unknown error"


def main():
    ap = argparse.ArgumentParser(description="store-all K-census over the non-square tilings")
    ap.add_argument("--tiling", action="append", choices=TILINGS)
    ap.add_argument("--decomp", action="append", choices=DECOMPS)
    ap.add_argument("--kmin", type=int, default=3)
    ap.add_argument("--kmax", type=int, default=18)
    ap.add_argument("--cap", type=float, default=CAP_SEC, help="per-cell wall-clock ceiling (s)")
    ap.add_argument("--cap-rss", type=int, default=CAP_RSS_MB, dest="cap_rss",
                    help="per-cell resident-memory ceiling (MB); overrun -> truncated, not OOM")
    ap.add_argument("--cap-records", type=int, default=CAP_RECORDS, dest="cap_records",
                    help="per-cell record ceiling (disk guard)")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 4))
    ap.add_argument("--outdir", default=OUTDIR)
    ap.add_argument("--hubs", type=int, default=HUBS_21,
                    help="2+1 start hubs to sweep (default %d, well past the measured saturation "
                         "point of 4 -- see find_example.DEFAULT_HUBS_21; 8 reproduces the narrower "
                         "pre-2026-07-21 sweep)" % HUBS_21)
    ap.add_argument("--all-K-111", action="store_true",
                    help="also enumerate 1+1+1 at odd K (default: even K only)")
    ap.add_argument("--all", action="store_true", help="every tiling x every decomp")
    args = ap.parse_args()

    tilings = args.tiling or (TILINGS if args.all else None)
    decomps = args.decomp or (DECOMPS if args.all else None)
    if not tilings or not decomps:
        ap.error("give --tiling/--decomp, or --all")

    cells = plan_cells(tilings, decomps, args.kmin, args.kmax, args.cap, args.outdir,
                       even_111=not args.all_K_111, hubs=args.hubs,
                       cap_rss=args.cap_rss, cap_records=args.cap_records)
    jobs = safe_jobs(args.jobs, cap_rss=args.cap_rss)
    if jobs < args.jobs:
        print("jobs %d -> %d (RAM-capped: %d jobs x %d MB would not fit)"
              % (args.jobs, jobs, args.jobs, args.cap_rss), flush=True)
    print("census: %d cells, %d jobs, caps %.0fs / %dMB / %d recs per cell -> %s"
          % (len(cells), jobs, args.cap, args.cap_rss, args.cap_records,
             os.path.relpath(args.outdir, REPO)), flush=True)
    # The sweep width is the single most important thing to read back off a run: the counts are a
    # function of it, so print it up front as well as recording it per cell.
    print("  hubs: 2+1 sweeps %d start trapezoids; 1+1+1 sweeps ambient variants %s  [commit %s]"
          % (args.hubs, {t: HUBS_111.get(t, [None]) for t in tilings}, _git_commit()), flush=True)

    done = []
    ex = ProcessPoolExecutor(max_workers=jobs)
    try:
        futs = {ex.submit(_worker, c): c for c in cells}
        for fut in as_completed(futs):
            cell = futs[fut]
            try:
                s = fut.result()
            except Exception as e:
                # A worker that CRASHED (BrokenProcessPool: an OOM-killed / segfaulted child) or an
                # unexpected exception surfaced out of _worker. Record it as an error cell and keep
                # going: one dead cell must neither abort the whole sweep nor lose the cells that
                # already finished. as_completed yields only DONE futures, so .result() won't block.
                s = {"tiling": cell[0], "decomp": cell[1], "K": cell[2],
                     "error": "".join(
                         traceback.format_exception(type(e), e, e.__traceback__)).strip()}
            done.append(s)
            if "error" in s:
                print("  ERROR %s %s K=%d\n%s" % (s["tiling"], s["decomp"], s["K"], s["error"]),
                      flush=True)
                continue
            print("  %-12s %-12s K=%-2d closing=%-7d tw0=%-6d %-22s (%.0fs, %sMB)"
                  % (s["tiling"], s["decomp"], s["K"], s["closing"], s["tw0"],
                     ("TRUNCATED " + s["stop"]) if s["truncated"] else "exhaustive",
                     s["dt"], s["peak_rss_mb"]), flush=True)
    finally:
        # Bounded teardown: never block on a wedged/dead worker (same pattern as square/engine/
        # search.py). Write index.json regardless, so even a mid-sweep abort leaves an index of the
        # cells that finished.
        ex.shutdown(wait=False, cancel_futures=True)
        ok, errs = _write_index(args.outdir, done)

    index = os.path.join(args.outdir, "index.json")
    print("\n%d/%d cells ok, %d truncated -> %s"
          % (len(ok), len(done), sum(1 for s in ok if s["truncated"]),
             os.path.relpath(index, REPO)), flush=True)
    if errs:
        # ERRORED banner: aggregate by exception signature so a SYSTEMATIC bug (many cells, same
        # error) is loud and distinct from a single flaky/crashed cell.
        sigs = Counter(_err_sig(s["error"]) for s in errs)
        print("\n!! %d/%d CELLS ERRORED (real bugs, not truncation):" % (len(errs), len(done)),
              flush=True)
        for sig, n in sigs.most_common():
            print("   %3d x  %s" % (n, sig), flush=True)
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
