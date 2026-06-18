# Candidate ideas for the 2+1 twist gate

Deep-research output (53-agent read-only workflow: map → theory → ideate → adversarial-vet →
synthesize) cross-checked against firsthand reads of `py/search.py`, `py/twostack.py`, `py/fold.py`,
`py/lattice/square.py`, `experimental/common.py`, and the two design docs
(`docs/research/twist_diagnosis.md`, `docs/research/hypothesis_2plus1_reduction.md`). The factual
backbone is `experimental/VERIFICATION.md` (twist formula faithful, parity σ-sound, shipped engine
does **not** twist-gate 2+1, `8x6#202` the lone twist-only witness).

## Headline

**Model B (canonical-strand jump) is already the answer.** The two "invent new math" directions were
adversarially killed (both re-inject the atan(½) seam artifact and break the `filled==jump` theorem).
The remaining work is *operationalize + physically validate*, not new theory.

**Recommended sequence: fold `8x6#202` first → if it JAMs, wire Model B (candidate #1) behind an
experimental flag.** Everything else is calibration (close the FOLD-side ground-truth gap) or
deferred theory.

## Background facts these candidates rest on

- **Twist invariant.** Foldable ⟺ all pairwise-loop twists vanish. A loop = `body + reversed(path1)`
  closed through the two fused footprint hubs; `Tw = (1/4π)·Σ σ(v)·γ(v)`, σ=(−1)^(x+y) checkerboard,
  γ=2·signed-turn. On-lattice ⇒ Tw ∈ 360·ℤ.
- **The 2+1 indeterminacy.** A rigid domino's per-placement Hamiltonian order is underdetermined from
  the fold sequence. The naïve centroid (one point/placement) leaves the lattice at along-axis folds
  → the **936° pathology** (non-360-multiple, non-physical).
- **Model B fix (canonical-strand jump).** Keep one strand cell/placement (the cell edge-adjacent to
  the 1-chain base ⇒ unit-seam hubs); the residual 2-unit shows up as an axis-aligned 3-jump. All
  turns are 90° multiples; Tw ∈ {0, ±720}. Cache-validated on 303 2+1 across 7 grids;
  **`filled==jump` 264/264** (the holey-grid repair, which routes 3-jumps through the deleted twin's
  holes with collinear γ=0, reproduces the jump Tw on every survivor).
- **atan(½) seam residual.** The non-canonical (diagonal-seam) strand and the partial/centroid-hybrid
  model both leave the cell sublattice at a 1↔2-unit seam → atan(½)=26.565° (doubled 53.13°),
  quantized to ±212.52° on L-footprints. This is the named "small sibling of 936°" — non-physical.
- **Shipped state.** `search.twist_check` returns `decided=False` for any chain with `len(baseCells)≠1`,
  so `verdict.twist` is `null` for all 2+1 — twist gates nothing for 2+1 today.
- **Ground truth.** 3 physical JAM labels (`6x5#1`, `6x6#1`, `6x7#8`), **zero FOLD labels**. All 3
  JAMs are caught upstream by the corrected reflection gate (`6x7#8` also by twist=720). `8x6#202`
  (Tw=−720) is the **sole** reflection+parity passer with Tw≠0 across all 264 — and it is physically
  unlabelled.

## Ranked candidates

| # | candidate | verdict | core of it |
|---|-----------|---------|------------|
| 1 | **Wire Model B into `search.twist_check` behind an experimental flag** | CONDITIONALLY PASS | cache-validated (303), `filled==jump` 264/264, Tw∈{0,±720}; add seam-diagnosis guard to `pick_canon_idx` (fall to `decided=False` if both strands DIAG); gate behind `opts['twist_2plus1_model_b']` |
| 2 | **Physically fold `8x6#202`** (Tw=−720) | NECESSARY DECIDER | the sole reflection+parity passer with Tw≠0; JAM ⇒ twist gate justified, FOLD ⇒ criterion incomplete. Highest information |
| 3 | **Fold the 6×5 2+1 trio** | MODERATE | fills the FOLD-side ground-truth gap (only JAM labels exist); 6×5 has no 1+1+1 → maximal edge case |
| 4 | **Validate the partial-decomp overhang class** | WEAK | fold representatives of the atan½ overhang buckets — real offset-fold vs jam |
| 5 | **Solve the inverse-HC order via bipartite CSP** | WEAK / SPECULATIVE | prove the canonical-strand rule is the unique MV-consistent HC order; doesn't change the shipped engine |
| 6 | Discrete Gauss-Bonnet holonomy reformulation | **FATAL** | breaks `filled==jump`; doesn't resolve the seam artifact |
| 7 | Footprint-middle hub-insertion routing | **FATAL** | re-injects the atan½ seam artifact; breaks the K-placement invariant |

---

## Candidate 1 — Wire Model B behind an experimental flag  *(CONDITIONALLY PASS)*

**Mechanism.** In `search.twist_check`, add a 2+1 branch (`len(baseCells)==2`): build the canonical
strand via `pick_canon_idx` (cell edge-adjacent to the 1-chain base), form the loop
`body + reversed(path1)`, run `common.loop_tw`; return `decided=True, Tw==0`. Gate the whole branch
behind `opts['twist_2plus1_model_b']` (false by default) so the shipped engine is unchanged in
production but the gate is live under test.

**Why it might work.** It only wires an *already-validated* model — nothing new. (1) cache-validated
on 303 2+1 across 7 grids; (2) `filled==jump` proven 264/264; (3) all turns are 90° multiples
(Tw ∈ {0,±720}), so the 936° pathology cannot appear; (4) the canonical-strand rule is deterministic
and rejects the ±360 diagonal-seam artifact by construction.

**Risks.** The seam-diagnosis fallback in `pick_canon_idx` picks strand 0 if *both* strands have
diagonal seams — which could re-admit the ±360 artifact. Flipping `verdict.twist` null→bool for 2+1
is an intentional behaviour change that ripples into golden/baseline/findings (see
`twist-2plus1-model-decision` memory).

**How to test.** (1) Add a seam-validation guard to `pick_canon_idx`: if both strands carry DIAG
seams, return `decided=False` (preserve the current null, don't guess). (2) Regression test the 68
1+1+1 cases to prove the decomp-branching doesn't disturb shipped 1+1+1 twist. (3) Keep the flag
false by default; regen golden + baseline only when the flag flips. (4) **Gate production rollout on
the `8x6#202` physical label** — this candidate is correct *iff* `8x6#202` JAMs.

**Skeptic refutations (and why they don't sink it).** Reviewers attacked every *new-math* variant for
breaking `filled==jump` — but this candidate adds no new geometry, it ships the model that *defines*
`filled==jump`. The only live objection is the both-strands-DIAG fallback, neutralized by the
guard above (fall to `decided=False`).

---

## Candidate 2 — Physically fold `8x6#202`  *(NECESSARY DECIDER — do this first)*

**Mechanism.** Fold the one case that disambiguates the whole question. `8x6#202` (Rect footprint,
K=16, Tw=−720, robust to both strand-index and full-centroid ⇒ not a hub/strand artifact) is the
**sole** 2+1 across all 264 cached that passes exit+parity+reflection yet has Tw≠0.

**Why it might work.** This is the single highest-information fold in the entire dataset. It is the
only experiment that separates "Tw=0 is *necessary*" (already proven) from "Tw=0 is *sufficient*".
- **JAM** ⇒ reflection false-passes a real jam, the twist gate earns its keep → wire Model B (#1).
- **FOLD** ⇒ Tw=−720 is a false-reject, the criterion is incomplete → twist theory needs work.

**Risks.** Fold-technique ambiguity (creases not pre-scored, material stiffness, non-intuitive
intermediate placements at K=16). Mitigate with cardstock + pre-creasing + an independent second
folder.

**How to test.** Pattern already parked at `results/2+1 testing/to_fold/8x6_202.json` (+ `_TEST_PLAN.md`):
footprint `(0,0)(1,0)(2,0)`, 2-chain base `(0,0)(1,0)`, 1-chain base `(2,0)`, full fold-arrow order
per chain. Fold both chains in arrow order; record FOLD / JAM / FOLD-with-overhang into
`results/foldfindings.json`.

**Skeptic note.** No reviewer disputes the value — only flags that one fold can't be done sloppily.
Hence the independent-folder mitigation.

---

## Candidate 3 — Fold the 6×5 2+1 trio  *(MODERATE)*

**Mechanism.** Fold the 3 distinct (post-dedup) 6×5 2+1 solutions, all predicted-FOLD (canonical Tw=0).

**Why it might work.** Current ground truth is JAM-only (3 labels, 0 FOLDs), so we cannot yet tell
whether Tw=0 is *sufficient* or merely *necessary*. 6×5 is the smallest grid with multiple 2+1
solutions, and it has **no 1+1+1 decomposition** — a maximal edge case where 2+1 is the only 3-chain
route, and where the lead earlier suspected non-foldability. All-FOLD here would be the first FOLD
calibration; any JAM despite Tw=0 would *falsify* (not just dent) the criterion.

**Risks.** Selection bias (fold all 3, not a subset). If all three jam despite Tw=0, the criterion is
wrong and deeper work is needed — but that outcome would be surprising given `filled==jump` + cache.

**How to test.** Extract the 3 from the 6×5 cache (post-reflection, post-parity), generate sheets via
`experimental/make_fold_bundle.py`, fold alongside the `8x6#202` session, record 3 entries.

---

## Candidate 4 — Validate the partial-decomp overhang class  *(WEAK)*

**Mechanism.** Fold 4–6 representatives of the partial (Model A) "overhang" buckets (atan½ residual,
±106.26/±212.52) to decide whether overhang is a *physical offset-fold* (closes but one end
protrudes) or just numerical noise.

**Why it might work.** If overhang maps cleanly to physical outcomes — intrinsic overhangs land
offset while `hub_removable` cases flatten — Model A becomes a fold-planning *intuition tool*
(predict offset magnitude), even though it stays out of the binary gate (Model B remains the gate).

**Risks.** Model A was discarded on math grounds (centroid-at-seams reintroduces off-lattice
geometry); zero overhang folds exist in ground truth; effort is high for a secondary hypothesis. If
overhang cases are bimodal (half fold, half jam) with no `hub_removable` correlation, the class isn't
predictive.

**How to test.** Bundle already parks the trio: `6x6#19` (flat control), `6x6#18` (intrinsic
overhang), `6x6#5` (hub-removable overhang). Fold; measure overhang distance vs `hub_removable`. Do
**not** retrofit into the twist criterion regardless of outcome.

---

## Candidate 5 — Solve the inverse-HC order via bipartite CSP  *(WEAK / SPECULATIVE)*

**Mechanism.** Enumerate all Hamiltonian orders compatible with a 2+1 fold sequence under
bipartite + adjacency + mountain/valley constraints; check whether the canonical-strand rule is the
*unique* solution.

**Why it might work.** Would upgrade the canonical-strand rule from ansatz to theorem (resolves open
question Q3, the per-panel HC order indeterminacy). Empirical uniqueness on the cache would lend
theorem-status credibility.

**Risks.** Doesn't change the shipped algorithm — the rule already *works* empirically (264/264).
Inverse enumeration is exponential (K! pruned by bipartite/MV but NP-hard), intractable for large K
(>10 on current grids). Pure theory contribution.

**How to test.** Small-K proof-of-concept first (6×4, K≤2) via backtracking or an SMT solver; report
`{fold_id, num_compatible_hc, is_unique}`. Scale to 6×5/6×6 only if uniqueness holds on small K.

---

## Candidate 6 — Discrete Gauss-Bonnet holonomy reformulation  *(FATAL)*

**Mechanism.** Recast twist as a discrete 1-form holonomy (parallel transport on the fold-lattice
dual graph) to give the σ-weighted turn sum a differential-geometry foundation.

**Why it was proposed.** Theoretical elegance — holonomy is a rigorous object; grounding twist in it
would be pedagogically clean.

**Skeptic refutations (FATAL).** (1) **Seam artifact reinjection** — the 1-form ω is undefined at
degenerate diagonal seams (fractional ω); the candidate offers no resolution. (2) **Breaks
`filled==jump`** — the filled repair inserts intermediate *cells* (a surface operation), which is not
a holonomy-preserving path reparametrization; ∫ω on the filled path uses a different edge set than the
jump path, so the integrals diverge unless a non-trivial equivalence is proven (it isn't). (3) The
1+1+1 cocycle identity (AC=AB+BC, empirically 68/68) gets no derivation and risks breaking
additivity across heterogeneous seams. (4) The proposed test (∫_filled ω = ∫_jump ω) is **circular** —
both equal 360·Tw_empirical by construction.

**Disposition.** Do not implement. If ever pursued: first prove ω is well-defined on
rectangular-footprint-only grids, prove path-independence explicitly (not via Stokes), and validate on
the triangle PoC (no off-lattice seams) — only then attempt unification.

---

## Candidate 7 — Footprint-middle hub-insertion routing  *(FATAL)*

**Mechanism.** Insert the footprint's geometric-middle cell (nearest lattice point to the
weighted-average) into the hub closure to force on-lattice seams and restore Tw symmetry between the
canonical and diagonal strands.

**Why it was proposed.** Correctly diagnoses that L-footprints produce diagonal hub seams carrying the
±360 artifact; tries to route them on-lattice.

**Skeptic refutations (FATAL).** (1) **Reinjects atan(½)** — on L-footprints the geometric center is
off-lattice (e.g. (⅔,⅔)); snapping to the nearest cell creates fractional-slope seam paths with
non-90° turns — the exact partial-decomp pathology that was already rejected. (2) **Breaks the
K-placements invariant** — inserting a cell at both hubs turns K+1 loop vertices into K+2, severing
the placement↔loop-point correspondence the filled path preserves. (3) **Violates `filled==jump`** —
the hub-routed path is neither jump nor filled, so it diverges on the 66/264 L-footprint diagonal-seam
cases. On Rect footprints (e.g. `8x6#202`) the "middle" *is* already a footprint cell, so the
insertion is a no-op — it fixes nothing where it's inert and breaks things where it acts.

**Disposition.** Do not pursue. The canonical-strand rule already avoids diagonal seams by
construction. The correct remedy for diagonal-seam concern is to *accept* that non-canonical strands
carry ±360 artifacts and enforce canonical-strand selection as the deterministic on-lattice rule —
then validate sufficiency physically (`8x6#202`).

---

## Recommended sequence

1. **Fold `8x6#202`** (candidate #2) — the necessary decider. Bundle parked at
   `results/2+1 testing/to_fold/`.
2. **If JAM → wire Model B** (candidate #1) behind `opts['twist_2plus1_model_b']`, with the
   seam-diagnosis guard. Regen golden/baseline/findings; flip the `test_gates.py` stub.
3. **If FOLD → the twist criterion is incomplete.** Tw=−720 would be a false-reject; revisit the
   strand-reduction hypothesis (candidate #5's CSP becomes worth the cost as a diagnostic).
4. **In parallel, fold the 6×5 trio** (candidate #3) to close the FOLD-side calibration gap, and
   optionally the overhang trio (candidate #4) to settle the partial-model interpretation.
5. **Candidates #6, #7 are closed** (FATAL) — recorded here so they aren't re-proposed.

## See also

- `experimental/VERIFICATION.md` — the math-faithfulness backbone (A/B/C/D).
- `docs/research/hypothesis_2plus1_reduction.md` — the strand-reduction theory.
- `docs/research/twist_diagnosis.md` — the forward crease/slit fix and pairwise-loop twist.
- `results/2+1 testing/to_fold/_TEST_PLAN.md` — the parked fold patterns + outcome table.
- memory `twist-2plus1-model-decision` — the ship-Model-B decision and corpus confirmation.
