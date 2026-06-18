# User Manual — 3-Stack Foldability

A complete, top-to-bottom guide to this repository: what it studies, how the pieces fit
together, and exactly how to drive every workflow — from a one-line search to the live,
taggable pattern database and the in-browser folding simulator.

This is the **orientation document**. Two companions go deeper where noted:

- [`COMMANDS.md`](COMMANDS.md) — the exhaustive command/flag/env reference.
- [`ENGINE_SPEC.md`](ENGINE_SPEC.md) — the Python-vs-JS engine, gate by gate.

Everything runs from the repo root (`3-stack-foldability/`). On this machine the interpreter is
the project venv: `.venv/Scripts/python.exe` (written as `python` below).

---

## 1. What this project is

The repo is a research toolkit for **3-stack kirigami foldability**: given a rectangular grid,
which cut-and-fold patterns can collapse a sheet into a 3-layer stack whose top and bottom
footprints match?

The core objects:

- **Footprint** — the starting region (an `L`- or `Rect`-triomino at some grid anchor and rotation).
- **Decomposition** — how the footprint splits into *chains* of cells: `2+1` (a 2-cell chain + a
  1-cell chain) or `1+1+1` (three single cells).
- **Folds** — each chain is reflected across creases, laying down `K = mn/3` successive mirrored
  copies. Direction vectors anchored on the footprint reflect through every fold.
- **Gates / verdicts** — geometric predicates that decide whether a candidate is *foldable*:
  arithmetic, exit-footprint, parity, vector-parity, reflection, and twist. See §6 for what each means.
- **Ground truth** — a real paper fold you performed. Recorded as a *physical finding*, it
  **outranks the engine**: when the engine predicts JAM but the paper folds (or vice-versa), that
  disagreement is surfaced as an engine-bug suspect.

The scientific aim is to use physical folding as ground truth to stress-test — and correct — the
math engine.

### The two engines

The solver exists twice, and they must agree:

- **Python (`py/`)** — the source of truth. Fast to iterate, caches results, runs the heavy searches.
- **Browser JS (`fold.js` / `search.js`)** — a cross-checked reference that powers the in-browser
  "Advanced search". Identical solution counts and canonical-hash sets to Python on 6×4 / 6×5 / 6×6.

There is exactly **one intended behavioural difference** (the arithmetic guard), documented in
[`ENGINE_SPEC.md`](ENGINE_SPEC.md). Any *other* divergence is a bug.

---

## 2. Mental model: prune vs. store-all

This is the single most important concept for using the data side of the repo.

The engine can run in two modes:

| Mode | What reaches storage | Use it for |
|------|----------------------|------------|
| **Gated** (default) | Only candidates that *survive every gate* (6×6 2+1 keeps ~40 of ~7960). Gates run during the DFS and **prune**. | The classic "here are the foldable patterns" result. |
| **Store-all** (`--store-all`) | **Every** D4-deduped covered candidate, with the gate verdicts attached as **non-destructive columns**. Nothing is pruned. | The "view everything, then filter/sort/tag" database. |

Store-all inverts the relationship: gates stop being filters and become **annotations**. You get
the whole covered space and decide what to look at — sort by any verdict, filter, tag, and compare
against physical ground truth. This is what feeds the SQLite database and the live viewer.

Legacy gated runs are byte-identical to before store-all existed; the new behaviour is fully behind
the `--store-all` flag.

---

## 3. Setup

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # pytest, jsonschema (+ numpy/matplotlib/pillow)
```

The search engine (`py/search.py`, `py/fold.py`) is pure-Python / numpy-free, so it also runs under
**PyPy** for a large speedup (see §8).

---

## 4. The end-to-end pipeline

```
  generate.py ──► results/<grid>_<hash>.json   (gated: foldable survivors)
       │
       └─ --store-all ─► results/<grid>_<hash>.json   (every covered candidate)
                         results/folddb.sqlite3        (the live read/write DB)
                                  │
                          serve.py (:8000)
                                  │
                    ┌─────────────┴─────────────┐
              browser viewer              physical findings
           (sort / filter / tag)        (paper-fold ground truth)
                                  │
                          v_compare: engine-vs-physical "agree" flag
```

A typical session:

```bash
# 1. Enumerate the full covered set for a grid into the DB
python py/generate.py --m 6 --n 6 --store-all

# 2. (first time only) seed the DB with any legacy JSON results + past findings
python py/migrate_to_sqlite.py

