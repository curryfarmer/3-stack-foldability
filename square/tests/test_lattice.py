"""test_lattice.py — per-lattice geometry invariants for the shared Lattice base (SQUARE half).

The five parametrized invariants below are SHARED with triangle/tests/test_lattice.py, which runs
the identical bodies against TriLattice / RightTriLattice / ScaleneLattice:
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
copies in sync by hand -- an invariant added here belongs in the triangle copy too.

Plus square-only pins for the relocated D4 / parity / exit-shape strategy (hand-derived values, so
they survive the later deletion of the legacy fold.py / search.py copies).
"""
import pytest  # noqa: E402

from lattice.square import SquareLattice  # noqa: E402  (sys.path set in conftest.py)


# (id, lattice factory, reflection tolerance)
def _lattices():
    return [
        ("square", SquareLattice(4, 4), 1e-9),
    ]


def _pointset_equal(A, B, tol):
    sa = sorted((round(p[0], 6), round(p[1], 6)) for p in A)
    sb = sorted((round(p[0], 6), round(p[1], 6)) for p in B)
    return len(sa) == len(sb) and all(
        abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol for a, b in zip(sa, sb)
    )


@pytest.fixture(params=_lattices(), ids=lambda p: p[0])
def lat_case(request):
    return request.param


def test_reflection_lands_on_neighbour(lat_case):
    """Reflecting a tile's vertices across a shared crease reproduces the neighbour's vertices."""
    _id, lat, tol = lat_case
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


def test_centroid_is_vertex_mean(lat_case):
    """Centroid equals the mean of the tile's Cartesian vertices."""
    _id, lat, _tol = lat_case
    for t in lat.tiles:
        vs = lat.vertices_cart(t)
        mx = sum(p[0] for p in vs) / len(vs)
        my = sum(p[1] for p in vs) / len(vs)
        cx, cy = lat.centroid(t)
        assert abs(cx - mx) < 1e-9 and abs(cy - my) < 1e-9, f"{_id}: {t}"


def test_shared_edge_symmetric(lat_case):
    """shared_edge(a,b) and shared_edge(b,a) are the same crease (unordered)."""
    _id, lat, _tol = lat_case
    for a in lat.tiles:
        for b in lat.neighbors(a):
            e_ab = {tuple(round(c, 6) for c in p) for p in lat.shared_edge(a, b)}
            e_ba = {tuple(round(c, 6) for c in p) for p in lat.shared_edge(b, a)}
            assert e_ab == e_ba, f"{_id}: {a},{b}"


def test_all_trapezoids_valid(lat_case):
    """Every trapezoid footprint is [arm, mid, arm] with mid adjacent to both arms, arms not."""
    _id, lat, _tol = lat_case
    traps = lat.all_trapezoids()
    assert traps, f"{_id}: no trapezoids"
    for arm1, mid, arm2 in traps:
        assert arm1 in lat.neighbors(mid) and arm2 in lat.neighbors(mid)
        assert arm2 not in lat.neighbors(arm1)


def test_square_centroid_and_sigma_concrete():
    """Square geometry is the literal checkerboard the triangle UP/DOWN coloring generalizes."""
    lat = SquareLattice(4, 4)
    assert lat.centroid((1, 2)) == (1.5, 2.5)
    assert lat.sigma((0, 0)) == 1 and lat.sigma((1, 0)) == -1 and lat.sigma((1, 1)) == 1


# ---- square strategy pins (hand-derived; independent of the legacy fold/search copies) ----

def test_square_reflect_scalar():
    assert SquareLattice.reflect_scalar(2, 3) == 3
    assert SquareLattice.reflect_scalar(0, 0) == -1
    assert SquareLattice.reflect_scalar(1, 2) == 2


def test_square_exit_shape():
    assert SquareLattice.exit_shape([(0, 0), (2, 0), (1, 0)]) == "Rect"
    assert SquareLattice.exit_shape([(0, 0), (0, 2), (0, 1)]) == "Rect"
    assert SquareLattice.exit_shape([(0, 0), (1, 0), (0, 1)]) == "L"
    assert SquareLattice.exit_shape([(0, 0), (3, 0), (1, 0)]) is None


def test_square_fold_directions():
    assert SquareLattice.fold_directions() == ("L", "R", "U", "D")


def test_square_automorphisms_are_d4_on_square_and_d2_otherwise():
    """The canonicalization group is the sheet's own symmetry group, derived not hardcoded.

    A square sheet admits all 8 of D4; a non-square one only the 4 with rot in {0, 2} (D2), since
    apply_transform's odd rotations land on the TRANSPOSED n x m sheet. This is the same rule
    twostack._canonical has always applied, and S3 brought the 3-stack engine into line with it."""
    for (m, n) in [(6, 6), (5, 5), (1, 1)]:
        assert len(SquareLattice.automorphisms(m, n)) == 8, f"{m}x{n} should admit all of D4"
    for (m, n) in [(6, 4), (4, 6), (9, 4), (8, 6)]:
        auto = SquareLattice.automorphisms(m, n)
        assert len(auto) == 4, f"{m}x{n} should admit only D2"
        assert {t["rot"] for t in auto} == {0, 2}
        assert {t["flip"] for t in auto} == {0, 1}


def test_square_d4_canonical_invariant_under_flip():
    """canonical_hash is invariant under a manual D4 flip of footprint + arrows."""
    m, n = 6, 4
    fp = {"cells": [(0, 0), (1, 0), (0, 1)]}
    chains = [
        {"kind": "2chain", "baseCells": [(0, 0), (1, 0)], "foldArrows": ["U", "R"]},
        {"kind": "1chain", "baseCells": [(0, 1)], "foldArrows": ["D"]},
    ]
    t = {"rot": 0, "flip": 1}
    fp2 = {"cells": [SquareLattice.apply_transform(t, x, y, m, n) for (x, y) in fp["cells"]]}
    chains2 = [
        {"kind": c["kind"],
         "baseCells": [SquareLattice.apply_transform(t, x, y, m, n) for (x, y) in c["baseCells"]],
         "foldArrows": [SquareLattice.transform_arrow(t, a) for a in c["foldArrows"]]}
        for c in chains
    ]
    assert SquareLattice.canonical_hash(fp, chains, m, n) == \
        SquareLattice.canonical_hash(fp2, chains2, m, n)
