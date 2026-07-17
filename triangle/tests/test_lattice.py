"""test_lattice.py — per-lattice geometry invariants for the shared Lattice base (TRIANGLE half).

The five parametrized invariants below are SHARED with square/tests/test_lattice.py, which runs the
identical bodies against SquareLattice:
  * reflecting a tile across the crease it shares with a neighbour lands on that neighbour,
  * sigma is a bipartite 2-coloring (alternates on every dual edge),
  * centroid is the mean of the tile's Cartesian vertices,
  * shared_edge is symmetric (same crease for (a,b) and (b,a)),
  * all_trapezoids returns valid footprints (middle adjacent to both arms, arms not adjacent).

WHY DUPLICATED RATHER THAN SHARED. The original parametrized ONE fixture over the square lattice AND
the three triangle lattices in a single list, so both packages were instantiated at COLLECTION time.
That is impossible now the suites are per-package: square/ and triangle/ each put a bare `lattice` on
sys.path, so co-importing them races whichever _bootstrap ran second. The bodies are therefore
duplicated deliberately, each suite parametrizing only over its own package's lattices. Keep the two
copies in sync by hand -- an invariant added here belongs in the square copy too.

The square copy additionally carries square-only D4 / parity / exit-shape pins, which have no
triangle counterpart. Before the split the triangle lattices had NO standalone tests at all -- they
were exercised only through the shared fixture, which is exactly what this file preserves.

HEXLATTICE (triangle-only, no square counterpart) rides the GEOMETRY invariants via geom_case, but
NOT test_sigma_bipartite: the honeycomb dual is the triangular lattice, which has odd 3-cycles, so it
is non-bipartite and sigma() is only a +1 placeholder (foldability there uses the loop-index
path_sigma, not a global 2-coloring). Adding it to the geometry set is what pins its novel
vertex-key/centroid geometry (corner = frozenset of 3 axial ids; centroid = mean of 6 corner keys).
"""
import pytest  # noqa: E402

import trilattice as TL          # noqa: E402  (sys.path set in conftest.py)
import righttri as RT            # noqa: E402
import scalene as SC             # noqa: E402
import hexlattice as HX          # noqa: E402  non-bipartite -> geometry invariants only


# (id, lattice factory, reflection tolerance)
def _lattices():
    """Lattices valid for ALL five invariants, INCLUDING the bipartite sigma 2-coloring."""
    return [
        ("tri", TL.TriLattice(2, 3), 1e-7),
        ("righttri", RT.RightTriLattice(3, 3), 1e-7),
        ("scalene", SC.ScaleneLattice(faces=TL.triangle_cells(4)), 1e-5),
    ]


def _geom_lattices():
    """_lattices() + HexLattice, which is NON-bipartite (odd dual 3-cycles) so it is excluded from
    test_sigma_bipartite but valid for every geometry invariant (reflection lands on the neighbour,
    centroid = vertex mean, shared_edge symmetric, trapezoids well-formed)."""
    return _lattices() + [("hex", HX.HexLattice(R=2), 1e-7)]


def _pointset_equal(A, B, tol):
    sa = sorted((round(p[0], 6), round(p[1], 6)) for p in A)
    sb = sorted((round(p[0], 6), round(p[1], 6)) for p in B)
    return len(sa) == len(sb) and all(
        abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol for a, b in zip(sa, sb)
    )


@pytest.fixture(params=_lattices(), ids=lambda p: p[0])
def lat_case(request):
    return request.param


@pytest.fixture(params=_geom_lattices(), ids=lambda p: p[0])
def geom_case(request):
    """The geometry invariants (everything except the bipartite sigma) run over the hex lattice too."""
    return request.param


def test_reflection_lands_on_neighbour(geom_case):
    """Reflecting a tile's vertices across a shared crease reproduces the neighbour's vertices."""
    _id, lat, tol = geom_case
    seen = 0
    for a in lat.tiles:
        for b in lat.neighbors(a):
            img = lat.reflect_across_edge(a, lat.shared_edge(a, b))
            assert _pointset_equal(img, lat.vertices_cart(b), tol), f"{_id}: {a}->{b}"
            seen += 1
    assert seen > 0


def test_sigma_bipartite(lat_case):
    """Sigma alternates on every dual edge (a proper 2-coloring)."""
    _id, lat, _tol = lat_case
    bad = [(a, b) for a in lat.tiles for b in lat.neighbors(a) if lat.sigma(a) == lat.sigma(b)]
    assert not bad, f"{_id}: {bad[:3]}"


def test_centroid_is_vertex_mean(geom_case):
    """Centroid equals the mean of the tile's Cartesian vertices."""
    _id, lat, _tol = geom_case
    for t in lat.tiles:
        vs = lat.vertices_cart(t)
        mx = sum(p[0] for p in vs) / len(vs)
        my = sum(p[1] for p in vs) / len(vs)
        cx, cy = lat.centroid(t)
        assert abs(cx - mx) < 1e-9 and abs(cy - my) < 1e-9, f"{_id}: {t}"


def test_shared_edge_symmetric(geom_case):
    """shared_edge(a,b) and shared_edge(b,a) are the same crease (unordered)."""
    _id, lat, _tol = geom_case
    for a in lat.tiles:
        for b in lat.neighbors(a):
            e_ab = {tuple(round(c, 6) for c in p) for p in lat.shared_edge(a, b)}
            e_ba = {tuple(round(c, 6) for c in p) for p in lat.shared_edge(b, a)}
            assert e_ab == e_ba, f"{_id}: {a},{b}"


def test_all_trapezoids_valid(geom_case):
    """Every trapezoid footprint is [arm, mid, arm] with mid adjacent to both arms, arms not."""
    _id, lat, _tol = geom_case
    traps = lat.all_trapezoids()
    assert traps, f"{_id}: no trapezoids"
    for arm1, mid, arm2 in traps:
        assert arm1 in lat.neighbors(mid) and arm2 in lat.neighbors(mid)
        assert arm2 not in lat.neighbors(arm1)
