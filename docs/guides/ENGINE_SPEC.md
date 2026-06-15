# Engine spec — Python vs JS, gate by gate

The 3-stack foldability solver exists twice:

- **Python (`py/`)** — the **source of truth**. `py/search.py` + `py/fold.py`.
- **Browser JS (`fold.js` / `search.js`)** — a cross-checked **reference** engine that powers the
  in-browser "Advanced search". It must agree with Python on every verdict.

`tests/test_parity_js.py` proves the two produce identical solution **counts and canonical-hash sets**
on the test grids (6×4, 6×5, 6×6). This document explains *why* — it lines up each gate predicate
side by side so a contributor can tell **intended drift** from **a bug**.

Every predicate below was read off the **code**, not the comments. Pipeline order is the order a
candidate is filtered:

> arithmetic → footprint enum → decomposition → connectivity → parity → exit footprint → reflection
> → twist → D4 canonical hash

## Summary

| # | Stage | Python | JS | Verdict |
|---|-------|--------|----|---------|
| 1 | arithmetic guard | `search.py:580-584` | `search.js:528-531` | **DRIFT** (intended) |
| 2 | footprint enum | `search.py:30-66` | `search.js:22-74` | AGREE |
| 3 | decomposition | `search.py:71-115` | `search.js:78-142` | AGREE |
| 4 | connectivity | `search.py:141-162` | `search.js:150-181` | AGREE |
| 5 | parity | `search.py:247-274` | `search.js:312-342` | AGREE |
| 6 | exit footprint | `search.py:279-297` | `search.js:352-373` | AGREE |
| 7 | reflection | `fold.py:154-169` | `fold.js:171-185` | AGREE |
| 8 | twist | `search.py:352-364` | `search.js:435-451` | AGREE |
| 9 | D4 canonical hash | `search.py:391-406` | `search.js:478-502` | AGREE |

