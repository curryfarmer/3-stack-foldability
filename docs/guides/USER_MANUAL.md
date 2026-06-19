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

- `runs` — one per generated set (params key, lattice, region, grid, opts/counts) + `label`, `notes`
  (hand-edit in any SQLite browser — survives re-runs), and `frozen` (1 = a preserved snapshot, see §7a).
- `patterns` — every covered candidate: `pattern_uid` (stable distinct-pattern id =
  `sha1(lattice|mxn|canonical_hash)[:12]`), `lattice` / `region` / `footprint_kind` (tiletype
  genericity — square now, triangle later), the verdict columns from §6, and a `detail_json` render
  blob (the exact `sol` shape the viewer renders, so the render path is unchanged).
- `tag` — EAV custom columns (add/remove a column with no migration), with `provenance`.
- `finding` — physical ground truth: `foldable`, `is_ground_truth`, and 3-tier `provenance`
  (`engine` | `handmath` | `physical`).
- `v_compare` — a VIEW joining engine prediction to physical result, exposing the `agree` flag.
- `patterns_grid` — a VIEW denormalizing the run's `m`/`n`/`label` onto each pattern row, so a
  DB-browser can filter by grid size directly (`patterns` itself only carries `run_id`).
- `model_compare` — a VIEW (long format, one row per pattern × twist hypothesis) putting each 2+1
  fold's engine prediction beside your physical observation with an `agree` flag (see §7d).

`norm_hash` (the sorted-keys, compact-separator canonicalization of `canonicalHash`) is the
cross-table join key.

**Served by `python serve.py`** (same-origin `:8000`, stdlib only, no deps):

| route | purpose |
|-------|---------|
| `GET /api/runs` | list runs + pattern counts (drives the View grid dropdown) |
| `GET /api/patterns?run=&lattice=&sort=&dir=&filter=col:val&filter=tag:KEY:val&limit=&offset=` | paged / sorted / filtered patterns + per-row tags + `agree` |
| `GET /api/compare?a=&b=` | engine-vs-engine diff of two runs by `pattern_uid` (verdict flips + only-in-A/B) |
| `POST /api/tag` | live single-tag upsert `{canonicalHash,key,value,provenance}` (value `null` = clear) |
| `POST /api/findings` | physical finding → validate → SQLite `finding` (**master**) + `LAB_LOG.md` + best-effort `foldfindings.json` export |

### 7a. Annotating runs + comparing engine versions

Tell runs apart and regression-test engine changes:

- **Annotate:** `--label "twist-fix v2"` / `--note "…"` on `generate`, or just open `folddb.sqlite3` in a
  SQLite browser and type into the `notes` column. Annotations survive a plain re-run of the same grid.
- **Compare old vs new engine:** generate a baseline, change the math, then re-run with
  `--snapshot "<label>"`. It freezes the old run (kept, `frozen=1`), writes the new run beside it, and
  prints which patterns' verdicts **flipped** (joined by the stable `pattern_uid`). Both runs stay
  browsable; the full diff is also `GET /api/compare?a=<old>&b=<new>`.

```bash
python py/generate.py --m 6 --n 6 --store-all                 # baseline
# … edit py/search.py / py/fold.py …
python py/generate.py --m 6 --n 6 --store-all --snapshot v1   # re-run + diff vs frozen "v1"
```

> **Security:** `ORDER BY` / `WHERE` columns are restricted to a closed whitelist and all values are
> parameterized — a user-registered tag key can never become a SQL-injection vector.

If the DB is absent (or you opened the page on `file://`), the viewer falls back to the static
`manifest.json` read path and write-back is disabled (use download / CLI submit instead).

### 7b. Database maintenance & manipulation

The SQLite DB is the **write-master** for everything (runs, patterns, tags, findings); the JSON files
are regenerable exports. This section is the full inventory of commands to inspect, edit, back up,
reset, and wipe it.

> **Close DB Browser for SQLite first.** If you have the `.sqlite3` file open in DB Browser (or any
> tool holding a write lock), `generate`/`serve`/`reset_db` will hit `database is locked`. Close it
> before any write. (A `PRAGMA busy_timeout=5000` rides out transient locks, not a held one.)
>
> **Back up before destructive ops** by copying the file: `cp results/folddb.sqlite3 results/folddb.bak.sqlite3`.

**Scratch / test DB** — rehearse destructive commands safely. Every CLI takes `--test` (→
`results/folddb.test.sqlite3`, gitignored) or `--db PATH`; `FOLDDB_SQLITE` overrides the default.

