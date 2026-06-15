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
