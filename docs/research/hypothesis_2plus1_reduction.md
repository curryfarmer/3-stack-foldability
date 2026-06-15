# Hypothesis — the 2+1 twist by half-tile reduction of the 2-chain

*Status: **computationally validated on the cache 2026-06-07** (`py/analyze_2plus1_reduction.py`,
303 solutions, 7 grids) — with two §2 corrections and §5.1 resolved to the canonical-strand rule
(see bracketed VALIDATION notes below). Physical confirmation still deferred to the ground-truth
set (`FOLDING.md`, `results/twoplus1_labels.json`).*

## 0. One-line statement

> **Collapse the rigid 2-chain to a single representative 1-chain by deleting half of its
> tiles. The surviving 1-chain reproduces the entire folding motion of the 2-chain, so the
> 2+1 problem becomes a chain-vs-chain problem on a *holey* grid — to which the existing
> parity and twist machinery (`σ = (−1)^{x+y}`, `γ` at L-corners, `Tw(L_{ij}) = 0`) applies
> verbatim.**

## 1. Why 2+1 was stuck, in one paragraph

The 1+1+1 case is settled: three 1-chains meet at two rigid footprint hubs (a theta graph),
and foldability is `Tw(L_{ij}) = 0` on all three pairwise loops, each loop's twist being the
paper's closed-loop sum `Tw = \tfrac{1}{4\pi}\sum_v \sigma(v)\,\gamma(v)`. That computation
needs an honest **panel path** — a lattice walk whose every turn is a multiple of 90°, so that
`γ ∈ {0, ±π}` and `Tw` lands on a multiple of `2π`. The 2-chain breaks this: it is a rigid
**domino** (base = two adjacent cells; every fold reflects both cells together — `search.py`),
so the obvious "one point per placement" path is the domino **centroid**, which moves *between*
lattice lines. Its turns are not 90° multiples, and indeed the centroid loop returned the
non-physical `936°` (not a multiple of `360°`) — the signal that the centroid is not a real
panel path. The panel-level Hamiltonian order *inside* the width-2 ribbon was therefore treated
as an unsolved inverse problem.

## 2. The reduction

A rigid domino has two cells at every step; call the two columns of the ribbon **strand P** and
**strand Q**. Because the domino is rigid, the two strands move in perfect lockstep: at every
fold `Q` is just `P` shifted by the fixed in-ribbon vector `+\mathbf{d}` (`\mathbf{d}` a unit
lattice vector, `(1,0)` or `(0,1)` depending on the domino's orientation). Knowing the
trajectory of `P` determines the trajectory of `Q` exactly, and vice versa.

**The move:** keep one strand (say `P`) as a genuine 1-chain and *delete the other strand's
tiles*. Deleting strand `Q` removes `K` cells from the grid — they become **holes**. What
survives is:

- `\hat{C}` — the **representative 1-chain** of the former 2-chain: one cell per placement,
  `\hat{C} = (p_0, p_1, \dots, p_{K-1})`, a true lattice walk;
- `C_1` — the original 1-chain, untouched;
- a **holey grid** `G^\circ = G \setminus Q` (the `K` deleted cells).

Two crucial properties carry over for free:

1. **It is a real panel path.** Each `p_k` is a lattice cell. **[VALIDATION CORRECTION
   2026-06-07: consecutive segments are NOT all unit moves — along-axis folds throw the far
   strand by 3, so step lengths are {1,3}.]** The salvaged core: steps are axis-aligned with
   *odd* lengths, so every turn is still `0°` or `±90°` and the checkerboard `σ=(−1)^{x+y}`
   still alternates every step. Hence `γ(p_k) ∈ {0, ±π}` and any loop twist is a multiple of
   `2π` — the `936°` pathology is gone (verified: canonical-strand loop twist ∈ {0, ±720} on
   all 303 cached 2+1 solutions). Using a **cell** instead of the **centroid** is the fix.
2. **It carries the 2-chain's twist.** **[VALIDATION CORRECTION 2026-06-07: the
   translation-equivariance argument fails as stated — `\mathbf{d}` is NOT constant; it flips
   sign at every along-axis fold (the strands swap sides; `reflect_cells` preserves list order,
   so `cells[0]`/`cells[1]` do track the two material halves). P and Q are therefore not
   translates, and their loop twists can differ — see §5.1. The faithful-proxy claim survives
   only for the *canonical* strand.]**

## 3. Why the holes do not matter

The twist criterion is **local and grid-shape-agnostic**. `Tw(L) = \tfrac{1}{4\pi}\sum_v
\sigma(v)\gamma(v)` reads only (i) the turn angle `γ` at each vertex of the walk, and (ii) the
checkerboard sign `σ(v) = (−1)^{x+y}` of the cell — both defined cell-by-cell, with no reference
to the ambient region being a full rectangle. Deleting `Q` punches holes in `G`, but `\hat{C}`
and `C_1` are still well-defined lattice walks through the remaining cells, and `σ` is still the
global checkerboard inherited from the original grid (this matters: the two strands `P`, `Q`
have *opposite* parity, so the choice of which strand to keep enters through `σ` — see §5). The
parity bookkeeping that the paper attaches to a full grid (`mn ≡ 0 (mod 6)`, `K` even, …) was
only ever an *existence* gate for finding patterns; the *twist evaluation* never needed it. So
"some holes, but we can literally employ the parity + twisting math on this" is exactly right —
the evaluation transfers unchanged.

