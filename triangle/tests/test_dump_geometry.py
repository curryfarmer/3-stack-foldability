"""test_dump_geometry.py — the TRIANGLE half of the fold-geometry/1 dump (S8), all four tilings.

In-process (single package, safe): drive dump_geometry.build for equilateral / righttri / scalene /
hex, asserting the dump is deterministic + canonical, byte-matches the committed golden the GUI's
cross-package fidelity test reads, and that `ids` are exactly each tiling's native tile ids (so a
drawn subset round-trips into scripts/fold_grid.py). scalene builds from parallelogram_cells; hex
from hex_rect -- the (m,n)->constructor branch under test.

sys.path is set by triangle/tests/conftest.py (via triangle/_bootstrap.py) -- never co-import square/.
"""
import json
import os

import pytest

import dump_geometry as DG   # type: ignore  # triangle/tri on sys.path via conftest

# native (i,j,o) orientation alphabets per tiling (docs/schema/fold-grid-1.md)
_O = {"equilateral": {"U", "D"}, "righttri": {"N", "E", "S", "W"}}


def _golden(root_dir, tiling):
    with open(os.path.join(root_dir, "smoketest", "golden", "geometry", tiling + ".json"),
              encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("tiling", ["equilateral", "righttri", "scalene", "hex"])
def test_matches_committed_golden(root_dir, tiling):
    g = _golden(root_dir, tiling)
    m, n = g["bounds"]["m"], g["bounds"]["n"]
    assert DG.build(tiling, m, n) == g


@pytest.mark.parametrize("tiling", ["equilateral", "righttri", "scalene", "hex"])
def test_deterministic_sorted_ids_and_canonical_adj(root_dir, tiling):
    g = _golden(root_dir, tiling)
    m, n = g["bounds"]["m"], g["bounds"]["n"]
    built = DG.build(tiling, m, n)
    assert built["schema"] == "fold-geometry/1"
    assert built["tiling"] == tiling
    assert len(built["ids"]) == len(built["polys"])
    assert built["ids"] == sorted(built["ids"])
    for i, j in built["adj"]:
        assert i < j
    assert built["adj"] == sorted(map(list, built["adj"]))
    assert DG.build(tiling, m, n) == built     # stable across calls


@pytest.mark.parametrize("tiling", ["equilateral", "righttri", "scalene", "hex"])
def test_ids_are_native_and_match_lattice(root_dir, tiling):
    """`ids` must be exactly the tiling's native tile ids, built from the same BUILDERS mapping the
    dump uses -- the round-trip-into-fold_grid contract."""
    g = _golden(root_dir, tiling)
    m, n = g["bounds"]["m"], g["bounds"]["n"]
    lat = DG.BUILDERS[tiling](m, n)
    native = sorted(list(t) for t in lat.tiles)
    assert DG.build(tiling, m, n)["ids"] == native


def test_native_id_shapes(root_dir):
    """The native-id contract per tiling (docs/schema/fold-grid-1.md id-shape table)."""
    for tiling in ("equilateral", "righttri"):
        for cell in DG.build(tiling, 2, 2)["ids"]:
            i, j, o = cell
            assert isinstance(i, int) and isinstance(j, int) and o in _O[tiling]
    for cell in DG.build("scalene", 1, 1)["ids"]:
        i, j, o, vid, oid = cell                   # 5-tuple
        assert o in {"U", "D"} and vid in {0, 1, 2} and oid in {0, 1, 2}
    for cell in DG.build("hex", 2, 2)["ids"]:
        q, r = cell                                # axial pair
        assert isinstance(q, int) and isinstance(r, int)


def test_native_orientation_is_y_up(root_dir):
    """Triangle emits raw +y-up coords (the dump never flips; the GUI records orientation). A solid
    block therefore spans strictly positive y."""
    for tiling in ("equilateral", "righttri", "scalene", "hex"):
        g = _golden(root_dir, tiling)
        ys = [y for poly in g["polys"] for (_x, y) in poly]
        assert max(ys) > 0
