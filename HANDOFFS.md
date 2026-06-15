# Session handoffs — 3-stack foldability revamp

Copy-paste the fenced block for the session you're starting as the first message of a fresh
Claude Code session. Each block is self-contained: what to **read first**, what to **build**, how
to **test**, what to **debloat**, what to **adversarially review**, and the **exit criteria**.

Full product spec: `~/.claude/plans/ok-the-goal-for-cheerful-pebble.md`.
Baseline the whole effort diffs against: `tests/BASELINE_RESULTS.md`.

## Universal rules (apply to every session)

- **Never silently change a verdict.** The golden suite must reproduce **1:1**. Any intended
  deviation is a *documented, justified* improvement written into `BASELINE_RESULTS.md`, never an
  accident.
- **Per-step quality loop, ≥2×, fidelity overrides everything:** `test → debloat → adversarial
  review`. A step is done only after **two consecutive passes** with the suite green, no new bloat,
  and the reviewer finding nothing that moves a verdict.
- **SWE standards:** small pure functions (maths takes/returns data, never touches disk), type
  hints, a one-line docstring per function/class stating **what it does** + **its I/O**. New code
  lands with its test in the same session.
- **Branch:** work on `revamp` (or a `revamp/<topic>` child); merge to `main` only after the full
  suite is verified green. ss0 is committed at `cb4552f`.
- **Run the net:** fast tier `pytest -m "not slow"` (~13s, every iteration); full fidelity
  `pytest` (heavy — 6x7 vet ~7 min) before declaring a session done. Slow tier alone:
  `pytest -m slow`. Parity needs `node` on PATH.

## Read-first for ANY session (shared context)
- `tests/README.md` — suite layout, how to run fast/slow/parity, how to regenerate golden.
- `tests/BASELINE_RESULTS.md` — the locked counts/verdicts + the 3 known gaps.
- `tests/enginelib.py` — the thin engine wrappers the tests call (`run_3stack`, `run_2stack`,
  `closing_candidates`, `norm_hash`, `solution_digest`).
- The plan file (above) — the session you're on, in full.

---

## ss1.5 — Performance toggles (multiprocessing + PyPy)

```
Session 1.5 of the 3-stack revamp: add multiprocessing and PyPy as two orthogonal, independently
toggleable performance switches. NEITHER may change a single verdict — the golden suite must stay
1:1 under every toggle combination. Work on branch `revamp` (or `revamp/perf`).

READ FIRST (context):
- tests/README.md, tests/BASELINE_RESULTS.md, tests/enginelib.py (shared net context).
- py/search.py — especially `run`, `enumerate_footprints`, `enumerate_decompositions`, and the
  per-footprint DFS. PIN DOWN the exact serial solution ORDERING + dedup (canonical_hash) — that
  ordering is the determinism contract the parallel path must reproduce byte-for-byte.
- py/generate.py — `build_opts`, `Search.run(opts) -> (solutions, ctx, err)` (where `jobs` threads in).
- HANDOFFS.md (this file) ss1.5 section.

BUILD:
- Multiprocessing: switch `--jobs N` (CLI) -> `opts["jobs"]` -> env `FOLD_JOBS`; `jobs=1` (default)
  routes through the UNTOUCHED serial path. Fan the per-footprint DFS across a ProcessPoolExecutor;
  each worker returns its local solution list. After gather, re-sort + dedup DETERMINISTICALLY so
  output is identical to serial. Windows = spawn: worker MUST be a module-level function (no
  closures/lambdas — unpicklable); chunk footprints per task (per-worker import cost is real);
  guard `if __name__ == "__main__"`. Keep search.py numpy-free on the hot path.
- PyPy: keep the engine pure-Python/PyPy-compatible (numpy/matplotlib/pillow stay OUT of search.py —
  they're render-only). Runner switch `FOLD_PY=pypy` (or a `run_search` wrapper) selects PyPy when
  present, else CPython. `--jobs` under PyPy must work (orthogonal). Document the measured speedup.

TEST (add tests/test_perf_toggles.py):
- Equality: 6x6 jobs=1 vs jobs=8 -> identical solution_digest AND identical canonical-hash set
  (slow-mark 6x6).
- Determinism: jobs=4 run twice -> identical ORDERING (not just set equality) — catches gather-order
  nondeterminism.
- Golden-under-load: run the existing golden suite with FOLD_JOBS=8 -> still 1:1. PyPy lane too if
  available.

DEBLOAT: remove any serial/parallel code duplication; keep one DFS, parametrized by an executor
(serial executor for jobs=1). No dead branches.

ADVERSARIAL REVIEW (hunt): nondeterministic merge order; dedup keeping the WRONG representative;
unpicklable closures; Windows-spawn re-import side effects; footprint-chunking off-by-one; sloppy
env parsing (FOLD_JOBS="" / "0" / "-1" / non-int); a "passing" equality test that only compares
counts not hashes/order.

EXIT: two consecutive green passes; golden 1:1 across {jobs=1, jobs=8} x {cpython, pypy-if-present};
BASELINE_RESULTS.md unchanged; speedup numbers in README; reviewer finds nothing moving a verdict.
```

