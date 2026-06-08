# Lab Log — Folding Drawer (3-stack HC folding)

Running log. Newest entry on top. Each entry: date, what was done, what was found, what's next.

---

## 2026-06-08 — triangle-lattice PoC (extend 3-stack to equilateral triangles)

New self-contained module `py/tri/` (lattice / fold / twist / search / render + `run_poc.py`),
run via `.\.venv\Scripts\python.exe`. Region = triangular lattice, bipartite by orientation
(UP σ=+1, DOWN σ=−1). Goal: test whether the square machinery (twist `Tw=0`, vector reflection,
sub-chain length) ports, and produce 3 examples each of 1+1+1 / 2+1.

**What ported + verified (the math transfers exactly):**
- Lattice + bipartite σ: 12-tri parallelogram and 24-tri hexagon built; every dual edge joins
  UP↔DOWN (σ alternates) — the triangle analog of the square checkerboard, verified.
- Reflection geometry: reusing `py/twostack.py _reflect_point`, all 26 directed dual adjacencies
  reflect a triangle exactly onto its neighbor (tol 1e-9) — folding across a triangle edge = the
  dual move, confirmed.
- Closed-loop twist: the 6-triangle ring around an interior vertex gives every γ = 120° (60° turn
  doubled), **Tw = 0**, a clean multiple of 360 — the triangle analog of "no 936° pathology".
  `tritwist.loop_twist` is the square `_pair_loop_twist` verbatim (atan2 odd/even σ-weighted).

**The obstruction (a genuine negative result, not a port bug):**
- 3-stack TILINGS exist (e.g. 24 distinct 1+1+1 tilings on the hexagon side-2, K=8; 48 2+1
  rib+1-chain covers on the 2×3) — chains start at a trapezoid footprint and tile the region.
- **But none CLOSE:** the three chain-ends never reform a congruent exit footprint. Tested across
  6 grids (parallelograms 2×3/4×3/5×3/3×5/4×6, hexagon side-2, big triangle side-6): **closing
  1+1+1 = 0 everywhere.** On every hexagon tiling the 3 ends are pairwise non-adjacent (degrees
  0,0,0); the 2+1 has 0 covers with both hubs adjacent.