# 3. Serve the viewer + read/write API
python serve.py            # http://localhost:8000

# 4. In the browser: View mode → sort/filter/tag; record a paper fold → writes back live
```

---

## 5. Running a search — `py/generate.py`

Enumerates footprints → fold DFS → verdicts, and caches the result as JSON.

```bash
python py/generate.py --m 6 --n 6                 # 3-stack, 6x6 (uses cache if present)
python py/generate.py --m 6 --n 5 --decomps 2+1 --allow-non-corner
python py/generate.py --m 6 --n 6 --store-all     # Phase A: store EVERY covered candidate + write SQLite
python py/generate.py --m 6 --n 6 --force         # ignore cache, recompute
python py/generate.py --list                      # print the manifest of cached runs
python py/generate.py --stacks 2 --m 6 --n 5      # RSPA 2-stack (Hamiltonian circuits)
```

Most-used flags (full table in [`COMMANDS.md`](COMMANDS.md)):

| flag | meaning | default |
|------|---------|---------|
| `--m N` / `--n N` | grid columns / rows (required) | — |
| `--stacks {2,3}` | 2 = RSPA HC baseline; 3 = footprint/decomp | 3 |
| `--store-all` | store every covered candidate; gates become columns; **also writes `folddb.sqlite3`** | off |
| `--allow-non-corner` | include off-corner footprints (combinatorial blow-up) | off |
| `--decomps 2+1,1+1+1` | chain decompositions | both |
| `--jobs N` / `--force` / `--list` | parallelism / recompute / show manifest | 1 / off / — |

**Output:** `results/<m>x<n>[_2stack]_<hash>.json` + `results/manifest.json`. A matching cached run
is reused unless `--force`. Store-all uses its own params hash (different result set), so it gets its
own file/key and won't clobber the gated run.

> **2-stack mode** is the RSPA baseline (Yang–You–Rosen): it enumerates Hamiltonian circuits on the
> grid graph and applies the paper's two conditions (vector-reflection + zero-twist). HC enumeration
> is validated against OEIS (4×4 = 6, 6×6 = 1072).

---

## 6. The verdict columns (what each gate means)

In store-all mode every candidate carries these as non-destructive columns. Pipeline order (the order
a gated run would filter):

> arithmetic → footprint enum → decomposition → connectivity → parity → exit footprint → reflection
> → twist → D4 canonical hash

| column | meaning |
|--------|---------|
| `arithmetic` | the grid's cell count tiles into `K = mn/3` folds per chain (each chain lays down exactly `K` placements) |
| `exit_footprint` | the union of each chain's **last** placement is 3 distinct cells congruent to the start shape |
| `parity` | orientation-aware fold-count parity (axis from footprint geometry; `2+1` needs the cross-crease fold count even, `1+1+1` falls back to `nH` even ∧ `nV` odd) |
| `vector_parity` | the σ-checkerboard-per-placement check — a separate, vector-based parity column |
| `reflection` | for each adjacent chain pair, the shared crease projects to **coincident oriented grid segments** in the final placement |
| `twist` | loop-twist `Tw = 0` for every pair — **decided only for `1+1+1`**; `2+1` is undecided (`NULL`) |

A pattern is "engine-foldable" when the deciding gates all pass. The viewer's **Agree** column
compares that prediction to your recorded physical result. Full predicate-by-predicate detail (and
the Python-vs-JS comparison) is in [`ENGINE_SPEC.md`](ENGINE_SPEC.md).

---

## 7. The pattern database + API — `results/folddb.sqlite3`

Store-all data + physical findings + custom tags live in **one SQLite DB — the write-master**. The
JSON files are a one-way export / `file://` fallback. The DB is **gitignored and regenerable**
(`store.export_json` writes the diffable archival JSON). Override its path with the `FOLDDB_SQLITE`
env var.

```bash
python py/migrate_to_sqlite.py                 # one-shot, idempotent: seed from results/*.json + foldfindings.json
python py/generate.py --m 6 --n 6 --store-all  # backfill the full covered set for a grid (re-runnable)
```

**Schema** (one row per distinct pattern):

- `runs` — one per generated set (params key, lattice, region, grid, opts/counts).
- `patterns` — every covered candidate: `pattern_uid` (stable distinct-pattern id =
  `sha1(lattice|mxn|canonical_hash)[:12]`), `lattice` / `region` / `footprint_kind` (tiletype
  genericity — square now, triangle later), the verdict columns from §6, and a `detail_json` render
  blob (the exact `sol` shape the viewer renders, so the render path is unchanged).
