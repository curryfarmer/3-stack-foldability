# Baseline conditions for 3-stack foldability

*Compiled 2026-06-08. Cross-references: `context.md` (Q1–Q7), `LAB_LOG.md` (dated findings),
`hypothesis_2plus1_reduction.md`, `proof_q2_wrapping.md`, the enumerator (`py/search.py` /
`search.js`) and fold engine (`py/fold.py` / `fold.js`). Python is authoritative; JS is the
cross-checked port.*

This note separates the **hard baseline** (the gates that define a valid 3-stack pattern,
twist excluded) from the **soft / conjectured** layer (statements that hold over every example
checked but are not exhaustively proven). The twist criterion (`Tw=0`) is intentionally kept
out of Part A — it is the one rule that does **not** gate the enumerator (annotation only for
1+1+1, `null` for 2+1) — and lives entirely in Part B.

Each item carries an **honesty tag**, because "enforced by the code" is not the same as
"proven":

- **PROVEN** — a genuine necessary condition with an argument.
- **DEFINITIONAL** — true by construction; it *defines* what a valid candidate is, not a theorem.
- **EMPIRICAL** — settled by exhaustive computation, no closed-form proof.
- **HEURISTIC** — a gate the code applies for convenience, not claimed necessary.

---

## A. Hard baseline conditions (everything except twist)

### A1. Arithmetic gates

| Condition | Formula | Tag | Where |
|---|---|---|---|
| Divisible by 6 | `m·n ≡ 0 (mod 6)` | **PROVEN** necessary | `py/search.py:422`, `search.js:532` |
| Chain length even | `K = m·n/3`, `K` even | **PROVEN** (corollary) | `py/search.py:425`, `search.js:534` |
| Min height gate | `n ≥ 4` | **HEURISTIC** (code: "conjectured rejection") | `search.js:535` |

**Why mod 6 is necessary.** A 3-stack pattern partitions the grid into three equal chains, so
`m·n` must be divisible by 3. The fold path of each chain is an even-length bipartite Hamiltonian
walk (alternating checkerboard colours), so the chain length `K = m·n/3` must be even — an extra
factor of 2. Hence `m·n ≡ 0 (mod 6)`. The real minimum grid sizes are not `n ≥ 4`; that gate is
heuristic and the true floors are resolved empirically (Part B, Q7).

### A2. Decomposition and tiling — DEFINITIONAL

- Every pattern is exactly one of **1+1+1** (three 1-chains, `K` cells each) or **2+1** (one
  2-chain of `2K` + one 1-chain of `K`). `search.js:77–142`, `py/search.py:69–113`
- A 2+1 requires the two 2-chain base cells to be **edge-adjacent** (Manhattan distance 1).
  `search.js:87`
- The chains **partition** the grid exactly: union covers all `m·n` cells, with no gap and no
  overlap. `search.js:185`

### A3. Footprint — DEFINITIONAL, plus one PROVEN verdict gate

- A footprint is 3 cells in one of two shapes: **L** (corner + two arms, 4 rotations) or
  **Rect / I** (3 collinear cells, horizontal or vertical). `search.js:13–73`, `py/search.py:20–63`
- Default anchor at the grid origin (`min x = min y = 0`) unless `allowNonCorner` is set.
  `search.js:31`
- **Exit-footprint congruence (PROVEN verdict gate).** After folding, each chain's final
  placement must be 3 cells whose bounding box is congruent to the *start* footprint shape
  (`(dx,dy)=(2,0)` or `(0,2)` → Rect; `(1,1)` → L; otherwise reject). A hard filter, not just
  enumeration. `search.js:352–373`, `py/search.py:277–295`

### A4. Vector / reflection conditions

**Reflection geometry — DEFINITIONAL (this *is* a fold).**

- Scalar mirror across a crease at continuous boundary `c`: `reflect_scalar(v, c) = 2c − 1 − v`.
  `py/fold.py:16`
