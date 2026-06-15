# Twist verdict — diagnosis & research findings

Date: 2026-05-26. Trigger: 6×6 solutions #2, #3 fold physically but the shipped
per-chain twist verdict (`search.js twistCheck`) flags them ✗ (false negatives).

## Verdict: per-chain twist is the wrong invariant

Three compounding mechanisms (evidence below):

1. **Open chains always flat-fold.** Turn-angle sum along an *open* chain measures path
   *curvature*, not entanglement. Confirmed-foldable 1-chains score nonzero (#2 `openTw=180`,
   #3 `openTw=360`); the value just tracks perimeter winding (the L-shape outer-ring wrap).
2. **Twist is a closed-loop invariant.** CWF / paper `Tw=(1/4π)Σg(i)` is defined over the
   single closed HC of all panels. Computing it on disconnected open segments is undefined.
   The turn-angle *primitive* is correct on closed loops — verified it returns `Tw=0` on the
   2×4 perimeter HC (paper Fig 13b, foldable) and a 4×4 ring.
3. **σ (mountain/valley) phase resets per chain.** σ_i alternates ±1 along the *global*
   panel order; `twistCheck` restarts the odd/even bucketing at each chain → phase offset by
   the count of panels preceding it in the true HC. No per-chain constant can fix it.

The physical model (confirmed with lead) is **one connected Hamiltonian circuit**; the
"chains" are segments joined by creases at the footprint. So the correct condition is a
single closed-loop turn-angle balance over the reconstructed HC — not per chain.

## Reconstruction prototype results (`/tmp/twist_research.js`)

Method: replay each chain's `foldArrows` to rebuild placements, then derive crease edges
(between a placement's cells touching a fold line and their mirror in the next placement).
Target = a single 2-regular cycle over all m·n cells (degree-2 everywhere, mn edges).

- **1-chains reconstruct cleanly**: degree-2 interior, degree-1 ends.
- **1+1+1 (I-shape)**: 3 clean paths — 33 edges, degHist `{1:6, 2:30}` (6 chain-ends, no
  isolated cells). Needs only **3 join edges** to close into one cycle. *Tractable.* But the
  joins are **ambiguous under adjacency alone**: ends cluster at the footprint and a start-end
  can touch two other ends (e.g. `(1,0)` ~ both `(0,0)` and `(1,1)`). Need the explicit
  footprint crease/slit rule to pick joins.
- **2-chain (2+1)**: **broken under reflection-only reconstruction.** A 2-chain base cell
  ends up degree-0 (isolated) and the chain fragments into ~6 path pieces (#2: 12 degree-1
  ends vs the 4 expected). Recovering a folded domino chain's per-panel HC order from
  reflections is the inverse problem and is ambiguous — the hardest unknown.

## Root cause of the reconstruction gap

The search emits **folds directly** and never records an explicit HC or the crease/slit
assignment on each grid edge. Reconstructing that assignment after the fact is under-
determined, especially for 2-chains. The clean fix is to **track crease/slit structure
forward during search** (or import the join rules from the MATLAB reference model).

## Recommended next steps (for lead decision)

1. **Forward crease tracking**: have `searchDecomposition` record which grid edges are
   creases (folds) vs slits as it builds, so the global HC is known exactly — no inverse
   reconstruction. Then run the validated closed-loop balance once (Stage B).
2. **Start with 1+1+1**: it already reconstructs to 3 clean paths; solving just the footprint
   join rule yields a correct global twist for the I-shape — matches the "1+1+1 is easiest"
   hypothesis. Defer the 2-chain (2+1) interior.
3. **Ground truth**: need ≥1 confirmed *non*-foldable 6×6 for negative validation (currently
   only have foldable #2,#3 and ✓ #5). Validate the pipeline against the 2-stack reference
   (`notwist.py`) on the paper's known cases first.

## Candidate fix: pairwise-loop twist (PROMISING)

Lead input: (1) footprint internal creases are **fused** (start footprint + exit footprint
are rigid hubs); (2) nonfoldable ground truth = some 6×5 patterns.

Fused hubs ⇒ structure is two hubs joined by 3 chains (theta graph). Natural condition:
**each PAIR of chains forms a 2-stack-like closed loop** (start-hub → chain A → exit-hub →
chain B → back); require `Tw=0` on all 3 pairwise loops.

Prototype on 1+1+1 6×6 (chain_i fwd + chain_j reversed, closed turn-angle balance):
- #1–4: pairs `01:0 02:0 12:0` → all foldable.
- #5–8: pairs `01:0 02:0 12:720` → entangled (2 full twists on the 1–2 pair).
- **Flips the per-chain false negatives**: #3,#4 (old per-chain verdict ✗) now pass all-zero.

Discriminates (not all-pass) and resolves the false negatives → strong candidate for the
correct 3-stack twist condition for **1+1+1 (I-shape)**.

**2+1 / 6×5 blocked.** 6×5 has no 1+1+1 solutions (only 3 corner 2+1) — consistent with the
I-shape boundary conjecture `(m−3)(n−3)≥9` (6×5→6<9). Tried the 2-chain as a composite-
centroid path: gives **non-physical twist** (936, not a multiple of 360). A rigid reflection
moves a domino centroid only perpendicular to each crease, so turns must be 90° multiples
and twist a 360 multiple — 936 proves the composite-centroid path is not a valid panel path.
⇒ 2-chain needs proper **per-panel HC reconstruction** (the unsolved Stage-A item); centroid
shortcut rejected. The lead's nonfoldable 6×5 are all 2+1, so 6×5 validation waits on this.

Recommendation: ship pairwise-loop twist for 1+1+1 now (matches the "I-shape easiest"
priority); treat the 2-chain reconstruction as a separate research item.

## Validated primitive (reuse)
`notwistClosed(centers)`: signed turn ×2 at each vertex, wrap-around, alternating odd/even
buckets, `Tw=0` iff `Σodd−Σeven==0`. Reproduces paper Tw=0 on 2×4 / 4×4 closed loops.
