# COMMANDS — how to run searches and everything else

Practical command reference for this repo. Run everything from the **repo root**
(`3-stack-foldability/`); the interpreter is the project venv:

```bash
.venv/Scripts/python.exe        # Windows (this machine)
# "python" below means that interpreter
```

> Keep this file current: when you add a command, flag, env var, or output path,
> update the relevant section here in the same change.

**Repo layout:** the live tree is the engine (`py/`, incl. the triangle lattice `py/tri/`), the
frontend (`index.html` + `*.js`), the test suite (`tests/`), ground-truth fixtures (`results/`),
and docs (`docs/guides/`, `docs/research/`). Retired analysis/render tooling lives under
`deprecated/` (not maintained); external reference material (the RSPA paper + the kirigami MATLAB
app) lives under `reference/`.

---

## Setup

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # pytest, jsonschema (+ numpy/matplotlib/pillow)
```

The **search engine** (`py/search.py`, `py/fold.py`) is pure-Python / numpy-free, so it also
runs under PyPy.

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
cached run is reused unless `--force`. The browser tool auto-loads these (see Browser tool below).

### Phase A: store EVERY covered pattern — `--store-all`

By default the engine **prunes**: gates (parity/reflection/twist) run during the DFS, so only
gate-survivors reach the JSON (6×6 2+1 keeps ~40 of ~7960 covered candidates). `--store-all` inverts
this: it stores **every** D4-deduped covered candidate, with the gate verdicts as **non-destructive
columns** (nothing is pruned). This is the "view everything, then filter" data set.

```bash
python py/generate.py --m 6 --n 6 --store-all          # all covered 6x6 patterns (gates = columns)
```

`--store-all` writes BOTH the JSON (`results/<grid>_<hash>.json`, its own params hash, for the
`file://` / static viewer) AND the **SQLite write-master** `results/folddb.sqlite3` (the live read/write
DB the served viewer uses). It's a different result set from the gated run, so it gets its own file/key.

---

## SQLite pattern DB + read/write API (`results/folddb.sqlite3`)

The store-all data + physical findings + custom tags live in one SQLite DB — the **write-master**;
the JSON files are a one-way export / `file://` fallback. The DB is **gitignored + regenerable**
(`store.export_json` writes the diffable archival JSON). Override the path with `FOLDDB_SQLITE`.

```bash
python py/migrate_to_sqlite.py                 # one-shot idempotent seed from results/*.json + foldfindings.json
python py/generate.py --m 6 --n 6 --store-all  # backfill the full covered set for a grid (re-runnable)
```

Schema (one row per distinct pattern): `runs` (one per generated set) → `patterns` (every covered
candidate: `pattern_uid` stable id, `lattice`/`region`/`footprint_kind` for tiletype-genericity,
the verdict columns `arithmetic/exit_footprint/parity/vector_parity/reflection/twist`, `detail_json`
render blob) + `tag` (EAV custom columns) + `finding` (physical ground truth, `is_ground_truth`,
3-tier `provenance` engine|handmath|physical) + `v_compare` (engine-vs-physical `agree` flag).
`norm_hash` (sorted-keys compact canonicalHash) is the cross-table join key.

`python serve.py` exposes it (same-origin :8000, no deps):

| route | purpose |
| --- | --- |
| `GET /api/runs` | list runs + pattern counts (drives the View grid dropdown) |
| `GET /api/patterns?run=&lattice=&sort=&dir=&filter=col:val&filter=tag:KEY:val&limit=&offset=` | paged/sorted/filtered patterns + per-row tags + `agree` (ORDER BY/WHERE whitelisted, values parameterized) |
| `POST /api/tag` | live single-tag upsert `{canonicalHash,key,value,provenance}` (value null = clear) |
| `POST /api/findings` | physical finding → validate → `foldfindings.json` + LAB_LOG + SQLite `finding` mirror |

If the DB is absent (or on `file://`), the viewer falls back to the static `manifest.json` read path
and write-back is disabled (download/CLI submit instead).

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

## Browser tool (results viewer + folding simulator)

