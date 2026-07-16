"""test_grid_ingest.py — S5 arbitrary-sheet ingest for the square engine.

Covers the compatibility invariant (a rectangle sheet reproduces the parameterized engine), the
theory-free Tier-0 invariants that must hold on ANY connected sheet, the fold-grid/1 loader, and a
seeded fuzz corpus. See docs/schema/fold-grid-1.md and docs/S5_HANDOFF.md.

The engine is driven in-process via search.run(opts) (never shelled out), mirroring test_golden.py.
A rectangle sheet forces NON-corner enumeration (an arbitrary sheet has no canonical corner), so every
rectangle-equivalence baseline runs the old path with allow_non_corner=True.
"""
import json
import os
import random

import pytest

import search as Search          # type: ignore  # on sys.path via conftest
import gridfile as GridFile      # type: ignore
import twist_jump               # type: ignore
import enginelib as EL           # type: ignore

PANELS = 3


# ---------- helpers ----------

def _opts(m, n, *, sheet=None, jobs=1, allow_non_corner=True, dedup=True):
    o = EL.opts_3stack(m, n, allow_non_corner=allow_non_corner, dedup=dedup, jobs=jobs)
    if sheet is not None:
        o["sheet"] = sheet
    return o


def _rect(m, n):
    return [[x, y] for y in range(n) for x in range(m)]


def _run(opts):
    sols, ctx, err = Search.run(opts)
    return sols, ctx, err


def _replay_coverage(sol, m, n):
    """Union of every cell across every placement of every chain, via twist_jump.replay. This is the
    set the fold physically occupies -- for a COVERED candidate it must equal the sheet S."""
    covered = set()
    for ch in sol["chains"]:
        placements = twist_jump.replay(ch["baseCells"], ch["foldArrows"], m, n)
        for pl in placements:
            for c in pl["cells"]:
                covered.add(tuple(c))
    return covered


def _assert_tier0(sols, S, m, n):
    """Theory-free invariants that hold for ANY sheet: every solution covers exactly S with no cell
    outside S and no base-cell overlap, and replaying its arrows never leaves S."""
    for sol in sols:
        base_union = set()
        for ch in sol["chains"]:
            for b in ch["baseCells"]:
                bc = (b["x"], b["y"])
                assert bc in S, f"base cell {bc} not in sheet"
                assert bc not in base_union, f"base cell {bc} overlaps"
                base_union.add(bc)
        fp = set((c["x"], c["y"]) for c in sol["footprint"]["cells"])
        assert fp <= S, "footprint escapes sheet"
        covered = _replay_coverage(sol, m, n)
        assert covered <= S, "a fold placement left the sheet"
        assert covered == S, "a covered solution does not tile the whole sheet"


# ---------- Tier 1: rectangle-equivalence (the compatibility invariant) ----------

@pytest.mark.parametrize("m,n", [
    (3, 4), (4, 3), (3, 6),
    pytest.param(6, 4, marks=pytest.mark.slow),
])
def test_rectangle_sheet_equivalent_to_parameterized(m, n):
    """A grid whose cells are exactly the m x n rectangle, ingested as a sheet, reproduces the old
    non-corner run byte-for-byte (solutions AND ctx counters)."""
    old, octx, oerr = _run(_opts(m, n))
    new, nctx, nerr = _run(_opts(m, n, sheet=_rect(m, n)))
    assert oerr is None and nerr is None, (oerr, nerr)
    assert new == old, f"{m}x{n}: sheet path diverged ({len(new)} vs {len(old)} solutions)"
    assert nctx == octx, f"{m}x{n}: ctx diverged"
    # A rectangle is a valid sheet S, so its real solutions exercise the Tier-0 replay/coverage checks.
    _assert_tier0(new, set(map(tuple, _rect(m, n))), m, n)


def test_sheet_none_is_a_noop():
    """Passing sheet=None explicitly is identical to omitting the key (the compat-invariant floor)."""
    a, actx, _ = _run(_opts(3, 4))
    opts = _opts(3, 4)
    opts["sheet"] = None
    b, bctx, _ = _run(opts)
    assert a == b and actx == bctx


# ---------- Tier 0: invariants on non-rectangular sheets ----------

# A 12-cell plus/cross (bbox 4x4 with the four corners removed); 12 % 3 == 0, 4-connected.
PLUS12 = [[1, 0], [2, 0], [0, 1], [1, 1], [2, 1], [3, 1],
          [0, 2], [1, 2], [2, 2], [3, 2], [1, 3], [2, 3]]
# A 9-cell L-polyomino (bottom row 5 wide + left column 4 tall); bbox 5x5, 9 % 3 == 0.
L9 = [[0, 0], [1, 0], [2, 0], [3, 0], [4, 0], [0, 1], [0, 2], [0, 3], [0, 4]]


@pytest.mark.parametrize("sheet,mn", [(PLUS12, (4, 4)), (L9, (5, 5))])
def test_tier0_invariants_nonrectangular(sheet, mn):
    m, n = mn
    S = set(map(tuple, sheet))
    sols, ctx, err = _run(_opts(m, n, sheet=sheet))
    assert err is None, err
    _assert_tier0(sols, S, m, n)