- Cause = parity/geometry: a trapezoid footprint is color {c1,c1,c2}; even-K paths flip color, so
  ends are {c2,c2,c1}, and the lone c1 end is never adjacent to both c2 ends on small grids.
  Also: parallelograms' honeycomb dual is too thin to host 3 disjoint equal paths at all; big
  triangles are color-unbalanced (#UP−#DOWN = s) so no balanced 1+1+1. The hexagon is the only
  balanced+fat small region, and it tiles but does not close.
- Consequence: the closed-loop twist CRITERION needs the loop's 2nd hub (the exit footprint);
  with no closing tiling, the pairwise-loop twist is fractional (e.g. AB=−404, BC=+404, AC=−240
  on a hex tiling) — i.e. undefined, exactly as expected for an open seam.

**Figures** (`report/tri/`): `lattice_hex2.png` (bipartite σ), `ring_twist.png` (verified Tw=0
closed loop), `tiling_111_{1,2,3}.png` (non-closing 1+1+1 tilings — visually: starts clustered at
the footprint, ends scattered to 3 far corners), `tiling_21.png`.

**Next (decision pending with lead):** the square port reproduces all the *math* but reveals an
existence/parity wall on small triangle grids. Options: (a) prove the parity obstruction as a
theorem (no closing trapezoid-to-trapezoid 1+1+1 on triangles); (b) adapt the triangle
footprint/exit model (different footprint shape, or translated/disconnected exit); (c) search
much larger / specially-shaped grids for a closing fold; (d) accept the open-path twist as the PoC
signal. See `TODO.md` research-extensions.

---

## 2026-06-08 — consolidated session report

Theme: hardening the 2+1 twist criterion. Three findings, one experiment designed. Test bed
for all computational claims: **every cached 2+1 solution — 303 across 7 grids** (6×4:2,
6×5:5×2 files, 6×6:14×2 files, 6×7:41, 8×6:129, 9×4:11, 12×4:82), replayed from
`results/*.json` via `py/fold.py`, twist via the shipped `_pair_loop_twist` primitive
(itself validated 2026-06-07: oracle 936/936 on stored 1+1+1 pairwise twists + paper 2×4 /
3×3-hole cases). All checks are read-only post-processing; no engine change. Physical
ground truth still pending (`results/twoplus1_labels.json` all-null).

**Finding 1 — "Filled" half-tile reduction: the strand loop made honest; recipe finalized.**
*Claim.* Lead objection: kept-strand 3-jumps are not panel-adjacent ⇒ strand "loop" isn't a
true loop. Fix: **fill each 3-jump through the two holes it skips** (= twin strand's old+new
cells, `P_k→Q_k→Q_{k+1}→P_{k+1}`). Lemma: inserted vertices are collinear (γ=0, contribute
nothing) and shift later indices by 2 (σ phase preserved) ⇒ **Tw(filled) ≡ Tw(jump)**.
*Verified by.* Per-solution assertions over all 303: unit-seam strand exists 303/303; filled
loop every step unit incl. seams+wrap 303/303; fills land only on holes + path simple (no
revisit) 303/303; loop length even 303/303; **Tw(filled) == Tw(jump) exactly 303/303**;
verdict histogram unchanged {0: 292, ±720: 11}.
*Consequence.* The filled loop is a genuine closed unit-step panel loop on the holey grid ⇒
the RSPA 2-stack theorem applies verbatim — no ansatz left in the strand model. Canonical
rule tightened from "non-DIAG strand" to **unit-seam strand** (base edge-adjacent to the
1-chain base; Rect 2JMP seams would need a single-cell insertion = odd index shift = σ-phase
break). Final recipe: (1) keep adjacent strand, (2) delete twin → holes, (3) fill 3-jumps,
(4) close with reversed 1-chain + unit hub seams; foldable ⟺ Tw=0. Bonus: the fill's ribbon
zigzag recovers a partial per-panel HC order of the 2-chain — the old "2-chain inverse
problem" largely dissolves.

**Finding 2 — Hub-exception domino tiling (lead's proposal): angle issue resolved, but it is
a THIRD inequivalent invariant.**
*Claim.* Keep the domino-level (centroid) body but connect at each hub through the single
tile adjacent to the 1-chain (2×1→1×1 transition). The cell-center↔centroid offset is ±0.5
purely along the domino axis ⇒ inserting it as an axis-aligned half-step removes all
fractional angles.
*Verified by.* Same 303-solution sweep: hybrid loop all steps axis-aligned 303/303;
**0 loops with fractional turns** (the ±212.52° = 4·2·atan(½) centroid-seam artifact is
gone). BUT **Tw(hybrid) ≠ Tw(strand) on 16/303**, differences all full twists
(−720×12, +720×3, +1440×1); hybrid flags 20 twisted vs strand's 11; on 8×6 #265 hybrid says
+720 where strand AND pure-centroid both say −720.
*Conclusion.* Angle-clean ≠ equivalent: the junction framing carries real turn content. The
hybrid is a third distinct invariant, still an ansatz (centroid vertices are not panels,
half-steps are not panel adjacencies), whereas the filled strand is theorem-grade.

**Finding 3 — Model-selection experiment designed; sheets ready.**
The strand-vs-hybrid conflicts land on already-printed sheets, giving a direct physical
discriminator with zero new fabrication. Priority folds (PNG + PDF in `report/foldsheets/`,
outcome table in `TODO.md`): **6×5 #1** (strand FOLD / hybrid JAM), **6×7 #8** (strand JAM /
hybrid FOLD), **6×6 #13** (both JAM — model-independent test of the twist criterion),
**6×6 #7** (both FOLD — positive control). Outcomes: (fold,jam) ⇒ strand wins; (jam,fold) ⇒
hybrid wins; (fold,fold) ⇒ both invariants wrong; (jam,jam) ⇒ both partially right, sharper
theory needed. Verdicts go in `results/twoplus1_labels.json` per `FOLDING.md`.

*Artifacts this session:* fill-recipe + hybrid validation runs (inline, reproducible against
`py/analyze_2plus1_reduction.py` helpers); `hypothesis_2plus1_reduction.md` §3b (loop-repair
lemma + tightened canonical rule); priority-fold PNGs `{6x5_1,6x7_8,6x6_13,6x6_7}.png`;
`TODO.md` priority-folds section.

## 2026-06-07

**Foldsheets regenerated (13 cases) + positive validation case chosen + `TODO.md` created.**
Lead requested one 6×6 2+1 predicted-foldable pattern → **6×6 #7** (L, 2chain-H, K=12;
canonical strand P unit/unit, Tw=0; self-checks clean). Re-rendered the curated make-sheets on
this machine (`report/foldsheets/`, was empty here) **adding the 3 predicted NEGATIVES**
(6×6 #13/#18, 6×7 #8, canonical Tw=±720) so hand-folding tests the criterion both ways;
`results/twoplus1_labels.json` template now 13 entries (all null). `6x6_7.png` rendered for
reference. Python deps now live in `.venv/` (matplotlib; gitignored). New `TODO.md` holds the
validation queue + lead's additions (clean up 3-stack code; physically exhaust 6×5; physical
models for bipartite-tiling necessity; extend to right/equilateral triangles + hexagons).
NB: criterion predicts **all five 6×5 2+1 fold** — opposite of the prior suspicion; those
sheets are the highest-information folds. Also new: `py/render_reduction.py` draws the
half-tile-reduced view of any 2+1 case (holey grid, kept-strand walk, ghost deleted strand,
hub seams, σ marks) — `report/foldsheets/6x6_7_reduced.png` rendered for #7; fixed a latent
legend-clipping bug (`clip_on`) in `make_foldsheets.py`/`explainer/lib.py` and re-rendered
all 13 sheets.

