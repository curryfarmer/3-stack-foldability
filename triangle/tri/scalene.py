"""scalene.py — the 30-60-90 right-triangle (kisrhombille *632) tiling.

Barycentric subdivision of the equilateral lattice: every equilateral face (i,j,o) splits into 6
right-scalene tiles, each = {a face vertex V, an adjacent edge-midpoint M, the face centroid G}
(right angle at M, 30 deg at V, 60 deg at G). Tile id = (i,j,o,vid,oid): vid in {0,1,2} = which of
the face's 3 vertices, oid in {(vid+1)%3,(vid+2)%3} = which incident edge (named by its other
vertex). Bipartite by orientation; gamma in {0,+-60,+-120,+-180}.

Reuses equilateral coords (trilattice.vcart / .centroid) for the base vertices, edge-midpoints,
and centroids. Interface mirrors RightTriLattice so the generic search/twist/hunt machinery runs.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import trilattice as TL  # noqa: E402
from lattice.base import Lattice  # noqa: E402  shared geometry layer


def vkey_cart(key):
    """Combinatorial vertex key -> Cartesian. Keys: ('V',(i,j)) | ('M',frozenset{va,vb}) |
    ('C',(i,j,o))."""
    t = key[0]
    if t == "V":
        return TL.vcart(key[1])
    if t == "M":
        a, b = tuple(key[1])
        pa, pb = TL.vcart(a), TL.vcart(b)
        return ((pa[0] + pb[0]) / 2.0, (pa[1] + pb[1]) / 2.0)
    return TL.centroid(key[1])   # 'C'


def tile_keys(tid):
    i, j, o, vid, oid = tid
    fv = TL.tri_vertices((i, j, o))
    V, other = fv[vid], fv[oid]
    return [("V", V), ("M", frozenset((V, other))), ("C", (i, j, o))]


def tile_cart(tid):
    return [vkey_cart(k) for k in tile_keys(tid)]


def centroid(tid):
    pts = tile_cart(tid)
    return (sum(p[0] for p in pts) / 3.0, sum(p[1] for p in pts) / 3.0)


def sigma(tid):
    V, M, G = tile_cart(tid)
    cross = (M[0] - V[0]) * (G[1] - V[1]) - (M[1] - V[1]) * (G[0] - V[0])
    return 1 if cross > 0 else -1


def subdivide(faces):
    out = []
    for (i, j, o) in faces:
        for vid in range(3):
            for oid in ((vid + 1) % 3, (vid + 2) % 3):
                out.append((i, j, o, vid, oid))
    return out


class ScaleneLattice(Lattice):
    """30-60-90 kisrhombille tiling over the shared Lattice base; supplies only the scalene
    vertex/sigma hooks (dual graph, creases, centroids, trapezoids come from the base)."""

    def __init__(self, faces=None, cells=None):
        if cells is None:
            cells = subdivide(faces)
        super().__init__(cells)

    def _tile_vertices(self, tid):
        return tile_keys(tid)

    def _vkey_to_cart(self, key):
        return vkey_cart(key)

    def _tile_sigma(self, tid):
        return sigma(tid)


def _shared_type(lat, a, b):
    """Classify the shared edge by its two key-types: 'VM', 'MG', or 'VG'."""
    types = sorted(k[0] for k in lat.shared[(a, b)])
    return {("M", "V"): "VM", ("C", "M"): "MG", ("C", "V"): "VG"}[tuple(types)]


def build_ambient_scalene(K, hub="omitVM"):
    """Big subdivided equilateral region + a central trapezoid hub. A scalene tile has 3
    inequivalent neighbours (across V-M / M-G / V-G edges) -> 3 hub classes, named by which
    neighbour becomes the forced `back` (omitVM/omitMG/omitVG: back = the omitted-type neighbour,
    arms = the other two)."""
    faces = TL.triangle_cells(2 * K + 6)
    lat = ScaleneLattice(faces=faces)
    cx = sum(c[0] for c in lat.cent.values()) / len(lat.cent)
    cy = sum(c[1] for c in lat.cent.values()) / len(lat.cent)
    mids = [t for t in lat.tris if len(lat.adj[t]) == 3]
    mid = min(mids, key=lambda t: (lat.cent[t][0] - cx) ** 2 + (lat.cent[t][1] - cy) ** 2)
    by = {_shared_type(lat, mid, n): n for n in lat.adj[mid]}
    backtype = hub[-2:]                       # 'VM' | 'MG' | 'VG'
    back = by[backtype]
    arms = [by[t] for t in ("VM", "MG", "VG") if t != backtype]
    S = [arms[0], mid, arms[1]]
    assert S[2] not in lat.adj[S[0]], "arms adjacent"
    assert set(lat.adj[mid]) == {S[0], S[2], back}, "mid-chain not forced"
    return lat, S, back


def scan_existence(Kmax=12):
    import prove_obstruction as PO
    print("\n30-60-90 (scalene) existence scan, 3 hub types:")
    print(" K | omitVM | omitMG | omitVG")
    first = None
    for K in range(2, Kmax + 1):
        row = {}
        for hub in ("omitVM", "omitMG", "omitVG"):
            lat, S, back = build_ambient_scalene(K, hub)
            cl, ex, mids = PO.count_closing(lat, S, back, K)
            row[hub] = cl
        print(" %2d | %6d | %6d | %6d" % (K, row["omitVM"], row["omitMG"], row["omitVG"]), flush=True)
        if first is None and any(row.values()):
            first = K
    print("=> first closing K =", first, " (square=8, equilateral=10, 45-45-90=>11)")
    return first


def _selfcheck():
    from lattice.reflect import reflect_point as _reflect_point
    from collections import Counter
    lat = ScaleneLattice(faces=TL.triangle_cells(4))
    print("tiles:", len(lat.tris), "(expect 6 * #faces =", 6 * len(TL.triangle_cells(4)), ")")
    bad = [(a, b) for a in lat.tris for b in lat.adj[a] if sigma(a) == sigma(b)]
    print("bipartite (sigma alternates on every dual edge):", "OK" if not bad else "FAIL %s" % bad[:2])
    print("degree histogram:", dict(Counter(len(lat.adj[t]) for t in lat.tris)))

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
    # twist anchor: the 6 sub-tiles of one face form a cycle around its centroid
    import tritwist as TW
    f = (1, 1, "U")
    ring6 = subdivide([f])
    # order them cyclically by angle around the centroid
    G = TL.centroid(f)
    ring6.sort(key=lambda t: __import__("math").atan2(centroid(t)[1] - G[1], centroid(t)[0] - G[0]))
    closed = all(ring6[(k + 1) % 6] in lat.adj[ring6[k]] for k in range(6))
    res = TW.loop_twist(ring6, cent=centroid, sigma=sigma)
    print("face 6-ring closed:", closed, "| gammas:", res["gammas"], "| Tw=%.0f" % res["Tw"],
          "(clean mult 360:", not TW.fractional(res["Tw"]), ")")


if __name__ == "__main__":
    import sys as _s
    _selfcheck()
    if len(_s.argv) > 1 and _s.argv[1] == "scan":
        scan_existence(int(_s.argv[2]) if len(_s.argv) > 2 else 12)
