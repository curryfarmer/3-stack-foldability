# Grid-Ingest Foldability Engine + Desktop GUI + Cleanup — 11 Session Handoffs

> ## TODO: fuse back to `main`
>
> This work lives on the **`grid-ingest`** branch, cut from `main` at `5a00df9`. All 11 sessions land
> here; `main` is not touched until the effort is done.
>
> **Merge back when:** S11's gate passes — i.e. the full standing gate (`scripts/run_tests.py` +
> `scripts/phystest check`, zero orphans) is green after a clean `pip install -e .[test]`.
>
> **Before merging, check for drift on `main`.** Sibling branches exist (`clean-package`, `revamp`,
> `feat/nonsquare-census`, several `wt/*`); if any of them lands on `main` first, re-verify the
> `file:line` seams cited throughout this document — they were captured against `5a00df9`.
>
> Merging earlier than S11 is fine **only** at a session boundary with that session's gate green. Never
> merge mid-session: gates are cumulative and a half-applied session leaves `main` without a proof.

> **How to use this document.** It is the execution plan for a multi-session effort, written so each
> session can be picked up cold. Read the **Context**, **Repo invariants**, and **Pre-flight** sections
> once, then jump to the session you are running — each handoff (S1–S11) is self-contained and states its
> own goal, verified `file:line` seams, changes, tests, gate, and known traps.
>
> **Sessions run in order.** Gates are cumulative: a session is not done until its own gate *and* every
> prior gate pass. Do not skip ahead — S3 is blocked on a fact only S1 can report, and S4/S5 build on the
> constructor and CLI work below them.
>
> Line references were verified against the tree as of 2026-07-15. Re-check any that look stale before
> relying on them; the **Corrections** pattern in each session shows what drift looks like.

## Context

