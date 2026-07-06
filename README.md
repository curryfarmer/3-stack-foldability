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
sq-generate --list                                  # summarize out/'s bundles
sq-render out/<uid>/<uid>.json --out somewhere/

tri-generate --tiling righttri --decomp 1plus1plus1 --K 16
tri-generate --tiling scalene --decomp 2plus1 --K 4
tri-render out/<uid>/<uid>.json
```

## Validating against physical ground truth

`scripts/validate.py` re-derives a fresh verdict for every physically-tested fold on record (not
just re-reading a stored boolean) and checks it still agrees with what was physically folded.
Requires the gitignored local research data (`docs/`, `report/`, `results/`) — skips gracefully
per engine if that data isn't present (e.g. a fresh clone):

```bash
python scripts/validate.py
```

It never imports both engines in one process — it subprocess-dispatches
`scripts/validate_triangle.py` and `scripts/validate_square.py` independently.

## Tests

```bash
pytest
```

Runs `smoketest/` — fast, offline, ground-truth-independent packaging/import/CLI smoke tests
(not a replacement for `scripts/validate.py`, which is the real regression proof).

## Repository layout

```
triangle/        installable package: the non-square-tiling engine + tri-render/tri-generate
square/          installable package: the square-grid engine + sq-render/sq-generate
scripts/         validate.py + validate_triangle.py + validate_square.py
smoketest/       tracked pytest suite (packaging/import/CLI smoke only)
reference/       external source material (the paper + the authors' own reference implementation)
```

`docs/`, `report/`, `results/`, `deprecated/` are local-only (gitignored) research history: lab
logs, generated figures, the physical-fold findings DB, and archived exploratory code. They exist
on the maintainer's machine but are not part of the tracked tree.
