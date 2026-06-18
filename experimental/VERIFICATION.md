# VERIFICATION — 3-stack parity + twist math vs the 2-stack reference

Read-only audit answering the lead's question: *"the set of reflection-passing 2+1 ≈ the set of
valid solutions — are the gates ineffective? Verify each engine's math against the 2-stack
reference, with explicit parity and twist checks, then apply those filters to the physical ground
truth."*

Harness: [`tests/2+1/verify_2plus1_math.py`](../tests/2+1/verify_2plus1_math.py) (run as a script).
Machine output: [`results/2+1 testing/_verification.json`](../results/2+1%20testing/_verification.json).
Reference oracles (imported **read-only**, never mutated): `py/twostack.py` (`twist_value`,
`reflection_cut`), `py/fold.py` (`reflection_verdict`), `py/lattice/square.py` (`parity_check`),
`py/search.py` (`_pair_loop_twist`). All 2+1 math lives in `experimental/` (`common.py` + the 4
engines). **No engine or gate was changed.**

## TL;DR

| Part | Question | Verdict |
|---|---|---|
| A | Is the twist formula the 2-stack reference's, unaltered? | **PASS** — 0 mismatches |
| B | Is the nH/nV parity gate σ-sound (a checkerboard necessary condition)? | **PASS** — 0 disagreements |
| C | Do the gates reproduce the 3 physical JAM ground truths? | **PASS** — all 3 predicted JAM |
| D | Are reflection and twist independent, or is the redundancy real? | reflection carries the load; twist is **near-redundant** on tested grids (1/264 exception) |

**Bottom line for the lead's worry:** the suspicion is half-right, and the math is *not* broken.
*Reflection* (with parity) is doing real work — it rejects 60+12 closing candidates on 6×6/6×7 and
catches 2 of the 3 physical jams. It is **not** redundant. What *is* near-redundant is the **twist**
gate: on every reflection+parity survivor of 6×6 and 6×7, Tw is already 0, so twist adds nothing
there. Across all 264 cached 2+1 (7 grids), the lone reflection+parity-passer with Tw≠0 is
**8x6#202** (Tw=−720) — the single witness that the gates are not *formally* identical. So
"reflected ≈ valid" is a real property of these grids, not a bug — and separately, the shipped
engine does not even evaluate 2+1 twist (`search.twist_check` stubs `decided=False`), so twist
currently gates nothing for 2+1.

## Part A — twist formula is the reference's, unaltered

For every cached 2+1 (all 4 path-builders) and every cached 1+1+1 (pairwise chain-centroid loops),
Tw was computed two ways on the **identical ordered point list** `body + reversed(path1)`:
experimental `common.loop_tw` (float, round-6) vs `twostack.twist_value` (the reference's exact
`round(deg)·2`, odd−even convention). For 1+1+1 the shipped `search._pair_loop_twist` was also
compared.

- **665 integer (90°-multiple) loops — 0 mismatches.** no / jump / normal decomp and the flat
  partials reproduce `twostack.twist_value` exactly.
- **735 1+1+1 pairwise loops — 0 mismatches** vs `twostack.twist_value` **and** vs the shipped
  `_pair_loop_twist`. The 1+1+1 twist the engine already ships is byte-faithful to the 2-stack.
- **391 partial-decomp atan(½) loops — 117 expected int-rounding gaps.** The only divergence: where
  partial's 1↔2-unit seam produces a (1,2)-slope turn, the true angle is `atan(½)=26.565°`
  (→ doubled 53.13°), but `twostack.twist_value` rounds **per vertex** to 27° (→ 54°), so e.g.
  106.26° reads as 108°. This is not a formula drift — it is the reference's integer convention
  **suppressing** the overhang signal. Implication: a shipped int-rounded twist cannot see the
  overhang class; the experimental float path is required to detect it.

⇒ The doubled-turn / odd−even twist invariant is the 2-stack reference's, unchanged. The 3-stack
generalisation (pairwise chain loops in place of the single Hamiltonian circuit) introduces no new
arithmetic. `filled == jump` (264/264, recorded elsewhere) is the evidence the 2-chain strand
reduction stays on-lattice and 2-stack-faithful.

## Part B — parity gate is the checkerboard-σ necessary condition

The per-chain `nH`/`nV` even/odd rule (`SquareLattice.parity_check`) has **no 2-stack analogue**
(2-stack parity is only `m·n` even). So it was checked for σ-soundness, not just "ported": a new
helper `common.parity_predicate_geom` recomputes the parity verdict from the **replayed geometry** —
each L/R fold reflects x once (flips x-parity), each U/D fold reflects y once (flips y-parity), so
the checkerboard σ=(−1)^(x+y) flips on every fold — and compares to the shipped gate.

- **509 cached solutions — 0 disagreements** between `parity_check` (arrow-letter counts) and the
  geometric σ recompute.
