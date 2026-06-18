# TODO — lab queue

Running list. Validation queue first (ordered by information value), then code chores, then
research extensions. Cross-references: `context.md` (Q1–Q7), `LAB_LOG.md` (findings),
`FOLDING.md` (fold protocol).

## Validation queue (the 2+1 / twist theory decider)

- [ ] **PRIORITY FOLDS — model selection (2026-06-08).** Two angle-clean 2+1 invariants now
      conflict (filled-strand vs hub-exception hybrid, 16/303 disagree); two conflicts are
      already printed sheets. Fold these FIRST, in order:
      1. **`6x5_1`** — strand: FOLD / hybrid: JAM  → **JAM (2026-06-08, physical): strand ✗,
         hybrid ✓.** Lead: the jam is an ORIENTATION-AWARE VECTOR REFLECTION failure — it dies at
         the reflection stage (UPSTREAM of twist), which the engine FALSE-PASSED (parity_check +
         reflection_check both pass in search.py because the rigid 2-chain is modeled as ONE
         panel). ⇒ engine reflection gate is unsound for 2-chains.
      2. **`6x7_8`** — strand: JAM / hybrid: FOLD  → **JAM (2026-06-08): strand ✓, hybrid ✗.**
      RESULT = (6x5_1 jam, 6x7_8 jam) = (jams, jams) → per the table, NEITHER twist model is a
      complete standalone criterion. BUT 6x5_1's failure is reflection-level, not twist: a
      strand-aware reflection gate would EXCLUDE 6x5_1 before twist is evaluated, so the strand
      TWIST criterion is not actually falsified by it (hybrid still dead via 6x7_8, which IS a
      genuine twist-stage disagreement). ACTION: fix 2-chain reflection check → re-classify → re-vet.
      ✓ DONE 2026-06-09 — reflection_check rewritten (`fold.reflection_verdict`): seed the SHARED
      hub crease, reflect each chain to its far end, require the two images to COINCIDE as oriented
      grid segments. Validated: rejects BOTH physical jams (6x5_1, 6x7_8); 6x5_1 now dies at
      reflection (upstream of twist) as predicted. NEW predictions to fold: **all 28 distinct 6x6
      2+1 now JAM (0 foldable on 6x6)** incl. the old `6x6_7` 'both-FOLD' control — if 6x6_7 folds,
      the segment-coincidence predicate is too strict. Caches regenerated; sheets show the vectors.
      3. **`6x6_13`** — both: JAM (tests twist criterion vs reality, model-independent)
      4. **`6x6_7`** — both: FOLD (positive control)
      Outcome table: (folds, jams) → strand wins; (jams, folds) → hybrid wins;
      (folds, folds) → both wrong; (jams, jams) → need more theory.
      ⚠ 2026-06-08 CORRECTION: earlier "HYBRID FALSIFIED, strand survives" (from 6x7_8 alone) is
      SUPERSEDED — 6x5_1 jam means strand's raw twist prediction is also wrong; resolution hinges
      on the reflection-gate fix (6x5_1 should never have been a twist candidate).
      PNGs: `report/foldsheets/{6x5_1,6x7_8,6x6_13,6x6_7}_path.png` (folding-path); PDFs same names.
