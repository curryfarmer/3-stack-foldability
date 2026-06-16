# Grid Folding Simulator

Browser tool for prototyping 2D origami-style folding on a square grid. Define a footprint, break it into composite groups, then drag groups across the grid to lay down their successive **mirrored copies** (folds). Direction vectors anchored on the footprint reflect through every fold automatically.

## Run

```bash
python -m http.server 8000      # from repo root (static viewer)
python serve.py                 # same viewer + in-page finding capture (POST /api/findings)
```

Open http://localhost:8000

## Python search backend (`py/`)

The heavy search (footprint enumeration + fold DFS + verdicts) is also available as a
Python CLI — faster to iterate on, and it caches results so you don't regenerate.

```bash
python py/generate.py --m 6 --n 6               # generate + cache
python py/generate.py --m 6 --n 5 --decomps 2+1 --allow-non-corner
python py/generate.py --m 6 --n 6 --force       # ignore cache
python py/generate.py --list                    # show what's cached
python py/generate.py --m 6 --n 6 --jobs 8      # multiprocessing (orthogonal: FOLD_PY=pypy)
```

**Full command reference** (searches, tests, triangle lattice, perf toggles):
see [`docs/guides/COMMANDS.md`](docs/guides/COMMANDS.md). Performance toggles (`--jobs`/`FOLD_JOBS`,
`FOLD_PY=pypy`) and their measured speedups are documented in [`tests/README.md`](tests/README.md).
Research notes and lab logs live in [`docs/research/`](docs/research/).

**Physical findings** (`py/findings.py` + `serve.py`): record a real paper-fold result for an
enumerated candidate, keyed by its `canonicalHash`, into the findings DB (`results/foldfindings.json`)
plus a dated `docs/research/LAB_LOG.md` entry. Capture in-browser with `python serve.py` (the
"Record physical finding" panel → Submit), or offline via `python py/findings.py submit <file>`. The
engine prediction stored alongside is a **gate verdict** (FOLD/JAM + failing gates), never a fold
index. Full usage in [`docs/guides/COMMANDS.md`](docs/guides/COMMANDS.md#physical-findings).

**2-stack mode** (RSPA baseline, Yang-You-Rosen): `generate.py --stacks 2 --m 6 --n 5`
enumerates Hamiltonian circuits on the grid graph and applies the paper's two conditions
(vector-reflection + zero-twist). Load the JSON in the browser's search panel ("Load results
JSON") to see each kirigami pattern — HC path, creases (red) / slits (gray) / cut edge
(green), with the foldable/twist verdict. (HC enumeration validated vs OEIS: 4×4=6, 6×6=1072.)

Results are written to `results/<m>x<n>[_2stack]_<hash>.json` with a `results/manifest.json` index.
A matching cached run is reused unless `--force`. The JSON matches the browser tool's own
export, so in the search panel use **Load results JSON** to visualise / browse a generated
file (loads onto the grid, drives the prev/next stepper, respects the Tw / shape / decomp
filters). The in-browser JS engine (`search.js`) is kept as a cross-checked reference —
both engines produce identical solutions on 6×4 / 6×5 / 6×6.

## Workflow

1. **Set dimensions** (top bar): pick `m` (cols) and `n` (rows).
2. **Footprint** tool: click cells to mark the starting region. They get a black outline.
3. **+ Group** (button on the grid card): create a composite group (A, B, …). It becomes the active group.
4. **Group select** tool: click footprint cells to add/remove them from the active group. Cells must lie inside the footprint.
5. **Vector** tool: click+drag inside one of the active group's cells. The arrow snaps to one of the four cell edges (creases) and points in one direction along that edge. Snap rule: dominant drag axis → top/bottom (if horizontal) or left/right (if vertical) edge; which side picked by start-position within the cell; direction = sign of drag along that axis.
6. **Fold (drag)** tool: click on any placement of a group, drag past an edge of the active placement → that placement reflects across the edge, leaving its image as a new placement. Drag further to chain folds. **Drag back across a crease** to *unfold* the last placement (counter decrements, placement removed). `H`, `V`, and `T = H + V` counters per group track horizontal, vertical, and total folds. Each fold lays down a small **orange chevron** at the crease, pointing in the fold direction. All vectors travel along.

## Tools

| Tool | Action |
|---|---|
| Pen | Paint cells with current color |
| Eraser | Clear paint + highlight on cell |
| Highlighter | Soft semi-transparent layer in current color |
| Footprint | Toggle cell membership in footprint |
| Group select | Toggle cell membership in active group's base |
| Fold (drag) | Drag a placement past its edge → folds reflect |
| Vector (drag) | Drag from inside an active-group cell → adds compass-snapped direction vector |

## Per-grid card buttons

- **+ Group** — make a new group on this grid
- **Reset folds** — drop all placements back to the originals
- **Clear vectors** — remove all vectors from all groups
- **Clear** — wipe everything on this grid (paint, footprint, groups)
- **×** — delete this grid

## Multi-grid

Press **+ Add Grid** in the top bar to add another grid below. Each grid keeps its own footprint, groups, vectors, and dimensions. The currently focused grid (blue border) is the one the top-bar `m` / `n` / `k` apply to.

## Notes

- Folds that would push cells off the grid are silently rejected.
- Editing dimensions trims any cells/footprint/group cells outside the new bounds and resets folds.
- No persistence yet — refreshing the page clears state. Undo/redo, save/load are obvious next adds.
