# The twisting math, from scratch — interactive lesson log

A first-principles, diagram-driven walkthrough of the **twist criterion** for flat-folding a
Hamiltonian-circuit kirigami pattern into compact stacks. Built interactively (module → checkpoint
→ next). This file is the durable reference; it is appended one module at a time as we go.

Companion material already in this folder:
- `EXPLAINER.md` / `EXPLAINER.html` — the polished prose + 17 SVG figures (A1–A12 2-stack, B1–B5 3-stack).
- `teach_twist.py` (to be built at M4) — renders the **per-corner twist ledger** on *real computed
  HCs*: T1 (2×4 ✓), T2 (real 6×6 ✓), T3 (3×3-ring ✗), T4a/T4b (1+1+1 example/counterexample).
- Source paper: `../resources/RSPA-2025-0696...pdf` (Yang–You–Rosen 2025), §3 reflection, §4 twist.

**Roadmap.** M0 object → M1 fold=reflection → M2 two reflections = rotation → M3 σ checkerboard
→ M4 the twist ledger (`g(i)=σγ`, `Tw`) → M5 why Tw=0 is exact (Călugăreanu–White–Fuller)
→ M6 full 2-stack rule → M7 3-stack theta graph + 1+1+1 example/counterexample → M8 why the
per-chain reduction fails → M9 the 2+1 open frontier.

Convention: cell `(x,y)`, columns `x`, rows `y`. Screen/figures may use +y up.

---

## M0 — The object, and the two ways folding fails

**What we fold.** A flat tessellated plate = a grid of unit-square panels. Goal: fold it flat into
compact **stacks** (2-stack = two equal piles; this project targets 3 stacks).

**The fold pattern is a single closed loop.** Build a graph: each panel = a node, each shared side
between two panels = an edge. A **Hamiltonian circuit (HC)** is a closed path visiting every panel
exactly once and returning to start. That HC *is* the fold pattern. Why a loop? A circuit forces
every panel to **degree 2** — one crease in, one crease out — so the sheet folds as **one connected
closed band**. (Two separate loops = disconnected gadgets; loose ends = a panel folds onto nothing
and the band never closes, so stacks can't be equal. "Degree-2-everywhere-and-connected" is the real
requirement; "HC" is its name.)

**Creases vs slits — the core rule:**
- Edge the HC **crosses** → **crease** (fold here).
- Edge the HC **does not cross** → **slit** (cut; no fold).

This turns over-constrained origami into foldable **kirigami**.

Worked case — 4×2 grid, HC around the perimeter (paper Fig 13b):

```
        crease          crease          crease
  (0,1)───────(1,1)───────(2,1)───────(3,1)
    │           ╎           ╎           │
 crease       slit        slit        crease     ← two middle rungs are NOT crossed
    │           ╎           ╎           │
  (0,0)───────(1,0)───────(2,0)───────(3,0)
        crease          crease          crease

  HC order: (0,0)→(1,0)→(2,0)→(3,0)→(3,1)→(2,1)→(1,1)→(0,1)→back
```

8 creases (the loop), 2 slits (the two interior vertical rungs). The folded loop is topologically a
**donut / annulus / ribbon** — which is exactly why a ribbon-linking theorem (CWF) is the right tool
in M5.

**Two independent failure modes.** Fold the loop flat. Two separate things can break:
1. **Reflection failure** — cut the loop into an open strip, fold it, check the two cut ends rejoin.
   If they land differently, the stacks come out **unequal** / don't close. (Separate condition; M6.)
2. **Twist** — even if the ends meet, the closed loop can be **self-entangled** (linked with itself)
   and physically cannot lie flat. Can't be undone without cutting.

**Twist is a property of the uncut, closed loop.** The whole game: compute one number `Tw`; the loop
is twist-foldable ⟺ `Tw = 0`.

*Checkpoint M0 (answered ✓):* 8 creases + 2 slits; non-circuit breaks folding because it's no longer
degree-2-connected.

---

## M1 — Folding is literally a mirror reflection

The atom of everything.

**Claim.** Folding panel `Pᵢ` flat onto neighbor `Pᵢ₊₁` across their shared crease = **reflecting
`Pᵢ` across the crease line** (a 2-D mirror reflection).

```
   before fold                 after fold (reflect across x=1)

   ┌───────┐ crease            crease ┌───────┐
   │  Pᵢ   │ │                      │ │  Pᵢ'  │
   │ ◣     │ │           ──►        │ │     ◢ │      corner marker ◣ → ◢
   └───────┘ │                      │ └───────┘      (jumped sides)
  (0,0)   x=1                     x=1   (1,0)
```

