# Test suite — fidelity net for the 3-stack foldability engine

This suite (Session 0) pins the **current** Python engine's mathematical output so later refactors
(cleanup, the tile/lattice abstraction, the findings pipeline) cannot silently change a verdict.
Every result is compared 1:1 against committed golden baselines; a deviation is a failing test
unless it is a documented, justified improvement.

## Layout

| file | what it locks |
| --- | --- |
| `conftest.py` | puts `py/`, `py/tri/`, `explainer/`, `tests/` on `sys.path`; dir fixtures |
| `enginelib.py` | thin reusable wrappers over the engine (`run_3stack`, `run_2stack`, `closing_candidates`, `find_closing_by_hash`, `norm_hash`, `solution_digest`) |
| `gen_golden.py` | regenerates the golden baselines from the engine (`tests/golden/*.json`) |
| `gen_baseline_report.py` | writes `BASELINE_RESULTS.md` from golden + a live decider probe |
| `test_gates.py` | unit tests for the maths primitives (reflection, fold bounds, parity, exit-footprint, twist, canonical-hash invariances) — hand-derived, no golden |
| `test_golden.py` | re-runs the engine and asserts 3-stack / 2-stack / vet output matches golden 1:1 |
| `test_physical_deciders.py` | matches each paper-fold decider's canonical hash in the engine's closing set; engine verdict must equal the recorded physics |
| `test_parity_js.py` + `js_shim/run_engine.mjs` | runs `fold.js`+`search.js` under node, asserts JS↔Py solution sets are identical |
| `test_tri_reference.py` | locks the committed triangle-lattice result counts + invariants |

## Running

```bash
# fast tier (default) — units, parity, deciders, fast golden (~1 min incl. node)
.venv/Scripts/python -m pytest -m "not slow"

# everything, including heavy engine re-runs (6x6/6x7/9x4 nc=False, 6x5 nc=True, 8x6/12x4)
.venv/Scripts/python -m pytest

# just the cross-engine JS<->Py parity (needs node on PATH)
.venv/Scripts/python -m pytest -m parity
```

`slow` marks expensive re-runs (large K / non-corner explosion); `parity` marks node-dependent
cross-engine checks. Markers are registered in `../pytest.ini`.

## Performance toggles (multiprocessing + PyPy)

Two orthogonal, independently toggleable speed switches for the 3-stack engine. **Neither changes a
verdict** — output stays byte-identical to the serial CPython baseline (solutions incl. order + id,
and every integer ctx counter). `test_perf_toggles.py` locks this 1:1 across both toggles and every
combination, including a golden-under-load run of the whole suite with `FOLD_JOBS=8`.

| toggle | how | default |
| --- | --- | --- |
| multiprocessing | `--jobs N` (generate.py) or env `FOLD_JOBS=N` | 1 (serial) |
| PyPy | env `FOLD_PY=pypy` (`pypy`/`pypy3` on PATH, or `FOLD_PYPY_BIN=<path>`) | CPython |

```bash
python py/generate.py --m 6 --n 6 --jobs 8          # 8 worker processes
FOLD_JOBS=8 python py/generate.py --m 6 --n 6        # same, via env (opts['jobs'] wins if both set)
FOLD_PY=pypy python py/generate.py --m 6 --n 6       # run the engine under PyPy
FOLD_PY=pypy FOLD_JOBS=8 python py/generate.py ...   # both — they compose
```

`--jobs` fans the per-footprint enumeration across a `ProcessPoolExecutor`, then replays the D4
dedup + sequential-id assignment serially in the parent over the footprint-ordered candidate stream,
so the result is identical to serial. `jobs=1` (default) routes through the untouched serial path.
Workers are module-level (picklable under the Windows *spawn* start method); the entry point must use
the standard `if __name__ == "__main__":` guard (generate.py and `_engine_entry.py` do). PyPy runs
the engine in a subprocess via `runner.run_search` and marshals results back as JSON; `FOLD_JOBS`
still applies inside it, so a PyPy child fans across processes too.

**Measured speedup** (6x6 corner, 24-core box, PyPy 7.3.20; all outputs verified 1:1):

| config | time | vs CPython serial |
| --- | --- | --- |
| CPython serial (`jobs=1`) | 21.7 s | 1.0x |
| CPython `jobs=8` | 3.6 s | **6.0x** |
| PyPy serial | 7.4 s | **2.9x** |
| PyPy `jobs=8` | 1.7 s | **13.2x** |

`--jobs` speedup is bounded by the footprint count: corner-only grids (`allowNonCorner=False`) have
only **6 footprints**, so fan-out saturates near 6 workers; non-corner sweeps (148 footprints for
6x6) scale further. The two toggles are independent and compose (≈6x × ≈3x ≈ 13x).

```bash
# perf-toggle fidelity (fast subset; full set incl. 6x6/6x7 under -m slow)
.venv/Scripts/python -m pytest tests/test_perf_toggles.py
# whole golden suite under multiprocessing load
FOLD_JOBS=8 .venv/Scripts/python -m pytest -m slow
```

## Regenerating the baselines (only when an improvement is intentional)

```bash
python tests/gen_golden.py core      # 3-stack {6x4,6x5,6x6,6x7,9x4} nc=False + {6x4,6x5} nc=True,
                                      #   2-stack, vet {6x4,6x5,6x6,6x7}, decider probe
python tests/gen_golden.py heavy     # 8x6, 12x4 (nc=False, K=16) — slow, opt-in
python tests/gen_golden.py vetonly   # just the vet sets + decider probe
python tests/gen_baseline_report.py  # rewrite BASELINE_RESULTS.md
```

The committed-manifest counts (allowNonCorner=False) are the cross-check: 6x4→2, 6x5→3, 6x6→12,
6x7→33, 9x4→19, 8x6→310, 12x4→90. If a regenerated golden disagrees with these without a
documented reason, the engine drifted — investigate before committing.

## Known finding (for Session-3 engine-rules spec / adversarial review)

A canonical hash is a D4 **dedup key**, not a replayable fold path: `transform_arrow` is not
replay-equivariant with `apply_transform`, so replaying a canonical hash's `(base, arrows)` can
leave the grid (e.g. 6x6 decider #1 exits at the 2nd `U`). Dedup is still internally consistent
(JS and Py agree, counts match committed), but whether the D4 orbit is *geometrically* exact is
worth an adversarial check.