- **0 bridge-identity failures**: `x_flip == nH%2` and `y_flip == nV%2` for every chain — the
  arrow counts are geometrically grounded (no replay/encoding drift).
- **`m·n` even on every grid** (the 2-stack parity) — trivially satisfied.

⇒ The nH/nV rule is exactly *"each chain's strand returns to a prescribed x/y parity relative to its
base"* — the checkerboard necessary condition for the K placements to stack onto the footprint. It
is sound and not arbitrary.

## Part C — the 3 physical JAM ground truths (the deciders)

`results/foldfindings.json` carries 3 physical JAM labels (and zero FOLD labels — one-sided ground
truth). Each was matched to a closing candidate by canonical hash and given the full **independent**
gate tuple (exit / parity via `parity_check` / reflection via `reflection_verdict` / twist via the
jump engine + `twostack.twist_value`):

| finding | decomp | parity | reflection | twist (jump) | caught by | physical |
|---|---|---|---|---|---|---|
| `6x5#1` | 2+1 | pass | **FAIL** | 0 | reflection | JAM ✓ |
| `6x6#1` | 2+1 | pass | **FAIL** | 0 | reflection | JAM ✓ |
| `6x7#8` | 2+1 | pass | **FAIL** | **720** | reflection **and** twist | JAM ✓ |

All 3 predicted JAM == physical JAM. **The 6x7#8 lab-note conflict is resolved:** the two old notes
("corrected reflection rejects it" vs "it's a twist-stage jam") are *both* true under the current
engine — the 2026-06-09 segment-coincidence reflection gate **already** rejects 6x7#8 (its chains'
hub-crease images land on different grid lines), **and** its jump-strand Tw=720 independently. So
6x7#8 is **not** a twist-only decider: there is no physical ground-truth case that twist alone
catches. The twist gate's unique value (8x6#202, below) remains physically **untested**.

## Part D — gate (in)dependence on the pre-gate population

The cache is post-reflection, so it *looks* like twist adds nothing. The honest test enumerates
**all** closing candidates (exit-passers, before gating) and builds the 3-gate breakdown for 2+1
(twist computed independently via the jump engine):

| grid (enum) | closing | 2+1 | refl+parity+Tw0 | **twist-only** reject<br>(refl+parity pass, Tw≠0) | reflection-only reject<br>(refl fail, Tw=0) | parity fails | reflection fails |
|---|---|---|---|---|---|---|---|
| 6×6 (non-corner) | 376 | 134 | 40 | **0** | 44 | 46 | 60 |
| 6×7 (corner) | 399 | 57 | 33 | **0** | 7 | 16 | 12 |
| 8×6 (cached witness) | — | — | — | **1** (`#202`, Tw=−720) | — | — | — |

- **Reflection is independent and load-bearing**: 44 (6×6) + 7 (6×7) candidates fail reflection but
  have Tw=0 — jams reflection catches that twist would pass. Reflection is *not* redundant.
- **Twist is near-redundant on tested grids**: 0 candidates pass reflection+parity yet fail twist on
  6×6 or 6×7. The 6×6 `refl+parity+Tw0 = 40` exactly equals the cached foldable-2+1 count → the cache
  *is* the reflection+parity+exit survivor set, and twist would not shrink it.
- **One global exception**: `8x6#202` is the sole 2+1 across all 264 cached that passes
  reflection+parity+exit yet has Tw≠0 (−720, robust to strand choice + full centroid). It proves the
  gates are not *formally* identical — but it is a single case and **physically unlabelled**.

## What this means / open items

1. **The math is faithful.** No formula or parity drift from the 2-stack reference (A, B).
2. **"Reflected ≈ valid" is real, and it's a statement about the *twist* gate, not reflection.**
   On 6×6 and 6×7 the reflection+parity survivors already have Tw=0, so twist is redundant there.
   Reflection itself rejects plenty (it is the binding 2+1 gate).
3. **Twist's standalone value rests on one unlabelled case.** `8x6#202` is the only reflection+parity
   passer with Tw≠0. Whether twist "earns its keep" hinges on folding it: JAM ⇒ reflection
   false-passes a real jam and the twist gate is justified; FOLD ⇒ Tw=−720 is a false-reject and the
   twist theory needs work. This is the highest-information paper fold (already TODO action #1).
4. **The shipped engine does not twist-gate 2+1** (`search.twist_check` returns `decided=False` for
   any 2-chain), so `verdict.twist` is `null` for all 2+1 and the cache was admitted by
   exit+parity+reflection only. Wiring Model B in is the existing TODO chore — gated on the 8x6#202
   physical label, which this round only *measures* the case for.

*Out of scope this round (flagged, not done): no gate/engine change; no new physical folds; the
FOLD-side ground-truth gap (only JAM labels exist) stays open.*