def test_determinism_serial_equals_parallel():
    """jobs=1 must byte-match jobs=N (the parallel path replays dedup/id in the parent)."""
    s1, _, e1 = _run(_opts(4, 4, sheet=PLUS12, jobs=1))
    s2, _, e2 = _run(_opts(4, 4, sheet=PLUS12, jobs=2))
    assert e1 is None and e2 is None
    assert s1 == s2, f"serial ({len(s1)}) != parallel ({len(s2)})"


@pytest.mark.parametrize("bad,why", [
    ([[0, 0], [0, 1]], "len % 3 != 0"),
    ([[0, 0], [1, 0], [2, 0], [10, 0], [11, 0], [12, 0]], "not 4-connected"),
    ([], "empty"),
])
def test_bad_sheets_rejected(bad, why):
    _, _, err = _run(_opts(1, 1, sheet=bad))
    assert err is not None, f"expected rejection: {why}"


# ---------- dedup: true Aut(S), not the rectangle's D4 (the canonical_hash fix) ----------

def test_automorphisms_use_actual_sheet_not_bbox():
    """The dedup group must be the sheet's OWN automorphisms, not the bounding box's. For the L9 sheet
    (bbox 5x5 square, so the bbox's group is all 8 of D4) the true Aut(S) is a PROPER subgroup -- if
    dedup minimized over all 8 it would over-merge distinct folds and silently drop solutions."""
    from lattice.square import SquareLattice as SL  # type: ignore
    bbox_group = SL.automorphisms(5, 5)                       # rectangle 5x5 -> D4, 8 elements
    aut_s = SL.automorphisms(5, 5, frozenset(map(tuple, L9)))  # L9's real symmetries
    key = lambda t: (t["rot"], t["flip"])   # transforms are dicts; compare by (rot, flip)
    assert len(bbox_group) == 8
    assert 0 < len(aut_s) < 8, "L9 is asymmetric enough that Aut(S) is a proper subgroup of D4"
    assert {key(t) for t in aut_s} <= {key(t) for t in bbox_group}


# ---------- fold-grid/1 loader ----------

def test_gridfile_normalizes_to_origin():
    spec = {"schema": "fold-grid/1", "tiling": "square",
            "cells": [[5, 5], [6, 5], [5, 6]], "stacks": "auto"}
    g = GridFile.parse_grid(spec)
    assert g["sheet"] == [[0, 0], [0, 1], [1, 0]]
    assert (g["m"], g["n"]) == (2, 2)


@pytest.mark.parametrize("spec,msg", [
    ({"schema": "nope", "tiling": "square", "cells": [[0, 0]]}, "schema"),
    ({"schema": "fold-grid/1", "tiling": "hex", "cells": [[0, 0]]}, "tiling"),
    ({"schema": "fold-grid/1", "tiling": "square", "cells": []}, "cells"),
    ({"schema": "fold-grid/1", "tiling": "square", "cells": [[0, 0], [0, 0]]}, "duplicate"),
    ({"schema": "fold-grid/1", "tiling": "square", "cells": [[0, 0]],
      "bbox": {"m": 9, "n": 9}}, "bbox"),
])
def test_gridfile_rejects_malformed(spec, msg):
    with pytest.raises(ValueError):
        GridFile.parse_grid(spec)


def test_gridfile_roundtrip_matches_inline_sheet(fixtures_dir, tmp_path):
    """A fold-grid/1 file on disk, ingested, produces the same solution set as the inline normalized
    sheet -- proving the loader + engine agree end to end. Also runs the Tier-0 invariants on it."""
    path = os.path.join(fixtures_dir, "grids", "L9.json")
    g = GridFile.load_grid(path)
    m, n, sheet = g["m"], g["n"], g["sheet"]
    from_file, fctx, ferr = _run(_opts(m, n, sheet=sheet))
    inline, ictx, ierr = _run(_opts(m, n, sheet=L9))
    assert ferr is None and ierr is None
    assert from_file == inline and fctx == ictx
    _assert_tier0(from_file, set(map(tuple, sheet)), m, n)


# ---------- Tier 4: fuzz (slow) ----------

def _random_polyomino(rng, size):
    """Grow a 4-connected polyomino of exactly `size` cells from the origin."""
    cells = {(0, 0)}
    frontier = [(0, 0)]
    while len(cells) < size:
        cx, cy = rng.choice(frontier)
        nbrs = [(cx + dx, cy + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        rng.shuffle(nbrs)
        placed = False
        for nb in nbrs:
            if nb not in cells:
                cells.add(nb)
                frontier.append(nb)
                placed = True
                break
        if not placed:
            frontier.remove((cx, cy))
    # normalize to origin
    minx = min(x for x, _ in cells)
    miny = min(y for _, y in cells)
    return [[x - minx, y - miny] for (x, y) in sorted(cells)]


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(6))
def test_fuzz_random_polyominoes(seed):
    rng = random.Random(1000 + seed)
    size = rng.choice([9, 12, 15])           # all % 3 == 0
    sheet = _random_polyomino(rng, size)
    xs = [c[0] for c in sheet]
    ys = [c[1] for c in sheet]
    m, n = max(xs) + 1, max(ys) + 1
    S = set(map(tuple, sheet))
    sols, ctx, err = _run(_opts(m, n, sheet=sheet))
    assert err is None, f"seed {seed} size {size} rejected: {err}"
    _assert_tier0(sols, S, m, n)
