"""test_foldoracle.py — the square geometry-exact second opinion + its human diagnosis.

foldoracle answers the STRONGER fold question (does ANY consistent flat-fold map into N cells exist)
than the shipped footprint search (which only enumerates L/Rect chains seated on a corner), so it can
say WHY a drawn region produced no record: a real fold the search misses (`fold-outside-model`), a
definitive impossibility (`no-fold`), or budget exhaustion (`undetermined`). This suite pins the two
folds the search provably misses — a straight strip folded in half, and a genuine fold-about-a-point —
plus soundness (every engine fold IS an oracle fold) and the corner-touch precision the point-pivot
message rests on.

SQUARE-ONLY, like every test here: square/ and triangle/ each ship a bare `lattice`, so foldoracle is
imported flat off conftest's sys.path and never alongside the triangle one.
"""
import itertools

import pytest

import foldoracle as OR                          # type: ignore  # on sys.path via conftest
import search as Search                          # type: ignore
import enginelib as EL                           # type: ignore
from lattice.square import SquareLattice, sheet_connected  # type: ignore


def _lat(cells, m=None, n=None):
    """A SquareLattice over an explicit origin-anchored cell list (bbox inferred when m/n omitted)."""
    m = m if m is not None else max(x for x, _ in cells) + 1
    n = n if n is not None else max(y for _, y in cells) + 1
    return SquareLattice(m, n, cells=[tuple(c) for c in cells])


# The 1x6 strip: folds in half into a 3-stack (3 footprint cells, 2 layers), yet `--stacks 3` finds
# nothing — the straight fold-in-half is outside the enumerated L/Rect footprint family. Its columns
# stack far-apart end tiles that touch NOWHERE, so it is NOT a fold-about-a-point.
_STRIP6 = [(x, 0) for x in range(6)]

# A genuine fold-about-a-point: this 8-cell region 4-stacks (4 footprint cells, 2 layers) with a column
# pairing two tiles that meet only at a corner. K=2, so the verdict is physically certain. Pinned from
# a deterministic tight-box search (square/tests found 32 such folds at size 8, cells 4).
_POINT_PIVOT8 = [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 2), (2, 0), (2, 1)]

# A connected, size-divisible region that STILL cannot fold into 3 cells: a definitive no-fold, not a
# mere divisibility reject. Pinned from the same search.
_NO_FOLD6 = [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 2)]


# --------------------------------------------------------------------------- the two missed folds
def test_strip_of_six_folds_but_the_search_misses_it():
    d = OR.diagnose(_lat(_STRIP6), [], cells=3)
    assert d["kind"] == "fold-outside-model"
    assert d["certain"] is True                       # K = 6/3 = 2 layers -> physically realizable
    assert len(d["columns"]) == 3                     # three footprint cells
    # It is NOT a point-pivot (the end tiles touch nowhere) -> the honest wording is "outside the
    # family", never the false "folds about a shared point".
    assert "outside the family" in d["message"]
    assert "shared point" not in d["message"]


def test_a_square_fold_about_a_point_is_diagnosed_as_such():
    lat = _lat(_POINT_PIVOT8)
    verdict, witness = OR.admits_stack(lat, cells=4)
    assert verdict == OR.FOLDS
    assert OR._has_point_pivot_column(lat, OR.witness_columns(lat, witness)) is True
    d = OR.diagnose(lat, [], cells=4)
    assert d["kind"] == "fold-outside-model"
    assert d["certain"] is True                       # K=2
    assert "shared point" in d["message"] and "corner" in d["message"]
    assert len(d["columns"]) == 4


