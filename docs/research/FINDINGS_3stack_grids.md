# Findings — 3-stack folding across bipartite-tileable grids

*Session 2026-06-08. Synthesis of the multi-grid extension of 3-stack HC folding. Running detail
in `LAB_LOG.md`; per-grid test record in `TEST_COVERAGE.md`; code in `py/tri/`.*

## The question

The square-grid 3-stack theory (three equal chains folding from a footprint back onto a congruent
footprint, foldable ⟺ pairwise-loop twist `Tw=0`) — does it extend to **other bipartite-tileable
grids**, and which ones actually fold?

## 1. Which grids are even candidates (theory)

The fold model reflects a flap across a crease (a shared tile edge). For the folded tile to land
back on the lattice, **every tile edge must be a mirror line of the tiling** ⇒ valid grids are the
single-tile **reflection (kaleidoscope) tilings**. There are exactly four:

| grid | tile | reflection group |
|------|------|------------------|
| square / rectangle | square | *2222 / *442 |
| equilateral | 60-60-60 triangle | *632 / *333 |
| 45-45-90 (tetrakis) | right isosceles | *442 |
| 30-60-90 (kisrhombille) | right scalene | *632 |

Bipartiteness (the σ = ±1 mountain/valley 2-coloring) needs an **even number of faces at every
vertex**; all four satisfy it. **Excluded:** hexagon-cells (dual = triangular lattice = *not*
bipartite); kagome & other mixed-tile tilings (adjacent tiles differ in shape ⇒ no tile→tile
fold); uniform rhombi (3 meet at the 120° corner ⇒ odd valence — and the 60-120 rhombus is just
the 2-triangle composite = our **2-chain**); trapezia (the 3-triangle composite = our **footprint**).
So the candidate set is closed: square (done) + the three triangle tilings.

## 2. The validity filter (what makes a fold real)

A 3-stack fold = three vertex-disjoint length-`K` chains from a 3-tile footprint hub, reconverging
to a congruent footprint. It is **physically foldable** iff **all** of:

1. **Closing** — start and exit are both congruent footprints (combinatorial existence).
2. **Tw = 0** — all three pairwise theta-loop twists vanish (no entanglement).
3. **Side-matching (the vector-reflection condition)** — each adjacent chain-pair (A·B and B·C)
   rejoins on the **same edge type** at start and exit, with B central at both ends. *Automatic on
   equal-edge tilings (square, equilateral); binding on unequal-edge tilings (45-45-90 has long
   hypotenuse vs short leg; 30-60-90 has three lengths).*