The engine is **parameterized**: `sq-generate --m 6 --n 6 --stacks 3 --decomps 2+1` materializes a full
m×n rectangle, enumerates footprints/decompositions/folds, writes `out/<uid>/` bundles. The goal is to
flip it: the user **dictates an exact grid** (an arbitrary connected set of a tiling's base cells) and the
engine **dictates the decomposition** — enumerating every way to fold that sheet into 2-stack, 3-stack,
n-stack. Delivered through a pure-Python desktop **grid GUI**. Alongside: make n-stack first-class (today
it works only through an untracked scratch script), standardize the renderers, and do thorough
housekeeping.

**Why 11 sessions.** The requirement is that each session is thoroughly tested before the next begins.
Reconnaissance found that impossible under the original Engine→GUI→Cleaning ordering:

| Verified finding | Consequence |
|---|---|
| `tests/` is **gitignored** (`.gitignore:31`); 25 test files + 17 goldens + fixtures are local-only. The only tracked test is `smoketest/test_packaging.py`. | Almost no regression gate exists to be thorough *with*. |
| `tests/conftest.py` inserts `ROOT/py`, deleted in the `py/ → square/+triangle/` rename. | The tree is **uncollectable** — those 25 files aren't passing, they don't run. |
| The acceptance oracle takes **132 min**, exits 1 on a **timeout** (not a disagreement), orphans ~50 workers. | The one gate proving the gates are correct is unusable and untrustworthy. |

So the test rewire and oracle repair — Pillar 3, *last*, in the original plan — become **S1 and S2**.
Everything else is gated on them.

Outcome unchanged: **draw any grid → get every foldable decomposition + printable foldsheets, across
square and all four triangle tilings**, on a clean, tested, documented codebase.

## Locked decisions

1. **Ingest** = arbitrary **connected** set of a tiling's base cells. The *sheet* becomes arbitrary; the
   *footprint* stays the existing canonical templates this pass.
2. **Tilings** = square + all 4 triangle tilings (equilateral, righttri, scalene, hex).
3. **n-stack** = **all-singleton** (`1+1+…+1`) for any n; square only.
4. **Engines stay separate, orchestrated.** Square and triangle are **never** imported in one process —
   each ships a bare-named `lattice` and co-import races `sys.path`. Subprocess-dispatch always.
5. **Verdict semantics = exploratory** — enumerate, gate, report with an explicit `gateValidityUnproven`
   flag. Physical folding stays the only ground truth.
6. **GUI** = pure-Python desktop (tkinter shell + embedded matplotlib canvas), full round-trip.
7. **Renderers** = per-track shared style + a cross-track written spec; no cross-package import.
8. **Housekeeping** = aggressive.
9. **Sequence** = Engine → GUI → Cleaning, **behind a test-infra prologue**.
10. **Oracle gate = fingerprint cache** — full 61-record proof every session, re-searching only grids whose
    engine inputs changed.
11. **canonical_hash fix ships with a ground-truth migration**, own session, provable before/after.
12. **Test corpus becomes tracked** — suites + the 16 golden baselines.
13. **Plan lives at `docs/SESSIONS.md`**, tracked via a `.gitignore` negation.

## Repo invariants (true for every session)

- **Never co-import `square` and `triangle` in one interpreter.** Both put a bare `lattice` on `sys.path`.
  Cross-engine work is always `subprocess.run([sys.executable, script, ...])`. Reference implementation:
  `scripts/validate.py:23-37`.
- **Windows orphan trap.** `subprocess.run(capture_output=True, timeout=…)` does **not** bound wall clock
  when the child spawns a `ProcessPoolExecutor`: `kill()` reaps only the direct child, the grandchildren
  inherited the stdout pipe write handles, and the post-kill `communicate()` blocks until they exit
  naturally. **Always file-redirect (`stdout=f, stderr=STDOUT`), never `PIPE`**, and reap with
  `taskkill /F /T /PID`. The correct pattern already exists, verbatim, at `scratch_examples/hunt_n4n5.py:43-51`
  (`_killtree`) and `:55-68` (file-redirect + poll loop).
- **`FOLD_JOBS`** is only consulted when `opts["jobs"] is None` (`square/engine/search.py:457-467`). Any
  caller that hardcodes `jobs=` silently disables the throttle.
- **Engines are stateless by design** — `square/generate.py:12-13`: *"every run re-derives and overwrites
  its bundles (no cache, no database)."* The S1 cache is an oracle-layer artifact, never an engine one.
- **Content-id convention** is `hashlib.sha1(payload)[:12]` over a canonical content string — `make_uid`
  (`square/generate.py:84-89`), `twostack` (`:204-211`), `gen_testset.fold_uid` (`:79-83`). New ids should
  follow it.
- **`results/` is 1.5 GB / 304 files** (one bundle, `8x6_ab9ad15e.json`, is 152 MB). Never checksum the tree.
- **`results/` and `report/` are gitignored** — every consumer needs a skip-guard so a fresh clone passes.

## Pre-flight — baseline the tree (do this before S1, same session)

**The working tree is dirty and the dirt is load-bearing.** It carries **two unrelated, tangled efforts**,
both uncommitted, and both depended on by sessions below. Nothing here may be discarded.

| Effort | Files | Depended on by |
|---|---|---|
| **n-stack `--panels` support** | `square/generate.py` (the `--panels` arg + `build_opts`), `square/engine/search.py` (`_all_singleton_decomp_key`), `square/render/figstyle.py` (CHAIN D/E/F for N>3) | **S4** |
| **S0 physical-testing suite** | `scripts/phystest/` (untracked), `smoketest/test_physical_suite.py` (untracked), `scripts/validate_square.py` + `validate_triangle.py` (`--json`), `pytest.ini` (`slow` marker) | **S1** (repairs it) |
| *unclassified — inspect before assigning* | `square/lattice/square.py`, `square/render/report_examples.py`, `triangle/tri/foldsheet_tri.py` | ? |

Untracked output/scratch dirs (`g_*/`, `scratch2s/`, `scratch_examples/`) are **not** to be committed —
S11 gitignores them. But **`scratch_examples/hunt_n4n5_results.jsonl` is S4's entire known-answer oracle**
and must be moved into the tracked test corpus before that ignore lands (S4 does this).

**Do:** split into separate commits on `grid-ingest`, one per effort, so each session's gate has a clean
before/after. Read `square/lattice/square.py`'s diff carefully — S3 rewrites `canonical_hash` in that same
file, and it must not start from an unexplained delta.

**Do not** start S1 on an ambiguous tree. Every session's gate is a before/after comparison and is
meaningless without a known baseline.

## The standing gate

From S2 onward **every** session ends with all of these green — not just its own tests:

```
python scripts/run_tests.py        # square/tests, triangle/tests, smoketest — separate interpreters
python scripts/phystest check      # 61-record physical ground truth, fingerprint-cached
# and: zero orphaned python processes afterward
```

Gates are cumulative and permanent. A session is not done until its own gate **and** every prior gate pass.

## Session map

| # | Session | Ships | Own gate |
|---|---|---|---|
| **S1** | Oracle repair + fingerprint cache | trustworthy, fast, orphan-free ground-truth gate | oracle PASS, warm ~seconds, zero orphans |
| **S2** | Test corpus resurrection + runner | tracked `square/tests` + `triangle/tests` + `run_tests.py` | all 3 suites green, isolated |
| **S3** | canonical_hash fix + migration | automorphism-subgroup canonicalization | oracle PASS **before and after** |
| **S4** | n-stack first-class | `square/nstack.py` + sweep, `--stacks N` | 11 known-answer jsonl rows reproduce |
| **S5** | Arbitrary-sheet ingest (square) | `cells=` lattice, `--grid-file`, search seams | rectangle round-trip ≡ parameterized |
| **S6** | Arbitrary-sheet ingest (triangle) | `foldgrid_tri.py`, 4 tilings, closure gate | triangle oracle 22/22 |
| **S7** | Orchestrator + grid-file contract | `scripts/fold_grid.py`, `proven` flag | round-trip; no co-import |
| **S8** | `dump-geometry` + GUI core | geometry dump, hit-test, connectivity | dump fidelity, 5 tilings |
| **S9** | GUI app shell | `gui/app.py`, dispatch, results | manual round-trip |
| **S10** | Renderer standardization | `tristyle.py`, `STYLE_SPEC.md`, masking | style conformance |
| **S11** | Housekeeping + docs + packaging | cruft, gitignore, docs, entry points | full gate after clean install |

---

# S1 — Oracle repair + fingerprint cache

**Goal.** Turn the physical-ground-truth oracle into a gate that is correct, fast, and orphan-free, so
every later session can lean on it.

**Why first.** The oracle is the *only* proof the gates are correct on canonical shapes. Today it is broken
three independent ways and its failure mode is indistinguishable from a real regression.

### State of the world (verified)

`scripts/phystest/check.py` (124 lines) — `_CHECKERS` (`:24-27`) maps `square`/`triangle` to
`scripts/validate_{square,triangle}.py`. `_run_checker(engine, script, timeout)` (`:30-54`),
`run_checks(engines=("square","triangle"), timeout=1800)` (`:57-94`), `_print_report` (`:97-107`),
`main(argv)` (`:110-123`).

- `:34-35` — `subprocess.run([sys.executable, script, "--json"], capture_output=True, text=True, timeout=timeout)`
- `:36-39` — `TimeoutExpired` → synthetic `{"kind": "timeout"}` mismatch, `hardError: True`
- `:41-46` — parses the **last** JSON-parseable stdout line, scanning `reversed(...)` (this is what tolerates
  validate_square's `progress:` lines)
- `:47-51` — no parseable line → `{"kind": "no_output"}`; `:52-53` — `hardError = returncode != 0 and not mismatches`
- `:69-74` — `any_mismatch = any(r.get("mismatches") …)`; **no kind filtering**
- `:76-83` — verdict ladder: `FAIL` if `any_mismatch or any_hard` → `NOTHING VALIDATED` → `PASS (with skip)` → `PASS`
- `:112` — `run_checks()` called **with no args**, so timeout is always the 1800 default; **no CLI override exists**
- `:119-122` — exit 1 on `anyMismatch` or `NOTHING VALIDATED`

`scripts/validate_square.py` (171 lines) — `_norm_hash` (`:66-68`), `_load_ground_truth` (`:71-82`, filters
`by == "john" and foldable is not None`), `_search_grid(Runner, m, n)` (`:85-103`), `run()` (`:106-153`).
Engine import is lazy inside `run()`: `import runner as Runner` (`:114`); bootstrap at `:57-61`.
`_search_grid` opts verbatim (`:88-96`):

```python
opts = {
    "m": m, "n": n, "stacks": 3,
    "shapes": {"L": True, "Rect": True},
    "decomps": {"2+1": True, "1+1+1": True},
    "allowNonCorner": True,
    "dedup": True,
    "jobs": os.cpu_count(),
    "storeAll": False,
}
```

Mismatch kinds: `not-enumerated` (`:133`), `twist_undecided` (`:139`), `verdict_disagree` (`:148`).
`--json` payload (`:162-165`): `{"engine","skipped","nAgree","nTotal","mismatches"}`. Skip returns a
3-tuple of `None` (`:110-112`) — note `mismatches` is `None`, not `[]`. Progress prints to stdout at
`:122`, `:126`, `:150`. **No `try/except` around the recompute**; `_search_grid` raises `RuntimeError` on
engine rejection (`:99`) which kills the process.

Ground truth: `results/foldfindings.json`, 45,277 bytes — **70 records, 61 match the john filter**, split
`6x4: 8, 6x5: 9, 6x6: 40, 6x7: 2, 6x8: 1, 8x6: 1`. `canonicalHash` is a serialized canonical *form*, not a
digest. Triangle: 133 `report/tri/**/folds/*.json`, narrowed to 22 by `actual.folded is not None`.

**No caching or source-fingerprint utility exists anywhere** — repo-wide greps for
`cache`/`lru_cache`/`fingerprint`/`sha256`/`md5` return zero. `results/.oracle_cache/` does not exist.

### Root cause (diagnosed — not a physical disagreement)

The 30-min per-engine timeout fires against a square checker needing ~132 min → synthetic `timeout`
mismatch → FAIL → exit 1. And the timeout **bounds nothing**: `capture_output=True` + `ProcessPoolExecutor`
grandchildren = the post-kill `communicate()` blocks until the search finishes naturally. That is both the
132 min and the ~50 orphans.

### Changes

1. **`check.py` — file-redirect, never `PIPE`.** This is what actually fixes the hang. Reap with
   `taskkill /F /T /PID`. Copy the working pattern from `scratch_examples/hunt_n4n5.py:43-68` verbatim.
   Stream progress through instead of discarding it (`:36-39` currently throws away all 132 min of output).
2. **`check.py` — separate infra failure from data disagreement.** `timeout`/`no_output`/`hardError` become
   verdict **`ERROR`**; only `verdict_disagree`/`not-enumerated`/`twist_undecided`/`exception`/
   `closure_gate_failed`/`unknown_decomp` are **`FAIL`**. Distinct exit codes. Add a `--timeout` CLI flag
   (today `:112` hardcodes the default).
3. **`validate_square.py`** — drop `jobs=os.cpu_count()` (`:94`); honour `FOLD_JOBS` by passing `jobs=None`
   or reading the env explicitly. Add the per-record `try/except` triangle already has
   (`validate_triangle.py:154-166`) so one bad record degrades to `kind="exception"`.
4. **Fingerprint cache.** Key = sha256 over the sorted `(relpath, content)` of the whole `square/` (resp.
   `triangle/`) package source **plus** the per-grid opts dict **plus** the record set for that grid. Coarse
   on purpose — any engine edit invalidates everything, so the cache can never mask a regression. Store
   per-grid `{norm_hash: verdict}` maps under `results/.oracle_cache/<fingerprint>.json`; re-search only on
   miss. **Never checksum `results/`** (1.5 GB).
5. **Optional, low-risk:** dedupe `norm_hash` — byte-identical in `records.py:20-23` and
   `validate_square.py:66-68`, and `records.py:22` already documents the coupling.

### Tests (extend `smoketest/test_physical_suite.py`)

- Cache hit/miss; a touched engine source file invalidates the fingerprint.
- Infra-vs-data verdict separation: a canned timeout → `ERROR`, a canned `verdict_disagree` → `FAIL`.
- A forced timeout leaves **zero** orphaned processes (the regression test for the actual bug).
- Existing 11 hermetic tests stay green.

### Gate

`phystest check` PASS on all 61 records; warm run ~seconds; cold run bounded and orphan-free; zero orphans
afterward (`Get-Process python`).

### Gotchas

- `check.py:41-46`'s reverse-scan exists **because** validate_square prints progress to stdout. Don't
  "clean up" the progress prints without fixing the parser, and vice versa.
- `scripts/validate.py` is a **second, independent dispatcher** — it passes no `--json` and no `timeout`,
  and detects skip by the substring `"SKIPPED" in out` (`:26`). Fix both or consciously leave it; don't
  assume fixing `check.py` fixes `validate.py`.
- Latent bug worth fixing while here: `validate_triangle.py:168-181` appends `closure_gate_failed` **without
  `continue`**, so a closure-failed record still runs `SFILT.apply` and can log a *second* mismatch and/or
  increment `n_agree`.
- `records.tested_square_index()` does **not** filter `by == "john"`, unlike `validate_square`. Intentional
  asymmetry — don't "harmonize" them blindly.

### Hand off to S3

**Report the exact count of `not-enumerated` records from the cold run.** S3's migration requires every
stored hash to be enumerable. If any is not, S3 is blocked until that is understood — do not route around it.

---

# S2 — Test corpus resurrection + isolated runner

**Goal.** A real, tracked regression gate that survives a fresh clone.

### State of the world (verified)

`tests/` is gitignored (`.gitignore:31`) — **0 files tracked**. `tests/conftest.py` does
`sys.path.insert(0, os.path.join(ROOT, "py"))` then `import _bootstrap`; **`py/` no longer exists** (only
`deprecated/py`), so collection fails and the entire tree is dead. Tests import engine modules by bare name
(`import search as Search`, `from lattice.square import SquareLattice`) — the flat py/ convention.

`tests/golden/` — 17 JSON (INDEX + 16 baselines: `2stack_6x4/6x5`, `3stack_6x4_c/nc`, `3stack_6x5_c/nc`,
`3stack_6x6_c`, `3stack_6x7_c`, `3stack_9x4_c`, `vet_6x4_c/nc`, `vet_6x5_c/nc`, `vet_6x6_c/nc`,
`vet_6x7_c`), all gitignored. `tests/fixtures/` — 7 JSON, gitignored.

Support files: `enginelib.py` (facade: `run_3stack`, `run_2stack`, `closing_candidates`, `norm_hash`,
`find_closing_by_hash`, `predicted_trace`, `solution_digest`), `gen_golden.py`, `js_shim/run_engine.mjs`.

`smoketest/` — `test_packaging.py` (**tracked**), `test_physical_suite.py` (untracked, not ignored).
`scripts/run_tests.py` **does not exist**. `pytest.ini` has `testpaths = smoketest`.

### Changes

- **Relocate + un-ignore.** `tests/` → `square/tests/` + `triangle/tests/`. The halves **cannot share an
  interpreter** (bare-`lattice` collision). Per-package `conftest.py`: insert the package dir, `import
  _bootstrap`, set `FOLD_JOBS=1`.
- **Salvage to square** (import rewire only — every imported module survives): `test_gates.py`
  (`fold`, `search`, `lattice.reflect`), `test_golden.py` + `enginelib.py`, `test_twist_reduction.py`,
  `test_store_all.py` (name misleading — no `store` import), `test_manifest_counts.py`,
  `test_perf_toggles.py`, `test_physical_deciders.py` (+ `results/` skip-guard), the square half of
  `test_lattice.py`.
- **Salvage to triangle:** `tests/tri/test_fold_validity.py`, `tests/tri/test_foldclose_truth.py`
  (**add a skip-guard** — it opens a gitignored anchor unconditionally → fresh-clone ERROR), the triangle
  half of `test_lattice.py`, `test_tri_reference.py` (data-gated on `results/tri_K12_hl_*.json`).
- **Rewrite** `test_twist_jump.py` — drop the deleted `twist_models` import, keep the `twist_jump` half.
- **Delete the 14 unsalvageable.** `findings`, `store`, `serve`, `reset_db`, `export_patterns`,
  `compute_twist_models`, `twist_models`, `migrate_to_sqlite`, `common` **exist nowhere outside
  `deprecated/`**: `test_findings_{db,lablog,matcher,migration,roundtrip,schema}.py`, `test_sqlite_store.py`,
  `test_read_api.py`, `test_write_api.py`, `test_reset_db.py`, `test_generate_db_flag.py`,
  `test_export_patterns.py`, `test_compute_twist_models.py`. Plus **`test_viewer_contract.py`** — its imports
  resolve (stdlib + fixtures only) but its subject, the shape `py/store.py` wrote, is gone.
- **Decide on `test_parity_js.py`** — needs `node` + the JS engine (`fold.js`/`search.js`) still reachable.
  Verify before salvaging; it also claims a `parity` marker that is **not** in `pytest.ini`.
- **Track** the suites, `enginelib.py`, `gen_golden.py`, the 16 goldens + `INDEX.json`, `tests/fixtures/`.
- **`scripts/run_tests.py`** — each suite in its **own interpreter**, mirroring `scripts/validate.py:23-37`.
  `pytest.ini` keeps `testpaths = smoketest` so bare `pytest` stays fast and safe.

### Anti-hang (the keystone)

Against the documented intermittent hang + Windows orphans: separate interpreters per package, `FOLD_JOBS=1`
in both conftests, file-redirect never `PIPE`, `taskkill /F /T` on timeout, tiny grids, expensive goldens
marked `slow`.

### Gate

`python scripts/run_tests.py` green across all three suites; zero orphans; S1 oracle still PASS; the suites
pass from a fresh clone (data-gated ones skip cleanly).

### Gotchas

- Salvaged tests import by **bare name** — the conftest path insert is what makes that work. Don't rewrite
  them to package-qualified imports; that breaks the `_bootstrap` convention the engines rely on.
- `fold3stack.egg-info/SOURCES.txt` lists the old `tests/test_*.py` paths. Stale; S11 regenerates it.
- `smoketest/test_physical_suite.py` already does its own `sys.path.insert` of `scripts/phystest` — there is
  no `smoketest/conftest.py`. Keep it that way or add one deliberately.

---

# S3 — canonical_hash automorphism fix + ground-truth migration — **DONE (2026-07-16)**

**Shipped.** `canonical_hash` now minimizes over the sheet's automorphism subgroup; the stored ground
truth was migrated through it and the oracle re-proved cold. What follows is what the session actually
found — **the plan below it was wrong on its central claim**, so read this part first.

### CORRECTION 1 — there was no over-merge. The premise was false.

The plan claimed all-of-D4 was "merging genuinely distinct folds". **It cannot**, and never did:

> A 3-stack fold covers the whole `m x n` sheet — `search.search_chains` admits a candidate only when
> its chains reserve all `m*n` cells. If two legal `m x n` candidates A, B share a D4 hash then the
> signature (fp cells + base + arrows) determines the configuration, so `B = s(A)` for some `s ∈ D4`.
> If `s` transposes, `s(A)` covers `n x m`; but B is legal on `m x n`; so `m == n`. **For `m != n`,
> D4-merge ⟺ D2-merge.**

Measured on every candidate of four grids (oracle opts, `dedup=False`) — **over-merged classes: 0**:

| grid | \|Aut\| | candidates | distinct old | distinct new | over-merged | reps changed |
|---|---|---|---|---|---|---|
| 6x4 | 4 | 52 | 13 | 13 | **0** | 13/13 |
| 6x5 | 4 | 52 | 13 | 13 | **0** | 9/13 |
| 6x6 | 8 | 428 | 107 | 107 | **0** | 0/107 |
| 9x4 | 4 | 360 | 90 | 90 | **0** | 90/90 |

So: dedup classes identical → **no golden count moved on any grid**; old→new is a **bijection** → no
data loss was ever possible. Pinned by `square/tests/test_canonical_group.py`.

**What was real** is a *representation* defect: the minimum could be attained at a non-automorphism, so
the representative described the fold on the transposed sheet and could sit **off-grid** (a stored 9x4
bundle had `fp` y=5 with n=4). That is unsound for anything reading the hash back as geometry —
`test_physical_deciders._is_corner_footprint` tests fp cells against the grid's corners. The fix makes
representatives on-grid by construction.

### CORRECTION 2 — the migration needs no search, and the plan's search was the expensive half.

`Fold.make_fold` returns `None` when a fold leaves the grid, so a stored hash (which *is* the fold,
serialized) can be replayed and checked for legality without enumerating anything. The plan's "re-search
each of the 6 grids" would have cost ~4.5h (6x8 = 2.1h, 8x6 = 2.0h, 6x7 = 21min) to migrate the 5 records
living on those grids. `scripts/migrate_canonical_hash.py` runs in seconds and was validated **223/223**
against an enumeration-derived witness map on 6x4/6x5/6x6/9x4.

### CORRECTION 3 — 7 grids, not 6; and 3 files, not 2.

Ground truth spans `6x4, 6x5, 6x6, 6x7, 6x8, 8x6, **9x4**`. The oracle never searches 9x4 (no cache
entry), so a 6-grid migration would have stranded it. Migrated: `results/foldfindings.json` (70),
`square/tests/fixtures/twoplus1_labels.json` (13 — **`gen_golden.probe_deciders` matches these against the
vet goldens**, so skipping it silently degrades every non-square decider to "not in any vet golden set"),
and `results/to_test_folds.json` (13, carries its own geometry and so cross-checks the migration).

**Deliberately NOT migrated:** `square/tests/fixtures/{6x4_bbc04a7f,6x5_c25f38f8}.json` — frozen bundles
from earlier separately-dated runs. `test_manifest_counts` anchors on their solution COUNTS (unmoved) and
never reads their hashes; rewriting them with today's engine would erode the independence that makes them
a cross-check. Their hashes are stale-but-unread, by design.

### CORRECTION 4 — the key-order artifact interacts with uids.

61 of 70 stored hashes serialize `"chains"` before `"fp"` (older serializer; `validate_square.py:20-28`).
`make_uid` hashes the RAW string, so **two records for the same fold had different uids purely from key
order** (`e194f4a50fe6` / `2c2f2702a626`, both 6x4 → now both `0728f7a454d5`). The migrator therefore
rewrites only hashes whose *content* changed, leaving the legacy key order — and the uid — untouched
everywhere else. 17 uids changed; `results/s3_uid_map.json` (`scripts/s3_uid_map.py`) lists them.

### Gotchas that held up

- The S1 cache fingerprints engine source — this change invalidated it wholesale; one full cold run.
- `records.append_square_finding` dedups on `(grid, norm_hash)` (`records.py:57-59`) — checked, no collisions.
- `make_uid` hashes `canonical_hash` into the bundle uid. One on-disk scratch bundle is now misnamed:
  `g_2p1_6x4/e194f4a50fe6` → `0728f7a454d5`. Left alone (untracked scratch).
- **`records.py:76` writes `foldfindings.json` with `indent=1` but the file on disk is `indent=2`** — the
  next `logresult` append will reformat the whole file. Pre-existing, not S3's; flagged for S11.

---

# S4 — n-stack first-class

**Goal.** Promote n-stack from an untracked scratch script to a tested, tracked, CLI-first capability.

### State of the world (verified — this re-scopes the session)

**n-stack already works.** `square/generate.py:41-44` has `--panels`, help text explicitly saying *"use e.g.
4 or 5 for an all-singleton 1+1+1+...+1 n-stack"*. `Search._all_singleton_decomp_key(panels)`
(`square/engine/search.py:68-71`) builds the `"1+1+1+1"` key. **This support is uncommitted** — both files
are dirty in the working tree (see Pre-flight).

What's actually missing: `square/generate.py:39-40` caps `--stacks` at `choices=(2, 3)`, so the n-stack knob
is the separate `--panels`. And the sweep tooling is untracked scratch.

**Gate math needs no change** (all verified): `twist_check`'s all-singleton branch is the pairwise theta loop
over C(N,2) pairs (`search.py:326-336`, via `_pair_loop_twist` at `:302-321`); parity falls to the
nH-even/nV-odd branch for ≠2 chains (`square.py:111-113`); reflection `_shared_crease_pairs` is all-pairs;
`exit_shape` is `panels`-parameterized. `figstyle.CHAIN` already carries 6 colors, D/E/F explicitly *"extend
the palette for n-stack (N>3)"* (`figstyle.py:28-31`).

**The scratch prototype** — `scratch_examples/hunt_n4n5.py` (141 lines, driver) + `hunt_worker.py` (48 lines).
Worker calls the engine **in-process** (`sys.path.insert(0, REPO/square)`, `import search as Search`,
`Search.run(opts)` at `:28`) — it bypasses `generate.py` and the CLI entirely. Opts verbatim (`:25-27`):

```python
all_key = Search._all_singleton_decomp_key(panels)
opts = {"m": m, "n": n, "panels": panels, "shapes": {"L": True, "Rect": True},
        "decomps": {"2+1": False, all_key: True},
        "allowNonCorner": True, "dedup": True, "jobs": 20}
```

Note `jobs: 20` hardcoded, `storeAll` **absent**, and a dependency on the **private**
`Search._all_singleton_decomp_key`. Result row shape (`:34-43`) — `survivors` is `ctx["afterDedup"]`, `jam`
is derived as `afterDedup - len(fold_sols)`, `bentExamples` capped at `bent[:3]`. The driver injects
`row["seconds"]` (`:87`) and prints `row['survivors'|'fold'|'jam'|'bentFoldCount'|'bentExamples']`
(`:131-134`) — a schema change breaks the print, not just the JSONL.

**The anti-orphan pattern to preserve, verbatim:** `_killtree(pid)` at `hunt_n4n5.py:43-51`
(`taskkill /F /T /PID`), file-redirect at `:55-58` (`stdout=f, stderr=subprocess.STDOUT` to
`_worker_{m}x{n}_p{panels}.tmp`), poll loop `:60-68`, resume-from-jsonl `already_done()` at `:91-103`.
Four stale 0-byte `_worker_*.tmp` files on disk prove the kill path fires.

### The known-answer oracle — narrower than assumed

`scratch_examples/hunt_n4n5_results.jsonl` **exists**, 35 lines. **panels=4 only — zero panels=5 rows**
(the ladder burned its 8h budget before reaching `for panels in (4, 5)`'s second iteration).

- **11 completed** (`err: null`, full gate fields): 4x4, 4x5, 4x6, 4x7, 4x8, 6x6, 4x9, **5x8**, 4x10, 4x11, 4x12
- **24 timeouts** carrying only `{m, n, panels, err, seconds}` — no gate fields, useless as an oracle
- **`jam` is 0 on every completed row** — that column discriminates nothing; gate on
  `coveredCount/exitPass/parityPass/survivors/fold`
- `fold > 0` at 4x4, 4x6, 4x8, 4x10, 4x12 (1 each) and **5x8 (fold=2, bentFoldCount=2)** — 5x8 is the only
  row with `bentExamples`, making it the most valuable single test case

Sample rows verbatim:
```json
{"m": 4, "n": 5, "panels": 4, "err": null, "coveredCount": 184, "exitPass": 6, "parityPass": 0, "survivors": 0, "fold": 0, "jam": 0, "bentFoldCount": 0, "bentExamples": [], "seconds": 0.3}
{"m": 4, "n": 12, "panels": 4, "err": null, "coveredCount": 184540, "exitPass": 20, "parityPass": 2, "survivors": 1, "fold": 1, "jam": 0, "bentFoldCount": 0, "bentExamples": [], "seconds": 726.3}
{"m": 6, "n": 8, "panels": 4, "err": "timeout", "seconds": 900.7}
```

### Changes

- `square/generate.py:39-40` — `--stacks` becomes `type=int`, no `choices`, validated `>= 2`;
  `panels = stacks` for `stacks >= 3`; keep `--panels` as a hidden back-compat alias (they must not
  contradict — decide precedence and test it).
- **`square/nstack.py`** — `run_grid(m, n, panels)` + `python -m square.nstack` CLI, wrapping `Search.run`.
  Promote `_all_singleton_decomp_key` to public or expose a proper accessor; don't ship a tracked tool
  depending on a private.
- **`square/nstack_sweep.py`** — the ladder driver, **preserving `taskkill /F /T` + file-redirect +
  resume-from-jsonl verbatim**, with `jobs` configurable (default 1, not 20).
- Delete `scratch_examples/{hunt_n4n5,hunt_worker}.py` **after** the tracked tools reproduce the jsonl.
- **Move `hunt_n4n5_results.jsonl` into the tracked test corpus** before deleting anything — it is currently
  untracked and is the entire oracle.

### Tests

`square/tests/test_nstack.py` — reproduce the gate counts for the **fast completed rows only** (4x4 p4 at
0.3s-class, 4x5, 4x6; 5x8 is the bent case but check its `seconds` before including). Rows with
`seconds > ~30` get marked `slow`. 4x12 took 726s — exclude from the default tier.

### Gate

The chosen jsonl rows reproduce exactly on `coveredCount/exitPass/parityPass/survivors/fold`; standing gate
green; zero orphans.

### Gotchas

- **`--stacks 4` is rejected today** (`choices=(2,3)`). Don't assume the CLI already does what `--panels` does.
- The `n5_*/` bundle dirs in `scratch_examples/` came from manual `--panels 5` runs, **not** the sweep — they
  are not evidence the sweep covers panels=5.
- `hunt_worker.py` omits `storeAll` entirely, so the sweep is gate-pruned, not store-all. Match that or
  document the divergence — it changes the counts.

---

# S5 — Arbitrary-sheet ingest (square)

**Goal.** The headline feature: the engine ingests an exact drawn grid.

**The load-bearing idea: a compatibility invariant.** The sheet threads as an *optional* `opts["sheet"]`.
Absent → every existing path runs byte-identically. Present → every rectangle-membership test becomes
cell-set membership.

### State of the world (verified)

`opts["sheet"]` is **unused repo-wide** — a clean seam. `--grid-file` does not exist.

- `run(opts, on_solution=None, is_cancelled=None)` — `search.py:538`. Reads `m, n = opts["m"], opts["n"]`
  (`:539`). **No `total` variable** — it inlines `(m * n) % panels` (`:552`) and `K = (m * n) // panels`
  (`:555`); `panels = opts.get("panels", 3)` (`:551`); `if K < 1` (`:556`).
- `enumerate_footprints` — `search.py:25-63`. In-bounds tests `0 <= x < m and 0 <= y < n` at **`:35`** (L
  branch) and **`:54`** (Rect branch). Corner special-cases, both gated on `not opts.get("allowNonCorner")`:
  L at `:36-40`, Rect at `:55-57`.
- `search_decomposition` — `search.py:167-236`. **`total_cells = m * n` at `:174`** (this is where `m*n`
  lives, not in `run`).
- `connectivity_ok` — `search.py:141-162`. Iterates `for y in range(n): for x in range(m):` at `:144-145`.
- `Fold.make_fold` — `fold.py:42-58`. Order: `bounds` (`:44`) → `fold_spec` (`:45`) → `reflect_cells`
  (`:46`) → **`if not in_bounds(new_cells, m, n): return None` (`:47`)**. Helper `in_bounds` at `:25-26`.
- **Parallel payload** — `_run_footprint_chunk` (`:483-512`), `_search_parallel` (`:515-533`). Payload tuple
  is `(m, n, K, opts, ordinal, i_start, i_end)`, unpacked `:490`, built `:522-523`. **The entire `opts` dict
  crosses the process boundary** — a sheet rides along free **if it is a list** (picklable). The worker
  re-runs `enumerate_footprints(m, n, opts)` at `:492`.
- **`SquareLattice.__init__(m, n)` — `square.py:26` — does NOT accept `cells=`.** It synthesizes at `:28`:
  `super().__init__([(x, y) for y in range(n) for x in range(m)])`. Only the `Lattice` ABC takes a cell list
  (`base.py:45`, `def __init__(self, cells)`). **This is a real constructor change, bigger than "thread an
  opt".**

`enumerate_decompositions`, `_evaluate_candidate`, and all four gates are cell-only and need **no change** —
they already operate on `footprint["cells"]`, now `⊆ S`.

### Changes

- **`SquareLattice(m, n, cells=None)`** — pass an explicit list through to `Lattice.__init__` when given,
  else synthesize as today. Mirror the triangle convention, which already does exactly this in all four
  lattices (e.g. `TriLattice.__init__(self, M=None, N=None, cells=None)`, `trilattice.py:96`).
- **Grid-file schema** `docs/schema/fold-grid-1.md`:
  `{schema:"fold-grid/1", tiling, cells:[<native tile id>…], stacks:[2,3]|[4]|"auto", bbox:{m,n}?}`. Cell ids
  are each engine's native tile id, JSON-arrayed: square `[x,y]`; equilateral `[i,j,"U"]`; righttri
  `[i,j,"N"]`; scalene `[i,j,"U",0,1]`; hex `[q,r]` — they round-trip exactly as
  `triangle/tri/render_fold.py:30-34` already reconstitutes them. In memory `opts["sheet"] = [[x,y],…]` — a
  **list**, reconstituted to a `frozenset` of tuples inside the engine.
- **`--grid-file`** on `square/generate.py` → `opts["sheet"]`.
- **Search seams:** `run` builds the frozenset, keeps `m,n` as the **bounding box** (reflection math +
  renderer still need it), adds a **BFS connectivity guard**, and makes `:552`/`:555` `len(sheet)`-based.
  `enumerate_footprints` — `:35`/`:54` become `cells ⊆ S`; drop the corner special-cases (`:36-40`, `:55-57`)
  when a sheet is present (no canonical corner on an arbitrary sheet). `search_decomposition:174` —
  `total_cells = len(sheet)`. `connectivity_ok:144-145` — iterate `sheet`, neighbor test `nb in sheet`.
- **`make_fold:47`** — additionally reject any reflected cell `∉ S`. Legacy `in_bounds` stays for the
  `sheet is None` path.
- **Parallel** — reconstitute the frozenset once inside `_run_footprint_chunk` (`:490-492`), not per-call.

### Tests — the thoroughness budget goes here

- **Tier 1 rectangle-equivalence (the key proof).** A grid-file whose `cells` are exactly an m×n rectangle,
  through the NEW ingest, must produce a solution set (uids + verdicts) **identical** to `sq-generate --m --n`
  on the OLD path. Battery: 4×4, 6×4, 6×6 × {L, Rect} × {2+1, 1+1+1}. This proves the generalized code
  restricted to a rectangle *is* the parameterized engine.
- **Tier 1 byte-identity.** `sheet is None` → the 16 goldens reproduce exactly.
- **Tier 0 invariants** (theory-free, hold on ANY sheet): union of chain cells `== S`, no overlap, no cell
  `∉ S`; replay each chain's `foldArrows` via `twist_jump.replay` and stay within `S` at every step; reject
  disconnected / `len(S) % panels != 0` / empty / singleton; **determinism with `--jobs 1` AND `--jobs N`**
  (parallel must byte-match serial).
- **Tier 3 hand-verified.** Small non-rectangular sheets with a fold checkable by hand (L-polyomino),
  fixtures under `square/tests/fixtures/grids/`.
- **Tier 4 fuzz** (`slow`). Seeded random connected polyominoes with `len % panels == 0` → Tier-0 invariants
  hold, engine never crashes/hangs/emits a cell outside `S`.

### Gate

Rectangle-equivalence exact across the battery; goldens byte-identical; Tier-0 holds on the fuzz corpus;
standing gate green.

### Gotchas

- `opts["sheet"]` **must be a list**, not a frozenset — it is pickled into worker processes (`:522`).
- Keeping `m,n` as bbox is not optional: reflection math and the renderer both need it. Don't drop them.
- The corner special-cases are `allowNonCorner`-gated *today*; with a sheet present they must drop
  **regardless** of that flag. Two different conditions — don't conflate.
- Memory records that `allowNonCorner=False` **understates/hides foldability** and falsified two published
  claims. Default arbitrary-sheet runs to non-corner.

---

# S6 — Arbitrary-sheet ingest (triangle)

**Goal.** Ingest parity for the four triangle tilings, 3-stack / 1+1+1 only.

### State of the world (verified)

- **`search_111(lat, K=None, require_exit=True)`** — `trisearch.py:70-96`. `K` defaults to
  `len(lat.tris) // 3` (`:71`). Returns a **list** of dicts. **Already ingests an arbitrary sheet**:
  `allset = set(lat.tris)` (`:73`), `freeb = allset - set(wa)` (`:77`), `freec = freeb - set(wb)` (`:79`),
  exhaustive-cover check `if set(wc) != freec: continue` (`:81`). The sheet enters **only via `lat`** —
  `search_111` itself takes no `cells=`. So ingest is entirely a lattice-constructor concern.
- **All four constructors already accept `cells=`:** `TriLattice.__init__(self, M=None, N=None, cells=None)`
  (`trilattice.py:96`); `RightTriLattice.__init__(self, M=None, N=None, cells=None)` (`righttri.py:63`);
  **`ScaleneLattice.__init__(self, faces=None, cells=None)` (`scalene.py:69`) — the odd one out, `faces=` not
  `M, N=`**; `HexLattice.__init__(self, R=None, cells=None)` (`hexlattice.py:87`).
- **The one real change.** `search_111` gates on `exit_ok` (`:48-55`, called `:83`, gated by `require_exit` at
  `:84`) and **never calls `reflection_closes_111`**. `foldclose.py:7-10` names this explicitly as the bug —
  `exit_ok` *"admits non-closing folds"*. `search_111:91` computes `foldable = closes and all(|Tw| < 1e-6)`,
  which `foldclose.py:10` calls *"the (unreliable) twist"*.
- **The shipped authority is `find_example.gen_111(tiling, K, hub, stats=None, budget=None, t0=None)`** —
  `find_example.py:137-183`. Gate order verbatim (`:166-176`): `SF.enum_111_general(...)` → **`if not
  FC.reflection_closes_111(lat, chains): continue`** → twist scored last. **Twist is a label, never a
  filter.** `twsig = "path"` (`:163`) — loop-index sigma, **not** the tiling's bipartite sigma.
- `reflection_closes_111(lat, chains)` — `foldclose.py:33-43`, returns `bool`. Sibling
  `reflection_closes_21(lat, two_tiles, one_chain, S, end_pair=None)` at `:66-98`.
- **Candidate shapes differ between the two producers.** `search_111` yields `{"decomp": "1+1+1", "footprint",
  "chains", "loops" (dict AB/BC/AC), "closes", "foldable", "frac"}`. `gen_111` yields `{"decomp":
  "1plus1plus1", "chains", "footprint", "end_footprint", "region", "tw" (list), "foldable", "tw_desc"}`.
  Reconcile deliberately.
- Triangle CLI: `triangle/tri/generate.py:49-85` — `--tiling {equilateral,righttri,scalene,hex}`,
  `--decomp {2plus1,1plus1plus1}`, `--K`, `--out`, `--budget`. Not finding an example returns **0, not an
  error** (`:61-65`).

### Changes

New `triangle/tri/foldgrid_tri.py`: `build_lattice(tiling, cells)` dispatching to the four constructors
(**special-case Scalene's `faces=` signature**), validating connectivity + `len(cells) % 3 == 0`, then calling
`search_111(lat)` **with the physical closure gate `foldclose.reflection_closes_111` added after `exit_ok`**,
matching `gen_111`'s order.

Triangle 2+1 is **not** generalized (rhombus-index-bound). Grid-file `stacks` for triangle is `[3]`.

### Gate

Triangle oracle 22/22; Tier-0 invariants on triangle sheets (union == S, no overlap, no escape, reject
disconnected / `%3 != 0`); `triangle/tests` green.

### Gotchas

- **Do NOT add an `edges_match_111` / edge-type gate.** `foldclose.py:46-57` carries a load-bearing NB:
  `reflection_closes_111` already implies it, and adding one **wrongly drops 72/94 closing folds at K=12 on
  equilateral**. This is a documented trap with a measured cost.
- **Use `twsig = "path"` (loop-index sigma), not the bipartite sigma.** Memory records that the 45-45-90
  anomaly was a twist-label bug fixed precisely by loop-index σ for 1+1+1.
- Twist is a **label, not a filter**, in the shipped authority. `search_111:91` currently folds it into
  `foldable`. Decide and document which semantics `foldgrid_tri` ships.
- Memory: the 2+1 twist model **does not port to triangles** (σ non-alternating → `Tw=0` unreliable). Don't
  try.
- `foldsheet_tri.py` is imported as `FS` by **engine** code (`find_example.py:35`, `solve_foldable.py:40`) —
  it is not a leaf module.

---

# S7 — Orchestrator + grid-file contract

**Goal.** One entry point: grid-file in, aggregated bundle out, across both engines.

### State of the world (verified)

`scripts/validate.py:23-37` is the subprocess-isolation reference (`subprocess.run([sys.executable,
str(script)], capture_output=True, text=True)`, triangle first then square, exit-code aggregation `:39-68`).

**`render_bundle.render_record(rec, out_dir, *, title=None)` is SQUARE-ONLY** —
`square/render/render_bundle.py:34-74`. Returns `{"json", "foldsheet", ["twist"]}`. Raises `ValueError`
without `uid` (`:42`) or `m`/`n` (`:45`). Dispatches on schema: `is_3stack` = has `chains`+`footprint`
(`:26`); `is_2stack` = has `circuit` (`:31`). Twist PNG only when `rec.get("decomposition") == "2+1"` (`:59`).

**There is no `triangle/tri/render_bundle.py`.** The triangle equivalent is
`render.render_record_json(json_path, uid, out_root)` — `triangle/tri/render.py:34-51` — which takes an
**already-on-disk JSON path, not a dict**, and returns `{'overlay','foldsheet','twist','reflect'}`. It
swallows `SystemExit` from `render_reflection` (`:43-50`) for equilateral 1+1+1.

**Bundle layouts differ:**

| | Square (`render_bundle.py:49-70`) | Triangle (`render.py:5-12`) |
|---|---|---|
| files | `<uid>.json`, `foldsheet_<uid>.png`, `twist_<uid>.png` (2+1 only) | `<uid>.json`, `overlay_`, `foldsheet_`, `twist_`, `reflect_` (skipped for eq 1+1+1) |
| json indent | `2` | `1` (`generate.py:80`) |

### Changes

New `scripts/fold_grid.py`: read the grid-file, dispatch by tiling to a package worker via subprocess, run the
requested stack counts (the square worker runs 2-stack + each n-stack **in one process** — same package),
aggregate into `out/<gridUid>/bundle.json` with a top-level `gateValidityUnproven` flag and an explicit
`proven` **boolean** (never string-sniffed downstream). Emit `sheetCells` per record so S10 can mask.

### Gate

`smoketest/test_orchestrator.py` round-trip; a subprocess guard asserting the orchestrator never co-imports
both engines; standing gate green.

### Gotchas

- The two render entry points have **incompatible signatures** (dict vs path) and **different output file
  sets**. The orchestrator must not pretend they're symmetric — normalize at the aggregation layer.
- `render_bundle.py:3-7` explains its own name: `square/render.py` (file) and `square/render/` (package) share
  a name, so `import render` resolves to the package. Don't "tidy" that away.
- Triangle "no example found" is exit **0**. Don't read a zero exit as "found something".

---

# S8 — `dump-geometry` + GUI core (headless)

**Goal.** The GUI's geometry foundation, fully testable without a display.

### State of the world (verified)

- **There is no `tile_cart` function.** `square/lattice/base.py` exposes the abstract `_vkey_to_cart` hook
  (`:82-83`), **`vertices_cart(tid)` (`:97-99`)**, `shared_edge_cart = shared_edge` alias (`:116`),
  `reflect_across_edge` (`:118-121`), `centroid` (`:101-102`) precomputed into `self.cent` (`:58`), and a
  `UnitTile` view (`:28-38`) via `tile(tid)` (`:107-109`) — which returns vertex **keys**, not Cartesian
  points. (Note: `draw_footprints` takes a `tile_cart` **parameter** — a passed-in callable, not a module
  function. Don't confuse them.)
- **Dual graph already exists** — `base.py:60-73`: `edge_owners` (`:61-64`), `self.adj` (`:65`),
  `self.shared` (`:66`) keyed both `(a,b)` and `(b,a)` (`:71-72`); adjacent iff `len(owners) == 2` (`:68`).
  Public `neighbors` (`:90-91`), `shared_edge` (`:111-114`). Edge identity via `_cyclic_edges` frozensets
  (`:21-25`).
- `gui/` does not exist. `dump-geometry` does not exist anywhere.

### Changes

New engine `dump-geometry --tiling X --bounds …` mode returning `{tid → polygon, adj}` built from
**`vertices_cart`** and the dual graph — **not** `tile_cart`. The GUI renders those polygons and hit-tests
clicks against them, uniform across all five geometries, sidestepping five geometry-specific inverse maps (the
scalene 6-way and hex axial-rounding traps). Adjacency for the connected-set check comes from the dump's
`adj`, not re-derived.

Ships headless-testable modules only: `gui/config.py` (palette/DPI **mirrored** from the style spec — no
`figstyle` import), `gui/tilings.py` (registry: token, engine argv, native y-orientation),
`gui/geometry_client.py` (subprocess the dump + cache), `gui/canvas.py` hit-test (`Path.contains_point`),
`gui/connectivity.py` (BFS over selected ∩ adjacency).

### Gate

Dump fidelity vs the engine for all 5 tilings (golden compare); hit-test at known cell centroids selects the
correct tid per tiling; connectivity accepts/rejects known sets; `smoketest/test_gui_contract.py` asserts
`import gui` exits 0 and never co-imports both engines.

### Gotchas

- `figstyle.py` sets `matplotlib.use("Agg")` at `:21` **before** the pyplot import and runs `apply_style()` at
  import (`:78`). The GUI needs `TkAgg`. Never import `figstyle` from `gui/` — mirror its constants
  (locked decision 7).
- Square is `+y-down`, triangle is `+y-up`. Intentional. `gui/tilings.py` carries per-tiling orientation.

---

# S9 — GUI app shell

**Goal.** The shippable feature: draw a grid, get folds.

### Changes

`gui/app.py` (tkinter root; picker → canvas → dispatch → results; `main()`); `gui/canvas.py` render half
(embedded `FigureCanvasTkAgg`, backend `TkAgg` set **before** importing pyplot — gives free equal-aspect +
data-coordinate hit-testing + polygon fill for all five geometries); `gui/dispatch.py` (write grid-file →
per-tiling argv → `subprocess.run(timeout)` on a worker thread; **cancel must `taskkill /F /T`** to reap
`--jobs` grandchildren — the same Windows bug S1 fixes in the oracle); `gui/results.py` (`ttk.Treeview`
verdict table + thumbnails + unproven badge read from the `proven` boolean); `gui/thumbs.py` (Pillow if
present, else `PhotoImage.subsample`).

Both tkinter and matplotlib are already available (`matplotlib==3.10.9` is the sole runtime dep) — no new
heavy dependency.

### Gate

Dispatch emits a grid-file that round-trips through the engine and builds correct argv; results parser reads a
fixture `<out>/<uid>/` collection into the table and raises the badge; **manual round-trip** — launch
`fold-gui`, draw a square sheet + an equilateral sheet, confirm foldsheets + verdict table + badge render
in-app.

### Gotchas

- The unproven badge reads an explicit `proven` boolean from S7. **Never string-sniff a verdict.**
- Square and triangle bundles have **different file sets** (S7) — the thumbnail picker must handle both.

---

# S10 — Renderer standardization

**Goal.** One style per track, one written contract across tracks, drifts fixed.

### State of the world (verified — the drift is concrete)

`square/render/figstyle.py` (286 lines) is the reference. `DPI = 150` (`:55`). `CUT = "#2a8f6f"` (`:41`).
`CHAIN` = 6 colors (`:30-31`). Full API: `apply_style` (`:63`), `cells` (`:83`), `chain_color` (`:91`),
`new_grid_axes` (`:98`), `draw_grid_cells` (`:116`), `draw_footprint` (`:129`), `draw_end_footprint` (`:140`),
`draw_base_cells` (`:149`), `draw_fold_path` (`:158`), `draw_reflection` (`:186`), `line_handle` (`:214`),
`patch_handle` (`:219`), `legend_panel` (`:224`), `pi_label` (`:232`), `verdict_line` (`:252`),
`verdict_badge` (`:261`), `draw_subnotes` (`:268`), `save(fig, out_path, *, dpi=DPI)` (`:279`).
`figstyle.py:12-13` states the contract: *"Triangle renderers … are a separate, independent package and do not
import this module."* Confirmed — zero triangle files import it.

**DPI drift — three ways, one savefig per file, no shared `save()`:**

| file:line | call | vs DPI=150 |
|---|---|---|
| `trirender.py:82` | `fig.savefig(path, dpi=150, bbox_inches="tight")` | match |
| `render_twist.py:129` | `dpi=160` | **+10** |
| `render_reflection.py:156` | `dpi=160` | **+10** |
| `render_general.py:61` | `dpi=170` | **+20** |
| `foldsheet_tri.py:290` | `dpi=170` | **+20** |

A single triangle bundle currently mixes 150/160/170 across its own PNGs.

**Other drift axes:** (a) **`foldsheet_tri.py:24` — `CUT = "#2a8"`, which expands to `#22aa88`, vs
`figstyle.CUT = "#2a8f6f"` — a genuinely different teal**; (b) `#6f4fb0` lives under **four** names —
`FOOTPRINT_EDGE` (figstyle`:32`), `END_OUTLINE` (`foldsheet_tri.py:30`), `LOOP_COL` (`render_twist.py:34`),
`ARROW_COL` (`render_reflection.py:39`); (c) grid edge `#bbb` (`trirender.py:32`, `render_general.py:32`) vs
`#dddddd` (`foldsheet_tri.py:221`, `render_reflection.py:69`) — split *within* the triangle track; (d) `#222`
shorthand vs `INK = "#222222"`; (e) `CHAIN` under three names — `CHAIN` (`trirender.py:21`), `CH`
(`render_general.py:15`), inline; (f) `TINT = ["#eaf3fb","#fdeeee","#eafaef"]` duplicated verbatim
(`foldsheet_tri.py:23` ≡ `render_reflection.py:38`); `FOLD_BADGE`/`JAM_BADGE` duplicated
(`render_twist.py:35` ≡ `render_reflection.py:40`).

`draw_footprints(ax, tile_cart, start_fp, end_fp=None, z0=8.4, labelsize=11, end_chirality=None)` —
`foldsheet_tri.py:40-78`. Generic over n-gons (`n = len(pc)` `:53`, nudge `3.0 / n` `:68` for hex). Already
shared by 4 of 5 renderers: `trirender.py:16` (called `:59`, `z0=3.6, labelsize=10`), `render_general.py:11`
(called `:49`, same), `render_reflection.py:36` (called `:80` and `:98`), plus `foldsheet_tri.py:238` itself.
`render_twist.py` is the one that does **not** import it.

### Changes

Extract `triangle/tri/tristyle.py` mirroring `figstyle.py`; move palette/DPI/`apply_style`/`save` out of the
five renderers; relocate `draw_footprints` into it; add `pi_label` + arrowhead `draw_walk_arrows`. Write
`docs/guides/STYLE_SPEC.md` (repurposed from the stale `REPORT_STYLE_GUIDE.md`) as the cross-track written
contract — DPI, coordinate convention, palette hex, bundle naming, arrow style, angle labels. `figstyle.py`
stays the reference implementation; **no cross-package import**.

Fix the drifts: DPI → 150 everywhere via `tristyle.save`; `CUT` → `#2a8f6f`; arrowheads on tri overlays;
`pi_label` for tri angles; document `+y-down` (square) vs `+y-up` (triangle) as an intentional, spec'd
convention — the tracks never share an axis, so unifying would flip every triangle diagram for no benefit. Add
`sheetCells` masking to `render_square.render` so arbitrary-sheet records draw only `S`.

### Gate

Source-level test asserting `figstyle.py` and `tristyle.py` share identical hex for the spec'd constants
(**comparison only, no import**); bundle-per-tiling regenerate ≡ generate (the README byte-consistency
contract); arbitrary-sheet record draws only `S`.

### Gotchas

- **`draw_footprints` relocation is not a move.** It closes over `CHIR_COLOR` (`:36`), `CHIR_TAG`,
  `START_FILL`/`START_OUTLINE` (`:29`), `END_OUTLINE` (`:30`) — all must travel with it.
- **`foldsheet_tri.py` is not a leaf.** Engine code imports it as `FS`: `find_example.py:35`,
  `solve_foldable.py:40`. Refactoring it can break the engine, not just renderers.
- Changing DPI changes every PNG byte. Expect the regenerate≡generate gate to need a baseline refresh, and
  say so explicitly rather than letting it look like a pass.
- `trirender.py:36` uses `#3399cc`/`#d83232` (= figstyle `VLY`/`MNT`) **for sigma labels, not creases**. Same
  hex, different meaning — don't unify semantics along with color.

---

# S11 — Housekeeping + docs + packaging

**Goal.** Leave the tree clean, documented, and installable.

Run `python scripts/validate.py` after **each** step — it is subprocess-per-engine, so it is immune to
test/doc churn.

### State of the world (verified)

`.gitignore` (32 lines) — `__pycache__/` (`:5`), `*.pyc` (`:6`), `.venv/` (`:7`), `.pytest_cache/` (`:8`),
`*.egg-info/` (`:9`), `node_modules/` (`:12-13`), `.claude/` (`:16`), `annotated-codebase/` (`:19`), `out/`
(`:22`), then the "local-only working dirs" block: `deprecated/` (`:27`), **`docs/` (`:28`)**, `report/`
(`:29`), `results/` (`:30`), `tests/` (`:31`), `experimental/` (`:32`). **Neither `scratch_examples/` nor
`scratch2s/` is ignored** — both show as `??`. Nor are the root `g_111_*`/`g_2p1_*` dirs.

`pyproject.toml` (25 lines) verbatim scripts + find:
```toml
[project.scripts]
tri-render = "triangle.tri.render:main"
tri-generate = "triangle.tri.generate:main"
sq-render = "square.render_cli:main"
sq-generate = "square.generate:main"

[tool.setuptools.packages.find]
include = ["triangle*", "square*"]
```
Sole runtime dep `matplotlib==3.10.9`; `[test]` extra is `pytest==9.1.0`. `packages.find` has **no
`where`/`exclude`** — it globs from repo root, so `gui*` must be added to `include`.

**The shim asymmetry, confirmed:** `triangle/render_cli.py` and `triangle/generate.py` **do not exist**.
`triangle/` top level is only `__init__.py`, `_bootstrap.py`, `lattice/`, `tri/`. Square has root-level CLI
shims (`square/render_cli.py:41 def main(argv=None)`, `square/generate.py:118 def main(argv=None)`); triangle's
entry points reach straight into `tri/` (`triangle/tri/render.py:77`, `triangle/tri/generate.py:49`). Note also
the naming split: square's render entry is `render_cli.py`, triangle's is `render.py`.

`fold3stack.egg-info/` exists at repo root, dated **Jul 7 vs pyproject's Jul 8 — stale**. Its `SOURCES.txt`
still lists the dead `tests/test_findings_*.py` etc.

`annotated-codebase/conftest.py` is **also broken** — it references `ROOT/py` (gone) and `ROOT/experimental`.

### Changes

1. **Delete cruft** (all gitignored/untracked, no import surface): `deprecated/`, `experimental/`,
   `annotated-codebase/`, stale `fold3stack.egg-info/`, every `__pycache__/`, the four stale 0-byte
   `scratch_examples/_worker_*.tmp`. **Keep** `results/` (the oracle's ground truth), `report/`, `reference/`.
2. **.gitignore surgery** — add `g_*/`, `scratch2s/`, `scratch_examples/`, `*.jsonl`, `_worker_*.tmp`,
   `_mont_*.png`; **narrow the blanket `docs/` ignore (`:28`)** to `docs/research/` + `docs/img/` so the
   tracked guides join the shared tree. This is what finally tracks `docs/schema/physical-test-1.md` (written
   in S0, currently stranded) and `docs/schema/fold-grid-1.md` (S5). **Before adding `*.jsonl`, confirm S4
   moved `hunt_n4n5_results.jsonl` into the tracked corpus** — otherwise the ignore strands the n-stack oracle.
3. **Docs** — rewrite `docs/guides/{COMMANDS,USER_MANUAL,ENGINE_SPEC}.md` to the current tree and the new
   surfaces (`--grid-file`, `sq-nstack`, `fold-gui`, `fold3`, `scripts/run_tests.py`); relocate `FOLDING.md`
   (lab methodology) to local-only `docs/research/`; delete `HANDOFFS.md` (ephemeral); update `README.md` CLI
   table + layout + Tests section.
4. **Packaging** — add `triangle/render_cli.py` + `triangle/generate.py` shims delegating to `triangle.tri.*`
   so both packages expose CLIs at the same level; add `sq-nstack`, `fold-gui = gui.app:main`, `fold3`; add
   `gui*` to `packages.find.include`; `py-modules` for a bare-module orchestrator; regen egg-info via
   `pip install -e .[test]`.

### Gate

Full standing gate after a clean `pip install -e .[test]`; packaging smoke exercises **every** entry point
(`sq-generate/-render`, `tri-generate/-render`, `sq-nstack`, `fold-gui`, `fold3`) with `--help`; zero orphans.

### Gotchas

- **`docs/` is ignored today** — this plan itself (`docs/SESSIONS.md`) needs the negation added at the start of
  the whole effort, not deferred to S11.
- `fold-gui --help` must not require a display. Test it headless.
- Renaming triangle's `render.py` entry to `render_cli.py` for symmetry would collide with the existing
  `trirender.py`/`render_fold.py`/`render_general.py` family in the same dir. Add a shim; don't rename.

---

## Already shipped (S0, done)

The physical-testing suite: `--json` on both checkers; `scripts/phystest/` (`curate → log → check → status`,
wired at `__main__.py:34-45`); `docs/schema/physical-test-1.md`; `smoketest/test_physical_suite.py` (11
hermetic tooling tests + 1 `slow` acceptance test); `slow` marker in `pytest.ini`. Verified: hermetic 11/11,
smoketest 16/16, live curate dedup (6×4: 8 generated, 8 already-tested, 0 queued), live curate real queue (4×6:
10 queued + foldsheets + valid manifest), `status` over 64 records.

**Its acceptance oracle is what S1 repairs.** None of the shipped tooling logic is wrong — it was built before
the anti-hang infra it depends on, which is exactly the ordering error this session split corrects.

## Known limitations (intentional this pass)

- **Triangle is 3-stack / `1+1+1` only** on arbitrary sheets; n-stack (n>3) is **square-only** — the triangle
  footprint is the fixed 3-cell trapezoid, triangle 2+1 is rhombus-index-bound, and triangle n-stack is
  recorded as largely obstructed. The GUI still lets you draw any tiling and "see if we can find something",
  consistent with the exploratory framing.
- **Gate validity is unproven for non-canonical shapes.** The reflection/twist/parity gates are derived for
  canonical sheets. On hand-drawn shapes they are heuristics; results are labeled `gateValidityUnproven` and
  are exploratory, not proofs. **Physical folding remains the ground truth** — any new foldable candidate on an
  arbitrary sheet is a hypothesis until folded, and the S0 `phystest` loop is exactly how that gets settled.
- **Footprints stay canonical** (L/Rect square, trapezoid triangle) — only the *sheet* is generalized.
  Arbitrary footprints are a later increment.
