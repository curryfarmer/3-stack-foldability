"""test_grid_edge_cases.py — degenerate drawn REGIONS for the triangle 1+1+1 grid ingest.

WHY THIS EXISTS. A user drew six equilateral triangles in a hexagon (the six that meet at one
vertex), expected it to fold, and got "no fold". It looks like a GUI bug and is not one; it is a
scope fact about the model, and nothing in the suite said so. `test_grid_ingest_tri.py` proves the
ingest re-discovers folds that DO exist (round-trip) and that emitted records are well-formed, but
its fuzz tier passes VACUOUSLY on a region that yields nothing — a structural zero and a broken
enumerator are indistinguishable there. This file pins the structural zeros, with their reason.

THE HEXAGON, EXPLAINED. `foldgrid_tri.enumerate_folds` seats the three chains on a trapezoid hub
(`lattice.base.Lattice.all_trapezoids`: a mid tile plus two of its NON-adjacent neighbours, so both
arms reflect onto the mid — that is the 3-stack start seat). The six triangles round a vertex form a
6-CYCLE in the dual graph: every tile has exactly two neighbours. So for every trapezoid in it, the
mid tile's only two neighbours ARE its own two arms, both already spent as chain starts — the mid
chain cannot reach length 2. Zero exact 3-covers, so the physical closure gate is never even
consulted. Same argument kills EVERY cycle region, at any length, on any tiling.

The user's own diagnosis ("we are folding about a point") is exactly right: the fan fold they had in
mind pivots about the centre vertex, joining the three 2-tile chains end-to-end round the point. The
engine's 1+1+1 is a different object — three chains seated on a shared EDGE-adjacent hub whose ends
reflect back onto their starts. Growing the hexagon out of the degenerate case restores folds
(hexagon of side 2 -> 24 closing folds), which is the control below.

Everything here runs in-process off `foldgrid_tri`, the `test_fold_validity.py` style; the Tier-0
record invariants are imported from the sibling suite rather than restated. sys.path comes from
triangle/tests/conftest.py -- never co-import square/.

Run: python -m pytest triangle/tests/test_grid_edge_cases.py -q
"""
import collections
import itertools

import pytest

import foldgrid_tri as FG     # noqa: E402  the module under test
import hexlattice as HX       # noqa: E402  hex ring region
import scalene as SC          # noqa: E402  scalene vertex-ring region
import trilattice as TL       # noqa: E402  equilateral hexagon / strip / big-triangle regions

from test_grid_ingest_tri import _assert_tier0   # noqa: E402  the shared record invariants


# --------------------------------------------------------------------------- region builders
def _vertex_ring(cells, v):
    """The tiles of `cells` incident to the equilateral vertex `v`, i.e. the ring round one point.
    I/O: (list[tid], (int, int)) -> list[tid]."""
    return [t for t in cells if v in TL.tri_vertices(t)]


def _eq_hexagon_of_six():
    """THE reported shape: the six equilateral triangles meeting at one vertex. `hexagon_cells(1)` is
    the side-1 hexagon, which is exactly that ring (its centre vertex is (1, 1))."""
    return [tuple(t) for t in TL.hexagon_cells(1)]


def _eq_annulus_of_eighteen():
    """The side-2 hexagon with its centre ring punched out: 18 tiles round a hole. Still a cycle, so
    the same argument applies at a length no one would call 'a hexagon'. `hexagon_cells(n)` is built
    on the big triangle with corners (0,0)/(3n,0)/(0,3n), so its centre vertex is (n, n)."""
    outer = [tuple(t) for t in TL.hexagon_cells(2)]
    inner = set(_vertex_ring(outer, (2, 2)))
    return [t for t in outer if t not in inner]