4. **Hole-free** — region simply connected (so it's a single physical sheet).

**The session's main lesson: Tw=0 is necessary but NOT sufficient.** On the 45-45-90 grid, 8 folds
were Tw=0 yet all failed side-matching — the missing filter (#3), which the square grid hides
because all its edges are equal.

## 3. Results per grid

| grid | dual deg | first closing K | Tw=0 fold | side-matching | **valid fold** |
|------|:--------:|:---------------:|-----------|---------------|----------------|
| **square** | 4 | 8 | yes | automatic | **YES** |
| **equilateral** | 3 | 10 | none ≤12 (K≥14) | automatic | pending (K=14) |
| **45-45-90** | 3 | 12 (HL hub) | 8 @ K=12 | **0/32 — all swap** | **no ≤12** |
| **30-60-90** | 3 | >12 (K≤12: 0) | — | — | pending |

Closing-threshold trend: **rises as tile symmetry drops** — square 8, equilateral 10, tetrakis 12,
scalene >12. (Higher dual degree = more reconvergence room = lower threshold; the square's degree-4
dual is the easiest.)

## 4. Key findings

1. **Closing 3-stack folds are not quadrilateral-only** — they exist for square (K=8), equilateral
   (K=10) and 45-45-90 (K=12).
2. **Equilateral PoC succeeds.** Closing folds exist at K≥10 (the earlier "no fold ≤K=8" was a
   finite-size artifact). All twists are clean multiples of 360; the theta cocycle **AC = AB+BC**
   holds exactly; **even K only** (odd K injects a −240° degenerate arm-arm seam artifact). Through
   K=12 every closing fold is *twisted* (the clean arm-mid loops are ±720, never 0) ⇒ equilateral's
   first Tw=0 is a K≥14 object. All closing folds through K=12 also have holes (the theta graph
   encloses two faces width-1 chains can't fill until they're long).
3. **Tw=0 ⇏ foldable on unequal-edge tilings.** 45-45-90 K=12: 8 Tw=0 folds, but **0/32 closing
   folds side-match** — every one swaps `A·B long→short, B·C short→long` (uniform 32/32 ⇒ looks
   like a *forced invariant* of the asymmetric HL hub). Side-matching is the vector-reflection
   condition made concrete.
4. **45-45-90 does tile solid** (2 of the K=12 folds were hole-free) — so the hole obstruction that
   dogs equilateral is gone there; it's the *side-matching* that blocks, not holes.
5. **Under the full filter, only the square grid has a confirmed valid fold so far.** Every
   non-square candidate is still open (equilateral pending K=14; tetrakis pending the symmetric LL
   hub at K≥14 or a proof the HL swap is forced; scalene pending K≥13). So "is 3-stack foldability
   essentially a square-grid phenomenon?" is a live, well-posed question.
6. **The machinery ports exactly.** On every grid: bipartite σ verified (alternates on every dual
   edge); folds = `_reflect_point` across the shared edge, **reflect-to-neighbour exact** on all
   dual edges (the foldability/kaleidoscope check); twist = doubled-turn atan2 sum, **anchor loops
   give Tw=0, clean multiples of 360**. The square `_pair_loop_twist` runs verbatim; `loop_twist`
   was generalized to take centroid/σ callables so it's lattice-agnostic.

## 5. Tools built (`py/tri/`, all reusable across tilings)

- **Lattices:** `trilattice` (equilateral), `righttri` (45-45-90 tetrakis), `scalene` (30-60-90
  kisrhombille) — each: tile ids, vertices, σ 2-coloring, dual adjacency via shared edges, centroids.
- **Generic engine:** `trifold` (`_reflect_point` folds), `tritwist` (`signed_turn`/`loop_twist`,
  now cent/σ-parameterized), `trisearch` (`grow_walks`/`exit_ok`/`pairwise_twists`),
  `prove_obstruction` (`grow`/`is_trapezoid`/`count_closing`, canonical-hub WLOG exhaustion),
  `hunt_foldable` (hole detector + Tw=0 hunt), `hunt_tw0` (twist census), `sidematch_scan`
  (side-matching filter).
- **Render:** `render_general` (chains overlay), `foldsheet_tri` (printable cut/fold sheets:
  mountain/valley creases, slits, footprint).
- **Saved data:** `results/tri_foldable_K12_hl.json` (8 Tw=0 folds), `results/tri_K12_hl_all.json`
  (all 32 closing folds with tw/holes/sidematch) — so nothing re-enumerates.

## 6. Open questions / next steps

1. **Prove (or refute) the HL side-swap is a forced invariant** — a parity argument on long-edge
   vs short-edge crossings along the chains. Cheap; decides whether HL can ever fold.
2. **Symmetric LL hub at K≥14** — both seams short, so side-matching is natural; LL has no closing
   fold ≤12, so this is the first place a *valid* tetrakis fold could appear.
3. **Equilateral K=14** — its first Tw=0 fold; side-matching is automatic there, so it would be
   valid immediately. (~19 h brute / overnight, or write the smart disjoint-path solver first.)
4. **Scalene K≥13** — does the kisrhombille ever close?
5. **Bake side-matching into `count_closing`** so the search filters from the start.
6. **Physical fold** of any eventual valid non-square example — the real-world decider (same
   standing gap as the 13 square foldsheets, `results/twoplus1_labels.json` still all-null).
7. **The deep question:** does *every* valid (bipartite reflection) tiling eventually admit a fold
   passing all four conditions, or is the square grid genuinely special?