**One drift only**, at stage 1, and it is deliberate (see [Drift](#the-one-drift-arithmetic-guard)).
Stages 5 and 7 *look* like they could drift but do not — see [Not drift](#not-drift).

---

## 1. Arithmetic guard — **DRIFT (intended)**

The grid is rejected before any enumeration unless its cell count can tile into `K = mn/3` triominoes.

**Python** `run()` `search.py:580-584` — relaxed to the structural minimum:

```python
if (m * n) % 3 != 0:
    return solutions, ctx, "mn not divisible by 3 (K must be integer)"
K = (m * n) // 3
if K < 1:
    return solutions, ctx, "K < 1 (empty grid)"
```

**JS** `run()` `search.js:528-531` — three additional gates:

```js
if ((m * n) % 6 !== 0) { ...onError('mn not divisible by 6'); ...return; }
const K = (m * n) / 3;
if (K % 2 !== 0) { ...onError('K = mn/3 must be even'); ...return; }
if (n < 4) { ...onError('n < 4 (conjectured rejection)'); ...return; }
```

JS enforces `(m*n)%6==0`, `K` even, and `n>=4`; Python keeps only `(m*n)%3==0` and `K>=1`. Python was
deliberately relaxed (`search.py:577-579` comment) so tiny/odd grids (e.g. 3×1) can be probed for
research. This is the **single behavioural difference** between the engines and is already documented
in `tests/test_parity_js.py:13-17`. It is benign for parity because **every test grid (6×4, 6×5, 6×6)
satisfies both gate sets**, so the two engines enumerate the same space and counts/hashes match.

> If you add a parity grid where the drift matters (JS returns 0, Python returns >0), `xfail` it in
> `KNOWN_DIFFS` rather than weakening either gate.

## 2. Footprint enumeration — AGREE

Both place the start triomino (`L` in 4 rotations, `Rect` as H/V) at every in-bounds anchor.

- **Python** `enumerate_footprints` `search.py:30-66`; bounds test `search.py:38`:
  `all(0 <= x < m and 0 <= y < n for (x, y) in cells)`.
- **JS** `enumerateFootprints` `search.js:22-74`; bounds tests at `search.js:30/34/59/61`.

Same shape set, same rotations, same bounds rule.

## 3. Decomposition — AGREE

Split the 3-cell footprint into chains: `2+1` (a 2-chain + a 1-chain) or `1+1+1` (three 1-chains).

- **Python** `enumerate_decompositions` `search.py:71-115`. For an `L`, the 2-chain must be two
  *adjacent* cells: `adj = lambda a, b: abs(a[0]-b[0]) + abs(a[1]-b[1]) == 1`. `1+1+1` is unconditional.
- **JS** `enumerateDecompositions` `search.js:78-142`, same adjacency rule for the 2-chain, same
  unconditional `1+1+1`.

## 4. Connectivity — AGREE

A DFS prune: the cells reached so far must still be partitionable into the remaining chain sizes.

- **Python** `connectivity_ok` `search.py:141-162` → `can_partition(component_sizes, remaining_sizes)`
  (`search.py:162`).
- **JS** `connectivityOK` `search.js:150-181` → `canPartition(...)` (`search.js:180`), invoked from
  `dfsChain` (`search.js:266`).

## 5. Parity — AGREE

Orientation-aware fold-count parity. The axis comes from footprint geometry
(`parallel_fold_axis` / `parallelFoldAxis`): for a `2+1`, horizontally-adjacent bases → vertical A/B
crease → require `nH` even; vertically-adjacent → require `nV` even. `1+1+1` falls back to the legacy
rule (`nH` even **and** `nV` odd).

- **Python** `parity_check` `search.py:259-274`:

```python
if axis == "H":
    if nH % 2 != 0: return False
elif axis == "V":
    if nV % 2 != 0: return False
else:
    if nH % 2 != 0 or nV % 2 != 1: return False
```

- **JS** `parityCheck` `search.js:323-342`:

```js
if (axis === 'H') { if (nH % 2 !== 0) return false; }
else if (axis === 'V') { if (nV % 2 !== 0) return false; }
else { if (nH % 2 !== 0) return false; if (nV % 2 !== 1) return false; }
```

See [Not drift](#not-drift) for why the `1+1+1` branch is identical despite reading differently.

## 6. Exit footprint — AGREE

The union of each chain's **last** placement must be 3 distinct cells forming a shape congruent to the
start shape.

- **Python** `exit_footprint_check` `search.py:279-297`.
- **JS** `exitFootprintCheck` `search.js:352-373`.

Both: `len == 3` and distinct; bbox `(dx=2,dy=0)` or `(dx=0,dy=2)` → `Rect`, `(dx=1,dy=1)` → `L`,
otherwise reject; final `shape == start_shape`.

## 7. Reflection — AGREE

The **new** orientation-aware segment-coincidence gate. For each adjacent pair of chains, seed their
shared crease as one world segment (`_hub_seed`/`hubSeed`), project each side to its final placement,
and require the two images to **coincide as oriented grid segments**.

- **Python** `reflection_verdict` `fold.py:154-169` — helpers `_hub_seed` (`fold.py:112-118`), `_seg`
  (`fold.py:121-132`), `_shared_crease_pairs` (`fold.py:135-151`); gate at `fold.py:165`:
  `coince = (_seg(a) == _seg(b))`.
- **JS** `reflectionVerdict` `fold.js:171-185` — helpers `hubSeed` (`fold.js:136-139`), `segKey`
  (`fold.js:143-152`), `sharedCreasePairs` (`fold.js:154-169`); gate at `fold.js:180`:
  `coince = segKey(a) === segKey(b)`.

Order-independence: Python `_seg` uses `frozenset(pts)`; JS `segKey` sorts `pts` before stringifying.
Same geometry. See [Not drift](#not-drift).

## 8. Twist — AGREE

Decided **only for `1+1+1`** (every chain single-cell); for `2+1` it returns undecided (`pass = None`).
When decided, every pair must have loop-twist `Tw = 0`. **Non-filtering** in both engines — counted, not
dropped.

- **Python** `twist_check` `search.py:352-364`: undecided unless
  `all(len(c["baseCells"]) == 1 for c in chains)`.
- **JS** `twistCheck` `search.js:435-451`: undecided unless
  `chains.every(c => (c.baseCells ? c.baseCells.length : 1) === 1)`.

## 9. D4 canonical hash — AGREE

Dedup **key** (not a replayable fold path): the lexicographic minimum signature across the 8 D4
transforms (4 rotations × 2 reflections) of the footprint + chain signatures.

- **Python** `canonical_hash` `search.py:391-406` — `json.dumps({"fp": fp, "chains": chain_sigs}, ...)`,
  `sig < best` over 8 transforms.
- **JS** `canonicalHash` `search.js:478-502` — same 8 transforms, lexmin.

---

## Not drift

Two stages read differently across the engines but compute the same verdict — flagged here so they are
not "fixed" into an actual divergence:

- **Parity `1+1+1` branch (stage 5).** Python's single `if nH % 2 != 0 or nV % 2 != 1: return False`
  is logically identical to JS's two sequential `if (...) return false; if (...) return false;`. Both
  reject exactly when `nH` is odd **or** `nV` is even. (Verified against the code, not the comments.)
- **Reflection coincidence (stage 7).** Python compares `_seg(a) == _seg(b)` (a `frozenset` of
  endpoints + direction); JS compares `segKey(a) === segKey(b)` (sorted endpoints + direction,
  JSON-stringified). Both are geometric segment coincidence, not lossy `(edge, sign)`-label equality.
  The old label gate is gone from **both** engines.

## The one drift: arithmetic guard

Stage 1 is the only place the engines diverge, and it is intended: Python is relaxed to `(m*n)%3==0`
+ `K>=1`; JS keeps the stricter `%6` / `K`-even / `n>=4` conjecture gates. Documented in
`tests/test_parity_js.py:13-17`; benign on all current parity grids. Any new grid where it bites should
be `xfail`'d, never papered over by changing a gate.
