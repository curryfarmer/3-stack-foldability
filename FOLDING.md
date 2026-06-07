# Physical fold harness — making ground-truth 2+1 labels

The 2+1 twist criterion can only be validated against **physically-confirmed** foldable /
non-foldable cases: the cache leaves 2+1 `verdict.twist = null`, and entanglement is a 3D
effect the 2D reflection model cannot show. So we fold card models and record the verdict.

## Generate the make-sheets

```bash
cd "Folding Drawer. "
python3 py/make_foldsheets.py        # -> report/foldsheets/<grid>_<id>.pdf  + results/twoplus1_labels.json
```

Each PDF is one case on the flat m×n grid:

| mark | meaning | action |
|---|---|---|
| **blue solid edge** | crease, **valley** | fold toward you |
| **red solid edge** | crease, **mountain** | fold away from you |
| **teal dashed edge** | **slit** | cut it |
| faint grey edge | rigid (2-chain domino internal) | leave attached, keep flat |
| purple outline | the 3 start-footprint cells | the target the stack collapses onto |
| A / B (chain colour) | which of the 3 stacks a region folds into | — |

The side panel lists the per-chain fold recipe (arrow per fold step, in order).

## Fold protocol (matches the reference card-model method)

1. Print on **two-colour cardstock** (or mark one side) so you can see which stack each panel
   lands in.
2. **Cut** every teal slit line.
3. **Fold** the creases in the recipe order (valley toward you, mountain away). Leave rigid
   (grey) edges flat/attached.
4. Judge the result:
   - **FOLDABLE** — collapses flat onto the 3-cell footprint as three clean stacks, no forcing,
     no self-intersection.
   - **NOT FOLDABLE** — self-blocks / entangles / cannot lie flat.
5. Record in `results/twoplus1_labels.json`: set `"foldable": true | false` and add a `"notes"`
   line (where it jammed, which stack, etc.).

## Curated set (10 cases)

Smallest-K and most diverse first; `6×5` are the suspected non-foldables (6×5 has no 1+1+1):

- `6×4` #1 (L, 2chain-H), #2 (L, 2chain-V) — K=8, smallest.
- `6×5` #1–5 (L-H ×2, Rect-V ×3) — K=10, key negatives.
- `6×6` #7 (L-H), #1 (L-V) — K=12, cross-check.
- `9×4` #8 (Rect-H) — K=12, Rect footprint.

## What the labels feed

Once filled, `results/twoplus1_labels.json` is the ground-truth set for the **next** phase:
reconstruct the 2-chain panel order (the crease graph is already derived in `py/foldpattern.py`),
build the three pairwise theta loops, apply the unified twist equation `Tw(L_ij)=0` (same as
1+1+1), and check it reproduces these physical verdicts.

## Crease/slit derivation (for reference)

`py/foldpattern.py` replays a solution and classifies every interior edge as crease / rigid /
slit purely from the fold geometry — no per-panel HC order needed. Self-check:

```bash
python3 py/foldpattern.py --self-check   # 615/615 partition OK; 1+1+1 6×6 degHist {1:6,2:30}
```
