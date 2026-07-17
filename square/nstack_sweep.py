#!/usr/bin/env python3
"""nstack_sweep.py — the n-stack grid ladder: sweep increasing grids for all-singleton folds.

Walks (m, n) in increasing-mn order for each panel count, runs each grid in its OWN subprocess with a
wall-clock timeout, and durably appends one JSON line per grid to a .jsonl -- flushed immediately, so
results survive the process/session being torn down mid-run. Re-running RESUMES: grids already in the
.jsonl are skipped, so a killed 8h sweep does not re-pay for what it already settled.

This sweep produced `square/tests/fixtures/nstack_p4_hunt_results.jsonl` -- 35 rows, panels=4 only,
because it burned its 8h budget before reaching panels=5. That file is the ONLY oracle for n-stack
and is pinned by square/tests/test_nstack.py, so the row schema is frozen; see square/nstack.py.

WHY A SUBPROCESS PER GRID, AND WHY THE KILL PATH LOOKS LIKE THIS. Cost scales brutally with panels:
6x8 at panels=4 is only 48 cells and ran unbounded under a 45-min cap. So a grid must be killable.
But on Windows a plain proc.kill() reaps only the DIRECT child -- a `jobs=N` worker has spawned N
multiprocessing grandchildren, which survive, keep running forever, AND hold the stdout pipe open, so
the recovery communicate() that subprocess.run() does internally after a timeout HANGS. Two halves,
both load-bearing, both preserved verbatim from the original:
  * redirect worker output to a FILE, never a PIPE  -> nothing to hold open, no hang
  * `taskkill /F /T` the whole tree, not proc.kill() -> no orphaned grandchildren
The same pattern guards the acceptance oracle (scripts/phystest/check.py).

`jobs` defaults to 1 so an accidental run cannot seize the machine. Jobs cannot change the RESULT
(search.run's parallel path is documented byte-identical to serial), only the wall-clock -- but it
changes that a LOT (4x8 at panels=4: 2.5s at jobs=20 vs 82s serial), so pass --jobs on a real sweep.

Run:
  python square/nstack_sweep.py --panels 4 --jobs 20
  python square/nstack_sweep.py --panels 4 5 --jobs 20 --budget 28800 --out results/nstack_sweep.jsonl
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PYTHON = sys.executable
WORKER = os.path.join(HERE, "nstack.py")

DEFAULT_BUDGET = 8 * 3600       # stop launching NEW grids past this (does not kill a running one)
DEFAULT_TIMEOUT = 15 * 60       # kill any single grid that runs longer than this
DEFAULT_MAX_N = 24              # grid-ladder ceiling per side


def grid_ladder(panels, max_n=DEFAULT_MAX_N):
    """Increasing-mn (m, n) pairs with m <= n, both >= 4, mn % panels == 0, n capped at max_n.
    Canonical m <= n only: the transpose is the same fold up to the sheet's symmetry, and enumerating
    both would double the sweep for nothing. I/O: (panels, max_n) -> list of (m, n)."""
    pairs = [(m, n) for n in range(4, max_n + 1) for m in range(4, n + 1)
             if (m * n) % panels == 0]
    pairs.sort(key=lambda mn: (mn[0] * mn[1], mn[1]))
    return pairs


def _killtree(pid):
    """Kill pid AND its whole descendant tree (taskkill /T) -- plain proc.kill() only kills the
    direct child, orphaning any multiprocessing grandchildren (jobs=N spawns N of them), which then
    keep running forever AND (on Windows) can keep the output pipe open, hanging the recovery
    communicate() subprocess.run() does internally after a timeout. Piping worker output to a file
    (see run_one) sidesteps the pipe-hang; taskkill /T sidesteps the orphaned-grandchildren leak."""
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                   capture_output=True, text=True)


def run_one(m, n, panels, *, jobs, timeout, tmpdir):
    """Run ONE grid in its own subprocess, bounded by `timeout` seconds -> a result row.

    Never raises: a timeout, a non-zero exit, and unparseable output all become an `err` row so one
    bad grid cannot take down the sweep. I/O: (m, n, panels, jobs, timeout, tmpdir) -> row dict."""
    t0 = time.time()
    out_path = os.path.join(tmpdir, f"_worker_{m}x{n}_p{panels}.tmp")
    argv = [PYTHON, "-u", WORKER, "--m", str(m), "--n", str(n), "--panels", str(panels)]
    if jobs is not None:
        argv += ["--jobs", str(jobs)]
    with open(out_path, "w", encoding="utf-8") as f:
        proc = subprocess.Popen(argv, stdout=f, stderr=subprocess.STDOUT)  # FILE, never PIPE
        timed_out = False
        while True:
            if proc.poll() is not None:
                break
            if time.time() - t0 > timeout:
                timed_out = True
                _killtree(proc.pid)            # the whole tree, not proc.kill()
                try:
                    proc.wait(timeout=30)      # a wedged reap must not propagate out of the sweep
                except subprocess.TimeoutExpired:  # (would kill a multi-hour run); the tree is already
                    pass                       # killtree'd + this grid becomes a timeout row below
                break
            time.sleep(2)
    dt = round(time.time() - t0, 1)
    with open(out_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    try:
        os.remove(out_path)
    except OSError:
        pass
    if timed_out:
        return {"m": m, "n": n, "panels": panels, "err": "timeout", "seconds": dt}
    if proc.returncode != 0:
        return {"m": m, "n": n, "panels": panels,
                "err": f"worker exit {proc.returncode}: {content[-500:]}", "seconds": dt}
    # stderr is merged into stdout (FILE, never PIPE), so a late warning can be the LAST line; scan
    # from the end for the first line that parses as a JSON object (the worker's one result row).
    row = None
    for line in reversed(content.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            row = parsed
            break
    if row is None:
        return {"m": m, "n": n, "panels": panels,
                "err": f"unparseable worker output: {content[-200:]}", "seconds": dt}
    row["seconds"] = dt
    return row


def already_done(results_path):
    """Set of (m, n, panels) already logged, so a restart resumes instead of re-running (and
    re-paying for) grids already settled. I/O: (results_path) -> set of (m, n, panels)."""
    done = set()
    if os.path.exists(results_path):
        with open(results_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:                           # a killed sweep can leave a truncated trailing line;
                    row = json.loads(line)     # skip+warn rather than crash the whole resume on it
                    key = (row["m"], row["n"], row["panels"])
                except (ValueError, KeyError, TypeError):
                    print(f"warning: skipping unparseable line in {results_path}: {line[:120]}",
                          flush=True)
                    continue
                done.add(key)
    return done


def sweep(panel_counts, results_path, *, jobs=1, budget=DEFAULT_BUDGET, timeout=DEFAULT_TIMEOUT,
          max_n=DEFAULT_MAX_N):
    """Walk each panel count's ladder, appending one row per grid. Returns the rows written."""
    t_start = time.time()
    tmpdir = os.path.dirname(os.path.abspath(results_path)) or "."
    os.makedirs(tmpdir, exist_ok=True)
    done = already_done(results_path)
    if done:
        print(f"resuming -- {len(done)} grid(s) already in {results_path}, skipping those",
              flush=True)
    written = []
    with open(results_path, "a", encoding="utf-8") as out:
        for panels in panel_counts:
            ladder = grid_ladder(panels, max_n)
            print(f"=== panels={panels}: ladder ({len(ladder)} grids) = {ladder} ===", flush=True)
            for (m, n) in ladder:
                if (m, n, panels) in done:
                    continue
                elapsed = time.time() - t_start
                if elapsed > budget:
                    print(f"!! budget ({budget}s) hit after {elapsed:.0f}s -- "
                          f"stopping before {m}x{n} panels={panels}", flush=True)
                    return written
                print(f"-> {m}x{n} panels={panels} ...", flush=True)
                row = run_one(m, n, panels, jobs=jobs, timeout=timeout, tmpdir=tmpdir)
                out.write(json.dumps(row) + "\n")
                out.flush()                    # durable per grid: the sweep may be killed any time
                written.append(row)
                if row.get("err"):
                    print(f"   ERR {row['err']} ({row['seconds']}s)", flush=True)
                    continue
                print(f"   survivors={row['survivors']} fold={row['fold']} jam={row['jam']} "
                      f"bent-fold={row['bentFoldCount']} ({row['seconds']}s)", flush=True)
                for ex in row["bentExamples"]:
                    print(f"      BENT {ex['hash']}: {ex['arrows']}", flush=True)
            print(f"=== panels={panels}: ladder exhausted (n up to {max_n}) ===", flush=True)
    print(f"DONE in {time.time() - t_start:.0f}s -- see {results_path}", flush=True)
    return written


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="n-stack grid ladder sweep -> one JSON row per grid, appended to a .jsonl")
    p.add_argument("--panels", type=int, nargs="+", default=[4],
                   help="panel counts to sweep, in order (default: 4)")
    p.add_argument("--jobs", type=int, default=1,
                   help="worker processes per grid (default 1). Cannot change the RESULT, only the "
                        "wall-clock -- but by a lot; use ~20 for a real sweep.")
    p.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                   help=f"stop launching new grids past this many seconds (default {DEFAULT_BUDGET})")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                   help=f"kill any single grid past this many seconds (default {DEFAULT_TIMEOUT})")
    p.add_argument("--max-n", type=int, default=DEFAULT_MAX_N,
                   help=f"grid-ladder ceiling per side (default {DEFAULT_MAX_N})")
    p.add_argument("--out", default=os.path.join(REPO, "results", "nstack_sweep.jsonl"),
                   help="results .jsonl (appended; re-running RESUMES from it)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    sweep(args.panels, args.out, jobs=args.jobs, budget=args.budget, timeout=args.timeout,
          max_n=args.max_n)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