- `tag` — EAV custom columns (add/remove a column with no migration), with `provenance`.
- `finding` — physical ground truth: `foldable`, `is_ground_truth`, and 3-tier `provenance`
  (`engine` | `handmath` | `physical`).
- `v_compare` — a VIEW joining engine prediction to physical result, exposing the `agree` flag.

`norm_hash` (the sorted-keys, compact-separator canonicalization of `canonicalHash`) is the
cross-table join key.

**Served by `python serve.py`** (same-origin `:8000`, stdlib only, no deps):

| route | purpose |
|-------|---------|
| `GET /api/runs` | list runs + pattern counts (drives the View grid dropdown) |
| `GET /api/patterns?run=&lattice=&sort=&dir=&filter=col:val&filter=tag:KEY:val&limit=&offset=` | paged / sorted / filtered patterns + per-row tags + `agree` |
| `POST /api/tag` | live single-tag upsert `{canonicalHash,key,value,provenance}` (value `null` = clear) |
| `POST /api/findings` | physical finding → validate → `foldfindings.json` + `LAB_LOG.md` + SQLite `finding` mirror |

> **Security:** `ORDER BY` / `WHERE` columns are restricted to a closed whitelist and all values are
> parameterized — a user-registered tag key can never become a SQL-injection vector.

If the DB is absent (or you opened the page on `file://`), the viewer falls back to the static
`manifest.json` read path and write-back is disabled (use download / CLI submit instead).

---

## 8. Performance toggles

Two orthogonal switches; **neither changes a verdict** (output is identical to serial). Locked by
`tests/test_perf_toggles.py`; measured speedups in [`../../tests/README.md`](../../tests/README.md).

```bash
python py/generate.py --m 6 --n 6 --jobs 8        # multiprocessing: 8 worker processes
FOLD_JOBS=8 python py/generate.py --m 6 --n 6      # same, via env (--jobs wins if both set)
FOLD_PY=pypy python py/generate.py --m 6 --n 6     # run the engine under PyPy
FOLD_PY=pypy FOLD_JOBS=8 python py/generate.py ... # both compose
```

- `--jobs` / `FOLD_JOBS` fans the per-footprint search across processes (speedup bounded by footprint
  count). Measured 6×6 jobs=8: **6.0×**.
- `FOLD_PY=pypy` runs the engine in a PyPy subprocess (`py/runner.py`). Needs `pypy`/`pypy3` on PATH,
  or set `FOLD_PYPY_BIN`. Measured 6×6: **2.9×** serial, **13.2×** with jobs=8.

---

## 9. The browser tool

```bash
python -m http.server 8000      # static viewer (GET only — no DB write-back, no capture)
python serve.py [8000]          # static viewer + read/write API + physical-finding capture
```

Open <http://localhost:8000>. It starts in **View results** mode. With `serve.py` + a populated
`folddb.sqlite3` it loads the **DB** (the grid dropdown lists `/api/runs`, auto-picking the largest =
store-all set, so you see everything); otherwise it auto-loads `results/manifest.json`. Pick another
grid from the dropdown, or use **Load results JSON** for any `results/*.json` file.

### View mode — browse, sort, filter, tag

- **Data-driven table:** click any header to **sort**; the **⚙ Columns** chooser shows/hides columns
  (including one per custom tag) and adds new tag columns (persisted in `localStorage`).
- **Agree column + GT badge:** surface engine-vs-physical (ground-truth) disagreements — bug suspects,
  highlighted red.
- **Live tagging:** in "Record physical finding", toggling **FOLD/JAM** or a tag **writes straight to
  the DB** (`/api/tag`, `/api/findings`) and patches just that row. Physical results are ground truth;
  pick **Provenance = hand-math / engine** to record a verdict *without* flagging it as ground truth.
- The findings filter row joins findings onto the loaded candidates and filters by **Actual**
  (FOLD/JAM/untested), **Predicted** (engine verdict), and each discovered tag key.

### Edit mode — the folding simulator

Toggle **Edit** in the topbar for the manual folding tools (Display options + Legend are shared
across both modes). Workflow:

