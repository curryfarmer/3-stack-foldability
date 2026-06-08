# Test coverage — what has been tested per grid

Running record of which grids / chain-lengths / configurations have actually been tested for
3-stack foldability, per lattice. "Computational" = enumerated + twist-checked by the tooling;
"Physical" = hand-folded ground truth. Cross-refs: `LAB_LOG.md`, `results/`, `py/tri/`.
Last updated 2026-06-08.

---

## Square grid (`search.py`/`search.js`, `results/*.json`) — PRIMARY, mature

**Computational (generated + twist-analyzed), by grid m×n:**

| grid | total sols | 1+1+1 | 2+1 | notes |
|------|-----------:|------:|----:|-------|
| 6×4  | 3   | 1   | 2   | smallest with 1+1+1 (mn=24≡0 mod 12) |
| 6×5  | 5   | 0   | 5   | 2+1-only (mn=30≡6 mod 12) |
| 6×6  | 30  | 16  | 14  | |
| 6×7  | 41  | 0   | 41  | 2+1-only (falsified the (m−3)(n−3)≥9 boundary) |
| 8×6  | 373 | 244 | 129 | largest cache |
| 9×4  | 26  | 15  | 11  | Rect footprints |
| 12×4 | 102 | 20  | 82  | |

- **1+1+1 twist**: validated on all cached 1+1+1 — 936 pairwise loops, oracle 936/936; cocycle
  (non-additivity) + single-degenerate-seam-loop confirmed. (`analyze_loop_seams.py`)
- **2+1 twist (strand reduction)**: validated on all 303 cached 2+1 solutions across the 7 grids;
  filled-loop lemma Tw(filled)==Tw(jump) 303/303; convention invariance 303/303.
  (`analyze_2plus1_reduction.py`)
- **2-stack reference**: 6×4, 6×5 (`*_2stack_*.json`).
- **Min-size sweep (Q7)**: all grids up to maxdim 20 / area 30 under relaxed gates
  (`sweep_minsize.py`).
- **mod-12 existence conjecture (Q6)**: 6 grids on record (6×4,6×6,9×4,12×4 positive; 6×5,6×7
  negative); 8×6 positive confirmed (244). 6×9 NOT yet generated.

**Foldsheets rendered (13, `report/foldsheets/`)**: 6×4 #1,#2 · 6×5 #1–5 · 6×6 #1,#7,#13,#18 ·
6×7 #8 · 9×4 #8.

**Physical (hand-folded) — 0/13 done.** `results/twoplus1_labels.json`: 13 cases, all
`foldable: null`. THE outstanding decider. Priority folds: 6×5#1, 6×7#8, 6×6#13, 6×6#7.

**Pending:** physically fold the 13 sheets; exhaustively physically check all 6×5; generate 6×9.

---

## Equilateral-triangle lattice (`py/tri/`) — PoC, succeeds

Bipartite σ = UP/DOWN. Closing folds = 3 disjoint K-chains, start+end both trapezoids. Canonical
hub is WLOG (p6m transitive on trapezoids), so the proof search fixes one hub.

**Existence — exhaustive from canonical hub (`prove_obstruction.py`):**

| K | closing folds | note |
|---|---|---|
| 2–9 | **0** | exhaustive |
| 10 | **2** | both twisted (AB=±720, BC=∓720, AC=0); 30-tri irregular region |
| 11 | exist | odd K → −240 arm-arm seam artifact (non-physical) |
| 12 | **94** | all twisted, **0 foldable**, **0 hole-free** (census `hunt_tw0.py` + `hunt_foldable.py`) |
| 13 | — | (stopped; K=10 counterexample already found) |
| ≥14 | not yet | next target for *foldable* + *hole-free* (even K) |

- **K=12 twist spectrum**: (+720,−720,0)×39, (−720,+720,0)×39, (±720,±720,±1440)×16; cocycle
  **AC=AB+BC** verified exactly. Even K only (odd K poisoned by the −240 seam artifact).
- **Solid-region tiling search (pre-canonical-hub work)** — 1+1+1 closing, exit-congruent:
  parallelograms 2×3, 3×2, 1×6, 3×3, 4×3, 3×4, 2×6, 4×6, 5×3, 3×5 → 0; big triangle s=3, s=6 → 0;
  hexagon n=1 (6), n=2 (24) → 0 closing (24 non-closing tilings on hex n=2); C2 disk (14/24/28
  tris) → 0. (All superseded: closing needs K≥10, found via free-roam/canonical hub.)
- **Free-roam (irregular, chains define their own region)**: 1+1+1 K≤8 (1.67M configs) → 0;
  2+1 K≤8 (1.18M configs) → 0 — both below the K=10 threshold.
- **2-stack control**: hexagon 6-ring closes, Tw=0 (verified).
- **Verified machinery**: bipartite (every dual edge +/−); reflect-to-neighbor exact;
  6-ring twist anchor γ=120°, Tw=0.