```bash
python -m http.server 8000      # from repo root (static; GET only)
python serve.py [8000]          # same static frontend + POST /api/findings (capture, see below)
```

Open http://localhost:8000 . It starts in **View results** mode. With `serve.py` + a populated
`folddb.sqlite3` it loads the **DB** (the grid dropdown lists `/api/runs`, auto-picking the largest =
store-all set so you see EVERYTHING); otherwise it falls back to auto-loading `results/manifest.json`.
Pick another grid from the dropdown, or use **Load results JSON** for any `results/*.json` file. Toggle
**Edit** in the topbar for the manual folding tools; Display options + Legend are shared across both modes.

The results table is **data-driven**: click any header to sort; the **⚙ Columns** chooser shows/hides
columns (incl. one per custom tag) and adds new tag columns (persisted in `localStorage`). The **Agree**
column + **GT** badge surface engine-vs-physical (ground-truth) disagreements (bug suspects, red row).
In "Record physical finding", toggling FOLD/JAM or a tag **writes live to the DB** (`/api/tag`,
`/api/findings`) and patches the row — physical = ground truth; pick **Provenance** = hand-math/engine to
record without flagging ground truth. (Served via `http.server` or `file://`: write-back is disabled and
the static manifest read path is used; use **Load results JSON** there.)

The in-browser JS engines (`fold.js`, `search.js`) live under **Advanced: in-browser search** in the
Results panel — kept as a cross-checked reference (identical to Python on 6x4/6x5/6x6; the single
intended gate difference is documented in `docs/guides/ENGINE_SPEC.md`). Full UI/workflow docs:
`README.md` (repo root).

---

## Physical findings (the user⇄engine capture loop) — `py/findings.py` + `serve.py`

Record a real paper-fold result for an enumerated candidate, keyed by its `canonicalHash`, into the
findings DB (`results/foldfindings.json`) + a dated `docs/research/LAB_LOG.md` entry. Three paths,
one pure `submit()`:

```bash
# 1. In-browser: serve.py, load a candidate, open "Record physical finding", Submit.
python serve.py                                   # POST /api/findings -> validate -> DB + LAB_LOG
# 2. Offline: the UI "Download JSON" button writes a finding file; submit it from the CLI.
python py/findings.py submit results/finding-6x5-1.json
# 3. Migrate the legacy labels into the DB (lossless; already run once):
python py/findings.py migrate results/twoplus1_labels.json results/foldfindings.json
```

- `submit` **validates first** (JSON-schema, `jsonschema`); a malformed finding writes nothing. The
  record is keyed by the normalized `canonicalHash`, so re-submitting overwrites (never duplicates),
  and the engine `predicted` block (gate verdict — FOLD/JAM + failing gates, never a fold index) is
  filled by enumerating closing candidates (slow on big grids like 6x7).
- **Scratch capture:** set `FOLDFINDINGS_DB` / `FOLDFINDINGS_LABLOG` to redirect writes to throwaway
  files (e.g. experiments) without touching the committed DB/log.
- **Custom tags:** a finding may carry a free-form `tags` map `{<key>: true|false}` (tri-state: omit a
  key = untested) to record which candidate 2-chain decomposition idea holds. In the View UI, set the
  tag keys once in "Record physical finding" (persisted in `localStorage`); each finding then shows a
  true/false/untested toggle per key. The findings filter row (under the result nav) joins findings
  onto the loaded candidates and filters by **Actual** (FOLD/JAM/untested), **Predicted** (engine
  verdict: parity∧reflection∧twist≠false), and each discovered tag key; the table gains a **Fold**
  column showing the recorded result.
- The matcher equivalence (engine verdict == recorded physics for the deciders) is locked by
  `tests/test_physical_deciders.py` + `tests/test_findings_matcher.py`.

---

## Triangle lattice (`py/tri/`)

Equilateral / right-triangle ports of the engine. Most run a self-check or small enumeration with
no args. Committed tri ground truth (`results/tri_*.json`) is locked by `tests/test_tri_reference.py`.

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
