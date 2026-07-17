"""test_fold_grid_record.py — the bundle-record enrichment fold_grid stamps for the filters.

fold_grid._build_bundle copies a NORMALIZED decomp + the per-gate verdict vector onto each bundle
record so the GUI / CLI can filter off bundle.json without opening per-uid files. The two engines
spell the decomposition differently (square `decomposition` "2+1"/"1+1+1"; triangle `decomp`
"2plus1"/"1plus1plus1") and carry different verdict shapes (square dict, triangle string) -- this pins
the normalization. scripts.fold_grid imports NO engine, so it loads in the smoketest interpreter.
"""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from scripts import fold_grid                     # noqa: E402  (stdlib only, no engine)


def test_record_decomp_normalizes_square():
    assert fold_grid._record_decomp({"decomposition": "2+1"}) == "2+1"
    assert fold_grid._record_decomp({"decomposition": "1+1+1"}) == "1+1+1"


def test_record_decomp_normalizes_triangle_spelling():
    assert fold_grid._record_decomp({"decomp": "2plus1"}) == "2+1"
    assert fold_grid._record_decomp({"decomp": "1plus1plus1"}) == "1+1+1"


def test_record_decomp_absent_is_none():
    # square 2-stack has no decomposition field
    assert fold_grid._record_decomp({"circuit": [[0, 0]], "lattice": "square2stack"}) is None


def test_record_vector_dict_passes_through():
    v = {"exitFootprint": True, "parity": True, "reflection": True, "twist": None}
    assert fold_grid._record_vector({"verdict": v}) == v


def test_record_vector_string_verdict_is_none():
    # triangle stores a plain verdict STRING -> no structured vector
    assert fold_grid._record_vector({"verdict": "PREDICTED FOLDABLE (Tw=0)"}) is None
    assert fold_grid._record_vector({}) is None