def test_point_pivot_detector_is_corner_touch_precise():
    """The square detector fires on a genuine corner-touch (exactly one shared vertex, no edge) and
    stays silent on both edge-adjacent and non-touching stacks — the distinction a straight square
    accordion needs, where far-apart tiles share a column without pivoting about any point."""
    lat = _lat([(0, 0), (1, 0), (0, 1), (1, 1), (2, 1)])
    assert OR._has_point_pivot_column(lat, [[(0, 0), (1, 1)]]) is True    # share only corner (1,1)
    assert OR._has_point_pivot_column(lat, [[(0, 0), (1, 0)]]) is False   # share an edge
    assert OR._has_point_pivot_column(lat, [[(0, 0), (2, 1)]]) is False   # touch nowhere


# --------------------------------------------------------------------------- the other verdicts
def test_a_definitive_no_fold_reads_no_fold():
    d = OR.diagnose(_lat(_NO_FOLD6), [], cells=3)
    assert d["kind"] == "no-fold"
    assert d["certain"] is True
    assert d["columns"] is None
    assert "cannot be flat-folded" in d["message"]


def test_size_not_divisible_by_cells_is_no_fold():
    # 5 tiles into 3 cells cannot give equal layers -> immediate no-fold (the cheap divisibility floor).
    assert OR.admits_stack(_lat([(x, 0) for x in range(5)]), cells=3)[0] == OR.NO_FOLD


def test_disconnected_region_is_no_fold():
    lat = SquareLattice(4, 1, cells=[(0, 0), (3, 0)])   # two cells, no shared edge
    assert OR.admits_stack(lat, cells=1)[0] == OR.NO_FOLD


def test_engine_folds_defer_without_searching():
    # A non-empty engine record list short-circuits to 'engine-folds' (no oracle search runs).
    d = OR.diagnose(_lat(_STRIP6), [{"anything": 1}], cells=3)
    assert d["kind"] == "engine-folds"
    assert d["columns"] is None
    assert "standard search" in d["message"]


def test_tiny_node_budget_is_undetermined():
    # Cap the backtracker so hard it cannot decide -> UNKNOWN -> the honest 'undetermined' reason.
    d = OR.diagnose(_lat(_POINT_PIVOT8), [], cells=4, node_cap=1)
    assert d["kind"] == "undetermined"
    assert d["certain"] is False
    assert "undetermined" in d["message"]


# --------------------------------------------------------------------------- soundness vs the engine
@pytest.mark.parametrize("m,n", [(3, 2), (3, 3), (2, 6)])
def test_every_engine_fold_is_an_oracle_fold(m, n):
    """SOUNDNESS: the shipped search only ever finds a subset of real fold maps, so whenever it returns
    a record for a region the oracle must independently agree the region FOLDS. Driven in-process
    through Search.run (never shelled), mirroring test_grid_ingest."""
    opts = EL.opts_3stack(m, n, allow_non_corner=True, jobs=1)
    sols, _ctx, err = Search.run(opts)
    assert not err, err
    if not sols:
        pytest.skip("engine found no fold for %dx%d -> nothing to check soundness against" % (m, n))
    lat = SquareLattice(m, n)                         # the full rectangle the engine searched
    assert OR.admits_stack(lat, cells=3)[0] == OR.FOLDS


@pytest.mark.slow
def test_point_pivot_folds_exist_at_practical_cells():
    """Regression floor for the discovery this module rests on: genuine square fold-about-a-point folds
    are not a triangle-only artifact — a tight deterministic sweep finds them at cells=2 and cells=4.
    If a refactor ever made _has_point_pivot_column silent, this catches it."""
    found = {2: 0, 4: 0}
    for bw, bh, size, cells in [(4, 3, 6, 2), (4, 4, 8, 4)]:
        coords = [(x, y) for x in range(bw) for y in range(bh)]
        for combo in itertools.combinations(coords, size):
            cs = list(combo)
            if (0, 0) not in cs or not sheet_connected(cs):
                continue
            lat = SquareLattice(bw, bh, cells=cs)
            v, w = OR.admits_stack(lat, cells)
            if v == OR.FOLDS and OR._has_point_pivot_column(lat, OR.witness_columns(lat, w)):
                found[cells] += 1
                break
    assert found[2] > 0 and found[4] > 0, found
