# COMMANDS — how to run searches and everything else

Practical command reference for this repo. Run everything from the **repo root**
(`3-stack-foldability/`); the interpreter is the project venv:

```bash
.venv/Scripts/python.exe        # Windows (this machine)
# "python" below means that interpreter
```

> Keep this file current: when you add a command, flag, env var, or output path,
> update the relevant section here in the same change.

---

## Setup

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # numpy, matplotlib, pillow, pytest, jsonschema
```

The **search engine** (`py/search.py`, `py/fold.py`) is pure-Python / numpy-free, so it also
runs under PyPy. numpy/matplotlib/pillow are only for the rendering scripts.

---

## Run a search (the main thing) — `py/generate.py`

Enumerates footprints → fold DFS → verdicts, and caches the result as JSON.

```bash
python py/generate.py --m 6 --n 6                 # 3-stack search, 6x6 (uses cache if present)
python py/generate.py --m 6 --n 5 --decomps 2+1 --allow-non-corner
python py/generate.py --m 6 --n 6 --force         # ignore cache, recompute
python py/generate.py --list                      # print the manifest of cached runs
python py/generate.py --stacks 2 --m 6 --n 5      # RSPA 2-stack (Hamiltonian circuits)
```

| flag | meaning | default |
| --- | --- | --- |
| `--m N` / `--n N` | grid columns / rows (required) | — |
| `--stacks {2,3}` | 2 = RSPA HC baseline; 3 = footprint/decomp | 3 |
| `--shapes L,Rect` | footprint shapes (3-stack) | `L,Rect` |
| `--decomps 2+1,1+1+1` | chain decompositions | `2+1,1+1+1` |
| `--allow-non-corner` | include off-corner footprints (combinatorial blow-up) | off |
| `--no-dedup` | disable D4 dedup | dedup on |
| `--jobs N` | parallel worker processes (see below) | 1 |
| `--force` | recompute even if cached | off |
| `--list` | print manifest and exit | — |

**Output:** `results/<m>x<n>[_2stack]_<hash>.json` + `results/manifest.json` index. A matching
cached run is reused unless `--force`. Load the JSON in the browser tool's search panel to view.

### Performance toggles (multiprocessing + PyPy)

Two orthogonal switches; **neither changes a verdict** (output identical to serial). Locked by
`tests/test_perf_toggles.py`. Full detail + measured speedups in `tests/README.md`.

```bash
python py/generate.py --m 6 --n 6 --jobs 8           # 8 worker processes
FOLD_JOBS=8 python py/generate.py --m 6 --n 6         # same, via env (--jobs wins if both set)
FOLD_PY=pypy python py/generate.py --m 6 --n 6        # run engine under PyPy
FOLD_PY=pypy FOLD_JOBS=8 python py/generate.py ...    # both — they compose
```

- `--jobs`/`FOLD_JOBS`: fans the per-footprint search across processes. `jobs=1` (default) = serial.
  Speedup is bounded by footprint count — corner grids have only 6 footprints (~6x ceiling);
  non-corner grids scale further. Measured 6x6: jobs=8 **6.0x**.
- `FOLD_PY=pypy`: runs the engine in a PyPy subprocess via `py/runner.py`. Needs `pypy`/`pypy3` on
  PATH, or set `FOLD_PYPY_BIN=<full path to pypy.exe>`. Measured 6x6: **2.9x** serial, **13.2x** with
  jobs=8. (PyPy installed here via `winget install PyPy.PyPy.3.11`.)

---

## Tests & baselines

```bash
# fast tier (units, parity, deciders, fast golden) — ~1 min
.venv/Scripts/python.exe -m pytest -m "not slow"

# everything incl. heavy engine re-runs (6x6/6x7/9x4, 8x6/12x4) — ~15-20 min
.venv/Scripts/python.exe -m pytest

# cross-engine JS<->Py parity (needs node on PATH)
.venv/Scripts/python.exe -m pytest -m parity

# perf-toggle fidelity (multiprocessing + PyPy identity); add -m slow for 6x6/6x7
.venv/Scripts/python.exe -m pytest tests/test_perf_toggles.py

