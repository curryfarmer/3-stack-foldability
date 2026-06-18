# experimental/ — candidate 2+1 twist engines

Four swappable ways to stand a rigid 2-chain (domino ribbon) in for a 1-chain so the closed-loop
twist gate applies. All share the geometry in `common.py` (replay via `py/fold.py` + the doubled-turn
loop sum); each engine differs only in the loop "body" it builds from the 2-chain placements.

| folder | engine | body builder | verdict |
|---|---|---|---|
| `no_decomp/` | un-reduced: whole-domino centroid per placement (the 936° approach) | `full_centroid_path` | `pass = Tw==0` |
| `jump_decomp/` | one kept strand, twin cells as holes; short-side folds = axis-aligned 3-jumps (Model B) | `strand_path` | `pass = Tw==0` |
| `normal_decomp/` | filled: kept strand with each 3-jump filled by its 2 collinear midpoints | `filled_path` | `pass = Tw==0` |
| `partial_decomp/` | lead's variable-width: 1-unit by default, 2-unit centroid kept at short-side folds | `model_a_path` | **3-way** (below) |

`normal_decomp == jump_decomp` is a theorem (filling a 3-jump inserts collinear, phase-even points →
Tw unchanged); the orchestrator verifies it on every case.

### partial_decomp is special

It is NOT a pass/fail gate. Its 1-unit↔2-unit seam steps a half-cell off the sublattice, so its Tw
can carry a (1,2)-slope `atan(½)` residual (±53.13°·k). That residual is the **overhang signature** —
the fold closes but lands offset, so one end sticks out past the target footprint (a candidate fold,
not a failure). Class:

- `flat` — Tw≈0, flat-folds onto the same footprint
- `overhang` — Tw = nonzero multiple of `2·atan½` → closes with a protruding strip *(promising)*
- `twisted` — Tw = nonzero multiple of 360° → genuine twist / jam
- `mixed` — neither → flagged explicitly

`pass = flat ∨ overhang`. Extra signals per case: `tw_hub1`/`hub_removable` (does the overhang vanish
when the two hub joins are forced 1-unit? → fixable hub seam vs intrinsic interior overhang), `sign`,
`n2units` (residual 2-units kept), `frac` (seam kinks).

## Run

```
# (optional) regen the 6x6 non-corner 2+1 cache (corner 6x6 has 0 2+1):
python py/generate.py --m 6 --n 6 --decomps 2+1 --allow-non-corner --jobs 8
# tag EVERY cached grid's 2+1 with all 4 engines + curate the minimal covering set
python experimental/run_2plus1_testing.py
```

`run_2plus1_testing.py` scans **all** `results/*.json` 3-stack caches with 2+1 (not just 6×6).
Outputs → `results/2+1 testing/`: `all_2plus1.json` (every tagged solution, `grid#id`),
`<grid>_<id>.json` (one representative per distinct 4-engine verdict-bucket), `_summary.json`.

## Headline finding (264 reflection-passing 2+1 across 7 grids)

`normal == jump`: **264/264** (filled == jump verified on data everywhere). The three lattice-sound
engines (`no`/`jump`/`normal`) agree, and reject **exactly 1 of 264** — `8x6#202`, a genuinely
twisted 2+1 (Tw=−720, robust to strand choice) that nonetheless **passed reflection+parity+exit**:
a reflection false-pass the twist gate would catch. On the other 263, reflection already forces Tw=0,
so the sound engines add nothing — **`partial` is the only differentiator**, splitting them
flat/overhang (the atan½ overhang = one end sticks out). `partial` also uniquely flags `8x6#202`
`mixed` (−507 = −720 twist + 212 overhang). 9 distinct 4-engine buckets total.