```bash
python py/generate.py --m 3 --n 2 --store-all --test   # populate the scratch DB (real DB untouched)
python serve.py --test                                  # serve the scratch DB
python py/reset_db.py --test --dry-run                  # rehearse a reset on the scratch DB
```

**Inspect** (read-only `sqlite3` shell, or any browser):

```bash
sqlite3 results/folddb.sqlite3 "SELECT (SELECT COUNT(*) FROM runs) runs, \
  (SELECT COUNT(*) FROM patterns) patterns, (SELECT COUNT(*) FROM tag) tags, \
  (SELECT COUNT(*) FROM finding) findings, \
  (SELECT COUNT(*) FROM finding WHERE is_ground_truth=1) ground_truth;"
sqlite3 results/folddb.sqlite3 "SELECT id,m,n,label,frozen,generated FROM runs ORDER BY id;"
sqlite3 results/folddb.sqlite3 "SELECT * FROM v_compare WHERE phys_foldable IS NOT NULL;"  # ground truths + agree flag
```

**Edit a run** label / note (annotations survive a plain re-run of the same grid):

```sql
UPDATE runs SET label='twist-fix v2', notes='re-derived seams' WHERE id=7;
```

**Tag CRUD** (EAV custom columns, no migration). Prefer `POST /api/tag` from the viewer for the
join-key bookkeeping, but raw SQL works (`norm_hash` = sorted-keys compact `canonicalHash`):

```sql
INSERT INTO tag(norm_hash,key,val_bool,provenance) VALUES('<norm_hash>','suspect',1,'handmath')
  ON CONFLICT(norm_hash,key) DO UPDATE SET val_bool=excluded.val_bool;   -- add / update
DELETE FROM tag WHERE norm_hash='<norm_hash>' AND key='suspect';         -- remove one
DELETE FROM tag WHERE key='suspect';                                     -- drop the whole column
```

**Delete a single run** (its patterns cascade via the FK; tags/findings are keyed by `norm_hash` and
are **not** touched):

```sql
PRAGMA foreign_keys=ON;                 -- sqlite3 shell defaults OFF; the app always sets it ON
DELETE FROM runs WHERE id=7;            -- patterns of run 7 vanish with it
```

**Reset to ground truth** (the physical-verification reset — clears all runs+patterns+tags and every
non-ground-truth finding, keeps `is_ground_truth=1`, then VACUUMs):

```bash
python py/reset_db.py --dry-run                  # preview before→after counts; writes nothing
python py/reset_db.py                            # do it (real DB) — keeps ground truths
python py/reset_db.py --export-findings          # dump findings → foldfindings.json first, then reset
python py/reset_db.py --all                      # also delete findings (fully empty DB)
```

| flag | effect |
| --- | --- |
| `--dry-run` | report the planned before→after per table; write nothing |
| (default) | keep `finding.is_ground_truth=1`; delete runs, patterns, tags, non-GT findings |
| `--all` | additionally delete all findings (empties the DB) |
| `--export-findings [PATH]` | dump findings → JSON (default `results/foldfindings.json`) before resetting |
| `--db PATH` / `--test` | target a specific / the scratch DB |

The raw SQL it runs (one transaction, then `VACUUM`):

```sql
DELETE FROM runs;                                       -- CASCADE clears patterns
DELETE FROM tag;
DELETE FROM finding WHERE COALESCE(is_ground_truth,0)!=1;  -- omit this line for --all (deletes all)
```

**Findings export / import** (DB ⇄ JSON — nothing is ever stranded):

```bash
python py/reset_db.py --export-findings results/foldfindings.json   # DB finding → JSON (regenerable export)
python py/migrate_to_sqlite.py                                       # JSON → DB (idempotent re-import)
```

**Export patterns as fold-pattern images** (the to-test batch — same sort/filter vocabulary as
`GET /api/patterns`). Renders one PNG per pattern into `--out` plus an `index.csv` cross-ref sheet:

```bash
python py/export_patterns.py --out batch_a --filter parity:true --sort reflection
python py/export_patterns.py --out batch_b --run 7 --filter twist:null --limit 50
python py/export_patterns.py --out batch_c --filter exit_footprint:true --filter is_ground_truth:null --test
python py/export_patterns.py --out batch_uid --uid 2c8aa1a11ccd --uid 5c205cb37ab0    # pull specific patterns
python py/export_patterns.py --out batch_uid --uids-file uids.txt                     # ... or one uid per line ('-' = stdin)
```

