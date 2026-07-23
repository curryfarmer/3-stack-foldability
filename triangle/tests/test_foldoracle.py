"""test_foldoracle.py — the geometry-exact fold ORACLE and the side-match guarantee it certifies.

foldoracle answers the question the shipped search cannot: does a drawn region flat-fold into a
3-stack AT ALL (not merely in the hub-seated chain family enumerate_folds searches), and if the
search missed a real fold, WHY. Three properties are pinned here:

  * SOUNDNESS       every fold the engine finds is also a fold the oracle finds (an engine fold IS a
                    consistent fold map), so the oracle only ever ADDS folds, never contradicts one.
  * COMPLETENESS    the reported point-pivot cases (six-round-a-point etc.) come back as a genuine
                    fold the search misses, across all four tilings, with the right machine `kind`.
  * SIDE MATCHING   no engine fold glues mismatched sides -- proven directly on the engine's own fold
                    (side_match_ok), swept to zero across every tiling. This is the "logically, a side
                    mismatch cannot fold flat" guarantee, made a test rather than a hope.

Live / in-process off foldoracle + foldgrid_tri (the test_fold_validity.py style). sys.path is set by
triangle/tests/conftest.py -- never co-import square/. Run:
  python -m pytest triangle/tests/test_foldoracle.py -q
"""
import itertools

import pytest

import foldgrid_tri as FG     # noqa: E402  the shipped hub-seated search (the thing the oracle second-guesses)
import foldoracle as OR       # noqa: E402  the module under test
import hexlattice as HX       # noqa: E402
import righttri as RT         # noqa: E402
import scalene as SC          # noqa: E402
import trilattice as TL       # noqa: E402


# --------------------------------------------------------------------------- region helpers
def _connected(lat, sub):
    sub = set(sub)
    s = next(iter(sub)); seen = {s}; st = [s]
    while st:
        t = st.pop()
        for nb in lat.adj[t]:
            if nb in sub and nb not in seen:
                seen.add(nb); st.append(nb)
    return len(seen) == len(sub)


def _connected_subsets(lat, size):
    for combo in itertools.combinations(lat.tris, size):
        if _connected(lat, combo):
            yield combo


# Hand-pinned NO_FOLD regions (derived, then frozen): connected, 6 tiles, and the oracle proves no
# 3-stack fold map exists at all. If the geometry ever changes these must be re-derived, loudly.
NO_FOLD_RIGHTTRI = [[0, 0, "N"], [0, 0, "E"], [0, 0, "S"], [1, 0, "N"], [1, 0, "E"], [1, 0, "W"]]
NO_FOLD_EQUILATERAL = [[0, 0, "U"], [0, 0, "D"], [1, 0, "U"], [1, 0, "D"], [0, 1, "U"], [1, 1, "U"]]


# --------------------------------------------------------------------------- the reported cases
def test_the_hexagon_of_six_is_a_real_fold_the_search_misses():
    """The bug report, as a positive statement: six equilateral triangles round a point DO fold into
    a 3-stack (fold in half), the engine returns nothing, and the oracle says exactly that -- a real
    fold outside the searched family, folding about the shared centre point, certain (K=2)."""
    lat = FG.build_lattice("equilateral", [tuple(t) for t in TL.hexagon_cells(1)])
    assert FG.enumerate_folds(lat, "equilateral") == []
    d = OR.diagnose(lat, [])
    assert d["kind"] == "fold-outside-model"
    assert d["certain"] is True                       # K = 2 layers -> physically realizable
    assert "shared point" in d["message"]
    assert len(d["columns"]) == 3