1. **Set dimensions** (top bar): pick `m` (cols) and `n` (rows).
2. **Footprint** tool: click cells to mark the starting region (black outline).
3. **+ Group**: create a composite group (A, B, …); it becomes active.
4. **Group select**: click footprint cells to add/remove them from the active group.
5. **Vector (drag)**: drag inside an active-group cell → adds a compass-snapped direction vector.
6. **Fold (drag)**: drag a placement past its edge → it reflects, leaving a mirrored copy; chain to
   keep folding; drag back across a crease to unfold. `H` / `V` / `T` counters track folds per group.

Tools, per-grid buttons, and multi-grid details are in the [root `README.md`](../../README.md).

The in-browser JS engines (`fold.js`, `search.js`) live under **Advanced: in-browser search** in the
Results panel — a cross-checked reference, identical to Python on 6×4 / 6×5 / 6×6.

---

## 10. Physical findings (the user⇄engine capture loop)

Record a real paper-fold result for an enumerated candidate, keyed by its `canonicalHash`, into the
findings DB (`results/foldfindings.json`) + the SQLite `finding` table + a dated
`docs/research/LAB_LOG.md` entry. Three paths, one pure `submit()`:

```bash
# 1. In-browser: serve.py, load a candidate, open "Record physical finding", Submit.
python serve.py                                   # POST /api/findings -> validate -> DB + LAB_LOG + SQLite

# 2. Offline: the UI "Download JSON" button writes a finding file; submit it from the CLI.
python py/findings.py submit results/finding-6x5-1.json

# 3. Migrate legacy labels into the DB (lossless; already run once):
python py/findings.py migrate results/twoplus1_labels.json results/foldfindings.json
```

- `submit` **validates first** (JSON-schema via `jsonschema`); a malformed finding writes nothing.
- Records are keyed by the normalized `canonicalHash`, so re-submitting **overwrites** (never
  duplicates). The engine `predicted` block stored alongside is a **gate verdict** (FOLD/JAM + failing
  gates), never a fold index.
- **Provenance** (`physical` | `handmath` | `engine`) decides ground truth: only a *physical* fold
  sets `is_ground_truth = 1` and can outrank the engine in `v_compare`.
- **Custom tags:** a finding may carry a free-form `tags` map `{key: true|false}` (omit a key =
  untested) to record which candidate 2-chain decomposition idea holds.
- **Scratch capture:** set `FOLDFINDINGS_DB` / `FOLDFINDINGS_LABLOG` to redirect writes to throwaway
  files without touching the committed DB/log.

---

## 11. Triangle lattice (`py/tri/`)

Equilateral / right-triangle ports of the engine. The SQLite schema already carries `lattice` /
`region` / `footprint_kind` + a generic `detail_json`, so triangle patterns slot into the same
`patterns` table (`lattice='tri'`) with no migration — wiring `tri/` output into the DB is a planned
follow-on. Most scripts run a self-check or small enumeration with no args; committed tri ground truth
(`results/tri_*.json`) is locked by `tests/test_tri_reference.py`.

```bash
python py/tri/run_poc.py                # full triangle 3-stack proof-of-concept (figures + summary)
python py/tri/trisearch.py              # enumerate 1+1+1 / 2+1 on the 2x3 tri grid
python py/tri/prove_obstruction.py [Kmax]   # proof-by-exhaustion: no closing folds up to K (default 12)
```