# whole golden suite under multiprocessing load
FOLD_JOBS=8 .venv/Scripts/python.exe -m pytest -m slow
```

Regenerate committed baselines **only when an improvement is intentional** (then they become the
new lock — see `tests/README.md`):

```bash
python tests/gen_golden.py core        # {6x4,6x5,6x6,6x7,9x4} nc=False + {6x4,6x5} nc=True, 2-stack, vet
python tests/gen_golden.py heavy       # 8x6, 12x4 (slow)
python tests/gen_baseline_report.py    # rewrite tests/BASELINE_RESULTS.md
```

---

## Browser tool (interactive folding simulator)

```bash
python -m http.server 8000      # from repo root
```

Open http://localhost:8000 . The JS engines (`fold.js`, `search.js`) are kept as a cross-checked
reference (identical to Python on 6x4/6x5/6x6). Use **Load results JSON** in the search panel to
visualise a `results/*.json` file. Full UI/workflow docs: `README.md`.

---

## Analysis (post-process the results cache)

These read `results/*.json` (or take explicit files) and print to stdout. Most take **no args**
(default = all cached 3-stack results) — not argparse-driven.

```bash
python py/sweep_minsize.py [max_dim] [max_area]   # L vs Rect counts across grids (default 12, 60)
python py/vet_enumerate.py count                  # all closing FOLD/JAM candidate counts
python py/vet_enumerate.py 6x4 6x5                # ...and render their fold-sheets
python py/analyze_twist.py                        # validate stored twist verdicts vs recompute
python py/analyze_2plus1_reduction.py             # validate 2+1 strand-reduction hypothesis
python py/analyze_loop_seams.py                   # validate 1+1+1 pairwise-loop seams
python py/analyze_wrap.py                         # Q2 perimeter-wrap hypothesis (L solutions)
python py/analyze_reflection.py                   # Q4 parity-vs-reflection contingency
python py/foldpattern.py --self-check             # validate crease/slit partition on all cached
python py/foldpattern.py results/<file>.json <id> # print one solution's cut/fold recipe
```

---

## Rendering (matplotlib — figures and make-sheets)

Output lands in `report/` (mostly `report/foldsheets/`).

```bash
python py/make_foldsheets.py                      # printable crease/slit sheets (curated 2+1 set) -> PDF
python py/render_foldpath.py [all]                # fold-PATH sheets (numbered spine) -> PNG
python py/render_valid.py 6x4 6x5                 # path sheets for all predicted-FOLD patterns of a grid
python py/render_vectors.py labels                # vector-reflection cascade sheets
python py/render_theta.py                         # 1+1+1 theta-graph schematic -> report/theta_111.*
python py/render_reduction.py results/<f>.json <id> [out.png]   # 2+1 strand reduction on holey grid
```

---

## Triangle lattice (`py/tri/`)

Equilateral / right-triangle ports of the engine. Most run a self-check or small enumeration with
no args.

```bash
python py/tri/run_poc.py                # full triangle 3-stack proof-of-concept (figures + summary)
python py/tri/trisearch.py              # brute-force enumerate 1+1+1 / 2+1 on the 2x3 tri grid
python py/tri/prove_obstruction.py [Kmax]   # proof-by-exhaustion: no closing folds up to K (default 12)
python py/tri/hunt_tw0.py <K>           # hunt Tw=0 closing 1+1+1 folds at even K -> report/tri/
python py/tri/hunt_foldable.py <K> [budget]   # hunt hole-free foldable folds -> report/tri/
python py/tri/trilattice.py             # } self-checks for the lattice / fold / twist primitives
python py/tri/trifold.py                # }
python py/tri/tritwist.py               # }
python py/tri/righttri.py               # 45-45-90 tetrakis tiling self-check
python py/tri/scalene.py                # 30-60-90 kisrhombille tiling self-check
```

---

## Explainer diagrams (`explainer/`)

```bash
python explainer/gen.py                 # twist-theory schematic set -> explainer/svg/
python explainer/teach_twist.py         # per-corner twist ledger on real HCs -> stdout + svg
```