| flag | effect |
| --- | --- |
| `--out DIR` (required) | output folder (created if absent); images named `{m}x{n}_{pattern_uid}.png` |
| `--filter COL:VAL` | repeatable; `col:true\|false\|null\|<int>` or `tag:KEY:val` (whitelist == the API) |
| `--sort KEY` / `--dir asc\|desc` | sort key (`reflection`, `parity`, `twist`, `seq`, …) + direction |
| `--run ID` / `--lattice NAME` | restrict to one run / lattice |
| `--uid UID` / `--uids-file PATH` | export specific `pattern_uid`(s). `--uid` is repeatable and one value may be a pasted batch (split on space / comma / newline); `--uids-file` reads one uid per line (`-` = stdin). Unmatched uids are reported, never silently dropped. |
| `--limit N` | cap images; prints how many of the total were dropped (never silent) |
| `--dpi N` / `--format png\|pdf` | render resolution / file format |
| `--db PATH` / `--test` | read a specific / the scratch DB |

> Same uid can appear in more than one run (a baseline + a `--snapshot`), and under `--no-dedup` even
> twice in one run. When two rows would share a filename the later one gets an `_r{run}s{seq}` suffix
> so no image is silently overwritten.

`index.csv` carries `pattern_uid`, `canonical_hash`, `norm_hash`, `run_id`, every verdict column, and
`phys_foldable`/`is_ground_truth` — record the physical result against the `canonical_hash` row.

**VACUUM / WAL checkpoint** (after big deletes; `reset_db.py` VACUUMs for you):

```bash
sqlite3 results/folddb.sqlite3 "VACUUM;"                       # reclaim freed pages
sqlite3 results/folddb.sqlite3 "PRAGMA wal_checkpoint(TRUNCATE);"  # fold the -wal back into the main file
```

**The final JSON wipe** (one-time, on your call). Once ground truths are rebuilt in the DB, the
legacy JSON is redundant — the DB is the sole master. This deletes the per-grid result files, the
manifest, and the findings JSON; the DB and `tests/fixtures/` retain everything needed (tests read the
frozen fixtures, not live `results/`):

```bash
python py/reset_db.py --export-findings        # OPTIONAL last backup of findings → JSON before the wipe
rm results/*.json results/manifest.json results/foldfindings.json
```

After the wipe, regenerate any pattern set on demand with `generate.py --store-all`; findings live in
the DB and round-trip to JSON via `--export-findings` / `migrate_to_sqlite.py`.

### 7c. The reset cycle — the physical-verification start-over loop

§7b is the *inventory* of maintenance commands; this is the *workflow* that strings them together — the
loop you run to verify the engine against paper and to start clean between engine versions.

**The one principle:** in this DB exactly one thing is irreplaceable — **ground-truth findings** (a real
paper fold you performed, `finding.is_ground_truth=1`). *Everything else is regenerable:* runs and
patterns come back from `generate.py --store-all`; tags and engine/hand-math findings are derived. So the
reset cycle can throw away all the regenerable cruft and rebuild from a clean slate without ever losing a
folded result.

```
  generate.py --store-all ──► export_patterns.py ──► fold the paper, record findings
   (rebuild covered set)       (PNG to-test batch)     (provenance=physical → is_ground_truth=1)
            ▲                                                          │
            │                                                          ▼
            └──────────── reset_db.py  ◄───────────────────────────────┘
                 (keep ground truths; drop runs/patterns/tags/non-GT findings; VACUUM)
```

**Run the loop:**

```bash
# 1. Rebuild the covered set for a grid into the DB
python py/generate.py --m 6 --n 6 --store-all

# 2. Export the physical to-test batch (any sort/filter from the API vocabulary)
python py/export_patterns.py --out batch_a --filter twist:null --sort reflection
#    -> batch_a/{m}x{n}_{pattern_uid}.png + batch_a/index.csv  (the cross-ref sheet)

# 3. Fold the paper. Record each result against its candidate's canonicalHash
#    (serve.py "Record physical finding", or py/findings.py submit) with provenance=physical.
#    Only physical findings set is_ground_truth=1 and can outrank the engine.

# 4. Start over — wipe everything regenerable back to bare ground truth
python py/reset_db.py --dry-run          # ALWAYS preview first: before->after counts, writes nothing
python py/reset_db.py --export-findings   # back up findings -> JSON, then reset (keeps ground truths)

# 5. Go to 1 with a fresh engine / clean DB; the ground truths persist across the whole loop.
```

