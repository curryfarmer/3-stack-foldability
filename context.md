# context.md — Grid Folding Simulator

Self-context for working on this app. Read before feature work.

## What it is

Browser tool, no build step, no deps, no framework. Vanilla JS + SVG. Prototypes 2D origami-style folding on a square grid. Define a footprint, split into composite groups, drag groups across grid laying down mirrored copies (folds). Vectors anchored on footprint reflect through every fold automatically. Also has an exhaustive search engine ("3-stack" enumerator) that finds valid fold solutions for given grid dims.

## Run

```bash
cd "Folding Drawer. "   # trailing space in dir name is intentional
python3 -m http.server 8000
```
Open http://localhost:8000. Must be served via **http://** — search spawns a Web Worker, `file://` cannot.

## Files

| File | Role | LOC |
|---|---|---|
| `index.html` | DOM scaffold: topbar, palette (tools/color/display/search), grids container, results table. Loads 4 scripts in order: fold, grid, search, app. | ~100 |
| `fold.js` | **Pure geometry, no DOM.** Reflection math, placement model, fold/unfold, vector projection. `Fold` IIFE. | ~150 |
| `grid.js` | `GridView` class. Renders one grid card to SVG, handles per-tool pointer events. `CELL=32`px. | ~497 |
| `search.js` | **Pure compute, no DOM.** Exhaustive 3-stack enumerator. `Search` IIFE. Dual-mode: main-thread `window.Search` AND Worker (`importScripts` + `self.onmessage`). Now a **cross-checked reference** for the Python port. | ~600 |
| `py/fold.py` `py/search.py` | **Python port** of the fold geometry + search engine. Verified to produce identical solutions to `search.js` (counts + canonical hashes + verdicts) on 6×4/6×5/6×6. | |
| `py/twostack.py` | **2-stack RSPA mode** (`generate.py --stacks 2`). Enumerates Hamiltonian circuits on the m×n grid graph (HC count validated vs OEIS A003763: 4×4=6, 6×6=1072), applies vector-reflection (port of `twostack.py`) + twist (port of `notwist.py`); foldable iff a valid cut exists AND Tw=0. Twist is structurally 0 for plain grids; reflection is the discriminator. Output JSON: `{circuit, cutEdge, verdict:{reflection,twist,foldable}, twistValue}`, `meta.stacks=2`. | |
| `py/generate.py` `py/store.py` | CLI + JSON cache. `generate.py --m --n [--shapes --decomps --allow-non-corner --no-dedup --force --list]`. Writes `results/<m>x<n>_<hash>.json` + `results/manifest.json`; reuses cache unless `--force`. Output shape = browser exportJson (`{meta,solutions}`). | |
| `report/shoot.js` | Playwright (channel:'chrome') screenshot driver: loads a results JSON into the live tool via `window.App.loadResultsData`, `stepToId(id)`, screenshots `svg.grid`/`.svg-wrap` → `report/figures/`. Toolchain: playwright-core + pandoc (MD→.docx) + matplotlib installed. See `report/README.md`. | |
| `app.js` | Top-level state, multi-grid mgmt, palette wiring, search panel UI + Worker glue. `App` IIFE, boots on `DOMContentLoaded`. | ~554 |
| `style.css` | Styling. | ~190 |
| `README.md` | User-facing workflow/tool docs. |

No persistence — refresh clears all state. No undo/redo (fold tool has drag-back unfold only).

## Core data model

**GridState** (`app.js` `newGrid`): `{ id, label, m, n, cells:Map<"x,y",{color,highlight}>, footprint:Set<"x,y">, groups:[] }`.

**Group**: `{ id, label('A'/'B'/…), color, baseCells:[{x,y}], vectors:[], placements:[], hFolds, vFolds }`.
- Letter→color stable across grids (`colorForLabel`, charCode-65 index into `groupPalette`).

**Placement** (`fold.js`): `{ cells, vectors, parityH, parityV, foldArrow, creaseAxis, creaseAt, parentBounds, transformChain }`.
- `placements[0]` = original (base). Each subsequent = one fold (reflection) of the prior.
- `transformChain` = ordered list of `{axis,cBoundary}` reflections; replay on a base vector → its image (`projectVector`).

**Vector**: `{ x, y, edge:'T'|'B'|'L'|'R', sign:±1 }`. edge = which cell side the arrow lies on (a crease). sign = direction along edge tangent. Reflection flips edge + sign per `EDGE_FLIP_H`/`EDGE_FLIP_V` (`fold.js`).

## Reflection math (fold.js)