---

## ss2 — Cleanup / bloat (no maths touched)

```
Session 2 of the 3-stack revamp: remove cruft UNDER the green test net. No maths changes — the
golden suite must stay 1:1 and BASELINE_RESULTS.md must come out byte-identical (that's the proof
cleanup touched no verdict). Work on branch `revamp`.

READ FIRST (context):
- tests/README.md, tests/BASELINE_RESULTS.md (shared net context).
- TODO.md — the already-flagged consolidation items.
- py/store.py — JSON shape {meta,solutions}, params_key hashing, manifest read/write (for the GC tool).
- results/manifest.json — what's live vs orphaned on disk.
- The five analyze_*.py and the render_*.py helpers (below) before merging them.

BUILD:
- Delete orphaned artifacts: stale report/foldsheets/*.png and superseded results/*.json caches not
  in manifest. Add a MANIFEST GC tool to py/store.py: prune result files not referenced by
  manifest.json (dry-run by default, --apply to delete).
- Consolidate shared replay/center-path/reflection helpers duplicated across
  py/analyze_twist.py, py/analyze_loop_seams.py, py/analyze_2plus1_reduction.py,
  py/analyze_reflection.py, py/analyze_wrap.py  ->  py/analyze_utils.py. Review the untracked
  render_foldpath.py / render_valid.py / render_vectors.py vs render_reduction.py / render_theta.py /
  make_foldsheets.py for duplication; fold common rendering into a shared helper or delete dead ones.
- Add a short docs index. Leave research notes (LAB_LOG.md, FINDINGS_*.md) intact.

TEST: full `pytest` green (proves cleanup changed no maths). Regenerate BASELINE_RESULTS.md
(`python tests/gen_baseline_report.py`) and diff — MUST be identical. Add a tiny unit test for the
manifest GC (it lists exactly the not-in-manifest files; never proposes a live file).

DEBLOAT: this IS the debloat step — but re-run the suite after EACH deletion batch, not once at the
end, so a bad delete is caught immediately.

ADVERSARIAL REVIEW (hunt): a "dead" file that's actually imported (grep before delete); GC tool that
would nuke a live result; a consolidation that subtly changes an analyze_* numeric output; a deleted
PNG still referenced by index.html/report markdown.

EXIT: two consecutive green passes; BASELINE_RESULTS.md unchanged; GC tool tested; nothing live deleted.
```

---

## ss3 — Engine-rules spec + front-end → viewer

