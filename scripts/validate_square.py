"""scripts/validate_square.py — regression proof for the square engine.

Re-derives a FRESH FOLD/JAM verdict for every john-verified square ground-truth record by running
the REAL search (`square.engine.search.run`, via `square.engine.runner.run_search` — the exact call
`square/generate.py` itself makes) on the record's grid size, then matching the ground-truth
candidate's canonical identity against the full set of engine-produced candidates for that grid.

GROUND TRUTH SOURCE: `results/foldfindings.json`, filtered to `by == "john"` and
`foldable is not None` — exactly 61 records as of 2026-07 (confirmed by direct count), spanning 6
distinct grids: 6x4 (8), 6x5 (9), 6x6 (40), 6x7 (2), 6x8 (1), 8x6 (1).

AXIS-ORDER FINDING (m vs n). `grid` is an "MxN" string. `square/generate.py`'s own uid-builder
formats grids as `f"{m}x{n}"` (`make_uid`, generate.py L76-77) and its CLI docstrings/help text
treat `--m` as columns and `--n` as rows (`enumerate_footprints(m, n, opts)` bounds-checks
`0 <= x < m` / `0 <= y < n`). So "6x4" parses as m=6 (columns), n=4 (rows) — confirmed empirically
below: with m=6,n=4 every one of the 8 ground-truth 6x4 records is found among the engine's
candidates and every foldable bit agrees; re-parsing the same records with the axes swapped
(m=4,n=6) would search an entirely different (and for these footprints, non-matching) grid.

CANONICAL-HASH FINDING (key order). `square.lattice.square.SquareLattice.canonical_hash` currently
serializes `json.dumps({"fp": fp, "chains": chain_sigs}, ...)` — "fp" first. Several stored
`canonicalHash` ground-truth strings serialize "chains" first (e.g. id=16, grid 6x4) — evidently
produced by an earlier version of the function with a different dict-literal key order. A literal
string `==` comparison would then spuriously report EVERY record as "not-enumerated" even though the
content is byte-for-byte the same candidate. We therefore normalize both sides the same way before
comparing: `json.dumps(json.loads(s), sort_keys=True, separators=(",", ":"))`. This is exactly the
task's own suggested fallback and is the only normalization that is robust to that historical key-
order change while still catching a REAL content difference (different footprint/chain/base/arrows).

WHICH ENGINE CANDIDATES TO MATCH AGAINST. We run the search in the *default* (non `--store-all`)
mode — the same mode `square/generate.py` runs without `--store-all`, and the one that plausibly
produced the candidates John was shown to test. In that mode `_evaluate_candidate` only emits a
solution once exitFootprint + parity + reflection ALL pass (`search.py._evaluate_candidate`); the
solution is emitted regardless of the twist verdict (twist is "non-filtering": decided-False JAMs
and undecided candidates still appear in `solutions`, carrying `verdict["twist"]` as
True/False/None). So a ground-truth record whose canonical identity is absent from that solution set
is a genuine "not-enumerated" regression (the candidate used to be a gate-survivor and no longer is),
distinct from a plain foldable-bit disagreement. The fresh engine verdict for a MATCHED candidate is
`sol["verdict"]["twist"] is True` (per docs/guides/ENGINE_SPEC.md stage 8: twist is decided for every
1+1+1 candidate and, since the 2+1 jump-strand twist model shipped into both engines, for every 2+1
candidate in this ground truth too — an undecided twist here would itself be a flagged anomaly).

`allowNonCorner=True` always (confirmed in prior investigation: ALL foldable 6x6 2+1 ground truth is
off-corner; a corner-only search would silently miss real folds), both decomps + both shapes enabled,
D4 dedup on, multiprocessing on (FOLD_JOBS, defaulting to os.cpu_count()) purely for wall-clock — the
parallel path is documented (search.py `_search_parallel`) to replay dedup/id serially in the parent
and be byte-identical to the serial path, so this is a performance knob only, not a behavior change.
That is also why `jobs` is excluded from the oracle cache key (see oracle_cache.py).

CACHING. The per-grid search dominates the wall clock; the record checks are cheap. `_search_grid`
is memoized by `scripts/phystest/oracle_cache.py`, keyed on the whole `square/` package source plus
the opts plus the runtime — so any engine edit invalidates everything and the cache cannot mask a
regression. Records are re-read and re-checked on EVERY run, hit or miss. `ORACLE_CACHE=0` forces a
cold run; the `--json` payload reports per-grid hit/miss so a PASS states its provenance.

Run standalone from anywhere:  python scripts/validate_square.py
"""
import json
import os
import sys
import time
from collections import defaultdict

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SQUARE_DIR = os.path.join(_REPO_ROOT, "square")
if _SQUARE_DIR not in sys.path:
    sys.path.insert(0, _SQUARE_DIR)