**Q1 2+1 — strand reduction VALIDATED on cache (canonical-strand rule); §5.1 strand-equivalence
DISPROVED; domino-bipartite variant subsumed. New `py/analyze_2plus1_reduction.py`** (303 2+1
sols across 6×4/6×5/6×6/6×7/8×6/9×4/12×4; oracle: trivial reduction on 1+1+1 reproduces all 936
stored pairwise twists).
- **Reduction preconditions all hold (303/303 self-checks)** but two §2 claims in
  `hypothesis_2plus1_reduction.md` are FALSE as stated: strand steps are **{1,3}** not unit
  (along-axis folds throw the far strand by 3), and `Q = P + fixed d` fails (d flips sign each
  along-axis fold — strands swap sides; `reflect_cells` preserves list order, so cells[0]/[1] do
  track material halves). Salvaged invariants: axis-aligned odd-length steps ⇒ checkerboard
  alternation intact, turns ∈ 90°·ℤ ⇒ twist physical. The 936° centroid pathology is gone.
- **§5.1 disproved → canonical-strand rule confirmed:** P/Q verdicts disagree 66/303. The
  DIAG-seam strand (L footprint, strand diagonal to the 1-chain base) carries a quantized
  **±360 (half-twist) seam artifact**: `tw_DIAG − tw_canon ∈ {0,±360}` in all 201 single-DIAG
  cases, never anything else. **Canonical strand = the non-DIAG one** (edge-adjacent to the
  1-chain base; the doc's own fallback rule). Canonical loop is always physical:
  tw ∈ {0,±720} (integer Tw), 303/303. Rect strands (unit/2JMP) agree exactly — choice
  immaterial when both loops are non-degenerate.
- **Approach A (domino-level bipartite / centroid path) is subsumed:** index parity IS the
  domino bipartite; centroid body is axis-aligned (steps 2/1) but the hub seam is off-lattice
  for L (±212.52 = 4×2·atan(½) artifact, the analog of the old 936°); centroid tw == canonical
  tw exactly on all 227 cases where the seam artifact vanishes (all Rect + offset-0 L). Use B.
- **Criterion (conjecture, cache-validated): 2+1 foldable ⟺ Tw(canonical-strand loop)=0.**
  After reduction the structure has cycle rank 1, so the single loop is the whole cycle space —
  no 1+1+1-style all-pairs subtlety. **Flagged twisted (11/303):** 6×6 #13(+720) #18(−720),
  6×7 #8(+720), 8×6 #41/#42/#44(+720) #127/#128(−720) #265(Rect,−720). **All 6×5 pass** —
  predicts the lead's suspected-nonfoldable 6×5 set actually folds (or the criterion is
  incomplete). Convention flips (σ phase / γ sign / both / orientation): 0 verdict changes.