- Cell reflection: a horizontal fold sends `(x, y) ↦ (2c−1−x, y)`; a vertical fold sends
  `(x, y) ↦ (x, 2c−1−y)`. `py/fold.py:22`
- The crease boundary is read off the active placement's bounding box: `R → xMax+1`, `L → xMin`,
  `D → yMax+1`, `U → yMin`. `py/fold.py:49`
- **In-bounds (hard).** Every reflected cell must lie in `[0,m) × [0,n)`, else the fold is
  rejected. `py/fold.py:61`
- **No overlap (hard).** A new placement's cells must not collide with any already-reserved cell.
  `search.js:277`
- Vector reflection (edges carry orientation, used by the reflection check):
  `EDGE_FLIP_H = {T:T, B:B, L:R, R:L}`, `EDGE_FLIP_V = {T:B, B:T, L:L, R:R}`, with the sign
  flipping on edges perpendicular to the fold axis. `py/fold.py:28`

**Parity filter — the actual binding acceptance gate (vector-derived).**

- Orientation-aware rule: in each chain, folds whose crease line is **parallel** to the
  inter-block (A/B) seam must occur an **even** number of times. For 2+1: if A,B are
  horizontally adjacent require `nH` even; if vertically adjacent require `nV` even.
  `py/search.py:245`
- 1+1+1 legacy form: per chain `nH` even **and** `nV` odd. `search.js:336`
- This parity check is what actually decides acceptance for the structural layer (Q4).

**Reflection-coincidence check — PROVEN REDUNDANT.**

- The check drives a canonical base vector `(edge T, sign +1)` through each chain's cumulative
  transform chain and requires all chains' final `(edge, sign)` to agree. `py/search.py:300`
- Q4 contingency analysis (6 grids) found **0** cases of `parity✓ ∧ reflection✗` and 54 of
  `parity✗ ∧ reflection✓`: i.e. `parity ⟹ reflection` always, and reflection is strictly looser.
  Dropping the reflection check is **output-preserving**. Not yet acted on (code chore in
  `TODO.md`). `context.md` Q4.

> **Twist is excluded here by design.** `Tw=0` is the only criterion that does not gate the
> enumerator; see Part B.

---

## B. Soft / conjectured / observed-not-proven conditions

Each holds over every example tested but is **not** exhaustively proven. Status uses the repo's
own vocabulary. The single biggest gap: the entire twist layer is computationally validated only
— **no case is physically confirmed yet** (`results/twoplus1_labels.json` is all-null).