- [ ] **Fold all 13 make-sheets, fill `results/twoplus1_labels.json`** (`report/foldsheets/`).
      Per-sheet checklist below — cut slits, fold creases in order, tick FOLD (collapses flat to
      the 3-cell footprint stack) or JAM (self-blocks). The **strand** column is the prediction
      under test (canonical-strand Tw: `Tw=0` → FOLD, `Tw=±720` → TWIST/JAM). Any mismatch
      falsifies or refines the criterion. ⚑ = the two cases where the hub-exception **hybrid**
      model disagrees with the strand model (model-selection deciders — fold these first).

      | # | sheet | shape | K | strand pred | model conflict | physical (FOLD/JAM) |
      |---|-------|-------|---|-------------|----------------|---------------------|
      | 1 | `6x4_1`  | L-H  | 8  | FOLD  | — | [ ] |
      | 2 | `6x4_2`  | L-V  | 8  | FOLD  | — | [ ] |
      | 3 | `6x5_1`  | L-H  | 10 | FOLD  | ⚑ hybrid JAM | [x] **JAM** (physical) → strand ✗ / engine refl-gate FIXED (now rejects) |
      | 4 | `6x5_2`  | L-H  | 10 | FOLD  | — | [ ] |
      | 5 | `6x5_3`  | L    | 10 | FOLD  | — | [ ] |
      | 6 | `6x5_4`  | L    | 10 | FOLD  | — | [ ] |
      | 7 | `6x5_5`  | L    | 10 | FOLD  | — | [ ] |
      | 8 | `6x6_7`  | L-H  | 12 | FOLD  | refl-JAM (2026-06-09 pred; all 6x6 2+1 jam) | [ ] |
      | 9 | `6x6_1`  | L-V  | 12 | FOLD  | — | [ ] |
      |10 | `9x4_8`  | Rect | 12 | FOLD  | — | [ ] |
      |11 | `6x6_13` | L    | 12 | TWIST | both JAM (model-indep.) | [ ] |
      |12 | `6x6_18` | L    | 12 | TWIST | — | [ ] |
      |13 | `6x7_8`  | L    | 14 | TWIST | ⚑ hybrid FOLD | [x] **JAM** (2026-06-08) → strand ✓ / hybrid ✗ |

      Strand-criterion tally on record: 10 FOLDABLE (Tw=0), 3 TWISTED (Tw=±720). PNGs exist for
      the 4 ⚑/control deciders; all 13 have PDFs.