- **Action:** physical labels are the decider (`twoplus1_labels.json` still all-null) — and the
  curated foldsheet set contains NO predicted-twisted case; add 6×6 #13/#18 + 6×7 #8 to the
  make-sheets so hand-folding can test the negatives, not just the positives.

**1+1+1 loop math validated against the two structural objections (new `py/analyze_loop_seams.py`).**
Question (lead): the three pairwise theta loops AB/AC/BC share chains (rank-2 cycle space), and one
loop literally closes with a diagonal step — does the math survive? Read-only sweep over all cached
1+1+1 (312 sols / 936 loops: 6×4, 6×6 ×2, 8×6, 9×4, 12×4):
- **Seam census:** every solution has exactly ONE degenerate-seam loop — the non-adjacent base
  pair (L: diagonal `(0,1)~(1,0)`; Rect: colinear 2-jump `(0,0)~(0,2)`) — degenerate at BOTH hubs
  (zero mixed loops ⇒ each chain keeps its footprint role at exit). The other two loops are honest
  unit-step lattice cycles where index parity = checkerboard, so the paper's Tw applies verbatim.
- **Diagonal artifacts cancel (empirically):** seam-flank doubled-turns are ±90/±270 (impossible
  on-lattice), contributing 0/±180 to odd−even with the body always compensating; all 936 loop
  values ∈ {0, 720} — integer Tw only, no 936°-style pathology. Cancellation is empirical, not
  theorem-backed (paper Tw is defined for unit-step loops) — "discriminates, not yet exact" stands.
- **Rank-2 ≠ 2 tests:** cocycle `Tw01−Tw02+Tw12 ≠ 0` in 55/312 (always ±720, pattern {0,0,720}) —
  twist is not additive over cycle sums (reconfirms 2026-06-04 disproof). Testing any fixed 2 loops
  misclassifies vs stored verdicts (drop12 → 51 wrong, drop02 → 4 wrong).
- **NEW — twist lives ONLY on the degenerate loop:** 624/624 unit-seam (adjacent-pair) loops have
  Tw=0; all 55 nonzero twists sit on the non-adjacent pair (L: pair 12, Rect: pair 02).
  **Conjecture:** adjacent-pair loops are identically Tw=0 ⇒ the 1+1+1 criterion reduces to a
  SINGLE loop test, `Tw(non-adjacent pair)=0`. Caveat: population is conditioned on
  exit+parity+reflection passing — test on the pre-twist candidate pool before believing the lemma.

## 2026-06-04

**2+1 — ground-truth fold harness + reduction hypothesis.** Decided to make physical labels
first (twist criterion is unfalsifiable without them; entanglement is 3D, invisible to the 2D
model). New `py/foldpattern.py` replays a solution and classifies every interior edge as
crease / rigid (2-chain domino internal) / slit purely from fold geometry — **no per-panel HC
order needed**. Self-check: **615/615** solutions partition cleanly; 1+1+1 6×6 crease degHist
`{1:6, 2:30}` matches the known reconstruction. `py/make_foldsheets.py` renders printable
make-sheets (`report/foldsheets/*.pdf`, 10 curated cases: 6×4/6×5/6×6/9×4, smallest-K +
suspected-nonfoldable 6×5) and emits `results/twoplus1_labels.json` for hand-fold verdicts. See
`FOLDING.md`. **Reduction hypothesis (lead, `hypothesis_2plus1_reduction.md`):** collapse the
rigid 2-chain to a representative 1-chain by deleting half its tiles (one strand → holey grid);
the surviving strand reproduces the domino's folding (rigid lockstep, translation-equivariant
turns), is on-lattice (fixes the 936 centroid artifact), and feeds the *same* `Tw(L)=0` machinery
→ 2+1 becomes a single chain-vs-chain loop on a holey grid. To validate against the labels.


