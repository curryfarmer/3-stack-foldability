# Hypothesis — the 2+1 twist by half-tile reduction of the 2-chain

*Status: hypothesis / thesis section. Not yet tested. Validation deferred to the physical
ground-truth set (`FOLDING.md`, `results/twoplus1_labels.json`).*

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

1. **It is a real panel path.** Each `p_k` is a lattice cell, so consecutive segments are unit
   moves and every turn is `0°` or `±90°`. Hence `γ(p_k) ∈ {0, ±π}` and any loop twist is a
   multiple of `2π` — the `936°` pathology is gone *by construction*. Using a **cell** instead
   of the **centroid** is the entire fix.
2. **It carries the 2-chain's twist.** The folding motion of the rigid domino is, up to the
   constant offset `+\mathbf{d}`, the folding motion of `P`. Twist is built from *turn angles*
   and the *checkerboard sign*, both of which are translation-equivariant; the constant
   `+\mathbf{d}` shift does not change any turn. So `\hat{C}` "reflects the overall folding of
   the 2-chain" exactly as hypothesised — it is a faithful proxy, not an approximation.

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

## 5. Open points to settle (during validation, not now)

These are the places the write-up should hedge until the physical labels (`FOLDING.md`) are in:

1. **Which strand — `P` or `Q`?** They have opposite checkerboard parity, so `σ` flips between
   them. Conjecture: by the global-`σ` argument the two give the same *verdict* (`Tw = 0` or
   not), even if magnitudes differ; this needs checking. If they disagree, the reduction needs a
   canonical-strand rule (e.g. the strand sharing the footprint hub with `C_1`).
2. **Is one loop enough?** 1+1+1 needed *all three* pairwise loops because twist is not additive
   over cycles. The reduction claims 2+1 has effectively one independent loop (rigid ribbon ⇒ no
   internal twist). This must be confirmed against a known non-foldable 2+1 (the `6×5`
   suspects): does the single `Tw(L)` flag it?
3. **Internal twist of the ribbon.** We assume a rigid domino contributes no twist of its own.
   If the domino can locally rotate relative to the 1-chain in a way the single strand misses,
   a correction term is needed.
4. **Hub/orphan handling.** The same chain-end orphan question as 1+1+1 applies to `\hat{C}`;
   reuse the fused-hub closure, do not re-introduce a per-chain interior-only sum (that was
   disproved for 1+1+1).

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