def _hex_ring_of_six():
    """The six hexagons at axial distance 1 from the origin — a 6-cycle round the (empty) centre."""
    lat = HX.HexLattice(R=2)
    return [t for t in lat.tris if (abs(t[0]) + abs(t[1]) + abs(t[0] + t[1])) // 2 == 1]


def _scalene_vertex_ring():
    """The first scalene vertex whose incident tiles form a 6-cycle. Derived, not hardcoded: the
    scalene tile id is a 5-tuple whose spelling is not something a test should pin by hand."""
    lat = SC.ScaleneLattice(faces=TL.triangle_cells(5))
    inc = collections.defaultdict(list)
    for t in lat.tris:
        for v in lat.verts[t]:
            inc[v].append(t)
    for _v, ts in sorted(inc.items(), key=repr):
        if len(ts) == 6 and _is_cycle(FG.build_lattice("scalene", [tuple(x) for x in ts])):
            return [tuple(x) for x in ts]
    raise AssertionError("no 6-tile scalene vertex ring found")


def _is_cycle(lat):
    """True iff every tile of `lat` has exactly two neighbours — the region's dual graph is a simple
    cycle. I/O: (Lattice) -> bool."""
    return all(len(lat.adj[t]) == 2 for t in lat.tris)


# The four cycle regions we can build. righttri is absent ON PURPOSE: its vertex rings hold 4 tiles
# (a square's corner) or 8 (the hypotenuse vertex), and neither length is divisible by 3, so the
# ingest rejects them at the guard before this shape question can even be asked.
CYCLE_REGIONS = [
    ("equilateral", "hexagon of six", _eq_hexagon_of_six),
    ("equilateral", "annulus of eighteen", _eq_annulus_of_eighteen),
    ("hex", "ring of six", _hex_ring_of_six),
    ("scalene", "vertex ring", _scalene_vertex_ring),
]


# --------------------------------------------------------------------------- the reported case
def test_the_equilateral_hexagon_of_six_yields_no_fold():
    """The bug report, pinned. Six triangles round a point: a legal, edge-connected, K=2 region that
    the ingest accepts and then finds nothing in. If this ever starts returning folds, the model
    changed and the explanation in this module's docstring is stale."""
    cells = _eq_hexagon_of_six()
    lat = FG.build_lattice("equilateral", cells)
    assert len(lat.tris) == 6 and len(lat.tris) // 3 == 2
    assert _is_cycle(lat), "the six triangles round a vertex must form a 6-cycle in the dual graph"
    assert FG.enumerate_folds(lat, "equilateral") == []


def test_the_hexagons_zero_comes_from_the_hub_not_the_closure_gate(monkeypatch):
    """WHERE the zero happens, which is the whole diagnostic value. The exact-3-cover enumeration
    dies first, so `reflection_closes_111` is never called even once — the hexagon is not a fold that
    fails to close, it is a region no seating reaches. The side-2 hexagon is the control: same tiling,
    same code path, the gate runs there."""
    calls = []
    real = FG.FC.reflection_closes_111
    monkeypatch.setattr(FG.FC, "reflection_closes_111",
                        lambda lat, chains: calls.append(1) or real(lat, chains))

    FG.enumerate_folds(FG.build_lattice("equilateral", _eq_hexagon_of_six()), "equilateral")
    assert calls == [], "the closure gate must never run on the hexagon (no 3-cover reaches it)"

    control = [tuple(t) for t in TL.hexagon_cells(2)]
    FG.enumerate_folds(FG.build_lattice("equilateral", control), "equilateral")
    assert calls, "control: the side-2 hexagon must reach the closure gate"


def test_a_cycle_regions_hub_mid_is_boxed_in_by_its_own_arms():
    """The mechanism, stated as an invariant over every cycle region and every hub in it: the mid
    tile's neighbour set IS the arm pair, so once the arms are spent as chain starts the mid chain has
    nowhere to grow. Any K >= 2 is therefore unreachable."""
    for tiling, name, build in CYCLE_REGIONS:
        lat = FG.build_lattice(tiling, build())
        assert _is_cycle(lat), "%s %s is not a cycle" % (tiling, name)
        traps = lat.all_trapezoids()
        assert traps, "%s %s: a cycle of length >= 4 still has trapezoid hubs" % (tiling, name)
        for arm1, mid, arm2 in traps:
            assert set(lat.adj[mid]) == {arm1, arm2}, \
                "%s %s: hub mid %r has a free neighbour" % (tiling, name, mid)


@pytest.mark.parametrize("tiling,name,build", CYCLE_REGIONS,
                         ids=[("%s-%s" % (t, n)).replace(" ", "-") for t, n, _ in CYCLE_REGIONS])
def test_a_cycle_region_never_yields_a_fold(tiling, name, build):
    """The general law the hexagon is one instance of, across three tilings and two ring lengths."""
    lat = FG.build_lattice(tiling, build())
    assert _is_cycle(lat)
    assert FG.enumerate_folds(lat, tiling) == [], "%s %s must yield no fold" % (tiling, name)


def test_the_hexagons_fan_partition_exists_but_no_hub_can_seat_it():
    """The fold the user had in mind, made explicit: the hexagon DOES split into three 2-tile chains
    (three rhombi round the centre). What rules it out is not connectivity, coverage or closure but
    the seat — those three chain starts are pairwise NON-adjacent, and a trapezoid hub is three
    mutually-touching tiles, so no hub in the region carries that triple."""
    lat = FG.build_lattice("equilateral", _eq_hexagon_of_six())
    order = _cycle_order(lat)
    chains = [(order[0], order[1]), (order[2], order[3]), (order[4], order[5])]

    for a, b in chains:                                   # each pair really is a legal 2-tile walk
        assert b in lat.adj[a]
    assert {t for pair in chains for t in pair} == set(lat.tris)   # and together they cover exactly S

    starts = frozenset(pair[0] for pair in chains)
    for a, b in itertools.combinations(starts, 2):
        assert b not in lat.adj[a], "the three chain starts must be pairwise non-adjacent"
    assert starts not in {frozenset(fp) for fp in lat.all_trapezoids()}


def _cycle_order(lat):
    """The tiles of a cycle region in walk order round the ring. I/O: (Lattice) -> list[tid]."""
    assert _is_cycle(lat)
    order = [lat.tris[0], lat.adj[lat.tris[0]][0]]
    while len(order) < len(lat.tris):
        nxt = [t for t in lat.adj[order[-1]] if t != order[-2]]
        order.append(nxt[0])
    return order


# --------------------------------------------------------------------------- the control
def test_the_side_two_hexagon_does_fold_closed():
    """Growing the hexagon out of the degenerate case restores folds — so nothing about hexagons, or
    about equilateral at large K, is broken. 0 predicted-flat is the separate, KNOWN equilateral
    1+1+1 obstruction (see test_grid_ingest_tri.test_equilateral_obstruction_zero_foldable), not
    another instance of this one."""
    cells = [tuple(t) for t in TL.hexagon_cells(2)]
    lat = FG.build_lattice("equilateral", cells)
    assert len(lat.tris) == 24 and not _is_cycle(lat)
    recs = FG.enumerate_folds(lat, "equilateral")
    _assert_tier0(lat, "equilateral", recs)
    assert len(recs) == 24, "side-2 hexagon closing-fold count drifted (was 24): %d" % len(recs)
    assert sum(r["foldable"] for r in recs) == 0, "equilateral 1+1+1 is obstructed -> 0 flat"


# --------------------------------------------------------------------------- other degenerate shapes
def test_the_smallest_legal_region_is_the_hub_itself():
    """K = 1: three tiles forming a trapezoid. Each chain is one tile, so start IS end and closure is
    trivial — the one shape where the ingest's answer is a single fold by construction."""
    lat = FG.build_lattice("equilateral", [(0, 0, "U"), (0, 0, "D"), (1, 0, "U")])
    recs = FG.enumerate_folds(lat, "equilateral")
    _assert_tier0(lat, "equilateral", recs)
    assert len(recs) == 1
    assert [len(c) for c in recs[0]["chains"]] == [1, 1, 1]


@pytest.mark.parametrize("name,cells", [
    ("strip of six", [(i, 0, o) for i in range(3) for o in ("U", "D")]),
    ("big triangle of side 3", [tuple(t) for t in TL.triangle_cells(3)]),
])
def test_other_small_equilateral_shapes_that_yield_nothing(name, cells):
    """Two more shapes a user would plausibly draw and expect something from. Neither is a cycle —
    both have degree-1 tiles — so they fail for their own reasons; they are pinned so a future change
    to the enumerator has to notice it moved them."""
    lat = FG.build_lattice("equilateral", cells)
    assert not _is_cycle(lat)
    assert FG.enumerate_folds(lat, "equilateral") == [], "%s unexpectedly folds" % name


def test_tiles_touching_only_at_a_point_are_rejected_as_disconnected():
    """Folding 'about a point' at the INPUT layer: two triangles that share exactly one vertex and no
    edge are not a connected region, however connected they look on screen. The guard rejects them
    loudly rather than silently searching a lattice with two components."""
    cells = [(0, 0, "U"), (1, 0, "U"), (2, 0, "U")]     # a row of UP tiles, corner to corner
    for a, b in zip(cells, cells[1:]):
        shared = set(TL.tri_vertices(a)) & set(TL.tri_vertices(b))
        assert len(shared) == 1, "fixture must touch at exactly one vertex, got %r" % (shared,)
    with pytest.raises(ValueError, match="edge-connected"):
        FG.build_lattice("equilateral", cells)


def test_json_list_cells_and_tuple_cells_agree():
    """The GUI writes fold-grid/1 cells as JSON arrays, the engines pass tuples. Same region either
    way — a cheap guard on the boundary the whole GUI path crosses."""
    cells = [tuple(t) for t in TL.hexagon_cells(2)]
    as_lists = [list(t) for t in cells]
    a = FG.enumerate_folds(FG.build_lattice("equilateral", cells), "equilateral")
    b = FG.enumerate_folds(FG.build_lattice("equilateral", as_lists), "equilateral")
    assert {FG._canon([[tuple(t) for t in c] for c in r["chains"]]) for r in a} == \
           {FG._canon([[tuple(t) for t in c] for c in r["chains"]]) for r in b}


# --------------------------------------------------------------------------- exhaustive small sweep
def _connected_subsets(lat, size):
    """Every edge-connected `size`-tile subset of `lat`, by brute force. Only sane for small lattices;
    the caller below uses an 18-tile one. I/O: (Lattice, int) -> iterator[tuple[tid, ...]]."""
    for combo in itertools.combinations(lat.tris, size):
        sub = set(combo)
        seen, stack = {combo[0]}, [combo[0]]
        while stack:
            t = stack.pop()
            for nb in lat.adj[t]:
                if nb in sub and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        if len(seen) == size:
            yield combo


@pytest.mark.parametrize("size,n_connected,n_cycles,n_with_fold", [(6, 183, 4, 46), (9, 740, 0, 96)])
def test_every_small_equilateral_region_sweeps_clean(size, n_connected, n_cycles, n_with_fold):
    """Exhaustive rather than fuzzed: EVERY edge-connected region of this size in a 3x3 equilateral
    lattice, ingested. Three claims at once — the emitted records are always well-formed, every cycle
    region yields nothing (the hexagon law, over the whole population), and folds at these sizes DO
    exist in quantity, so a global regression to 'always zero' cannot hide here. Sub-second."""
    lat = TL.TriLattice(3, 3)
    connected = cycles = with_fold = 0
    for combo in _connected_subsets(lat, size):
        connected += 1
        sub = FG.build_lattice("equilateral", list(combo))
        recs = FG.enumerate_folds(sub, "equilateral")
        _assert_tier0(sub, "equilateral", recs)
        if _is_cycle(sub):
            cycles += 1
            assert recs == [], "cycle region %r yielded a fold" % (combo,)
        if recs:
            with_fold += 1
    assert (connected, cycles, with_fold) == (n_connected, n_cycles, n_with_fold)


@pytest.mark.slow
def test_a_region_with_a_real_hole_still_reports_holes_zero():
    """A drawn annulus that DOES fold (the side-3 hexagon with its centre ring punched out). `holes`
    is stamped 0 even though the shape plainly encloses one, and that is correct as defined: `holes`
    counts AMBIENT tiles the fold leaves uncovered, and a region-built lattice is its own ambient
    (foldgrid_tri._record). Pinned because the number is load-bearing for the renderer and reads as
    wrong to anyone looking at the picture."""
    outer = [tuple(t) for t in TL.hexagon_cells(3)]
    inner = set(_vertex_ring(outer, (3, 3)))
    annulus = [t for t in outer if t not in inner]
    lat = FG.build_lattice("equilateral", annulus)
    assert len(lat.tris) == 48
    recs = FG.enumerate_folds(lat, "equilateral")
    _assert_tier0(lat, "equilateral", recs)
    assert len(recs) == 24, "side-3 annulus closing-fold count drifted (was 24): %d" % len(recs)
    assert {r["holes"] for r in recs} == {0}