Full script list in [`COMMANDS.md`](COMMANDS.md#triangle-lattice-pytri).

---

## 12. Tests & baselines

```bash
# fast tier (units, parity, deciders, fast golden) — ~1 min
.venv/Scripts/python.exe -m pytest -m "not slow"

# everything incl. heavy engine re-runs (6x6/6x7/9x4, 8x6/12x4) — ~15-20 min
.venv/Scripts/python.exe -m pytest

# cross-engine JS<->Py parity (needs node on PATH)
.venv/Scripts/python.exe -m pytest -m parity

# perf-toggle fidelity (multiprocessing + PyPy identity)
.venv/Scripts/python.exe -m pytest tests/test_perf_toggles.py
```

What the key suites lock:

- `test_golden.py` / `test_manifest_counts.py` — engine solution counts vs committed baselines
  (manifest counts are the independent cross-check; store-all entries are skipped there because they
  hold the *covered* set, not the gated count).
- `test_gates.py`, `test_lattice.py`, `test_physical_deciders.py` — the geometric predicates.
- `test_store_all.py`, `test_sqlite_store.py` — store-all behaviour + the SQLite layer (incl.
  no-dedup keeps every distinct candidate).
- `test_read_api.py`, `test_write_api.py` — `serve.py` routes (malformed params → 400 not 500;
  provenance gates ground truth; tag/finding write-back round-trips).
- `test_findings_*.py` — the findings schema, DB, LAB_LOG, matcher, migration.
- `test_perf_toggles.py` — multiprocessing + PyPy produce identical output (PyPy subtests skip if no
  PyPy on PATH).

Regenerate committed baselines **only when an improvement is intentional**:

```bash
python tests/gen_golden.py core        # core grids + 2-stack
python tests/gen_baseline_report.py    # rewrite tests/BASELINE_RESULTS.md
```

---

## 13. Repository map

```
3-stack-foldability/
├─ README.md                 # the folding simulator + backend quickstart
├─ index.html, style.css     # the browser UI
├─ app.js                    # results viewer + DB read/write + capture panel
├─ grid.js                   # grid rendering (GridView)
├─ fold.js, search.js        # the in-browser JS reference engine
├─ serve.py                  # static server + /api read/write routes
├─ py/                       # the Python engine (source of truth)
│  ├─ generate.py            #   CLI entry: search → cache JSON (+ SQLite under --store-all)
│  ├─ search.py, fold.py     #   footprint enum, fold DFS, gates, reflection verdict
│  ├─ twostack.py            #   RSPA 2-stack (Hamiltonian circuits)
│  ├─ store.py               #   SQLite layer (schema, upserts, export_json)
│  ├─ findings.py            #   physical-finding submit / migrate / schema
│  ├─ migrate_to_sqlite.py   #   one-shot idempotent DB seed
│  ├─ runner.py, _engine_entry.py   # PyPy subprocess plumbing
│  ├─ lattice/               #   Lattice ABC + SquareLattice + reflect primitive
│  └─ tri/                   #   triangle-lattice engine (equilateral / right / scalene)
├─ tests/                    # pytest suite + golden baselines + tests/README.md (perf)
├─ results/                  # generated JSON, manifest.json, folddb.sqlite3 (gitignored), findings
├─ docs/
│  ├─ guides/                #   USER_MANUAL.md (this file), COMMANDS.md, ENGINE_SPEC.md, FOLDING.md, HANDOFFS.md
│  └─ research/              #   LAB_LOG.md, findings notes, proofs, TODO
├─ deprecated/               # retired analysis/render tooling (not maintained)
└─ reference/                # external material (RSPA paper, kirigami MATLAB app)
```

---

## 14. Troubleshooting / FAQ

- **The viewer shows static JSON, not the DB.** You opened it on `file://`, or used
  `python -m http.server`, or `folddb.sqlite3` doesn't exist. Run `python serve.py` and generate a
  store-all set (`--store-all`) or seed with `migrate_to_sqlite.py`. Write-back (tagging) only works
  through `serve.py`.
- **`--store-all` gave a different file than my gated run.** Expected — it's a different result set
  (the full covered space), so it gets its own params hash and filename. The gated file is untouched.
- **Tagging in the browser doesn't persist.** Write-back needs `serve.py` (not `http.server`) and a
  present DB. On `file://` the radios fall back to download/CLI submit.
- **`test_perf_toggles.py` "hangs" under a sandbox.** It spawns subprocesses; that's a sandboxing
  artifact of the runner, not a code failure. The PyPy subtests skip cleanly when no PyPy is on PATH.
- **A physical result disagrees with the engine.** That's the point — it shows up as `agree = 0` (red
  row, **Agree** column). Physical is ground truth; the disagreement is an engine-bug suspect to
  investigate via [`ENGINE_SPEC.md`](ENGINE_SPEC.md).
- **I changed engine output and golden tests fail.** Only regenerate baselines if the change is an
  intended improvement (§12). Otherwise the failure is catching a regression.

---

## 15. Where to go next

| You want to… | Read |
|--------------|------|
| Every flag, env var, and output path | [`COMMANDS.md`](COMMANDS.md) |
| How a candidate is judged, gate by gate (Py vs JS) | [`ENGINE_SPEC.md`](ENGINE_SPEC.md) |
| The folding simulator UI in detail | [root `README.md`](../../README.md) |
| Measured perf numbers + baseline policy | [`../../tests/README.md`](../../tests/README.md) |
| The folding model / math notes | [`FOLDING.md`](FOLDING.md), [`../research/`](../research/) |
| Lab results + dated fold log | [`../research/LAB_LOG.md`](../research/LAB_LOG.md) |
