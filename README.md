# fold3stack

Two independent, code-only Python engines that search for and verify **3-stack folds**
(compact-stack tessellated-plate folding, after Yang–You–Rosen, see [`reference/`](reference/)):

- **`square/`** — folds on a square grid: footprint + 2-chain/1-chain (or 1+1+1) decomposition,
  reflection-closure + twist gates. Also supports the paper's original 2-stack (Hamiltonian-circuit)
  mode.
- **`triangle/`** — folds on non-square tilings: equilateral, 45-45-90 right-isosceles, 30-60-90
  scalene, and regular hexagon. Same closure/twist idea, ported to each tiling's own geometry.

The two packages are **fully independent** — no cross-imports. Each has its own `lattice`
subpackage, its own `_bootstrap.py`, and its own pair of CLIs. They happen to both use a bare
module name `lattice` internally, so **never import both packages in the same Python process** —
run them in separate processes (every script in this repo already does this).

## Install

```bash
python -m venv .venv
.venv/Scripts/pip install -e .          # editable install; add [test] for pytest
```

This installs four console scripts:

| command        | package  | does                                                        |
|-----------------|----------|--------------------------------------------------------------|
| `sq-generate`   | square   | search for folds on an `m×n` grid, write `out/<uid>/` bundles |
| `sq-render`     | square   | re-render an existing `out/<uid>/<uid>.json` record           |
| `tri-generate`  | triangle | search one tiling/decomposition/K for a closing fold          |
| `tri-render`    | triangle | re-render an existing triangle record                          |

## Output format

Both engines write the same on-disk contract: one self-contained folder per fold, named after a
12-hex content hash (`uid`, `sha1(lattice \| MxN \| canonical-geometry)`):

```
out/<uid>/
  <uid>.json              full record: chains, footprint, verdict, geometry
  foldsheet_<uid>.png      printable foldsheet
  twist_<uid>.png          twist-enumeration diagram (when the record is a 2+1/1+1+1 case)
  overlay_<uid>.png        triangle only: chain overlay
  reflect_<uid>.png        triangle only: vector-reflection diagram (skipped for equilateral
                           1+1+1 — that case has no chain-footprint geometry to reflect)
```

`*-render` re-derives the same image bundle from a saved `.json` with zero search — regenerating
a record and re-rendering it are the same code path, so the two are always byte-consistent.

## Examples

```bash
sq-generate --m 6 --n 6                            # 3-stack, both decomps, corner footprints
sq-generate --m 6 --n 5 --decomps 2+1 --allow-non-corner
sq-generate --stacks 2 --m 6 --n 5                 # RSPA 2-stack (Hamiltonian circuits)
sq-generate --stacks 4 --m 4 --n 8                 # n-stack: all-singleton 1+1+1+1
sq-generate --list                                  # summarize out/'s bundles
sq-render out/<uid>/<uid>.json --out somewhere/

tri-generate --tiling righttri --decomp 1plus1plus1 --K 16
tri-generate --tiling scalene --decomp 2plus1 --K 4
tri-render out/<uid>/<uid>.json
```

## Validating against physical ground truth

The engines make falsifiable claims about paper: every fold on record was physically folded by hand,
and the engine's verdict must still match that outcome. Both tools below **re-derive** a fresh
verdict by re-running the search — never by re-reading a stored boolean — and need the gitignored
local research data (`results/`), skipping gracefully per engine when it is absent (a fresh clone):

```bash
python scripts/validate.py       # both engines' regression proofs
python scripts/phystest check    # the acceptance oracle (see the caveat below)
```

Neither imports both engines in one process; both subprocess-dispatch the per-engine checkers.

**`phystest check` is expensive and its result is not a simple pass/fail.** It re-enumerates every
recorded grid from scratch, which is hours on the big ones (6x8 alone measured 2.6h), so results are
cached per `(engine-source fingerprint, grid)` under `results/.oracle_cache/` — edit anything under
`square/{engine,lattice,twist}` and every square entry is invalidated by design. It distinguishes
`FAIL` (a record genuinely disagrees — a real regression) from `ERROR` (the harness timed out or
broke, so **nothing was proven either way**); conflating those two is what made an earlier version of
this oracle untrustworthy. Note its 4h default timeout is smaller than a fully-cold square run, so
from a cold cache it takes **two invocations** — the per-grid cache survives a kill, so just re-run.

## Tests

```bash
python scripts/run_tests.py     # the gate: all three suites, each in its own interpreter
pytest                          # smoketest/ only (what a bare pytest is configured to run)
```

There are three tracked suites, and they can **never share an interpreter** — `square/` and
`triangle/` each put their own bare-named `lattice` on `sys.path`, so collecting both in one process
races whichever `_bootstrap` ran second. `run_tests.py` dispatches each separately:

| suite            | covers                                                        |
|------------------|---------------------------------------------------------------|
| `smoketest/`     | packaging / import / CLI smoke — offline, ground-truth-free     |
| `square/tests/`  | the square engine: gates, goldens, canonical hashing, n-stack   |
| `triangle/tests/`| the triangle engine: per-tiling geometry, closure, fold validity |

Expensive engine sweeps are marked `slow` and **deselected by default** (`pytest.ini`'s
`addopts = -m "not slow"`). Run them with `pytest -m slow`; some honour `FOLD_JOBS=N` to parallelize.

Passing tests are not the same as agreeing with reality — for that, see below.

## Repository layout

```
triangle/        installable package: the non-square-tiling engine + tri-render/tri-generate
square/          installable package: the square-grid engine + sq-render/sq-generate
  tests/         the square suite (golden baselines + fixtures live here, tracked)
scripts/         run_tests.py (the gate) + validate*.py + phystest/ (the acceptance oracle)
smoketest/       tracked pytest suite (packaging/import/CLI smoke only)
reference/       external source material (the paper + the authors' own reference implementation)
```

`docs/`, `report/`, `results/` are local-only (gitignored) research history: lab logs, generated
figures, and the physical-fold findings DB. They exist on the maintainer's machine but are not part
of the tracked tree — everything needed to run the suites is tracked.
