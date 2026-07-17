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

Two ways to drive the engines: the raw per-package CLIs below (`sq-generate` / `tri-generate`), or
the higher-level [`gui/`](gui/) front-ends — an interactive **draw-and-fold window** and a matching
**headless CLI** — that let you fold a hand-drawn sheet with example-vs-full search and result
filtering ([jump to that section](#draw-and-fold--the-gui-front-ends)).

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
  schematic_<uid>.png      folding schematic: footprint + base cells + foldpath
  twist_<uid>.png          twist-enumeration diagram (jump-strand for 2+1, pairwise loops for
                           1+1+1, turn-angle analysis for 2-stack)
  <uid>_analysis.json     triangle only: per-loop twist enumeration + seam/reflection verdict
                           (subsumes the retired reflect_ / overlay_ images)
```

Both tracks now emit the same standardised **two-image** bundle (schematic + twist); the triangle
track adds a small `<uid>_analysis.json` in place of its old reflection/overlay PNGs.

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

## Draw-and-fold — the `gui/` front-ends

Beyond the raw engine CLIs there is a small **tkinter app** that lets you *draw* a sheet on any tiling
and fold it, plus a **headless twin** that does the same from a script. Both drive the engines only
through the `scripts/fold_grid.py` orchestrator (subprocess-only — `gui/` imports no engine, keeping
the never-co-import invariant), so they fold and filter identically; one renders to a window, the
other to stdout.

`gui/` is **not** an installed console script — run it from the repo root:

```bash
python -m gui.app                 # the interactive window
python -m gui.app --out mydir     # bundles go to mydir/ (default: ./out)
python -m gui.app --help          # works with no display (argparse exits before Tk)
```

The GUI needs **Tk** — bundled with the python.org and Windows builds; on some Linux distros install
`python3-tk`.

### Using the window

1. **Pick a tiling** (`square`, `equilateral`, `righttri`, `scalene`, `hex`) and an `m×n` size, then
   **New grid** to lay down that ambient block to draw on. *New grid only draws an empty grid — it
   never loads a past result.*
2. **Draw the sheet.** Click a tile to toggle it; **drag to paint** several at once — a drag that
   starts on an empty tile *adds*, one that starts on a filled tile (or any right-drag) *erases*. The
   sheet must be **connected** before **Fold** lights up.
3. **Shape the search** (second row — narrower = faster): which **stacks** to try (2 / 3 — how many
   plate layers the sheet collapses into; 2-stack is the paper's Hamiltonian-circuit case, 3-stack
   adds the footprint decomposition + closure/twist gates), which **decomp** (2+1 / 1+1+1 — leave
   both checked to search both, check exactly one to restrict), and **find: all | example**.
4. **Fold.** Results fill the table on the right; **Cancel** kills a run in flight.
5. **Filter + view.** The filter bar narrows the rows live; click a row to preview its fold image
   (choose which image with the kind buttons, or read a "no image for this record" note).

### Single example vs. every fold

**find: all** enumerates *every* footprint × decomposition — the complete answer (all folds, exact
counts), but slow on big grids (the square engine can weigh 100k+ candidates). **find: example
(fast)** stops at the **first** foldable it finds and returns just that one:

- square 3-stack — the first twist-decided FOLD,
- square 2-stack — the first foldable Hamiltonian circuit (the circuit *enumeration* still runs in
  full — the RSPA engine's fixed cost — so `example` saves less here than for 3-stack / triangle),
- triangle — the first closing 1+1+1 fold.

Use **example** to answer *"does any fold exist?"* cheaply; use **all** when you need to enumerate or
count them. Restricting stacks/decomps speeds up *both* modes. Under the hood this is the engines'
`--first` flag, threaded GUI → `fold_grid.py` → each engine.

### Filtering

Filters act on the **computed** rows: the foldability vector can't be known without folding, so
filtering is always *post-search* — it narrows what is shown, it does not change what is computed (the
search-shaping row above does that). Filter by:

- **stacks** — 2 or 3;
- **decomp** — 2+1 or 1+1+1 (either engine's spelling is accepted — `2plus1` → `2+1`);
- **foldable** — keep only folds;
- **foldability vector** — per-gate pass/fail: **exit** footprint, **parity**, **reflection**,
  **twist**.

Triangle records carry a single verdict *string* (no structured per-gate vector), so any vector
filter drops them.

## Headless folding — `python -m gui.cli`

The same core with no window — for scripts and CI. It reads a drawn region and prints the filtered
verdict table:

```bash
python -m gui.cli --grid-file region.json                          # fold + full table
python -m gui.cli --grid-file region.json --first --only-foldable  # "any fold?" fast
python -m gui.cli --grid-file region.json --stacks 2,3 --decomp 2+1 --require reflection,twist
python -m gui.cli --grid-file region.json --json                   # machine-readable rows
```

The **region** is a `fold-grid/1` file — an arbitrary connected polyomino / tiling region, not just a
rectangle. Write one by hand:

```json
{
  "schema": "fold-grid/1",
  "tiling": "square",              // square | equilateral | righttri | scalene | hex
  "cells": [[0, 0], [1, 0], [0, 1]] // native tile ids: square => [x, y] integer pairs
}
```

…or just fold once in the GUI: it leaves the drawn region at `out/_grid.json`, itself a valid
`fold-grid/1`. (The full per-tiling id spec is in `docs/schema/fold-grid-1.md`, part of the
maintainer's local-only `docs/` tree — not present on a fresh clone.)

| flag                        | kind   | does                                                        |
|-----------------------------|--------|-------------------------------------------------------------|
| `--grid-file PATH`          | in     | the `fold-grid/1` region to fold (**required**)             |
| `--out DIR`                 | in     | bundle output root (default `./out`)                        |
| `--stacks 2,3`              | search | which square stack counts to search                          |
| `--decomps 2+1`             | search | restrict the square decompositions searched                  |
| `--first`                   | search | stop at the first foldable example (fast)                    |
| `--timeout SEC`             | search | per-engine wall-clock budget                                 |
| `--decomp 2+1,1+1+1`        | filter | show only these decompositions                               |
| `--require reflection,twist`| filter | show only rows PASSING these gates (`exit,parity,reflection,twist`) |
| `--only-foldable`           | filter | show only foldable rows                                      |
| `--json`                    | out    | emit the filtered rows as JSON instead of a table            |

Note the singular/plural split: `--decomps` (plural) *shapes the search*; `--decomp` (singular)
*filters the output*. Exit codes: **0** ok, **1** no bundle produced (a schema-valid region the
engine hard-failed on — a crash or internal error), **2** bad arguments or an unreadable /
wrong-schema grid file (a schema-bad grid is caught here, before any engine runs).

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
gui/             the draw-and-fold front-ends (run from repo root, NOT installed): `python -m gui.app`
                 (window) + `python -m gui.cli` (headless); subprocess-only, imports no engine
scripts/         run_tests.py (the gate) + fold_grid.py (the GUI's orchestrator) + validate*.py +
                 phystest/ (the acceptance oracle)
smoketest/       tracked pytest suite (packaging/import/CLI smoke only — incl. gui/ contract)
reference/       external source material (the paper + the authors' own reference implementation)
```

`docs/`, `report/`, `results/` are local-only (gitignored) research history: lab logs, generated
figures, and the physical-fold findings DB. They exist on the maintainer's machine but are not part
of the tracked tree — everything needed to run the suites is tracked.