- `reflectScalar(v, cBoundary) = 2*cBoundary - 1 - v` — mirror integer cell coord across continuous boundary.
- `makeFold(active, dir, m, n)`: returns new placement or `null` if leaves grid. dirs `L/R/U/D`. R→cBoundary=xMax+1, L→xMin, D→yMax+1, U→yMin.
- `detectDirection(active, cursor)`: cursor must be past one edge AND within perpendicular band → returns dir.
- Screen coords: **+y is down**.

## Tools (grid.js pointer dispatch)

pen / eraser / highlight (paint), footprint (toggle membership, drag-paints), group (toggle cell in active group's base — must be inside footprint), fold (drag placement past edge → reflects; drag back across crease → unfolds, decrements counter; loops up to 24 iters/move), vector (drag inside active-group base cell → compass-snapped edge arrow, `snapVectorFromDrag`).

`preventOverlap` checkbox gates fold collision (`overlapsExisting` = union of all placement cells).


## Search engine (search.js) — the heavy part

Exhaustive enumerator for valid "3-stack" fold solutions. Pipeline stages:
1. **Arithmetic gate**: `mn%6===0`, `K=mn/3` even, `n>=4`. Else reject.
2. **Footprint enum** (`enumerateFootprints`): shapes L (4 rotations) + Rect (H/V). `allowNonCorner` opt relaxes the bbox-at-origin restriction.
3. **Decomposition enum** (`enumerateDecompositions`): `2+1` (one 2-chain + one 1-chain) and `1+1+1` (three 1-chains).
4. **DFS** (`searchDecomposition`): per chain, fold K times via `Fold.makeFold`, reserve cells, backtrack. `connectivityOK`/`canPartition` prune by checking unclaimed region components match remaining chain sizes. Leaf = full coverage (`reserved.size===m*n`).
5. **Verdicts** on each candidate: `exitFootprintCheck` (union of last placements ≅ start shape), `parityCheck` (**orientation-aware vector symmetry**: folds whose crease line is **parallel** to the A/B inter-block crease must be even — `parallelFoldAxis` derives the axis from base-cell adjacency: vertical A/B crease → nH even, horizontal → nV even; 2+1 only, 1+1+1 falls back to legacy nH-even/nV-odd), `reflectionCheck` (all chains' final tangent agree), `twistCheck` (per-chain Tw=0, **non-filtering** — annotates ✓/✗ + raw Tw, does not drop). See twist note below.
6. **Dedup** (`canonicalHash`): D4 canonical (4 rot × flip), keeps lexicographically smallest sig.

Worker glue: `app.js buildWorkerBlobUrl` inlines `importScripts(fold.js)` + `importScripts(search.js)` into a Blob URL (robust vs direct importScripts path resolution). Messages: `run`/`cancel` in; `progress`/`solution`/`done`/`error` out. Results → table; CSV/JSON export; `loadSolution` rebuilds groups+folds onto focused grid.

**Result browsing** (`app.js`): sticky `#searchNav` bar above the grid with ◀/▶ prev/next + ←/→ arrow keys + "Result i of N", a one-line summary (`Tw=0 ✓ L 2+1`), and display filters — **"Tw=0 only"** (`tw0Only`), **Decomp** (`decompFilter`: 2+1 / 1+1+1), **Shape** (`shapeFilter`: L / Rect). `filteredSolutions()` chains all three and is the single source for the table, counter, and stepper set; `stepTo(idx)` clamps `state.search.cursor` and calls `loadSolution`. Filters are display-only.

**Load results JSON** (`app.js` `#searchLoadJson`): file picker reads a `{meta,solutions}` JSON (from `py/generate.py` or a browser export), sets `state.search.solutions` + `lastOpts`, syncs the m/n inputs from `meta`, and renders via the same table/nav/stepper path. Lets the browser visualise precomputed Python results without running the in-browser search.

**2-stack visualisation** (`grid.js drawTwoStack`, gated by `view.twoStack` / `state.search.stacks===2`): when a `meta.stacks===2` JSON is loaded, the mode auto-switches; `loadTwoStack` sizes the grid and renders the kirigami pattern — HC path (blue dotted), creases (crossed edges, bold red), slits (uncrossed interior edges, gray dashed), cut edge (green), verdict label. The results table switches to 2-stack columns (reflection/twist/foldable/Tw); the prev/next stepper + "Tw=0 only"→foldable-only filter + screenshots all reuse the existing path. Loading a 3-stack file clears `view.twoStack`.

## Display options (app.js state.display)

Toggles: showLabels, showVectors, showFoldArrows, showPlacements, showFootprint, showPaint. Ranges: vectorSize, placementInset, chevronSize. All re-render via `api.renderAll()`.

## Conventions / gotchas

- `fold.js` and `search.js` MUST stay DOM-free (search.js runs in Worker too).
- Script load order in index.html matters: fold → grid → search → app.
- `key(x,y) = "x,y"` string keys in grid.js/app.js; `cellKey(x,y)=x*1000+y` int keys in search.js (m,n≤999 collision-free).
- Dir name `"Folding Drawer. "` has a trailing space — quote paths.
- Resizing dims (`applyDimsToFocused`) trims out-of-bounds cells/footprint/group cells and resets folds.
- All renders are full SVG rebuilds (`while firstChild remove`), not diffed.

---

# Research context — the math this app prototypes

This simulator is a prototyping tool for a research project: **3-stack folding of tessellated rectangular grids via Hamiltonian Circuits.** Extends Yang/You/Rosen (2025, Proc. Roy. Soc. A) 2-stack work to 3-stack. Goal: characterize which m×n grids admit 3-stack folding; mine general rules from generator output.

## Setup

- Grid m×n unit panels (m=cols, n=rows). Hamiltonian Circuit (HC) traces all cells; **edges crossed = folds, edges not crossed = slits.**
- 3-stack targets:
  - **L-shape:** 2+1 footprint (2-chain + 1-chain).
  - **I-shape:** 3×1 footprint (1+1+1, three open chains).

These map directly to the app's `enumerateFootprints` (L/Rect) and `enumerateDecompositions` (2+1 / 1+1+1).

## Universal necessary conditions (small, clean set)

1. `mn ≡ 0 (mod 6)` — HC bipartite + 3-equal-partition divisibility. (app: arithmetic gate `mn%6===0`)
2. `K = mn/3` even — implied by (1). (app: `K%2!==0` reject)
3. **Twist = 0** — Călugăreanu-White-Fuller no-entanglement (closed-loop). **← this is the stubbed verdict in search.js.**

## Per-chain parity (per-chain, NOT between-chain)

Chain endpoints (i₀,j₀)→(i_end,j_end):
- `N_H ≡ j_end − j₀ (mod 2)`
- `N_V ≡ i_end − i₀ (mod 2)`
- `N_H + N_V = K − 1` (odd, since K even) → exactly one of N_H/N_V odd per chain.

App's `parityCheck` uses nH even / nV odd — a special case. **Between-chain parity matching is NOT universal** — generator found valid patterns with both chains identical fold counts. Don't enforce it.

## Working hypothesis (project lead)

**L-shape 1+1+1 is the easiest to find a clean recipe for.** Reasoning: 2 of the 3 chains always wrap the outermost perimeter of the grid minimally — they're forced/near-forced. So the real problem reduces to **solving the interior** only. Once certain constraints are enforced, the interior becomes much more tractable than the full search. Recipe-hunting should start here, not with the general case.

## I-shape boundary conjecture

`mn ≥ 3(m+n)  ⇔  (m−3)(n−3) ≥ 9`. I-shape (1+1+1) only.
- Boundary cases: 6×6, 12×4. Predicts 6×4, 9×4 admit only L-shape (no I-shape).
- L-shape analog likely weaker, maybe `(m−2)(n−2) ≥ 6` — unverified.

## Comb+zigzag archetype — RETIRED (2026-06-03)

**Scrapped.** The corner-L comb+zigzag recipe and its `k = 1 + 2m(n−3)/[3(n−2)]` formula
were one archetype among many — never general. Now superseded: **2+1 solutions are proven
not to require the zigzag** (the generator finds valid non-zigzag 2+1 patterns), so the
zigzag layer count `k` characterizes nothing. The top-bar `k` readout + swap widget were
removed from the app (`app.js`/`index.html`/`style.css`) this date. Kept only as history:
the formula and its existence conditions (`(n−2)|2m`, `3|m OR 3|n`, `n≥4`) described that
single archetype, not the solution space.

## Known cases

- Working (L): 6×4, 9×4, 6×7, 6×5 (twist uncertain), 10×6 (predicted).
- Failing: 6×6 (passes arithmetic, fails in practice — twist obstruction suspected), 6×3 (rotational constraint).

## Big finding

No single recipe characterizes the full solution space (the retired comb+zigzag `k` formula
was archetype-specific; 2+1 proven not to need the zigzag). Many distinct archetypes. General
3-stack characterization is likely **two-tier**:
1. Universal arithmetic/topological conditions (small, clean).
2. Existence of ≥1 archetype config (catalog-based, NOT closed-form).

## Open questions

- Verify `(m−3)(n−3)≥9` across more grids (esp. 12×4, 6×6).
- Derive L-shape boundary condition.
- Catalog archetypes (cluster generator output).
- 6×6: twist failure vs path-graph failure?
- Physically test 10×6.
- Central (non-corner) footprints. (app: `allowNonCorner` opt)
- L-shape 4 rotations — differing constraints?
- Resolve 6×5 twist.

## Analysis priorities (limited compute, ~12×12 max)

1. Cut-edge classification (position/orientation clustering).
2. Failure-mode taxonomy (isolate binding conditions).
3. Archetype clustering (per-archetype rules).
4. Boundary signature (shared boundary ⇒ shared archetype).

## What NOT to chase

- Universal closed-form k (doesn't exist across archetypes).
- Between-chain parity matching (not universal).
- Single arithmetic recipe replacing all conditions.
- ML/statistical methods (data too sparse).

## Math toolkit

- Itai-Papadimitriou-Szwarcfiter (1982) SIAM J. Comput. 11:676 — HC existence on grid graphs.
- Keshavarz-Kohjerdi & Bagheri (2016) TCS 621:37 — HCs on L-shaped grid graphs.
- Conway-Lagarias (1990) JCTA 53:183 — tile-homotopy invariants, boundary words.
- Călugăreanu-White-Fuller — Lk = Tw + Wr; twist condition basis.
- Yang-You-Rosen (2025) Proc. Roy. Soc. A 481:20250696 — 2-stack baseline.

---

# Reference code — `resources/twist_reference_code/kirigami-programme/`

The **2-stack baseline** generator (Yang & Rajkumar). MATLAB app (`KirigamiApp.mltbx`) + Python compute backend. `requirements.txt`: networkx 3.3, numpy 1.26.4, matplotlib 3.8.4. `plots/` has worked examples (foldable/not-foldable). This is reference for porting twist + reflection logic into our search.js, NOT part of the web app.

Python pipeline (`python files/`, driven by `main.py` via subprocess + temp/*.json):
1. **`lattice.py`** (694 lines) — build lattice graphs from geometry. `G1` = panel edges, `G2` = dual/center graph (HC runs on G2). Supports squares + other geometries (hexagon, triangle).
2. **`hamiltonian.py`** — enumerate all HCs on G2 via parallel backtracking from a start node. Dedup by `normalize_circuit` (D4: 9 rotations × 4 mirrors, then cyclic rotations + reversal, take min). **Our analog: `searchDecomposition` DFS + `canonicalHash`.**
3. **`twostack.py`** — **reflection/foldability check.** Split each circuit into two opposite half-paths; reflect the start edge along each path (`reflect_edge_along_path` mirrors successively about each crossed edge midpoint); foldable iff both halves reflect the start edge onto the same target edge. **Our analog: `reflectionCheck` (drive canonical vector through transformChain, compare final tangents).**
4. **`notwist.py`** — **TWIST = 0 check.** `check_valid_circuit`: walk consecutive edge pairs around circuit, compute signed turn angle (`2×` the degrees, sign from 2D cross product), bucket alternately into odd/even index lists; valid iff `sum(oddangles) − sum(evenangles) == 0`. **← This is exactly the algorithm to implement for the stubbed `twist` verdict in `search.js` (`exitFootprintCheck`/`parityCheck`/`reflectionCheck` siblings).** Note: our placements are reflections, not an explicit traced circuit — need to reconstruct the fold/crease path order to apply the alternating turn-angle sum.

Mapping summary (reference → our app):
| Reference (2-stack, Python) | Our app (3-stack, JS) |
|---|---|
| `lattice.py` G2 graph | implicit m×n grid in `fold.js`/`search.js` |
| `hamiltonian.py` HC enum | `searchDecomposition` DFS over folds |
| `normalize_circuit` D4 dedup | `canonicalHash` (4 rot × flip) |
| `twostack.py` edge reflection | `reflectionCheck` / `Fold.projectVector` |
| `notwist.py` turn-angle balance | `twistCheck` (per-chain Tw=0, non-filtering) ✅ |

---

# RSPA 2-stack paper (the baseline we extend)

`resources/RSPA-2025-0696.R1_Proof_...pdf` — Yang, You, Rosen, *Folding a tessellated uniform-thick plate into compact stacks*, Proc. Roy. Soc. A 2025 (DOI 10.1098/rspa.2025.0696). 20pp. **This is the 2-stack baseline; our project extends it to 3 stacks.** Read directly: needs poppler — `pdftotext -layout <pdf> out.txt` (poppler installed via brew this session).

## Framework (2-stack)

- **Tessellation → grid graph** (Def 2.2): node per panel, edge between panels sharing a side. Surface must have **even # panels** with **reflection symmetry** across shared edges (so paired top/bottom layers, complete overlap).
- **Hamiltonian Circuit** on grid graph (Prop 2.1): visits each panel once → each panel connects to exactly 2 neighbours. **Edges crossed by HC = creases (folds); edges not crossed = slits.** Turns origami (over-constrained) into kirigami. HC existence is NP-complete; brute-force enumeration is standard (they use Sharma's Python enumerator, then keep non-isomorphic via D4 normalization — same idea as `hamiltonian.py normalize_circuit` and our `canonicalHash`).

## The two necessary+sufficient conditions (the Theorem, §5)

A loop of uniform-thick panels folds into two equal stacks **iff**:

**(i) Vector reflection condition (Prop 3.1).** Imaginary-cut the closed HC at edge eᵢ → open Hamiltonian path; the cut edge becomes two vectors eᵢ⁻, eᵢ⁺ at the two ends. Folding = successive **reflections** of these vectors about each crossed crease (zig-zag = alternating mountain/valley). If after equal #reflections from both ends eᵢ⁻ and eᵢ⁺ coincide in position+orientation, the open ends rejoin → two **equal** stacks. (This is `twostack.py`; our analog is `reflectionCheck`.)

**(ii) No twist (Prop 4.1): Tw = 0.** Without cutting the loop, folding must be entanglement-free.
- **Local rotation** (Def 4.2): folding Pᵢ→Pᵢ₊₁ then →Pᵢ₊₂ gives `g(i) = σᵢ·γᵢ`. Sign `σᵢ = +1` for odd i, `−1` for even i (valley vs mountain).
- For **squares**: γᵢ depends on the second reflection across Pᵢ₊₁ — `π` for side s1, `0` for s2, `−π` for s3. (Triangles: ±2π/3.)
- **Cumulative**: `Odd(𝒫)=Σ g(i)` over odd i, `Even(𝒫)=Σ` over even i. Each adjacent fold is double-counted across two local rotations.
- **Twist** (Def 4.4): `Tw = (1/4π) Σ_{i=1}^{2n} g(i)`. Two-stack-foldable iff **Tw = 0**, i.e. `Odd(𝒫)` and `Even(𝒫)` balance.
- Worked: 2×4 squares → Odd=−2π, Even=2π → Tw=0 ✓. Square-with-hole → Odd=0, Even=4π → twisted ✗.

**`notwist.py` implements exactly this**: `angles_between_consecutive_edges` computes the signed turn angle at each circuit vertex (×2, sign from 2D cross product), buckets alternately into odd/even, and `check_valid_circuit` returns `sum(odd) − sum(even) == 0`.

Ported then revised. The original per-chain open-path twist produced false negatives (flagged foldable 6×6 #2,#3 as ✗): twist is a *closed-loop* invariant, and per-chain on open segments measures path curvature + resets the σ (mountain/valley) phase. Full diagnosis → `resources/twist_diagnosis.md`.

**CURRENT (`search.js twistCheck`): pairwise-loop twist.** Lead confirmed model = one connected HC with **fused** footprint creases (start + exit footprints are rigid hubs) → the 3 chains form a theta graph; each PAIR of chains is a 2-stack-style closed loop. `twistCheck`: for each chain build the placement-centroid path, then for every pair compute the closed-loop turn-angle balance (`pairLoopTwist`, the validated notwist primitive over chain-i-fwd + chain-j-rev); pass iff all pairs `Tw=0`. **Decided only for 1+1+1** (all 1-chains — centroid path is a valid unit-cell panel path); **2+1 left pending** (`verdict.twist=null`, shows "—") because the 2-chain per-panel HC ordering is unresolved and a centroid path there is non-physical (yields e.g. 936, not a 360-multiple). Verdict carries `sol.twistPairs=[{i,j,tw}]`; UI hover + CSV `tw_list` show pair twists; still non-filtering. Validated on 1+1+1 6×6: #1–4 all-pairs-0, #5–8 have a 720 pair.

## Extension to 3 stacks (this project)

Paper's own future work (§7): "folding into asymmetric or **odd-numbered stacks**" + "any even number by combining two-stack modules." Our project is the odd/3-stack case. Inherited from 2-stack: HC framework, reflection condition, **Tw=0 still required** (closed-loop). New for 3-stack: 3-way equal partition (`mn≡0 mod 6`), L vs I footprints, per-chain parity (replaces the single-loop parity), chain decomposition (2+1, 1+1+1).

---

# Open questions — current research frontier (as of 2026-05)

The handoff's original open-questions list is above (under "Research context"); this is the
refined, active frontier informed by what the generator + twist work has since revealed.
Lead is attacking Q1–Q4 over the week of 2026-05-28. Each below: what we know, what blocks
it, and the concrete next step / relevant code & data.

## Q1. Twist criterion for 2+1 and 1+1+1

**UPDATE 2026-06-07 — 2+1 criterion now CONJECTURED + cache-validated (strand reduction).**
`py/analyze_2plus1_reduction.py` (303 2+1 sols, 7 grids; oracle 936/936): the half-tile
reduction (`hypothesis_2plus1_reduction.md`) works with a **canonical-strand rule** — replace
the rigid 2-chain by its strand **edge-adjacent to the 1-chain base** (cells[i] per placement;
order-preserved by `reflect_cells`), close the single loop with the 1-chain, require `Tw=0`.
Canonical loop twist is always physical ({0,±720}); the *other* (diagonal-seam) strand carries
a quantized ±360 half-twist artifact (§5.1 strand-equivalence disproved; doc corrected). The
domino-level-bipartite/centroid variant is subsumed (off-lattice seam for L). Cycle rank 1
after reduction ⇒ single loop suffices structurally. **Flagged twisted: 11/303** (6×6 #13/#18,
6×7 #8, 8×6 #41/#42/#44/#127/#128/#265); **all 6×5 suspects PASS** — physical labels
(`FOLDING.md`) are now the decider; foldsheet set should add the predicted negatives
(6×6 #13/#18, 6×7 #8). Convention invariance (σ phase / γ sign / orientation flips) verified:
0 verdict changes across all cached loops (1+1+1 + 2+1).

**UPDATE 2026-06-04 — 1+1+1 unified equation pinned.** Validated (read-only `py/analyze_twist.py`,
68 1+1+1 sols 6×6/12×4/9×4/6×4): the **correct** criterion is `Tw(L_ij)=0` on **all three**
pairwise theta loops (= the shipped `twist_check`) — **68/68**. The EXPLAINER §2.5 *proposed*
reduction to per-chain `T_A=T_B=T_C` is **DISPROVED** (45/68): (1) cocycle obstruction — twisted
sols `{AB:0,AC:0,BC:720}` make `Tw_AB−Tw_AC+Tw_BC=720≠0`, so no per-chain potential exists; (2)
false negatives on foldable sols. **Twist is a closed-loop invariant, not a homology class** —
rank-2 cycle space but non-additive over cycle sums ⇒ must test all 3 loops, not an independent
2. Engine already correct; no code change. 2+1 still blocked only on 2-chain panel order. See
EXPLAINER §2.3/§2.5 (corrected) + LAB_LOG 2026-06-04.

**State.** 1+1+1 is *decided*: pairwise-loop twist (`search.js twistCheck` / `py/search.py
twist_check`) — each pair of the 3 chains forms a closed loop through the two fused
footprint hubs; require `Tw=0` on all pairs. Validated to discriminate on 6×6 1+1+1 (#1–4
all-pairs-0, #5–8 carry a 720 pair) and it fixes the per-chain false negatives. **2+1 is
pending** (`verdict.twist=null`): a 2-chain's per-panel HC order inside the domino is
unresolved, and a composite-centroid path there is non-physical (gives 936 = not a 360
multiple).

**Blocks.** (a) Reconstruct the 2-chain per-panel ordering (the inverse problem — search
emits folds, not an explicit HC). (b) The current pairwise loop closes through the hubs with
*diagonal* seam jumps (e.g. `(4,3)→(3,4)`), which break the checkerboard alternation at 2
points and inject the spurious `±90/±270` seam terms — so absolute `tw` magnitudes carry
hub artifacts (still discriminate, not yet exact). (c) No confirmed *non*-foldable label to
pin the threshold for 2+1 (lead has nonfoldable 6×5 — all 2+1 — to feed in).

**Math we established.** Twist = `Σ σ_i·(2·turn_i)` around the closed loop; `σ` alternates
mountain/valley. Crucially **odd/even position along the HC = the bipartite (checkerboard)
2-coloring** — every unit step flips `(x+y) mod 2`, so twist reads as *(turning on one
colour class) − (turning on the other)*. Clean fold ⟺ the two colour classes turn
equal-and-opposite. Twist depends on the *order/phase* of turns vs the valley/mountain
rhythm, **not** on net move counts (proven: #4 `(6,5)(2,9)(6,5)` ✓ vs #5 `(6,5)(8,3)(6,5)`
✗ — identical parity signature, opposite verdict). Validated primitive reproduces paper
`Tw=0` on 2×4 / 4×4 closed loops. Full diagnosis in `resources/twist_diagnosis.md`.

**Next step.** Solve the 2-chain HC reconstruction (or track crease/slit forward in the
search so the HC is known exactly), fix the hub-seam geometry to a true edge-adjacent route,
then validate both decomps against confirmed fold/no-fold cases (esp. the nonfoldable 6×5).

## Q2. Proof of non-wrapping for L 1+1+1 (or counterexample)

**Hypothesis (lead).** In every L-shape 1+1+1 solution, 2 of the 3 chains *minimally wrap
the outermost perimeter* of the grid; only the 3rd chain solves the interior.

**State.** Unproven. We have generator output to test against: 16 distinct 1+1+1 solutions
for 6×6 (and the `py` cache makes more grids cheap). Empirically all 6×6 1+1+1 are shape L
with per-chain `(nH,nV)` always `(even, odd)`.

**Next step (concrete, tractable now).** For each 1+1+1 solution, compute each chain's cell
set and test whether the boundary ring (perimeter cells) is exactly covered by 2 of the 3
chains, and whether those 2 are "minimal" (no interior detours). If it holds across all
generated grids → strong evidence; then attempt a proof (e.g. parity/area argument: perimeter
length vs chain length `K`, corner constraints). If any solution has a perimeter cell owned
by the *interior* chain, or a wrapping chain dipping inside → counterexample. This is a pure
post-processing pass over `results/*.json` — no engine change needed.

## Q3. Generalised recipe for L 1+1+1

**Idea (follows from Q2).** If 2 chains are forced onto the perimeter, the third chain's
path is *largely determined* — it must Hamilton-traverse the interior region with fixed
entry/exit at the footprint, even `nV`/odd `nH` (or vice versa per orientation), and land on
the exit footprint. So the recipe = (i) the forced perimeter wrap for 2 chains + (ii) a
constrained interior fill for the 3rd.

**State.** Conjectural; depends on Q2. (The old comb+zigzag `k` recipe — now retired — was one
such archetype-specific instance; 2+1 is proven not to need the zigzag.)

**Next step.** Once Q2 characterises the wrap, enumerate the interior-chain degrees of
freedom on small grids from the cache; look for a closed form for the interior path (length,
turn pattern) as a function of `m,n`. Cross-check any candidate recipe by generating its
chains and running them through the verdicts (`loadSolution` / `generate.py`).

## Q4. Tightening the vector-reflection criteria

**State.** Two checks currently gate "vectors stay aligned": orientation-aware `parityCheck`
(folds perpendicular to the inter-block crease must be even — `vectorPerpAxis`, 2+1 only;
1+1+1 falls back to legacy nH-even/nV-odd) **and** `reflectionCheck` (drive a canonical
vector through each chain, require all final tangents agree). They were kept *both* on the
conservative path.

**Open.** (a) Is the perpendicular-folds-even parity rule *sufficient* on its own (lead's
hypothesis), making `reflectionCheck` redundant — or does reflectionCheck still reject cases
parity admits? (b) The 1+1+1 generalisation of the vector rule is unresolved: an L corner has
two perpendicular creases, and a naive per-crease rule wrongly rejects the working solutions
(empirically all chains are nH-even there) — so what is the correct single-axis (or
multi-vector) rule for 1+1+1? (c) Does the rule need a *sign/direction* condition beyond
parity (vectors mustn't end on opposite sides — parity fixes the axis but maybe not the
side)?

**Next step.** Instrument the engine to log, per solution, both verdicts independently
(parity-pass vs reflection-pass) and find any solution where they disagree — that isolates
whether reflectionCheck adds constraint. Pure logging change in `search.js`/`py/search.py`.

**Findings (2026-05-28, `py/analyze_reflection.py`).** Ran both verdicts independently over the
exit-footprint-passing candidate population for 6×4 / 6×5 / 6×6 / 5×6 / 3×4 / 4×3 / 3×2 (harness
cross-checked — its both-pass-then-dedup counts reproduce the engine's solution counts exactly:
6×4=3, 6×5=5, 3×4=4, 4×3=2, 3×2=2). Contingency `parity × reflection`:
- **parity✓ ∧ reflection✗ = 0** across every grid, decomp and shape. So parity ⟹ reflection:
  `reflection_check` never rejects anything parity admits. **It is redundant** — dropping it
  leaves the accepted set unchanged. (Answers Q4a; confirms the lead's hypothesis.)
- **parity✗ ∧ reflection✓ = 54.** Reflection is strictly the *looser* check; parity is binding.
  For **2+1** reflection is *vacuous* — every 2+1 candidate passes it (P✗R✗=0), parity does all
  the discrimination. For **1+1+1** reflection does reject some (P✗R✗=44) but never beyond parity.
- **Q4c:** all 44 reflection failures are *edge* mismatches; **zero sign-only** mismatches. No
  evidence a sign/direction condition is needed beyond parity — parity already fixes the edge.
- **Q4b:** every accepted (P✓R✓) 1+1+1 solution — L *and* Rect — has all three chains' final
  vector identical at **(edge B, sign +1)**, with per-chain **nH even, nV odd** in every case.
  So the legacy nH-even/nV-odd rule is *consistent* with all accepted L 1+1+1 (it does NOT wrongly
  reject them, contrary to the earlier worry) — it is simply stricter than vector-coincidence.

**Remaining open.** Whether parity *over*-rejects genuinely-foldable configs (the 54 P✗R✓ cases:
reflection-admitted but parity-rejected) cannot be decided from vectors alone — needs twist /
physical ground truth (ties into Q1/Q2). Dropping `reflection_check` is an *output-preserving*
simplification (safe), pending a decision to act on it. Not yet verified on `search.js` (Python
authoritative; engines cross-checked).

## Q5. Extending to other shapes (lower priority)

The reference programme (`resources/twist_reference_code/.../lattice.py`) already handles
hexagons, triangles, parallelograms, and arrays with internal holes via a general
lattice/dual-graph + HC enumeration. Our tool is square-grid only (footprint = L / Rect on a
square lattice). Extending means generalising `fold.py`/`fold.js` reflection geometry and the
footprint enumeration to other tilings — large; defer until the square-grid 3-stack theory
(Q1–Q4) is settled.

## Q6. Rectangle folding recipe / 1+1+1-rectangle criteria

The I-shape boundary conjecture `(m−3)(n−3) ≥ 9` predicts which grids admit 1+1+1 (I-shape):
6×5 gives `6 < 9` → **no 1+1+1** (confirmed: the engine finds 0 1+1+1 for 6×5, only 2+1).
Open: verify the conjecture across more grids (the `py` cache makes this a batch run —
`generate.py` over a grid sweep, then check which have ≥1 1+1+1 solution), derive the
analogous L-shape boundary, and find a constructive recipe for the I-shape interior.

## Q7. Minimum grid size — L vs Rect (resolved empirically 2026-05-28)

**Question.** What is the minimum grid that admits a valid solution, and does it differ
between the L footprint and the Rect (I-shape, 3×1) footprint?

**Method.** Gate-relaxed exhaustive sweep. The three arithmetic/conjectural gates were
removed *for testing* (`py/search.py:419` marked `# TEST`): the `mn%6==0` requirement relaxed
to `mn%3==0`, the `K=mn/3` even gate dropped, and the `n≥4` gate dropped. Only `mn%3==0` is
kept — it is structural (`K=mn/3` must be a positive integer to tile). Driver:
`py/sweep_minsize.py <maxdim> <maxarea>`, runs L-only and Rect-only per grid, counts solutions
passing exitFootprint + parity + reflection, split by decomposition and twist verdict.

**Result — the two minimums differ; L is always larger.**

| "valid" definition | L min grid | Rect (I / 3×1) min grid |
|---|---|---|
| any valid (exit+parity+reflection) | **4×3** (area 12, K=4) | **3×1** (area 3, K=1) |
| valid 1+1+1 (any twist) | **5×6** (area 30) | **3×2** (area 6) |
| valid 1+1+1 with Tw=0 | **5×6** (area 30) | **3×2** (area 6) |

**Findings.**
- **Rect bottoms out at 3×1**: the footprint *is* the whole grid, K=1, zero folds → trivial
  I-shape (a 2+1 solution; twist undecided). First *Tw=0* Rect is 3×2 (1+1+1).
- **L bottoms out at 4×3 / 3×4 (area 12), not smaller.** The L footprint needs a 2×2 bounding
  box (m≥2, n≥2); area-6 grids (3×2, 2×3) and area-9 (3×3) fit the footprint but yield **0**
  valid L — the fold geometry cannot produce a valid L-exit that tight.
- **The gates were the binding constraint for Rect, not for L.** Removing the gates drops the
  Rect minimum from area 12 (3×4, the smallest grid passing the *original* `mn%6==0`+`n≥4`
  gates) down to area 3 (3×1). The L minimum stays at area 12 — 4×3 is just the transpose of
  3×4, which already passed the original gates. So Rect's small-grid floor is *gate-imposed*,
  while L's floor is *structural* (footprint + folding), independent of the arithmetic gates.
- **L 1+1+1 does not exist below 5×6.** Every valid L solution below 5×6 is 2+1. Since twist
  is decided only for 1+1+1 (2+1 → `verdict.twist=null`, cf. Q1), the smallest L grid on which
  Tw=0 can be *asserted* is 5×6 (16 distinct 1+1+1 there; subset Tw=0).

**Caveat.** These minimums are under the *relaxed* gates. Under the original gates Rect and L
both first appear at 3×4 (area 12); the divergence is exactly what relaxing the gates exposes,
and it isolates that the Rect floor is arithmetic while the L floor is geometric.

**Open follow-on.** Prove the L area-12 floor (why 3×2/2×3/3×3 admit no valid L-exit); confirm
whether 5×6 is genuinely the smallest L 1+1+1 across non-corner footprints
(`allowNonCorner`, untested here); decide whether "minimum grid for valid L-shaped HCs" should
be quoted as 3×4 (any decomp) or 5×6 (Tw=0-assertable 1+1+1). Tooling: `py/sweep_minsize.py`.

---

# New features this round

(to fill in once scoped)