**Q1 twist — unified 1+1+1 equation pinned; EXPLAINER §2.5 per-chain form DISPROVED.**
Ran a candidate-idea workflow (6 lenses → 18 candidates → adversarial verify → synth) then
validated against the cache with new read-only `py/analyze_twist.py` (68 1+1+1 sols across
6×6/12×4/9×4/6×4; oracle O1 2×4→0, O2 3×3-hole→+720 both PASS).
- **Correct unified equation (1+1+1 and 2+1):** foldable ⟺ `Tw(L_ij)=0` on **all three**
  pairwise theta loops `L_ij` = chain i (S→E) + chain j (E→S), each via the paper closed-loop
  `Tw=(1/4π)Σσγ`. = the shipped `search.py twist_check`. **Matches ground truth 68/68.** Engine
  was already correct; no code change needed.
- **§2.5 `T_A=T_B=T_C` (per-chain global-σ) is WRONG — 45/68.** Two disproofs: (1) **cocycle
  obstruction** — if `Tw(L_ij)=T_i−T_j` then `Tw_AB−Tw_AC+Tw_BC=0` forced, but twisted sols are
  `{AB:0,AC:0,BC:720}` ⇒ 720≠0, so no per-chain potential exists; (2) **false negatives** —
  foldable sols (all pairwise 0) give disagreeing `T=[0,180,−180]` etc. (interior-corner sum
  drops the orphan/hub terms). Root: **twist is a closed-loop invariant, not a homology class** —
  theta cycle rank is 2 but twist isn't additive over cycle sums, so all 3 loops must be tested
  (twisted pair = BC for L, AC for some Rect). Corrected EXPLAINER §2.3/§2.5/§3 + this log.
- **2+1 unchanged:** same all-pairwise-zero form; still blocked only on recovering the 2-chain
  per-panel order (forward-crease tracking is the clean enabler). Validation artifact:
  `py/analyze_twist.py`.

**Q2 wrapping — empirical + proof attempt (strong-partial).** Live `py/analyze_wrap.py`:
6×6 1+1+1 = **8/8 CLEAN-WRAP** (2 chains cover the full 20-cell ring, interior chain touches
0 ring cells); 2+1 = **0/14** → wrapping is **1+1+1-specific**, not a property of all decomps.
Proof workflow (7 agents: area-counting · parity/checkerboard · corners/Jordan · connectivity,
+ 2 adversary + synth) → **strong-partial, survives, no counterexample.**
- **Proved (backward):** exact cell accounting — `ring R=2m+2n−4`, `K=mn/3`,
  `interior=(m−2)(n−2)`, and `ring+interior=3K`; `2 wrap = R + spill`, `spill=2K−R`;
  `3rd chain = interior − spill = K` exactly (zero slack). `K<R` ⟺ `(m−3)(n−3)>3` (always,
  ≥9) ⇒ no single chain covers the ring ⇒ ≥2 must. Bipartite colour-balance forces the 3rd
  chain interior *given* the 2 cover the ring.
- **Missing lemma (forward, the crux):** *footprint-forced ring partition* — two
  footprint-anchored single-path `(nH even, nV odd)` chains must cover every ring cell with no
  gap. Close this ⇒ wrapping theorem done.

**Q6 dent — boundary conjecture not sufficient.** Generated **6×7** (42 cells, ~11 min): 41
sols, **ALL 2+1, ZERO 1+1+1** despite `(m−3)(n−3)=12≥9`. So `(m−3)(n−3)≥9` is **necessary,
not sufficient** (under `allowNonCorner=false`). Pattern: 6×6 (even×even) has 1+1+1; 6×7
(even×odd) does not → **suspected extra parity condition** (both dims even?).
Caveat: 6×7=0 is corner-footprint only; non-corner untested.

**Q6 RESOLVED (conjecture) — existence is ARITHMETIC, not geometric.** New data (9×4, 6×4 —
generated today) breaks BOTH the `(m−3)(n−3)≥9` boundary AND the even×even parity rider: **9×4
is odd×even with (m−3)(n−3)=6<9 yet has 15 1+1+1** (6 L + 9 Rect). Tabulating `mn mod 12`:
- has 1+1+1: 6×4 (24), 6×6 (36), 9×4 (36), 12×4 (48) — all `mn≡0 mod12`.
- none: 6×5 (30), 6×7 (42) — both `mn≡6 mod12`.
**Conjecture (6/6): a grid admits 1+1+1 ⟺ `mn ≡ 0 (mod 12)` (⟺ K=mn/3 ≡ 0 mod 4).** Cleanly
replaces the falsified area boundary. (Corrects old note "6×4 only L 2+1" — 6×4 has 1 Rect
1+1+1.) Running 8×6 (48≡0 → predict HAS) and 6×9 (54≡6 → predict NONE) now double as tests.
Open: derive WHY K≡0 mod4 (likely a fold-parity / 3-chain exit-matching argument).