```
Session 3 of the 3-stack revamp: make Python canonical and DOCUMENT both engines in one place, then
demote the in-browser search to a viewer. No verdict changes; golden 1:1. Work on branch `revamp`.

READ FIRST (context):
- tests/BASELINE_RESULTS.md — the JS<->Py parity section + the 3 known gaps (esp. "canonical hash is
  a D4 dedup key, NOT a replayable path").
- tests/test_parity_js.py + tests/js_shim/run_engine.mjs — how JS<->Py parity is checked; KNOWN_DIFFS.
- py/search.py + py/fold.py — every gate predicate (arithmetic, exit-footprint, parity, reflection
  [orientation-aware segment coincidence], twist, D4 dedup, canonical_hash).
- fold.js + search.js — the corresponding JS rules; the known drift (JS enforces mn%6, K-even, n>=4;
  Python relaxed to mn%3).
- index.html, app.js, grid.js, search.js — the front-end entry path.

BUILD:
- Write ENGINE_SPEC.md: every Python gate with its PRECISE predicate, side-by-side with the JS rule,
  marking agreement vs drift (seed from the parity KNOWN_DIFFS table). This is the "note the
  mechanisms so inconsistencies are resolvable" deliverable.
- Front-end: default path becomes "load Python results JSON" (viewer); keep search.js but mark it
  secondary in ENGINE_SPEC.md.

TEST: parity harness now references ENGINE_SPEC.md; full `pytest` green; every known diff is either
resolved in code (with golden updated + justified) or explicitly catalogued in the spec. Add a test
asserting the viewer's loaded-JSON shape matches store.py's {meta,solutions} contract.

DEBLOAT: remove any front-end search code paths made dead by the viewer switch (only if truly unused).

ADVERSARIAL REVIEW (hunt): a spec claim that doesn't match the actual predicate (read the code, not
the comment); a drift case the parity test silently xfails; viewer loading a stale/!=contract JSON.

EXIT: two consecutive green passes; ENGINE_SPEC.md complete + accurate; known-diffs resolved or
catalogued; BASELINE_RESULTS.md unchanged (or deviation documented).
```

---

## ss4 — Tile / Lattice abstraction (the big refactor)

```
Session 4 of the 3-stack revamp: generalise the rectangular engine to arbitrary reflection tilings;
square becomes ONE lattice subclass. The ENTIRE golden suite must reproduce 1:1 through the new
abstraction — that's the whole point. Angle stays abstracted (read only via centroid+sigma, never
branched on). Work on branch `revamp` (consider `revamp/lattice`).

READ FIRST (context):
- tests/BASELINE_RESULTS.md — the counts the abstraction must reproduce exactly.
- py/tri/trilattice.py, righttri.py, scalene.py, trifold.py, tritwist.py, trisearch.py — the PROVEN
  abstraction pattern (lattice classes + cent/sigma callbacks, generic Cartesian _reflect_point,
  generic loop_twist(loop, cent, sigma)). Copy this shape.
- py/fold.py lines ~16-58 (axis-aligned reflect, L/R/U/D dirs) and py/search.py lines ~19-64, 75,
  155, 215, 245-272, 367-399 (T/B/L/R edge labels, Manhattan adjacency, hardcoded D4) — the concrete
  square-only hotspots to replace.
- py/foldpattern.py — fold encoding consumed downstream.

BUILD:
- New py/lattice/: UnitTile + Lattice base exposing centroid, sigma, vertices, neighbors(),
  shared_edge(other)->(p1,p2), reflect_across_edge(edge). Reuse the generic Cartesian _reflect_point.
- SquareLattice subclass wraps current square geometry; adapt tri/righttri/scalene to the same base.
- Port fold.py / search.py to consume the abstraction instead of hardcoded axis/edge/Manhattan/D4.

TEST: the entire ss1 golden suite reproduces 1:1 through the abstraction (run full `pytest`). Add
lattice-level unit tests PER lattice: reflection lands on the correct neighbour; sigma is bipartite;
centroid is correct; shared_edge is symmetric. Any intentional deviation -> documented in
BASELINE_RESULTS.md as "more robust because...".

DEBLOAT: delete the now-dead hardcoded square geometry once SquareLattice replaces it; one reflection
primitive, not two.

ADVERSARIAL REVIEW (hunt): a hotspot still branching on shape/angle; SquareLattice that disagrees
with the old hardcoded path on ONE edge/orientation (off-by-one in reflect or edge labelling); a D4
dedup that changed canonical orbits; sigma parity flipped; centroid/vertex winding inconsistent
between lattices.

EXIT: two consecutive green passes; full golden 1:1 through the abstraction; per-lattice units green;
any deviation documented; reviewer finds nothing moving a verdict.
```

