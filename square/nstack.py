#!/usr/bin/env python3
"""nstack.py — the n-stack (all-singleton) search as a tracked, importable capability + CLI.

An "n-stack" here is the all-singleton decomposition `1+1+1+...+1`: N chains of one base cell each,
on an N-cell footprint. N=3 is the familiar 1+1+1; this module is the N>=3 generalization. There is
no separate n-stack engine — `search.run` is already generic over `opts["panels"]` (the gate maths
was verified panel-parameterized in S4's survey: twist's pairwise theta loop over C(N,2), parity's
nH-even/nV-odd branch, reflection's all-pairs shared-crease scan, and a `panels`-parameterized
exit_shape). This module is the missing *front door*: it names the opts, fixes the row schema, and
gives the sweep something tracked to call.

THE ROW SCHEMA BELOW IS FROZEN by `square/tests/fixtures/nstack_p4_hunt_results.jsonl` — the only
oracle we have for n-stack, recorded by the overnight sweep that this module's opts reproduce.
Drifting the schema strands it, and it cannot be cheaply remade (that sweep burned an 8h budget and
still never reached panels=5). Two opts are load-bearing for that comparison:
  * `storeAll` must stay ABSENT, so the search is gate-PRUNED, not store-all. The oracle rows were
    produced that way; turning it on changes `survivors` and invalidates every row.
  * `allowNonCorner` must stay True — the sweep was non-corner, and corner-only is known to HIDE
    foldability outright.

HASHES IN THIS SCHEMA ARE NOT COMPARABLE ACROSS S3. `bentExamples[].hash` is a `canonicalHash`, and
S3 (2026-07-16) narrowed canonicalization from all of D4 to the sheet's automorphism subgroup, which
rewrote every representative on a NON-SQUARE sheet (e.g. the 5x8 bent row). The dedup CLASSES did not
move -- an N-stack fold covers the whole sheet, so a transposed image covers `n x m` and is never a
legal `m x n` candidate; for `m != n`, D4-merge <=> D2-merge -- so every COUNT below is S3-invariant
and the pre-S3 oracle rows still reproduce exactly. Gate on the counts; never on a stored hash.

Run:
  python square/nstack.py --m 5 --n 8 --panels 4
  python square/nstack.py --m 4 --n 8 --panels 4 --jobs 20
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # square/ on path
import _bootstrap  # noqa: E402,F401  (puts square/{engine,twist,render} on sys.path)

import runner as Runner  # noqa: E402
import search as Search  # noqa: E402


def all_singleton_decomp_key(panels):
    """'1+1+1' at panels=3, '1+1+1+1' at panels=4, ... — the opts/CLI key naming the all-singleton
    decomposition. The public accessor for the engine's helper: tracked callers (this module,
    generate.py, nstack_sweep.py, the tests) must not reach for a leading-underscore engine private.
    I/O: (panels:int) -> str."""
    return Search.all_singleton_decomp_key(panels)


def build_opts(m, n, panels, *, allow_non_corner=True, dedup=True, jobs=None):
    """The all-singleton search opts for one grid.
    I/O: (m, n, panels, allow_non_corner, dedup, jobs) -> opts dict for Search.run/Runner.run_search.

    Defaults mirror the scratch sweep that produced the oracle jsonl (allowNonCorner=True,
    dedup=True, both shapes, 2+1 off) so its rows stay reproducible -- EXCEPT `jobs`, which the
    original hardcoded to 20. `jobs` cannot change the RESULT, only the wall-clock (search.run's
    parallel path is documented byte-identical to serial), so defaulting it to None here is safe and
    keeps an import of this module from silently seizing 20 cores."""
    if panels < 3:
        raise ValueError("panels must be >= 3 (got %r)" % (panels,))
    all_key = all_singleton_decomp_key(panels)
    return {
        "m": m, "n": n, "panels": panels,
        "shapes": {"L": True, "Rect": True},
        "decomps": {"2+1": False, all_key: True},
        "allowNonCorner": allow_non_corner,
        "dedup": dedup,
        "jobs": jobs,
    }


def is_bent(rec):
    """Does any chain change direction (more than one distinct arrow)? A 'bent' fold is the
    interesting n-stack case -- the straight ones are the trivial accordions.
    I/O: (solution record) -> bool."""
    return any(len(set(ch.get("foldArrows", []))) > 1 for ch in rec["chains"])


def run_grid(m, n, panels, *, allow_non_corner=True, dedup=True, jobs=None, use_runner=True):
    """Run one grid's all-singleton search -> one result row (the oracle jsonl's schema).

    `use_runner=True` goes through runner.run_search, picking up the FOLD_PY=pypy toggle. Both paths
    produce identical rows -- the PyPy boundary marshals (solutions, ctx, err) back -- so this only
    buys speed. Pass use_runner=False to force in-process.

    On engine rejection the row is `{m, n, panels, err}` with NO gate fields, matching the 24 timeout
    rows in the oracle: callers must check `err` before reading counts.
    I/O: (m, n, panels, ...) -> row dict."""
    opts = build_opts(m, n, panels, allow_non_corner=allow_non_corner, dedup=dedup, jobs=jobs)
    if use_runner:
        sols, ctx, err = Runner.run_search(opts)
    else:
        sols, ctx, err = Search.run(opts)
    if err:
        return {"m": m, "n": n, "panels": panels, "err": err}
    fold_sols = [s for s in sols if s["verdict"]["twist"] is True]
    bent = [s for s in fold_sols if is_bent(s)]
    return {
        "m": m, "n": n, "panels": panels, "err": None,
        "coveredCount": ctx["coveredCount"], "exitPass": ctx["exitPass"],
        "parityPass": ctx["parityPass"], "survivors": ctx["afterDedup"],
        "fold": len(fold_sols), "jam": ctx["afterDedup"] - len(fold_sols),
        "bentFoldCount": len(bent),
        # hash is a post-S3 canonical rep -- NOT comparable with a pre-S3 oracle row (see module doc)
        "bentExamples": [{"hash": s["canonicalHash"],
                          "arrows": [ch["foldArrows"] for ch in s["chains"]]}
                         for s in bent[:3]],
    }


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="n-stack (all-singleton 1+1+...+1) search for one grid -> a JSON result row")
    p.add_argument("--m", type=int, required=True, help="columns")
    p.add_argument("--n", type=int, required=True, help="rows")
    p.add_argument("--panels", type=int, default=4,
                   help="chain/panel count N (>=3); N=3 is the classic 1+1+1 (default 4)")
    p.add_argument("--jobs", type=int, default=None,
                   help="parallel worker processes (default: serial / env FOLD_JOBS)")
    p.add_argument("--corner-only", action="store_true",
                   help="restrict to corner footprints (the sweep and its oracle use non-corner; "
                        "allowNonCorner=False is known to HIDE foldability)")
    p.add_argument("--no-dedup", action="store_true",
                   help="disable canonical dedup (symmetry-aware: D4 on a square sheet, D2 otherwise)")
    p.add_argument("--in-process", action="store_true",
                   help="bypass runner's PyPy toggle and call search.run directly")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    row = run_grid(args.m, args.n, args.panels,
                   allow_non_corner=not args.corner_only,
                   dedup=not args.no_dedup,
                   jobs=args.jobs,
                   use_runner=not args.in_process)
    print(json.dumps(row))
    return 1 if row.get("err") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