@pytest.mark.parametrize("tiling,region", [
    ("equilateral", [tuple(t) for t in TL.hexagon_cells(1)]),
    ("hex", None),                                     # filled below (needs the lattice)
    ("scalene", None),
])
def test_point_pivot_folds_are_found_across_tilings(tiling, region):
    """Every tiling that has a six-round-a-vertex ring: the ring folds, the engine misses it, the
    oracle reports fold-outside-model with a point-pivot column."""
    if tiling == "hex":
        hl = HX.HexLattice(R=2)
        region = [t for t in hl.tris if (abs(t[0]) + abs(t[1]) + abs(t[0] + t[1])) // 2 == 1]
    elif tiling == "scalene":
        region = _scalene_vertex_ring()
    lat = FG.build_lattice(tiling, [tuple(c) for c in region])
    assert FG.enumerate_folds(lat, tiling) == []
    d = OR.diagnose(lat, [])
    assert d["kind"] == "fold-outside-model"
    assert "shared point" in d["message"]


def _scalene_vertex_ring():
    lat = SC.ScaleneLattice(faces=TL.triangle_cells(5))
    import collections
    inc = collections.defaultdict(list)
    for t in lat.tris:
        for v in lat.verts[t]:
            inc[v].append(t)
    for _v, ts in sorted(inc.items(), key=repr):
        if len(ts) == 6:
            sub = FG.build_lattice("scalene", [tuple(x) for x in ts])
            if all(len(sub.adj[x]) == 2 for x in sub.tris):
                return [tuple(x) for x in ts]
    raise AssertionError("no scalene 6-ring found")


def test_strip_of_six_folds_but_not_by_a_point_pivot():
    """A drawn 1x3 rhombus strip: each rhombus folds in half, giving three 2-layer cells. A real fold
    the hub search misses -- but NOT a point pivot (every column is edge-adjacent), so the message is
    the plainer 'outside the family' rather than the shared-point one."""
    lat = FG.build_lattice("equilateral", [(i, 0, o) for i in range(3) for o in ("U", "D")])
    d = OR.diagnose(lat, [])
    assert d["kind"] == "fold-outside-model"
    assert "shared point" not in d["message"]


# --------------------------------------------------------------------------- definitive no-fold
@pytest.mark.parametrize("tiling,region", [
    ("righttri", NO_FOLD_RIGHTTRI),
    ("equilateral", NO_FOLD_EQUILATERAL),
])
def test_a_genuinely_unfoldable_region_reads_no_fold(tiling, region):
    """The other honest answer: a region with no 3-stack fold at all. The oracle's NO is definitive
    (it searched every fold map, not just the hub-seated ones), so the message must NOT hedge."""
    lat = FG.build_lattice(tiling, [tuple(c) for c in region])
    assert FG.enumerate_folds(lat, tiling) == []
    verdict, witness = OR.admits_stack(lat, 3)
    assert verdict == OR.NO_FOLD and witness is None
    d = OR.diagnose(lat, [])
    assert d["kind"] == "no-fold" and d["certain"] is True
    assert "cannot be flat-folded" in d["message"]


def test_engine_folds_defer_to_the_engine():
    """When the standard search DOES find folds, the oracle steps back -- kind 'engine-folds', no
    second-guessing of the engine's own FOLD/JAM verdicts."""
    lat = FG.build_lattice("equilateral", [tuple(t) for t in TL.hexagon_cells(2)])
    folds = FG.enumerate_folds(lat, "equilateral")
    assert folds
    d = OR.diagnose(lat, folds)
    assert d["kind"] == "engine-folds" and d["columns"] is None


# --------------------------------------------------------------------------- soundness (engine subset oracle)
@pytest.mark.parametrize("tiling,full,sizes", [
    ("equilateral", lambda: TL.TriLattice(2, 3), (6,)),
    ("righttri", lambda: RT.RightTriLattice(2, 2), (6,)),
])
def test_every_engine_fold_is_also_an_oracle_fold(tiling, full, sizes):
    """Soundness: an engine fold is by definition a consistent fold map, so any region the engine
    folds the oracle must also declare foldable. If this ever fails, the oracle is UNDER-counting and
    a 'no-fold' message could contradict a real engine result."""
    lat0 = full()
    checked = 0
    for size in sizes:
        for combo in _connected_subsets(lat0, size):
            lat = FG.build_lattice(tiling, list(combo))
            if FG.enumerate_folds(lat, tiling):
                verdict, _ = OR.admits_stack(lat, 3)
                assert verdict == OR.FOLDS, "engine folded a region the oracle calls %s: %r" % (verdict, combo)
                checked += 1
    assert checked, "no engine folds found to check soundness against"


# --------------------------------------------------------------------------- the side-match squash
@pytest.mark.parametrize("tiling,full,sizes,expect_folds", [
    ("righttri", lambda: RT.RightTriLattice(2, 2), (3, 6), True),
    ("equilateral", lambda: TL.TriLattice(2, 3), (3, 6), True),
    ("scalene", lambda: SC.ScaleneLattice(faces=TL.triangle_cells(3)), (3, 6), True),
    ("hex", lambda: HX.HexLattice(R=2), (3, 6), True),
])
def test_no_engine_fold_ever_glues_mismatched_sides(tiling, full, sizes, expect_folds):
    """The guarantee the user asked for, swept to zero: across every connected region of these sizes,
    every fold the engine reports lands each chain tile onto its hub as an EXACT congruent copy --
    same vertex set and same edge-length multiset. A single short-leg-onto-hypotenuse landing would
    trip side_match_ok. There are none, on any tiling."""
    lat0 = full()
    folds = mismatched = 0
    for size in sizes:
        for combo in _connected_subsets(lat0, size):
            lat = FG.build_lattice(tiling, list(combo))
            for rec in FG.enumerate_folds(lat, tiling):
                folds += 1
                if not OR.side_match_ok(lat, rec):
                    mismatched += 1
    assert mismatched == 0, "%d %s fold(s) glue mismatched sides" % (mismatched, tiling)
    if expect_folds:
        assert folds, "swept no %s folds -- the guarantee would be vacuous" % tiling


# --------------------------------------------------------------------------- coverage census (golden)
@pytest.mark.slow
@pytest.mark.parametrize("size,connected,engine_regions,oracle_regions", [
    (6, 183, 46, 131),
    (9, 740, 96, 654),
])
def test_oracle_finds_far_more_folds_than_the_search_on_a_3x3(size, connected, engine_regions, oracle_regions):
    """The scale of the gap, frozen. Over every connected region of a 3x3 equilateral lattice: the hub
    search folds `engine_regions` of them, the oracle `oracle_regions` -- the difference is the
    population of real folds the search cannot express (85 at size 6, 558 at size 9). Also a global
    guard that neither number silently collapses to zero."""
    lat0 = TL.TriLattice(3, 3)
    n = eng = orc = 0
    for combo in _connected_subsets(lat0, size):
        n += 1
        lat = FG.build_lattice("equilateral", list(combo))
        if FG.enumerate_folds(lat, "equilateral"):
            eng += 1
        verdict, _ = OR.admits_stack(lat, 3)
        if verdict == OR.FOLDS:
            orc += 1
    assert (n, eng, orc) == (connected, engine_regions, oracle_regions)
    assert orc > eng