## 3b. Loop repair — the "filled" reduction (added 2026-06-08)

Objection (lead): the kept strand's 3-jumps are not panel-adjacent steps, so the strand loop
violates the closed-loop-of-adjacent-panels premise. **Repair:** every 3-jump passes over
exactly the two holes left by the twin strand at that fold (`P_k → [Q_k, Q_{k+1}] → P_{k+1}`);
re-route the walk *through* them. **Lemma (validated 303/303):** the inserted vertices are
collinear (γ = 0, contribute nothing) and shift all later indices by 2 (σ phase preserved), so
`Tw(filled) ≡ Tw(jump)` exactly. The filled loop is a genuine closed unit-step panel loop on
the holey grid — simple (no revisits), even length, unit seams — so the paper's 2-stack twist
theorem applies verbatim. The jump version is its "deflated" shortcut, not an approximation.
Canonical-strand rule accordingly tightened to: **keep the strand whose base cell is
edge-adjacent to the 1-chain base** (unit seams at both hubs; exists in all 303 cached
solutions). Side effect: the filled walk's ribbon zigzag recovers a partial per-panel HC
order of the 2-chain — the formerly "unsolved inverse problem".

## 4. The resulting 2+1 criterion

After reduction, 2+1 presents as **two** honest 1-chains, `\hat{C}` and `C_1`, joined at the
footprint hubs — a single fundamental loop `L = \hat{C}\ (S\!\to\!E) + C_1\ (E\!\to\!S)`. The
hypothesised criterion is the same closed-loop condition as everywhere else:

$$\boxed{\ \text{2+1 foldable} \iff \mathrm{Tw}(L)=\frac{1}{4\pi}\sum_{v\in L}\sigma(v)\,\gamma(v)=0\ }$$

i.e. the 2-chain (as a rigid unit, stood in for by `\hat{C}`) must not entangle with the
1-chain. This is structurally a **2-stack** test (one loop), which is sensible: a *rigid* ribbon
cannot twist against itself, so the only entanglement available in 2+1 is between the ribbon and
the lone chain. The whole 3-stack apparatus collapses, for this decomposition, to a single
pairwise loop on the reduced grid.

## 5. Open points to settle (updated with 2026-06-07 computational answers)

1. **Which strand — `P` or `Q`?** **ANSWERED (empirically): they do NOT always agree —
   verdicts disagree 66/303.** The strand whose loop closes through a *diagonal* hub seam
   (L footprint, strand diagonal to the 1-chain base) carries a quantized **±360 (half-twist)
   seam artifact**: `tw_DIAG − tw_canon ∈ {0, ±360}` in all 201 single-DIAG cases. The
   **canonical-strand rule is exactly the fallback conjectured here: use the strand
   edge-adjacent to `C_1`'s base (non-DIAG seams)** — its loop twist is always an integer
   multiple of 720 (physical). For Rect footprints both strands are non-degenerate (unit/2JMP
   seams) and agree exactly, so the choice is immaterial there.
2. **Is one loop enough?** **Structurally yes after reduction:** `{\hat{C}, C_1}` between two
   fused hubs has cycle rank 1 — the single loop *is* the whole cycle space, so there is no
   1+1+1-style all-pairs subtlety. But the empirical answer to "does it flag the 6×5
   suspects?" is **NO — all 6×5 2+1 pass (`Tw=0`)**. The criterion *does* discriminate
   elsewhere (11/303 flagged: 6×6 #13/#18, 6×7 #8, 8×6 #41/#42/#44/#127/#128/#265). Either
   the 6×5 set actually folds, or the single-loop criterion is incomplete — only the physical
   labels can decide.
3. **Internal twist of the ribbon.** Still open (needs physical labels); no computational
   counterevidence — canonical-strand values are always physical integers.
4. **Hub/orphan handling.** Unchanged: fused-hub closure reused; per-chain interior-only sums
   stay disproved.
5. **(New) Domino-level-bipartite variant is subsumed.** Treating the 2-chain as one unit per
   placement (centroid path; index parity = domino bipartite) gives the same body turns but an
   off-lattice hub seam for L footprints (±212.52° = 4·2·atan(½) artifact — the small sibling
   of the 936° pathology); it equals the canonical-strand twist exactly whenever its seam
   artifact vanishes (227/303, incl. all Rect). Use the strand reduction.

## 6. How this slots into the existing tooling

- The representative strand `\hat{C}` is trivial to extract: take cell index `0` (or `1`) of
  each placement of the 2-chain — `placements[k]["cells"][0]` — which is already what
  `py/foldpattern.py` replays. No inverse problem, no centroid.
- The reduced `{\hat{C}, C_1}` then feeds the *same* pairwise-loop evaluator used for 1+1+1
  (`_pair_loop_twist` / the closed-loop `twist_value`), now over a 2-chain set.
- Validation target: the physical labels in `results/twoplus1_labels.json` produced by the fold
  harness — the reduction is correct iff `Tw(L) = 0` matches the hand-folded verdicts.

---

*Relation to prior notes:* this supersedes the rejected composite-**centroid** path (the `936°`
artifact, `resources/twist_diagnosis.md`) by replacing the centroid with an on-lattice
**representative cell**; it keeps the validated 1+1+1 equation (`Tw(L_{ij})=0`,
`EXPLAINER.md §2.3`) and the disproof of the per-chain `T_A=T_B=T_C` reduction (`§2.5`).
See `context.md` Q1.