import _bootstrap  # noqa: E402  puts square/ (for `import lattice`) + square/{engine,twist,render} on sys.path

_PHYSTEST_DIR = os.path.join(_REPO_ROOT, "scripts", "phystest")
if _PHYSTEST_DIR not in sys.path:
    sys.path.insert(0, _PHYSTEST_DIR)                  # after the engine bootstrap: engine wins any tie
import oracle_cache as OC  # noqa: E402  stdlib-only; imports no engine package

GROUND_TRUTH_PATH = os.path.join(_REPO_ROOT, "results", "foldfindings.json")


def _norm_hash(canonical_hash_str):
    """Key-order-independent normal form of a canonicalHash JSON string (see module docstring)."""
    return json.dumps(json.loads(canonical_hash_str), sort_keys=True, separators=(",", ":"))


def _load_ground_truth():
    """61-ish john-verified records, grouped by grid string. Returns (by_grid, present) where
    present is False only when results/foldfindings.json does not exist (fresh-clone skip)."""
    if not os.path.isfile(GROUND_TRUTH_PATH):
        return {}, False
    with open(GROUND_TRUTH_PATH, encoding="utf-8") as f:
        data = json.load(f)
    johns = [r for r in data if r.get("by") == "john" and r.get("foldable") is not None]
    by_grid = defaultdict(list)
    for r in johns:
        by_grid[r["grid"]].append(r)
    return by_grid, True


def _jobs():
    """Worker count: FOLD_JOBS when set, else os.cpu_count().

    NB: do NOT "simplify" this to `jobs: None`. search.py's `_resolve_jobs` only consults FOLD_JOBS
    when opts["jobs"] is None and otherwise falls back to *1*, so passing None would silently make
    this oracle serial — hours slower — whenever FOLD_JOBS happens to be unset."""
    env = os.environ.get("FOLD_JOBS", "").strip()
    if env:
        try:
            return max(1, int(env))
        except ValueError:
            pass
    return os.cpu_count()


def _opts(m, n):
    """The exact search opts for one grid. Extracted so the cache key and the search itself read
    from ONE literal and cannot drift apart. I/O: (int, int) -> dict."""
    return {
        "m": m, "n": n, "stacks": 3,
        "shapes": {"L": True, "Rect": True},
        "decomps": {"2+1": True, "1+1+1": True},
        "allowNonCorner": True,
        "dedup": True,
        "jobs": _jobs(),
        "storeAll": False,
    }


def _search_grid(Runner, m, n):
    """Run the real 3-stack search for one grid, default (non-store-all) mode, allow-non-corner,
    both shapes/decomps.

    Returns {normalized_canonical_hash: twist_tristate}, where the tri-state is
    sol["verdict"]["twist"] (True=FOLD / False=JAM / None=undecided) — the only field the caller
    consumes, and the only one that needs to survive a JSON round-trip through the cache.
    NB: a value of None is MEANINGFUL (undecided); absence of the key means not-enumerated. Callers
    must test membership, not truthiness."""
    opts = _opts(m, n)
    solutions, ctx, err = Runner.run_search(opts)
    if err:
        raise RuntimeError("search rejected m=%d n=%d: %s" % (m, n, err))
    by_hash = {}
    for sol in solutions:
        by_hash.setdefault(_norm_hash(sol["canonicalHash"]), sol["verdict"]["twist"])
    return by_hash


