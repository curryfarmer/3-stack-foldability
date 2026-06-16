"""trifold.py — fold geometry for the triangle lattice.

A fold is a reflection across a shared triangle EDGE line (the crease). We reuse the generic,
coordinate-agnostic line-reflection primitive from the 2-stack reference (py/twostack.py:
_reflect_point), exactly as the square engine reflects across axis-aligned crease lines — the
only difference is the crease now lies at a 0/60/120-degree orientation.

Key fact (verified in _selfcheck): reflecting a triangle across the edge it shares with a
neighbor lands its vertices exactly on that neighbor's vertices. So a chain's fold motion is a
walk on the dual graph, and the cumulative reflection tracks orientation for the twist.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lattice.reflect import reflect_point as _reflect_point  # noqa: E402  generic reflect across line through a,b
import trilattice as TL              # noqa: E402


def reflect_pt(p, edge_cart):
    a, b = edge_cart
    return _reflect_point(p, a, b)


def reflect_tri_cart(verts_cart, edge_cart):
    return [reflect_pt(p, edge_cart) for p in verts_cart]


def _key(p, tol=1e-9):
    return (round(p[0] / tol) * tol, round(p[1] / tol) * tol)


def same_point_set(a, b, tol=1e-7):
    sa = sorted(_key(p, tol) for p in a)
    sb = sorted(_key(p, tol) for p in b)
    return all(abs(pa[0] - pb[0]) < tol and abs(pa[1] - pb[1]) < tol for pa, pb in zip(sa, sb))


def centroid_path(walk):
    """tid walk -> list of Cartesian centroids (the panel path for twist)."""
    return [TL.centroid(t) for t in walk]


def is_walk(lat, walk):
    """True if consecutive triangles in the walk are dual-adjacent and no triangle repeats."""
    if len(set(walk)) != len(walk):
        return False
    return all(walk[k + 1] in lat.adj[walk[k]] for k in range(len(walk) - 1))


def _selfcheck():
    lat = TL.TriLattice(2, 3)
    # reflecting UP(0,0) across its shared edge with DOWN(0,0) must reproduce DOWN(0,0)
    up, dn = (0, 0, "U"), (0, 0, "D")
    edge = lat.shared_edge_cart(up, dn)
    up_cart = [TL.vcart(v) for v in lat.verts[up]]
    dn_cart = [TL.vcart(v) for v in lat.verts[dn]]
    refl = reflect_tri_cart(up_cart, edge)
    print("reflect UP(0,0) across shared edge == DOWN(0,0):", same_point_set(refl, dn_cart))
    # a few more neighbor reflections, all directions
    ok = True
    for a in lat.tris:
        a_cart = [TL.vcart(v) for v in lat.verts[a]]
        for b in lat.adj[a]:
            r = reflect_tri_cart(a_cart, lat.shared_edge_cart(a, b))
            b_cart = [TL.vcart(v) for v in lat.verts[b]]
            if not same_point_set(r, b_cart):
                ok = False
    print("all", sum(len(lat.adj[t]) for t in lat.tris), "neighbor reflections land on neighbor:", ok)
    # walk validation
    w = [(0, 0, "U"), (0, 0, "D"), (1, 0, "U")]
    print("trapezoid is a valid walk:", is_walk(lat, w))


if __name__ == "__main__":
    _selfcheck()
