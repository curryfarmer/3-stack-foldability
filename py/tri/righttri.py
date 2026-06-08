"""righttri.py — the 45-45-90 right-isosceles (tetrakis square) tiling, a second bipartite
reflection-tiling to test 3-stack folding on.

Each unit square (i,j) is split by BOTH diagonals into 4 right-isosceles triangles meeting at the
centre, orientation o in {N,E,S,W} (right angle at centre, 45 deg at the two square corners).
Tile id = (i,j,o). This is a kaleidoscope (*442) tiling: every edge is a mirror line, so a fold
maps a tile exactly onto its neighbour (verified in _selfcheck via _reflect_point).

Interface mirrors trilattice.TriLattice so the generic search/twist/hunt machinery runs on it:
  .tris .verts .edges .cent .adj .shared  + .all_trapezoids() .shared_edge_cart()
  + module fns vcart/centroid/sigma and instance .centroid()/.sigma().
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

_W = {"N": 0, "S": 0, "E": 1, "W": 1}   # sigma sublattice weight per orientation


def vcart(key):
    """Integer vertex key (2x,2y) -> Cartesian (x,y)."""
    return (key[0] / 2.0, key[1] / 2.0)


def tile_vertices(tid):
    """Tile (i,j,o) -> its 3 integer vertex keys (2 square-edge corners + the square centre)."""
    i, j, o = tid
    c = (2 * i + 1, 2 * j + 1)                       # square centre
    if o == "N":
        return [(2 * i, 2 * j + 2), (2 * i + 2, 2 * j + 2), c]
    if o == "S":
        return [(2 * i, 2 * j), (2 * i + 2, 2 * j), c]
    if o == "E":
        return [(2 * i + 2, 2 * j), (2 * i + 2, 2 * j + 2), c]
    return [(2 * i, 2 * j), (2 * i, 2 * j + 2), c]    # W


def _edges(verts):
    a, b, c = verts
    return [frozenset((a, b)), frozenset((b, c)), frozenset((c, a))]


def tile_cart(tid):
    return [vcart(v) for v in tile_vertices(tid)]


def centroid(tid):
    vs = tile_cart(tid)
    return (sum(p[0] for p in vs) / 3.0, sum(p[1] for p in vs) / 3.0)


def sigma(tid):
    return 1 if (tid[0] + tid[1] + _W[tid[2]]) % 2 == 0 else -1


def solid_block(M, N):
    """4*M*N triangles tiling a solid M x N square region (hole-free by construction)."""
    return [(i, j, o) for j in range(N) for i in range(M) for o in ("N", "E", "S", "W")]


class RightTriLattice:
    def __init__(self, M=None, N=None, cells=None):
        self.M, self.N = M, N
        if cells is None:
            cells = solid_block(M, N)
        self.tris, self.verts, self.edges, self.cent = [], {}, {}, {}
        for tid in cells:
            vs = tile_vertices(tid)
            self.tris.append(tid)
            self.verts[tid] = vs
            self.edges[tid] = _edges(vs)
            self.cent[tid] = centroid(tid)
        owners = {}
        for tid in self.tris:
            for e in self.edges[tid]:
                owners.setdefault(e, []).append(tid)
        self.adj = {tid: [] for tid in self.tris}
        self.shared = {}
        for e, os_ in owners.items():
            if len(os_) == 2:
                a, b = os_
                self.adj[a].append(b)
                self.adj[b].append(a)
                self.shared[(a, b)] = e
                self.shared[(b, a)] = e

    def centroid(self, tid):
        return self.cent[tid]

    def sigma(self, tid):
        return sigma(tid)

    def neighbors(self, tid):
        return self.adj[tid]

    def shared_edge_cart(self, a, b):
        p, q = tuple(self.shared[(a, b)])
        return (vcart(p), vcart(q))

    def all_trapezoids(self):
        out, seen = [], set()
        for mid in self.tris:
            nbs = self.adj[mid]
            for a in range(len(nbs)):
                for b in range(a + 1, len(nbs)):
                    arm1, arm2 = nbs[a], nbs[b]
                    if arm2 in self.adj[arm1]:
                        continue
                    fp = [arm1, mid, arm2]
                    key = frozenset(fp)
                    if key not in seen:
                        seen.add(key)
                        out.append(fp)
        return out


def _edge_len(lat, a, b):
    (px, py), (qx, qy) = lat.shared_edge_cart(a, b)
    return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5


def build_ambient_right(K, hub="LL"):
    """Big solid block + a central trapezoid hub. Tetrakis tiles have 1 hypotenuse + 2 leg
    neighbors, giving two inequivalent hubs: LL (arms = the two legs) and HL (arms = hyp+leg).
    Returns (lat, S=[arm1,mid,arm2], back) where `back` is the mid-chain's forced first step.
    """
    s = 2 * K + 4   # big enough that a K-step walk from the centre never hits the boundary
    lat = RightTriLattice(s, s)
    cx = sum(c[0] for c in lat.cent.values()) / len(lat.cent)
    cy = sum(c[1] for c in lat.cent.values()) / len(lat.cent)
    mids = [t for t in lat.tris if len(lat.adj[t]) == 3]
    mid = min(mids, key=lambda t: (lat.cent[t][0] - cx) ** 2 + (lat.cent[t][1] - cy) ** 2)
    nb = lat.adj[mid]
    legs = [n for n in nb if _edge_len(lat, mid, n) < 0.99]   # half-diagonals
    hypo = [n for n in nb if _edge_len(lat, mid, n) >= 0.99]  # square edge (len 1)
    if hub == "LL":
        S, back = [legs[0], mid, legs[1]], hypo[0]
    else:  # HL
        S, back = [hypo[0], mid, legs[0]], legs[1]
    assert S[2] not in lat.adj[S[0]], "arms adjacent (not a trapezoid)"
    assert set(lat.adj[mid]) == {S[0], S[2], back}, "mid-chain not forced"
    return lat, S, back


def pair_tw(chains):
    """Three theta pairwise-loop twists, using this lattice's centroid/sigma."""
    import tritwist as TW
    names, pairs, res = ["AB", "BC", "AC"], [(0, 1), (1, 2), (0, 2)], {}
    for nm, (i, j) in zip(names, pairs):
        loop = list(chains[i]) + list(reversed(chains[j]))
        res[nm] = TW.loop_twist(loop, cent=centroid, sigma=sigma)
    return res