**12×4 confirms both leads (even×even, (m−3)(n−3)=9).** 102 sols; has 1+1+1 (10 L + 10 Rect) →
even×even parity prediction ✓. Wrap test: **10/10 L 1+1+1 CLEAN-WRAP** (ring=28 covered exactly
15+13, interior chain 0/16; spill=2K−R=4, interior=(m−2)(n−2)=20=K+spill ✓). Combined with 6×6
→ **18/18 clean-wrap across two grids** (square 6×6 + thin 12×4), zero counterexamples — strong
cross-aspect-ratio evidence for Q2. Parity table so far: even×even {6×6, 12×4} HAVE 1+1+1;
even×odd {6×7} has NONE. 8×6 generating to confirm the even×even positive. ⇒ revise Q6 boundary
to likely need an **even×even** rider on `(m−3)(n−3)≥9`.

## 2026-06-03

**Built `explainer/` — first-principles twist-theory diagram set.** New standalone matplotlib
module (decoupled from the fold engine): `lib.py` (primitives + `grid.js` palette), `gen.py`
(17 figures → `svg/`), `EXPLAINER.md` (walkthrough, builds to HTML via pandoc), `README.md`.

- **Track A (A1–A12) — 2-stack:** grid→graph, HC creases/slits, fold=reflection,
  two-reflections=rotation (γ=2α), square γ∈{0,±180}, σ checkerboard `(−1)^{x+y}`, g(i)=σγ,
  odd-reflection flip = the two stacks, even-loop bipartite, worked 2×4 `Tw=0` and ring `Tw=+1`,
  CWF `Lk=Tw+Wr`.
- **Track B (B1–B5) — 1+1+1:** loop vs theta graph, theta anatomy (2 rigid hubs + 3 chains,
  rank 2), pairwise loops, chain-end orphan reflection (Q8) + fused-hub closure, proposed
  criterion.
- **Proposed 1+1+1 math captured (refines current pairwise code):** per-chain
  `T_i = Σ σ(v)γ(v)` over interior L-corners with a **global** `σ=(−1)^{x+y}` (not per-chain
  index — that reset was the old false-negative); foldable ⟺ `T_A=T_B=T_C`. Derived from CWF on
  the theta's 2 fundamental cycles (each pairwise `Tw = T_i−T_j`); the common S→E rotation cancels
  from every pairwise twist (forward − reverse), so twist constrains only the agreement, not its
  magnitude (magnitude is geometric — `exitFootprintCheck`). Computing `T_i` independently avoids
  the diagonal hub-seam ±90/±270 artifacts of the concatenated pairwise walk. **Not yet ported
  to `search.js`/`py/search.py`** — proposal only; validate vs 6×6 cache (#1–4 all-pairs-0,
  #5–8 a 720 pair) and a confirmed non-foldable before acting. Ties to Q1/Q8.

**Session start.** Re-read report, resources, results to reload context.

- Reviewed: `context.md`, `report/README.md`, `resources/twist_diagnosis.md`, `results/manifest.json`.
- Cached results on disk: 6×4 (3 sols), 6×5 (5 sols), 6×6 (30 sols); plus 2-stack 6×4 (15 HC), 6×5 (44 HC).
- Repo state: **not a git repo yet** — `git init` + first commit pending (see TODO).

**Open questions surfaced** (detail in chat / `context.md` Q1–Q7). Active frontier:
- Q1 twist criterion for 2+1 (blocked on 2-chain per-panel HC reconstruction).
- Q2 non-wrapping proof for L 1+1+1 (post-processing pass — tractable now).
- Q3 generalised L 1+1+1 recipe (depends on Q2).

**Planned this session:** codebase cleanup + first git commit.

**Next:** _to fill in as work proceeds._