| # | Condition | Statement | Evidence on record | Status | Refs |
|---|---|---|---|---|---|
| Q6 | **mod-12 existence** | a grid admits a **1+1+1** solution iff `m·n ≡ 0 (mod 12)` (equivalently `K ≡ 0 mod 4`) | 6/6 grids: positives 6×4, 6×6, 9×4, 12×4, 8×6 (244 sols); negatives 6×5, 6×7 (0). Replaces the falsified `(m−3)(n−3) ≥ 9` boundary (6×7 has `12 ≥ 9` yet zero 1+1+1) | **Conjectured**, cache-clean; *why* `K≡0 mod 4` is unknown | `LAB_LOG` 2026-06-04; `context.md` Q6 |
| Q2 | **L-1+1+1 clean-wrap** | exactly 2 of the 3 chains cover the entire boundary ring; the 3rd stays interior (`ring R = 2m+2n−4`, interior spill `2K−R`) | 18/18 (6×6 + 12×4); contrast 0/14 for 2+1 — wrapping is 1+1+1-specific | **Observed + strong-partial proof**; missing the *footprint-forced ring-partition* lemma | `LAB_LOG` 2026-06-04; `proof_q2_wrapping.md`; `context.md` Q2 |
| 1+1+1 | **Pairwise-loop twist** | foldable ⟺ `Tw(L_ij) = 0` on all three theta loops (`Tw = (1/4π)Σ σ(v)γ(v)`) | 68/68 solutions; 936/936 loops land on `{0, 720}`, no fractional twist | **Computationally validated, physically pending** | `context.md` Q1; `LAB_LOG` 2026-06-04/-07; `EXPLAINER.md` §2.3 |
| 1+1+1 | **Single-loop reduction** | only the non-adjacent (degenerate-seam) pair can carry twist; adjacent-pair loops are always `Tw=0`, so the 3-loop test may collapse to one | 624/624 adjacent loops = 0; all 55 nonzero twists sit on the non-adjacent pair | **Conjectured** on the *accepted* pool; must be tested on the **pre-twist** candidate pool | `LAB_LOG` 2026-06-07; `TODO.md` |
| 2+1 | **Canonical-strand reduction** | collapse the rigid 2-chain to its unit-seam strand (filled half-tile reduction); foldable ⟺ `Tw(loop) = 0` on the reduced holey-grid loop | 303/303 pass all self-checks; `Tw(filled) == Tw(jump)` exactly, 303/303; canonical twist ∈ {0, ±720} | **Validated on cache, physically pending** | `hypothesis_2plus1_reduction.md` §3b; `LAB_LOG` 2026-06-07/-08 |
| 2+1 | **Hub-exception hybrid** | alternative domino-tiling model with a 2×1→1×1 transition at the hubs; angle-clean | 303/303 axis-aligned, but disagrees with the strand model on 16/303 (all full-twist deltas) | **Ansatz, inequivalent** — not the criterion; used only to drive the model-selection folds | `LAB_LOG` 2026-06-08 |
| — | **Diagonal hub-seam closure** | the diagonal (L) / 2-jump (Rect) hub seams inject ±90/±270 artifacts that cancel against body turns, keeping `Tw` an integer multiple of 360 | 936/936 loops ∈ {0, 720}; 0 fractional turns | **Validated ansatz, NOT a theorem** — the paper's `Tw` is defined for unit-step loops only; load-bearing | `LAB_LOG` 2026-06-07; `TODO.md`; `resources/twist_diagnosis.md` |
| Q3 | **Interior-chain recipe** | if Q2 forces 2 chains onto the perimeter, the 3rd chain's interior path is largely determined | depends entirely on Q2 | **Conjectural**, blocked on Q2 (old comb+zigzag archetype retired — was archetype-specific) | `context.md` Q3 |
| — | **Convention invariance** | σ-phase, γ-sign, and orientation flips never change a verdict, given consistency | 0 verdict changes across 303 (2+1) + 936 (1+1+1) | **Validated** | `LAB_LOG` 2026-06-07/-08 |
| Q7 | **Minimum grid size** | L any-decomp floor = 4×3 (area 12, *geometric*); Rect floor is gate-imposed (drops to 3×1 under relaxed gates); L 1+1+1 `Tw=0` floor = 5×6 | exhaustive sweep ≤ area 30, all dims ≤ 20 (`py/sweep_minsize.py`) | **Empirically resolved**, no closed-form proof | `context.md` Q7; `LAB_LOG` 2026-06-04 |

### What would upgrade the load-bearing soft items to proven

- **Twist (1+1+1 and 2+1):** physically fold the curated ground-truth set (13 sheets,
  `report/foldsheets/`) and fill `results/twoplus1_labels.json`; confirm `Tw=0 ⟺` folds flat.
  This is the single decider for the whole twist layer.
- **mod-12 (Q6):** generate 6×9 (`54 ≡ 6`, predict zero 1+1+1) for a 7th data point; then derive
  why `K ≡ 0 (mod 4)`.
- **Wrapping (Q2):** prove the footprint-forced ring-partition lemma (`proof_q2_wrapping.md`).
- **Diagonal hub-seam:** give the seam closure a discrete framing on non-unit-step lattice paths,
  or route the closure through the footprint middle cell to stay on-lattice.

---

*Twist excluded from Part A per the working definition of "baseline." The honest summary: only
the mod-6 arithmetic (A1) and the reflection-redundancy result (A4) are genuine theorems; the
rest of Part A is definitional geometry or a heuristic/empirical floor, and the entire twist
apparatus (Part B) is validated on the cache but awaits physical ground truth.*
