"""test_dump_geometry.py — the SQUARE half of the fold-geometry/1 dump (S8).

In-process (single package, safe): build a SquareLattice directly and drive dump_geometry.emit_geometry
/ build, asserting the dump is deterministic, canonical, and byte-matches the committed golden that the
GUI's cross-package fidelity test (smoketest/test_gui_contract.py) reads. Also pins the load-bearing
contract that `ids` are exactly the fold-grid/1 native tile ids, so a drawn subset round-trips into
scripts/fold_grid.py.

sys.path is set by square/tests/conftest.py (via square/_bootstrap.py) -- never co-import triangle/.
"""
import json
import os

import pytest

import dump_geometry as DG        # type: ignore  # square/ on sys.path via conftest
from lattice import SquareLattice  # type: ignore

GOLDEN = os.path.join("smoketest", "golden", "geometry", "square.json")


@pytest.fixture(scope="module")
def golden(root_dir):
    with open(os.path.join(root_dir, GOLDEN), encoding="utf-8") as f:
        return json.load(f)


def test_matches_committed_golden(golden):
    """The dump the GUI will subprocess must equal the committed golden, built here in-process."""
    m, n = golden["bounds"]["m"], golden["bounds"]["n"]
    assert DG.build(m, n) == golden


def test_emit_is_schema_and_index_aligned():
    g = DG.build(3, 3)
    assert g["schema"] == "fold-geometry/1"
    assert g["tiling"] == "square"
    assert g["bounds"] == {"m": 3, "n": 3}
    assert len(g["ids"]) == len(g["polys"]) == 9      # ids[k] <-> polys[k]
    # square block: unit squares, so the tight rook grid has 2*3*2 = 12 interior edges
    assert len(g["adj"]) == 12


def test_deterministic_sorted_ids_and_canonical_adj():
    g = DG.build(3, 3)
    assert g["ids"] == sorted(g["ids"])               # sorted -> deterministic
    for i, j in g["adj"]:
        assert i < j                                   # canonical, each undirected edge once
    assert g["adj"] == sorted(map(list, g["adj"]))     # whole list sorted
    assert DG.build(3, 3) == g                          # stable across calls


def test_ids_are_foldgrid_native_cells():
    """`ids` must be exactly the SquareLattice's native (x, y) ids -- a drawn subset is a valid
    fold-grid/1 `cells` list (docs/schema/fold-grid-1.md: square => [x, y] integer pairs)."""
    g = DG.build(2, 2)
    native = sorted(list(t) for t in SquareLattice(2, 2).tiles)
    assert g["ids"] == native
    for cell in g["ids"]:
        assert len(cell) == 2 and all(isinstance(c, int) for c in cell)


def test_polys_are_lattice_vertices_cart():
    """polys[k] is ids[k]'s Cartesian boundary straight from the shared Lattice surface."""
    lat = SquareLattice(2, 2)
    g = DG.build(2, 2)
    for cell, poly in zip(g["ids"], g["polys"]):
        expect = [[round(x, 9), round(y, 9)] for (x, y) in lat.vertices_cart(tuple(cell))]
        assert poly == expect