- [ ] **Exhaustively check (physically) 6×5 grids** *(lead)*. All five 6×5 2+1 solutions are
      in the sheet set; strand criterion predicts ALL foldable — contradicting the earlier
      non-foldable suspicion (and the hybrid disagrees on #1) — highest-information folds.
- [ ] **1+1+1 single-loop conjecture**: adjacent-pair loops ≡ Tw=0 (2026-06-07 finding,
      624/624 on accepted solutions). Test on the **pre-twist candidate pool** (population
      conditioned only on exit+parity+reflection) before trusting the reduction to one loop.
- [ ] **Q6 mod-12 conjecture**: generate 6×9 (54 ≡ 6 mod 12 → predict ZERO 1+1+1). The 8×6
      positive prediction is already confirmed by the cache (244 1+1+1) — log it.
- [ ] **Q2 wrapping**: run `py/analyze_wrap.py` on 8×6 L 1+1+1 (extend 18/18 clean-wrap to a
      third grid); the forward *footprint-forced ring partition* lemma is still the missing
      piece of the proof.
- [ ] **Formalize degenerate-seam handling**: the diagonal hub closure is a validated ansatz,
      not a theorem — and it is load-bearing (1+1+1: all twist lives on the DIAG-seam loop;
      2+1: the DIAG strand carries a quantized ±360 artifact). Candidate fix: route the loop
      closure through the footprint middle cell (stay on-lattice) or derive a hub correction.

## Physical / explanatory models

- [ ] **Create physical models to explain bipartite tiling necessity** *(lead)* — card/paper
      demonstrators showing why the checkerboard 2-coloring (σ alternation = mountain/valley
      rhythm) is forced, tying into the explainer Track A figures (`explainer/svg/A6`, `A9`).

## Code chores

- [ ] **Findings-DB revamp** *(john, 2026-06-18)*. Restructuring the findings store. Independent
      seed already captured: **`results/to_test_folds.json`** (schema `to_test_folds/v1`, 13 records,
      builder `experimental/build_to_test_store.py`) — the 13-case physical to-test queue, fully
      self-contained + re-importable (grid-fitting replayable coords + foldOrder, enginePredicted
      [refl/parity only — twist undecided for 2+1], 4-engine twistEngines, joined physical label).
      Verified: all 13 replay in-grid, re-canonicalize to the queue hash, re-import clean vs
      `findings.py validate_finding`. NOTE excludes the 4 newer to_fold/ deciders (8x6#202, 6x6#19,
      6x6#5); 6x6#19/#5 are on the 6x6 grid already in the file, so it is not the complete 6x6 set.

- [ ] **Clean up the 3-stack code** *(lead)*. ⚠ 2026-06-09: the "drop redundant `reflection_check`
      (output-preserving)" item is RETRACTED — that held only for the mis-ported label gate; the
      corrected orientation-aware gate is BINDING (drops all 28 6x6 2+1 + 51/292 1+1+1) and is NOT
      output-preserving. Remaining candidates: fold the validated
      analysis scripts' shared replay/loop helpers into one module (`analyze_twist` /
      `analyze_loop_seams` / `analyze_2plus1_reduction` all re-implement replay + center-path);
      port the 2+1 canonical-strand twist into `py/search.py` / `search.js` so `verdict.twist`
      is no longer `null` for 2+1 (after physical labels confirm).
- [ ] **Test the 4 experimental 2+1 twist engines** (2026-06-16, `experimental/`). Built
      No / Jump / Normal / Partial-decomp engines (one folder each, shared `common.py`) +
      `run_2plus1_testing.py` which scans ALL caches → **264 2+1 across 7 grids** →
      `results/2+1 testing/` (`all_2plus1.json` + 9 curated `<grid>_<id>.json` qualitative classes;
      n2units is a recorded range, not a splitter + `_summary.json`). On-data findings:
      (i) `normal == jump` **264/264** → filled == jump confirmed on data everywhere;
      (ii) the 3 sound engines (no/jump/normal) agree and **reject EXACTLY 1 of 264 — `8x6#202`**, a
      genuinely twisted 2+1 (Tw=−720, robust to both strand idx and the full centroid, so NOT a
      hub/strand artifact) that PASSED reflection+parity+exit → a **reflection false-pass** the twist
      gate would catch; (iii) on the other 263 reflection already forces Tw=0 (936° artifact absent),
      so **partial decomp is the sole differentiator**: flat vs overhang (6×6: 24/16, every L
      overhang, flat only Rect; split varies by grid), some overhangs *hub-removable* vs *intrinsic*;
      partial uniquely flags `8x6#202` `mixed` (−507 = −720 twist + 212 overhang). 0/40 6×6 have
      physical labels in `foldfindings.json` (no ground truth — gate-survivors only).
      **ACTION (paper, ranked):** (1) **`8x6#202`** — the lone all-engine reject: does it JAM
      (→ reflection false-passes a real jam, twist gate earns its keep) or FOLD (→ Tw=−720 is a
      false-reject, twist theory needs work)? Highest information. (2) an overhang case — a flat
      (`6x6_19`), a hub-removable overhang (`6x6_5`), an intrinsic overhang (`6x6_1` L / `6x6_18`
      Rect): does overhang fold with a real protruding strip (lead's hypothesis) or jam? Decides
      whether partial decomp earns a place beside the jump gate.
      ⇒ **Candidate ideas ranked + vetted (2026-06-16, `docs/research/2plus1_twist_candidates.md`):**
      53-agent research workflow + 2-skeptic adversarial vet. Headline: **Model B IS the answer**;
      the two "new math" directions (Gauss-Bonnet holonomy, footprint-middle hub routing) are FATAL
      (re-inject atan½ / break filled==jump). Real work = operationalize + validate. Recommended
      sequence: **fold `8x6#202` first → if JAM, wire Model B behind `opts['twist_2plus1_model_b']`**
      (with a seam-diagnosis guard: both-strands-DIAG ⇒ fall to `decided=False`). Fold bundle parked
      at `results/2+1 testing/to_fold/` (8x6#202, 6x6#19 flat control, 6x6#18 intrinsic + 6x6#5
      hub-removable overhang).
- [x] **Annotated learning copy built (2026-06-16, `annotated-codebase/`, GITIGNORED + regenerable).**
      Concept-grouped teaching snapshot of the engine — search / fold-geometry / twist-engines /
      reference-validation — every core function annotated (docstring + I/O + Semantic + worked
      example) with unit + fidelity (copy==real `py/`) + integration tests. 46 files;
      `.venv/Scripts/python.exe -m pytest annotated-codebase/` → **280 passed, 4 skipped** (opt-in
      slow via `ANNOTATED_SLOW=1`). Hand-spot-checked: every number in `twist-engines/WORKED_EXAMPLES.md`
      (6x4#1 replay, strand vs centroid, `pick_canon_idx`, filled==jump 264/264, jump frac-turns 0 vs
      centroid 564) reproduced byte-exact from the real engine. NOT source of truth — `py/` is.
- [x] **Verify 2+1 parity + twist math vs 2-stack reference** (2026-06-16, `tests/2+1/verify_2plus1_math.py`
      + `experimental/VERIFICATION.md`, read-only; py/ untouched, all 2+1 math in `experimental/`).
      **A** twist formula faithful (665 int loops + 735 1+1+1 pairs, 0 mismatch vs `twostack.twist_value`
      AND shipped `_pair_loop_twist`; partial's atan½ loops diverge only by twostack int-rounding, which
      hides overhang). **B** nH/nV parity = checkerboard-σ necessary cond (509 sols, 0 disagree, bridge
      `x_flip==nH%2` holds, m·n even). **C** all 3 physical JAMs predicted JAM — 6x5#1/6x6#1 by reflection
      (Tw=0), 6x7#8 by reflection AND Tw=720 (resolves the 6x7#8 lab conflict: corrected reflection ALSO
      rejects it → no physical case is twist-only). **D** reflection rejects many twist passes (refl-only
      44 on 6x6, 7 on 6x7) so reflection is binding; but twist-only (passes refl+parity, Tw≠0) = **0** on
      6x6 & 6x7 — only `8x6#202` is twist-only across all 264 (physically UNLABELLED). ⇒ "reflected≈valid"
      is real & not a bug: it's the TWIST gate that's near-redundant on tested grids; its standalone case
      rests entirely on folding `8x6#202` (= action #1 above). Shipped engine still doesn't twist-gate 2+1.
- [ ] **Repo deep-dive / debloat pass** *(lead, 2026-06-16)*. ss2 debloated but bloat remains —
      stray scripts + stale artifacts to sort; lead to audit the tree and prune. While there: fold
      the validated analysis scripts' shared replay/loop helpers into ONE module — `experimental/
      common.py` was lifted from `tests/analyze_twist_2plus1_compare.py`, which itself duplicates
      `analyze_twist` / `analyze_loop_seams` / `analyze_2plus1_reduction`; consolidate so the
      engines + harness import a single geometry/twist core.
- [ ] git: repo has uncommitted analysis scripts + doc updates from 2026-06-07.

## Research extensions (lead)

- [~] **Extend 3-stack ideas to right triangles, equilateral triangles, and hexagons.**
      *Equilateral PoC done + SUCCEEDS (2026-06-08, `py/tri/`):* math ports exactly — bipartite σ
      (UP/DOWN), `_reflect_point` folds, closed-loop twist (6-ring → γ=120°, Tw=0, clean) all
      verified — and **closing 3-stack folds EXIST at K≥10** (proof-by-exhaustion: 0 closing for
      K=2..9, 2 at K=10; the earlier "no closing fold" was a finite-size artifact of K≤8). The two
      K=10 folds have clean twists (AB=±720, BC=∓720, AC=0) and are twisted → criterion discriminates.
      *Next on triangles:* (a) find a *foldable* (all-loops Tw=0) example — K=12 hole-free hunt
      running (`py/tri/hunt_foldable.py`, ~30 min); if empty, **K=14 (even only) is the next
      target — NOT today**: brute force is ~19 h (40×/+2K growth, ~280K it/s), so first write a
      smarter disjoint-path solver (target a translated/rotated exit hub + prune dead branches +
      exploit forced mid-chain/symmetry) → likely a few hours, then run overnight.
      (b) port the 2+1 rhombus-ribbon reduction to K≥10; (c) physical fold of a predicted example.
      *Still TODO (general port):* generalised reflection geometry in `fold.py`/`fold.js`,
      per-tiling footprint enumeration, σ/γ tables per polygon; right triangles + hexagons-as-cells.
      2-stack reference builds these lattices
      (`resources/twist_reference_code/kirigami-programme/python files/lattice.py`). Cf. `context.md` Q5.