**Pending:** K=14 (foldable + hole-free); 2+1 rhombus-ribbon reduction at K≥10; physical fold.

---

## 45-45-90 right-triangle (tetrakis) lattice (`py/tri/righttri.py`) — in progress

Bipartite σ = (−1)^(i+j+w(o)). γ ∈ {0,±90,±180}. Tiles pack into solid squares (hole-free by
construction). Two inequivalent hub types: **LL** (arms = the two legs) and **HL** (arms =
hypotenuse + leg).

- **Lattice verified (3×3 = 36 tiles)**: bipartite OK; reflect-to-neighbor exact on all 96 dual
  edges (genuine foldable reflection tiling); 4-ring twist anchor γ=−180°, Tw=0 clean.
- **Existence — exhaustive from canonical hub, both LL+HL (corrected ambient 2K+4)**:
  K=2..11 (odd AND even) → 0; **K=12: LL=0, HL=32 closing**. So **first closing K = 12** (on the
  hypotenuse+leg hub; the two-legs hub has none through 12). Higher than equilateral (10) and
  square (8) but NOT impossible — the "solid packing helps" bet was wrong (degree-3 dual with
  girth-4 square-cycles is more constrained, not less), yet it still closes by K=12.
- **K=12 HL twist census (32 closing)**: **8 FOLDABLE (Tw=0), of which 2 are HOLE-FREE.** All
  twists clean (multiples of 360, fractional=0); cocycle AC=AB+BC holds; histogram (0,0,0)×8 +
  twisted (±720,0,±720)/(±720,±720,±1440)/(±720,∓720,0). **This is the first foldable AND
  hole-free 3-stack fold found on any non-square grid** — the prize equilateral couldn't give ≤K=12.
- Examples rendered: `report/tri/tetra_foldable_hf_{1,2}.png`.

**Result: 45-45-90 supports foldable, hole-free 3-stack folds at K=12.** Done (modulo physical fold).

---

## 30-60-90 right-triangle (kisrhombille *632) lattice (`py/tri/scalene.py`) — in progress

Barycentric subdivision of the equilateral lattice (each face → 6 right-scalene tiles
{vertex, edge-midpoint, centroid}). Bipartite σ = orientation. γ ∈ {0,±60,±120,±180}. Three
inequivalent hub types (omitVM / omitMG / omitVG, by which neighbour-edge the mid-chain exits).

- **Lattice verified**: bipartite OK; reflect-to-neighbor exact on all 264 dual edges (genuine
  foldable reflection tiling); face 6-ring twist anchor γ=120°, Tw=0 clean.
- **Existence — all 3 hub types**: K=2..10 → **0 closing**. K=11,12 scan IN PROGRESS.

**Pending:** K=11,12 results; if all 0, this + 45-45-90 = both right-triangle tilings empty
through K=12 (while equilateral closes at K=10) → strong signal the difficulty is geometry-specific.

---

## Running threshold table (first K with a closing 3-stack fold)

| grid | tile | dual | first closing K | first *foldable* (Tw=0) K |
|------|------|------|-----------------|---------------------------|
| square | quad | deg-4 | 8 | ≤8 (yes) |
| equilateral | 60-60-60 | deg-3 honeycomb | 10 | none ≤12 (K=14 pending) |
| 45-45-90 | tetrakis | deg-3 girth-4 | **12** (HL hub; LL=0 @12) | **12** (8 foldable, 2 hole-free) |
| 30-60-90 | kisrhombille | deg-3 | **>10** (K=11,12 pending) | — |

**Headline:** closing 3-stack folds exist for square (8), equilateral (10), 45-45-90 (12) — NOT
only quadrilaterals. *Foldable* (Tw=0) folds confirmed for square AND **45-45-90** (first non-square
foldable+hole-free fold, K=12); equilateral still none ≤12 (K=14 pending).

---

## Non-candidate grids (documented, not tested — fail the premise)

The fold model needs every tile edge to be a **mirror line** of the tiling (so a fold maps a tile
onto its neighbor) ⇒ valid grids are the single-tile **reflection/kaleidoscope tilings** only:
square, equilateral, 45-45-90, 30-60-90.

- **Hexagon-cells**: dual = triangular lattice = **not bipartite** (odd cycles) → excluded.
- **Kagome (3.6.3.6) and other mixed-tile bipartite tilings**: adjacent tiles differ in shape →
  no tile→tile fold → excluded.
- **Uniform rhombus tiling**: 3 rhombi meet at the 120° corners ⇒ odd valence ⇒ not face-bipartite,
  no edge mirrors → excluded as a standalone grid. (The 60-120 rhombus IS the rigid 2-triangle unit
  of the equilateral lattice = our 2-chain.)
- **Trapezium tiling**: a trapezium is the 3-triangle footprint/hub of the equilateral lattice;
  standalone bipartite+mirror check pending, expected to fail.
- **30-60-90 right triangle**: a valid 4th kaleidoscope tiling — not yet built.