---

## ss5 — Structured physical-findings pipeline (UI-driven)

```
Session 5 of the 3-stack revamp: build the machine-testable user<->engine loop, captured through the
EXISTING JS frontend. Engine prediction must still match the recorded deciders. Work on branch
`revamp`.

READ FIRST (context):
- tests/BASELINE_RESULTS.md — the physical-decider section + the "one-sided ground truth" known gap
  (all current deciders are JAM; need a confirmed FOLD).
- results/twoplus1_labels.json — the current findings shape ({grid,id,canonicalHash,foldable,notes,...});
  this is what you migrate.
- tests/test_physical_deciders.py — how a finding is matched to the engine (hash-match, NOT replay;
  understand why replay is unsafe before designing the trace).
- app.js, grid.js, fold.js — the existing draw/replay/vector/group UI tools to reuse for capture.
- py/store.py — the DB/JSON write path + manifest; LAB_LOG.md — the research log to append to.

BUILD:
- FoldFinding schema + JSON-schema validation:
  {grid,id,canonicalHash,foldable:bool|null, jam:{atFold:int,crease:[p,p],reason:enum},
   foldOrder:[...], observed:{...}, by, date, notes}.
- Capture via the SAME JS UI: user draws/replays the physical fold, marks did-it-fail / why / WHERE
  (fold step / crease / reason), submits to the backend (engine + research logs). Reuse fold/vector/
  group tools, not a separate form.
- Flag engine-enumerated failures from the UI: pick any candidate the engine enumerated (incl.
  predicted-JAM rejects from the vet set), confirm/refute + annotate where it failed. Flagged
  failures written EXPLICITLY into the findings DB AND appended to LAB_LOG.md automatically.
- Engine emits a predicted fold TRACE (per-fold layer/placement state) so predicted jam step can be
  compared to the observed one.
- Backend submit path: small endpoint/CLI that validates FoldFinding against the schema, upserts into
  the findings DB keyed by canonicalHash, writes a dated LAB_LOG entry. Migrate twoplus1_labels.json
  to the new schema (preserve existing physical results + prose).

TEST: schema-validation tests (accept valid, reject each malformed field); a prediction-vs-observation
matcher tested against the existing deciders (engine predicted jam fold# == recorded observation for
6x5#1, 6x6#1, 6x7#8); a round-trip test (UI-shaped payload -> submit -> DB row + LAB_LOG line).
Migrated labels must still pass test_physical_deciders.

DEBLOAT: one findings schema/writer; remove the ad-hoc foldable-bit handling superseded by FoldFinding.

ADVERSARIAL REVIEW (hunt): schema that accepts a finding with a hash no engine candidate has; a
migration that drops prose/results; trace whose fold-index convention != the UI's; LAB_LOG append
that double-writes or corrupts on re-submit; submit that mutates the DB before validation passes.

EXIT: two consecutive green passes; deciders still match; migration lossless; round-trip + schema
tests green; reviewer finds nothing moving a verdict.
```

---

## ss6 (optional, later) — Unified output / FoldScheme

```
Session 6 (optional) of the 3-stack revamp: a shared FoldScheme type across 3-stack / 2-stack / tri
so all renderers consume ONE format. Deferred until the ss4 abstraction settles (it determines the
canonical fold encoding). Work on branch `revamp`.

READ FIRST (context):
- py/foldpattern.py — current fold encoding.
- py/store.py — {meta,solutions} JSON contract.
- py/tri/trifold.py + py/fold.py — the two encodings to unify.
- py/lattice/ (from ss4) — the abstraction the unified scheme rides on.

BUILD: a FoldScheme dataclass/schema covering all three engines; adapt renderers to consume it.

TEST: round-trip every existing golden solution through FoldScheme -> identical render inputs; full
`pytest` 1:1.

DEBLOAT: collapse per-engine bespoke output structs into FoldScheme.

ADVERSARIAL REVIEW (hunt): a field one engine needs that FoldScheme drops; lossy round-trip; renderer
divergence post-unification.

EXIT: two consecutive green passes; golden 1:1; one output format; reviewer clean.
```