def run():
    """Returns (n_agree, n_total, mismatches, cache). n_total is None (skip signal) when
    results/foldfindings.json is absent. `mismatches` entries are dicts with kind in
    {"not-enumerated", "verdict_disagree", "twist_undecided", "exception"}. `cache` maps each grid
    to "hit"/"miss" so a PASS can state whether it came from a fresh search or from disk."""
    by_grid, present = _load_ground_truth()
    if not present or not by_grid:
        return None, None, None, {}

    import runner as Runner  # noqa: E402  lazy: keeps this module import-safe/side-effect-light

    n_agree = 0
    n_total = 0
    mismatches = []
    cache = {}
    for grid, recs in sorted(by_grid.items()):
        m_str, n_str = grid.split("x")
        m, n = int(m_str), int(n_str)
        print("progress: searching grid %s (%d ground-truth records)..." % (grid, len(recs)),
              flush=True)
        _t0 = time.time()
        opts = _opts(m, n)
        try:
            engine_by_hash, hit = OC.get_or_compute(
                OC.fingerprint("square", _SQUARE_DIR, opts, extra_files=[os.path.abspath(__file__)]),
                lambda: _search_grid(Runner, m, n),
                meta={"engine": "square", "grid": grid, "opts": opts,
                      "recordsDigest": OC.records_digest(recs)})
        except Exception as exc:                       # one bad grid degrades to a mismatch...
            cache[grid] = "error"
            for r in recs:                             # ...rather than killing the whole proof
                n_total += 1
                mismatches.append({"grid": grid, "id": r.get("id"), "kind": "exception",
                                    "detail": "%s: %s" % (type(exc).__name__, exc)})
            print("progress: grid %s FAILED: %s: %s" % (grid, type(exc).__name__, exc), flush=True)
            continue
        cache[grid] = "hit" if hit else "miss"
        print("progress: grid %s search done in %.1fs (cache %s), %d gate-surviving candidates"
              % (grid, time.time() - _t0, cache[grid], len(engine_by_hash)), flush=True)
        for r in recs:
            n_total += 1
            key = _norm_hash(r["canonicalHash"])
            # Membership, NOT .get(): a present value may legitimately be None (twist undecided).
            # Conflating the two would misreport every not-enumerated record as twist_undecided.
            if key not in engine_by_hash:
                mismatches.append({"grid": grid, "id": r.get("id"), "kind": "not-enumerated",
                                    "detail": "ground-truth canonicalHash not found among the "
                                              "engine's gate-surviving candidates for this grid"})
                continue
            twist = engine_by_hash[key]
            if twist is None:
                mismatches.append({"grid": grid, "id": r.get("id"), "kind": "twist_undecided",
                                    "detail": "engine twist verdict is undecided for a matched "
                                              "candidate (expected decided for this ground truth)"})
                continue
            fresh = bool(twist is True)
            actual = bool(r["foldable"])
            if fresh == actual:
                n_agree += 1
            else:
                mismatches.append({"grid": grid, "id": r.get("id"), "kind": "verdict_disagree",
                                    "fresh": fresh, "actual": actual})
        print("progress: grid %s done, running total %d/%d agree (%d mismatches so far)"
              % (grid, n_agree, n_total, len(mismatches)), flush=True)

    return n_agree, n_total, mismatches, cache


if __name__ == "__main__":
    _json = "--json" in sys.argv[1:]
    n_agree, n_total, mismatches, cache = run()
    if _json:
        # Machine-readable form consumed by scripts/phystest (the physical-testing suite). Exit
        # code matches the human form: 0 on PASS or SKIP, 1 only on a real mismatch.
        print(json.dumps({"engine": "square", "skipped": n_total is None,
                          "nAgree": n_agree, "nTotal": n_total,
                          "mismatches": mismatches or [], "cache": cache}))
        sys.exit(1 if mismatches else 0)
    if n_total is None:
        print("square: SKIPPED (no ground-truth data present)")
        sys.exit(0)
    print("square: %d/%d agree (cache: %s) (mismatches: %s)"
          % (n_agree, n_total, cache or "-", mismatches))
    sys.exit(0 if not mismatches else 1)
