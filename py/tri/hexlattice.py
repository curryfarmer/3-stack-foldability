"""hexlattice.py — the regular hexagonal (honeycomb) tiling, faces as tiles.

Unlike the three triangle tilings, honeycomb FACE-adjacency (the dual graph) is the triangular
lattice, which has odd 3-cycles -> it is NON-bipartite. So there is NO global sigma(tid)->+-1
2-coloring; the foldability twist must use the PATH-FOLLOWING sigma (tritwist.path_sigma: +-1 by
loop index), never lat.sigma(tid) (a +1 placeholder here). Everything else ports: each edge of a
regular hexagon is a mirror line, so a fold reflects a hexagon exactly onto its edge-neighbor
(verified in _selfcheck), and the generic Lattice base supplies the dual graph / creases /
centroids / trapezoids / reflection.

Flat-top hexagons. Tile id = axial (q, r); center P(q,r) = (1.5 q, sqrt3 (r + q/2)). The 6 corners
sit at 0,60,...,300 deg. A corner is shared by exactly 3 hexagons and equals the centroid of their
3 centers, so its combinatorial KEY = frozenset of those 3 axial ids (the same trick scalene.py
uses for shared vertices): neighbors then emit identical shared-edge frozensets regardless of which
tiles are in the region. Interface mirrors righttri/scalene so the generic machinery runs on it.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lattice.base import Lattice  # noqa: E402  shared geometry layer

SQRT3 = math.sqrt(3.0)

# axial neighbor offsets (flat-top), CCW by edge-direction angle 30,90,...,330
_NB = ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1))


def neighbors_axial(tid):
    q, r = tid
    return [(q + dq, r + dr) for (dq, dr) in _NB]


def _hex_center(q, r):
    return (1.5 * q, SQRT3 * (r + q / 2.0))


def corner_keys(tid):
    """The 6 corner vertex KEYS of hexagon (q,r), CCW from the 0-deg (east) corner. Corner k (at
    angle 60k) is the meeting point of this hex and neighbors _NB[k-1], _NB[k]; its key is the
    frozenset of those 3 axial ids (= the centroid of their 3 centers)."""
    nb = neighbors_axial(tid)
    return [frozenset((tid, nb[(k - 1) % 6], nb[k])) for k in range(6)]


def vkey_cart(key):
    """Corner key (frozenset of 3 axial ids) -> Cartesian (centroid of the 3 hex centers)."""
    pts = [_hex_center(q, r) for (q, r) in key]
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def tile_cart(tid):
    return [vkey_cart(k) for k in corner_keys(tid)]


def centroid(tid):
    return _hex_center(*tid)


def sigma(tid):
    """Placeholder. Honeycomb faces are NON-bipartite (no global 2-coloring); foldability twist
    uses tritwist.path_sigma along the loop, NOT this value."""
    return 1


def _axial_dist(q, r):
    return (abs(q) + abs(r) + abs(q + r)) // 2


def hex_disk(R):
    """All hexagons within axial distance R of the origin (a compact, near-circular patch)."""
    return [(q, r) for q in range(-R, R + 1) for r in range(-R, R + 1)
            if _axial_dist(q, r) <= R]


def hex_rect(M, N):
    """An M x N rhombus of hexagons (axial box). Handy as a solid ambient block."""
    return [(q, r) for q in range(M) for r in range(N)]


class HexLattice(Lattice):
    """Regular honeycomb (faces = tiles) over the shared Lattice base; supplies only the
    hexagon vertex/sigma hooks. NON-bipartite dual -> sigma() is a +1 placeholder."""

    def __init__(self, R=None, cells=None):
        self.R = R
        if cells is None:
            cells = hex_disk(R)
        super().__init__(cells)

    def _tile_vertices(self, tid):
        return corner_keys(tid)

    def _vkey_to_cart(self, key):
        return vkey_cart(key)

    def _tile_sigma(self, tid):
        return sigma(tid)


def build_ambient_hex(K):
    """Big honeycomb disk + a central trapezoid hub S=[arm1, mid, arm2] (mid = origin; arms = two
    NON-adjacent neighbors). Returns (lat, S, back=None): a hex mid has degree 6, so the mid-chain
    is NOT forced (unlike degree-3 triangle mids), hence back is None and enum_111_general must run
    its non-bipartite slow path."""
    lat = HexLattice(R=K + 2)
    mid = (0, 0)
    nb = neighbors_axial(mid)
    arm1, arm2 = nb[0], nb[2]                 # two neighbors one apart -> non-adjacent
    assert arm1 in lat.adj[mid] and arm2 in lat.adj[mid], "arms not adjacent to mid"
    assert arm2 not in lat.adj[arm1], "arms adjacent (not a trapezoid)"
    return lat, [arm1, mid, arm2], None


def _selfcheck():
    from collections import Counter
    from lattice.reflect import reflect_point as _reflect_point
    import tritwist as TW

    lat = HexLattice(R=2)
    print("tiles:", len(lat.tris), "(hex_disk R=2 -> expect 19)")
    deg = Counter(len(lat.adj[t]) for t in lat.tris)
    print("degree histogram:", dict(deg), " interior(deg6)=", deg.get(6, 0))

    # NON-bipartite: the dual has odd 3-cycles. (0,0),(1,0),(0,1) are mutually adjacent.
    tri3 = [(0, 0), (1, 0), (0, 1)]
    cyc = all(tri3[(k + 1) % 3] in lat.adj[tri3[k]] for k in range(3))
    print("odd 3-cycle present (non-bipartite):", cyc)

    # foldable tiling: reflecting a hexagon across each shared edge lands exactly on its neighbor
    def same(A, B, tol=1e-6):
        ka = sorted((round(p[0] / tol) * tol, round(p[1] / tol) * tol) for p in A)
        kb = sorted((round(p[0] / tol) * tol, round(p[1] / tol) * tol) for p in B)
        return all(abs(a[0] - b[0]) < 1e-5 and abs(a[1] - b[1]) < 1e-5 for a, b in zip(ka, kb))

    ok, n = True, 0
    for a in lat.tris:
        ac = tile_cart(a)
        for b in lat.adj[a]:
            p, q = lat.shared_edge_cart(a, b)
            if not same([_reflect_point(pt, p, q) for pt in ac], tile_cart(b)):
                ok = False
            n += 1
    print("reflect-to-neighbour exact on all", n, "dual edges (foldable tiling):", ok)

    # twist anchor: the 6 neighbors of the origin form a 6-ring; path-following sigma -> clean Tw
    ring = neighbors_axial((0, 0))
    closed = all(ring[(k + 1) % 6] in lat.adj[ring[k]] for k in range(6))
    res = TW.loop_twist(ring, cent=centroid, sigma=TW.path_sigma(6))
    print("origin 6-ring closed:", closed, "| gammas:", res["gammas"],
          "| Tw(path-sigma)=%.0f" % res["Tw"], "(clean mult 360:", not TW.fractional(res["Tw"]), ")")
    print("num trapezoid footprints in R=2 disk:", len(lat.all_trapezoids()))
    lat2, S, back = build_ambient_hex(4)
    print("build_ambient_hex(4): tiles=%d  S=%s  back=%s  mid-degree=%d"
          % (len(lat2.tris), S, back, len(lat2.adj[S[1]])))


if __name__ == "__main__":
    _selfcheck()