def scan_existence(Kmax=12):
    """Smallest even K with a closing 3-stack fold (either hub type)."""
    import prove_obstruction as PO
    print("\n45-45-90 existence scan (closing folds, both hub types):")
    print(" K | LL closing | HL closing")
    first = None
    for K in range(2, Kmax + 1, 2):
        row = {}
        for hub in ("LL", "HL"):
            lat, S, back = build_ambient_right(K, hub)
            cl, ex, mids = PO.count_closing(lat, S, back, K)
            row[hub] = cl
        print(" %2d | %10d | %10d" % (K, row["LL"], row["HL"]))
        if first is None and (row["LL"] or row["HL"]):
            first = K
    print("=> first closing K =", first, " (square=8, equilateral=10)")
    return first


def census(K):
    """At chain length K: full twist histogram + foldable + hole-free over all closing folds."""
    import prove_obstruction as PO
    import tritwist as TW
    from hunt_foldable import holes
    from collections import Counter
    print("\n45-45-90 census at K=%d:" % K)
    for hub in ("LL", "HL"):
        lat, S, back = build_ambient_right(K, hub)
        arm1, m, arm2 = S
        mids = [p for p in PO.grow(lat, m, K, {arm1, arm2}) if p[1] == back]
        hist, closing, holefree, foldable = Counter(), 0, 0, []
        for pm in mids:
            um = set(pm)
            for pa in PO.grow(lat, arm1, K, um | {arm2}):
                ua = um | set(pa)
                for pc in PO.grow(lat, arm2, K, ua):
                    if not PO.is_trapezoid(lat, [pa[-1], pm[-1], pc[-1]]):
                        continue
                    closing += 1
                    L = pair_tw([pa, pm, pc])
                    hist[tuple(round(L[k]["Tw"]) for k in ("AB", "BC", "AC"))] += 1
                    hh = bool(holes(lat, set(pa) | set(pm) | set(pc)))
                    if not hh:
                        holefree += 1
                    if all(abs(L[k]["Tw"]) < 1e-6 for k in L):
                        foldable.append((pa, pm, pc, hh))
        print("  hub %s: closing=%d  hole-free=%d  foldable(Tw=0)=%d  [foldable&hole-free=%d]"
              % (hub, closing, holefree, len(foldable), sum(1 for f in foldable if not f[3])))
        print("    twist (AB,BC,AC) histogram:", dict(hist))


def _selfcheck():
    from twostack import _reflect_point  # generic line reflection (folds)
    lat = RightTriLattice(3, 3)
    print("tiles:", len(lat.tris), "(expect", 4 * 3 * 3, ")")
    bad = [(a, b) for a in lat.tris for b in lat.adj[a] if sigma(a) == sigma(b)]
    print("bipartite (sigma alternates on every dual edge):", "OK" if not bad else "FAIL %s" % bad[:3])
    from collections import Counter
    deg = Counter(len(lat.adj[t]) for t in lat.tris)
    print("degree histogram:", dict(deg))

    def same(A, B, tol=1e-7):
        ka = sorted((round(p[0] / tol) * tol, round(p[1] / tol) * tol) for p in A)
        kb = sorted((round(p[0] / tol) * tol, round(p[1] / tol) * tol) for p in B)
        return all(abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol for a, b in zip(ka, kb))

    ok = True
    nseam = 0
    for a in lat.tris:
        acart = [vcart(v) for v in lat.verts[a]]
        for b in lat.adj[a]:
            p, q = lat.shared_edge_cart(a, b)
            refl = [_reflect_point(pt, p, q) for pt in acart]
            bcart = [vcart(v) for v in lat.verts[b]]
            nseam += 1
            if not same(refl, bcart):
                ok = False
    print("reflect-to-neighbour exact on all", nseam, "dual edges (foldable tiling):", ok)
    # twist anchor: 4 triangles around a square centre form a 4-cycle
    import tritwist as TW
    i, j = 1, 1
    ring = [(i, j, "N"), (i, j, "E"), (i, j, "S"), (i, j, "W")]
    closed = all(ring[(k + 1) % 4] in lat.adj[ring[k]] for k in range(4))
    res = TW.loop_twist(ring, cent=centroid, sigma=sigma)
    print("square-centre 4-ring closed:", closed, "| sigmas:", [sigma(t) for t in ring],
          "| gammas:", res["gammas"], "| Tw=%.0f" % res["Tw"],
          "(clean mult of 360:", not TW.fractional(res["Tw"]), ")")
    print("num trapezoid footprints in 3x3:", len(lat.all_trapezoids()))


if __name__ == "__main__":
    import sys as _s
    _selfcheck()
    if len(_s.argv) > 1 and _s.argv[1] == "scan":
        first = scan_existence(int(_s.argv[2]) if len(_s.argv) > 2 else 12)
        if first:
            census(first)