**Two load-bearing facts about a reflection:**

1. **Isometry** — preserves distances and angles; panels stay rigid unit squares. A fold is a *rigid*
   motion (this rigidity is what conserves the linking number `Lk` later — no cutting, no stretching).
2. **Orientation-reversing** — matrix `det = −1`. The marker flip `◣→◢` is the visible sign: a
   face-up panel becomes **face-down**. Which face is up decides *which stack* a panel lands in.

**Folding the whole strip = composing reflections, one per crease.** Panel `P_k`'s folded position =
reflect across crease 1, then 2, …, then k. Code does this literally: `twostack.py:_reflect_point`
mirrors a point across each crossed edge's line; `_reflect_along` chains them along the path. A
direction vector glued to a panel is carried through every crease the same way → its folded image.

**Determinant multiplies.** Each reflection is `det = −1`, det is multiplicative, so after **k** folds:

$$\det = (-1)^k \quad\Rightarrow\quad k\text{ even} \to \text{face-up},\qquad k\text{ odd} \to \text{face-down}.$$

That is the entire "which of the two stacks" mechanism, already implied by one fact about reflections.
Cashed out in M3.

*Checkpoint M1 (answered ✓):* (1) fold+unfold across the same line = **identity**, face-up (the
`α=0` case of M2's law — two reflections across one line is exactly the identity). (2) `P₃` is
**face-down**: 3 reflections, `det=(−1)³=−1`.

---

## M2 — Two reflections = a rotation (where turning is born)

**The Euclidean fact.** Reflection across line `L₁` then across `L₂`, with the lines meeting at angle
`α`, equals a **rotation by `2α`** about their intersection. (Parallel lines → translation; same line
→ `α=0` → identity.)

Two-line proof (directions): a reflection across a line at angle `θ` sends a direction `φ ↦ 2θ−φ`.

$$\varphi \xmapsto{L_1} 2\theta_1-\varphi \xmapsto{L_2} 2\theta_2-(2\theta_1-\varphi)=\varphi+2(\theta_2-\theta_1)=\varphi+2\alpha.$$

The direction rotates by `2α`. The **doubling** is the crucial fact.

**Apply to folding.** Fold `Pᵢ→Pᵢ₊₁` (reflect across crease `c₁`) then `Pᵢ₊₁→Pᵢ₊₂` (reflect across
`c₂`). Composition = a **local rotation** `γ = 2α` injected at `Pᵢ₊₁`, `α` = angle between creases.

**On a square grid** creases are axis-aligned, so consecutive creases are parallel or perpendicular:

```
   STRAIGHT pass-through            L-CORNER
   c₁ ∥ c₂  (α = 0)                c₁ ⟂ c₂  (α = 90°)
   γ = 2·0 = 0                     γ = 2·90° = ±180°
```

So `γ ∈ {0, ±180°}`:
- **Straight** pass-through → `γ = 0` (contributes nothing).
- **L-corner** → `γ = ±180°`; the **sign = turn handedness** (left/CCW `+180`, right/CW `−180`).
  As bare rotations `±180` coincide, but we sum *signed* turns, so the sign matters in the total.

**Punchline: only L-corners carry rotation; straights are free.** Twist is built purely from the HC's
corners. Code: `twostack.py:twist_value` reads incoming/outgoing step vectors at each vertex,
`cross=v₁×v₂` gives the sign, `atan2(cross,dot)` gives ±90°, `×2` gives the `±180` (= `γ=2α`).

*Checkpoint M2 (answered ✓):* (1) the 4 grid-corners are L-corners, the 4 middle cells straight;
(2) each `γ=+180` going CCW, uniform handedness; (3) bare sum `= ±720` — and normalization does
**not** rescue it (`720°=4π`, `4π/4π=1` would call it twisted). The missing piece is the alternating
sign `σ` (M3), which flips every other corner so `+720` collapses to `0`.

---

## M3 — σ: the mountain/valley checkerboard (the missing sign)

**Folds alternate mountain/valley along the loop** (accordion zigzag: up, down, up, down). Encode as
`σ = +1` (valley) / `−1` (mountain).

**σ is a checkerboard, not HC-dependent.** Every unit grid step flips `(x+y) mod 2`, so consecutive
HC cells alternate color automatically. Hence the M/V alternation **is** the 2-coloring:

$$\sigma = (-1)^{x+y} \qquad +1\text{ (valley) on even cells},\quad -1\text{ (mountain) on odd cells}.$$

A fixed property of position — same checkerboard for every HC. (Equivalently `(−1)^i` index parity
along the loop; they agree up to a global offset from the start cell — the subtlety that returns in
M8.)

**Why σ multiplies γ.** The same geometric turn lands `Pᵢ` **under** vs **over** `Pᵢ₊₂` depending on
valley-then-mountain vs the reverse → opposite twist sign. So the counted quantity is `g(i)=σᵢγᵢ`.

**2×4 corners with σ (resolves the M2 hook):**

```
   corner   (x+y)  σ=(−1)^{x+y}   γ(CCW)   g=σγ
   (0,0)      0       +1           +180     +180
   (3,0)      3       −1           +180     −180
   (3,1)      4       +1           +180     +180
   (0,1)      1       −1           +180     −180
                                          ─────
                                    Σ g =     0   →  Tw = 0  ✓ folds
```

Bare turns `+720`; `σ` flips alternate corners → `+180−180+180−180 = 0`. The checkerboard pairs the
corners equal-and-opposite. *That* is the cancellation, not normalization.

**Why `g=σγ` — why equal turns alternate sign (the conceptual crux).** The alternating sign *is* the
M1 face-flip renamed. Three beats:
1. **Carry the panel normal `N`.** Each fold is a reflection (`det=−1`) → flips the panel over → `N`
   points up/down/up/down = `(-1)^k = (-1)^{x+y} = σ`. `σ` is just *which face is up where you stand*.
2. **A turn's twist-sign depends on which face is up.** "Left/CCW" is a handedness call; it needs a
   reference for "up." Flip the sheet → a left turn reads as a right turn. Twist is one global number,
   so every corner must be reported in **one common up-direction**; a corner on a face-down panel gets
   **negated** → contribution `= σᵢγᵢ = g(i)`.
3. **Adjacent corners sit on opposite faces** (face flips every step), so equal geometric turns
   `+180,+180` land as `+180,−180`. The alternation is forced by the sheet turning over at each crease,
   not imposed.

Picture (fig `A7`): valley→mountain makes `Pᵢ` end **under** the stack; mountain→valley makes it end
**over** — same |rotation|, opposite twist sign = `σ`. Chain of identities:
`sign flip at alternating corners = M/V alternation = face-flip (−1)^k (M1) = (−1)^{x+y} = σ`.
So twist ≠ "total turning" (always `±720`, the boring winding) — it's turning **weighted by the
checkerboard**, which is what detects entanglement.

**Two independent signs per corner (don't conflate them).** A corner's contribution `g` is a *product*
of two `±1`s from different sources:

| input | symbol | `+1` | `−1` | source |
|---|---|---|---|---|
| turn direction | `d` (sign of `γ`) | left/CCW | right/CW | geometry of the path |
| parity / face | `σ` | even `(x+y)` | odd `(x+y)` | the checkerboard (M3) |

$$g(i)/180° = \sigma_i\cdot d_i = (\text{parity sign})\times(\text{turn-direction sign}).$$

```
  turn    parity   σ    d    g
  left    even    +1   +1   +180
  left    odd     −1   +1   −180
  right   even    +1   −1   −180
  right   odd     −1   −1   +180
```

Neither alone fixes the sign. The 2×4 *looked* parity-only because going CCW every corner was a left
turn (`d=+1` everywhere) so `σ·d` reduced to `σ`; that's special (convex loop). Any S-bend/zigzag (all
real 6×6 HCs) flips `d` too, so both matter. In `twostack.py:twist_value`: `cross` sign = `d`
(`ang=atan2(cross,dot)*2 = ±180`), the `i%2` bucket + `odd−even` = `σ`, and `g = σ·γ` is their product.

*Checkpoint M3 (answered ✓):* (1) ring corners all **even** parity → `σ=+1` everywhere → `Σg=4π` →
`Tw=+1`, twisted. (2) `σ` is HC-independent because **every unit grid step flips `(x+y) mod 2`** — a
fact about the grid, true for any path.

**Deep takeaway (corner spacing).** 2×4 corners are an **odd** #steps apart → parity flips → `σ`
alternates `+,−,+,−` → cancel to 0. Ring corners are **even** (2) apart → parity preserved → `σ`
reinforces `+,+,+,+` → pile to `4π`. *Twist = whether the corners' parities alternate (cancel) or
align (accumulate).*

---

## M4 — The twist ledger on real HCs (the centerpiece)

Tool: `teach_twist.py`. It walks a real HC corner-by-corner, printing
`cell · σ · turn(L/R) · γ(±180) · g=σγ · running Σg`, then `Tw = Σg/720°`. It **asserts** the
hand-walked `Σg` equals the reference `twostack.py:twist_value()`, so the ledger is provably the same
invariant. Figures (grid + σ checkerboard + HC + stamped corners beside the ledger):
`svg/T1_ledger_2x4`, `svg/T2_ledger_6x6`, `svg/T3_ledger_ring` (`.svg`/`.png`). Regenerate:
`python3 explainer/teach_twist.py`.

**T1 — 2×4 (foldable, 4 corners):**
```
 #  cell    σ  turn  γ      g     Σg
 1 (3,0)   −1   L   +180  −180   −180
 2 (3,1)   +1   L   +180  +180     +0
 3 (0,1)   −1   L   +180  −180   −180
 4 (0,0)   +1   L   +180  +180     +0   → Tw = 0 ✓
```

**T2 — real 6×6 snake (foldable, 12 corners).** Has both L and R turns (#3,4,7,8 are right) so `d`
*and* `σ` both matter, not parity alone:
```
 #  cell    σ  turn  γ      g     Σg          #  cell    σ  turn  γ      g     Σg
 1 (5,0)   −1   L   +180  −180   −180         7 (1,3)   +1   R   −180  −180   −180
 2 (5,1)   +1   L   +180  +180     +0         8 (1,4)   −1   R   −180  +180     +0
 3 (1,1)   +1   R   −180  −180   −180         9 (5,4)   −1   L   +180  −180   −180
 4 (1,2)   −1   R   −180  +180     +0        10 (5,5)   +1   L   +180  +180     +0
 5 (5,2)   −1   L   +180  −180   −180        11 (0,5)   −1   L   +180  −180   −180
 6 (5,3)   +1   L   +180  +180     +0        12 (0,0)   +1   L   +180  +180     +0  → Tw=0 ✓
```

**T3 — 3×3 ring (twisted, 4 corners).** All same sign → never returns:
```
 #  cell    σ  turn  γ      g     Σg
 1 (2,0)   +1   L   +180  +180   +180
 2 (2,2)   +1   L   +180  +180   +360
 3 (0,2)   +1   L   +180  +180   +540
 4 (0,0)   +1   L   +180  +180   +720   → Tw = +1 ✗
```

**Punchline (visible in the Σg column):** foldable ⇒ the running total keeps **returning to 0**
(corners arrive in canceling `−180/+180` pairs); twisted ⇒ it **climbs monotonically** and never comes
home. "Does the partial sum return to 0 or drift?" *is* the twist test. (This is what
`search.py twist_check` evaluates per candidate.)

**σ is relative, not absolute (origin convention).** The bottom-left cell `(0,0)` is even → `σ=+1` →
valley → face-up (matches M1: panel 0 has zero folds, `det=+1`). But "even=+1" is pinned to the origin
— shift the origin one cell and every parity flips. Only the **alternation** (the checkerboard pattern)
is physical, not the labeling: globally flipping every `σ` sends `Σg→−Σg`, which preserves `Tw=0`
(stays 0) and `|Tw|=1` (stays twisted). So foldability is invariant under a global σ-flip — the only
rule is **pick one origin and stay consistent across the whole loop.** Concrete (T2, 6-tall): lower-left
`(0,0)`→even→valley `+`; upper-left `(0,5)`→`5` odd→mountain `−` (the red `−180` at corner #11). They're
5 (odd) rows apart so the checkerboard forces opposite parity. Index from the top-left as `(1,1)`
instead and you'd call it "even" — a different, equally valid origin; just don't mix the two. (This is exactly what the naïve
*per-chain* twist violates in M8: it resets σ's origin per chain → phantom phase → false negatives.
Fix = one global `σ=(−1)^{x+y}`.)

*Checkpoint M4 (pending):* in T2, the running total returns to 0 after every **pair** of corners. (1)
Which corner cancels #1, and what makes them a canceling pair (same/different `σ`? same/different
`d`?)? (2) On a *solid* m×n grid every HC has `Tw=0` (we checked 1072/1072 for 6×6) — argue why no
solid grid can be twisted, but a grid **with a hole** (the ring) can.

---

<!-- M5+ appended as the lesson continues -->