**When you reset:** a new engine version (regenerate patterns, re-check them against the same physical
ground truth — disagreements are bug suspects); the DB got cluttered with throwaway experiments; or you
want the empty-but-for-ground-truth baseline.

**The safety rails — use them in this order:**

| rail | command | what it buys you |
| --- | --- | --- |
| rehearse | `--test` (scratch DB at `results/folddb.test.sqlite3`) | run the whole destructive loop on a throwaway DB; the real one is untouched |
| preview | `reset_db.py --dry-run` | see the exact before→after per-table counts before anything is deleted |
| back up findings | `reset_db.py --export-findings [PATH]` | dump `finding` → JSON before the wipe (skipped under `--dry-run`) |
| back up the DB | `cp results/folddb.sqlite3 results/folddb.bak.sqlite3` | a full file copy — the surest undo |

> **`--all` empties the DB** — it deletes ground-truth findings too. That is *not* part of the normal
> cycle (which exists to preserve them); reach for it only to start from a genuinely empty DB.

**The terminal step (one-time, operator-only — do not run unprompted).** Once ground truths are rebuilt
in the DB and you no longer need the legacy JSON, the DB becomes the sole master and the per-grid result
files / manifest / findings JSON are redundant. That final wipe is documented at the end of §7b; tests
keep passing because they read the frozen `tests/fixtures/`, not live `results/`.

### 7d. 2+1 twist-model validation (preds vs actual)

The engine deliberately ships `twist = NULL` for `2+1` (§6) — several competing reductions *predict*
whether a 2+1 fold closes flat, and which is right is an open physical question. This layer lets you
**fold the paper and check each hypothesis against reality**, per pattern, without touching the
production engine.

- **The registry** — `py/twist_models.py` holds every hypothesis as one entry in `MODELS`
  (`modelA` partial-decomp, `modelB` jump-decomp, `modelC` no-decomp today). **Add a hypothesis** =
  add an entry; **change one** = edit its function. Each carries a source-hash version so a re-run
  after a change is detectable.
- **Two tag keys per model.** For each hypothesis the DB holds `<model>_pred` (what the engine
  computes, `provenance='engine'`) and `<model>_actual` (what *you* observed folding it). Distinct
  keys ⇒ no collision; both auto-render as viewer columns; adding a model needs zero schema/UI work.
  The `_pred` row also carries the raw twist in `val_int` and Model-A's class in `val_text`.
- **Backfill the predictions** — `py/compute_twist_models.py` recomputes every registered model on
  each stored 2+1 solution and upserts the `<model>_pred` tags. Idempotent + re-runnable.

```bash
python py/compute_twist_models.py            # gate-valid 2+1 across every run (the default scope)
python py/compute_twist_models.py --verbose  # also print each pattern's per-model tw/class
python py/compute_twist_models.py --all-2plus1   # every 2+1, not just the gate-valid subset
python py/compute_twist_models.py --prune    # drop <model>_pred rows for hypotheses you removed
python py/compute_twist_models.py --dry-run  # compute + report; write nothing
```

"Gate-valid" = a 2+1 fold whose every *decided* gate passes (arithmetic, exit-footprint, parity,
vector-parity, reflection) — so the twist is the only open question. That is the set worth folding.

- **Record your observation** in the browser: the capture panel seeds `modelA_actual` /
  `modelB_actual` / `modelC_actual` toggles by default — fold the paper, set each true/false.
- **Spot mismatches.** The viewer grows one **`A?`/`B?`/`C?`** agree column per hypothesis (✓ = engine
  model matches your fold, ✗ = it disagrees → that hypothesis is suspect, `—` = need both). Or in a
  SQL browser:

```sql
SELECT * FROM model_compare WHERE agree = 0;            -- engine-vs-reality mismatches, per model
SELECT model_key, eng_pass, eng_tw, eng_class, phys_pass FROM model_compare WHERE pattern_uid='…';
```

Once enough folds are recorded, the model whose `_pred` agrees with `_actual` most often is the
keeper — then prune the losers and fold the registry winner into the engine.

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
- **UID filter:** the **UID** box in the results bar narrows the table to one or more `pattern_uid`s —
  paste a batch (space / comma / newline separated) to pull exactly the candidates you care about. (DB
  mode only; `pattern_uid` rides on the served row.) Mirrors `export_patterns.py --uid`.
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
