# TODO — lab queue

Running list. Validation queue first (ordered by information value), then code chores, then
research extensions. Cross-references: `context.md` (Q1–Q7), `LAB_LOG.md` (findings),
`FOLDING.md` (fold protocol).

## Validation queue (the 2+1 / twist theory decider)

- [ ] **PRIORITY FOLDS — model selection (2026-06-08).** Two angle-clean 2+1 invariants now
      conflict (filled-strand vs hub-exception hybrid, 16/303 disagree); two conflicts are
      already printed sheets. Fold these FIRST, in order:
      1. **`6x5_1`** — strand: FOLD / hybrid: JAM
      2. **`6x7_8`** — strand: JAM / hybrid: FOLD
      3. **`6x6_13`** — both: JAM (tests twist criterion vs reality, model-independent)
      4. **`6x6_7`** — both: FOLD (positive control)
      Outcome table: (folds, jams) → strand wins; (jams, folds) → hybrid wins;
      (folds, folds) → both wrong; (jams, jams) → need more theory.
      PNGs: `report/foldsheets/{6x5_1,6x7_8,6x6_13,6x6_7}.png`; PDFs same names.
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
      | 3 | `6x5_1`  | L-H  | 10 | FOLD  | ⚑ hybrid JAM | [ ] |
      | 4 | `6x5_2`  | L-H  | 10 | FOLD  | — | [ ] |
      | 5 | `6x5_3`  | L    | 10 | FOLD  | — | [ ] |
      | 6 | `6x5_4`  | L    | 10 | FOLD  | — | [ ] |
      | 7 | `6x5_5`  | L    | 10 | FOLD  | — | [ ] |
      | 8 | `6x6_7`  | L-H  | 12 | FOLD  | control (both FOLD) | [ ] |
      | 9 | `6x6_1`  | L-V  | 12 | FOLD  | — | [ ] |
      |10 | `9x4_8`  | Rect | 12 | FOLD  | — | [ ] |
      |11 | `6x6_13` | L    | 12 | TWIST | both JAM (model-indep.) | [ ] |
      |12 | `6x6_18` | L    | 12 | TWIST | — | [ ] |
      |13 | `6x7_8`  | L    | 14 | TWIST | ⚑ hybrid FOLD | [ ] |

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

- [ ] **Clean up the 3-stack code** *(lead)*. Known candidates: drop the redundant
      `reflection_check` (proven output-preserving, `context.md` Q4); fold the validated
      analysis scripts' shared replay/loop helpers into one module (`analyze_twist` /
      `analyze_loop_seams` / `analyze_2plus1_reduction` all re-implement replay + center-path);
      port the 2+1 canonical-strand twist into `py/search.py` / `search.js` so `verdict.twist`
      is no longer `null` for 2+1 (after physical labels confirm).
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
