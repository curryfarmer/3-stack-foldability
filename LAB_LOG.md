# Lab Log — Folding Drawer (3-stack HC folding)

Running log. Newest entry on top. Each entry: date, what was done, what was found, what's next.

---

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
