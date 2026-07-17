"""foldwalk.py — lattice-agnostic flat-fold geometry: compose the single reflection primitive
along a chain (or a fold tree) to get the TRUE folded image of a tile.

This is the geometry the triangle/general 3-stack example generator was missing. The square engine
already folds-and-checks via reflect_point (py/engine/fold.py reflection_verdict); the triangle path
only ever checked dual-GRAPH topology (trisearch.exit_ok) + an unreliable twist, so it admitted
folds that don't physically close and rendered un-folded tile ids as the "footprint". Here we fold
for real.

Every reflection tiling in this repo is a kaleidoscope: reflecting a tile's Cartesian vertices
across the crease it SHARES with a dual-neighbour lands them exactly on that neighbour (verified
exact on all dual edges: equilateral / righttri / scalene / hex). So composing reflections along a
walk is exact and meaningful on all of them.

Anchoring convention: index 0 of a walk (root of a tree) is the identity frame; every other tile's
transform composes the reflections across the creases on the path back to the anchor. Adjacent tiles
sharing original crease e have transforms differing by reflection across e (R_e fixes e pointwise,
so M_u = M_t . R_e keeps the hinge shared) — that is exactly the recurrence M_k = M_{k-1} . R_{e_k}.
"""
import os
import sys
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lattice.reflect import reflect_point  # noqa: E402  the single reflection of record


# --------------------------------------------------------------------------- walk fold
def fold_transform(lat, walk):
    """Return foldM(p): map a Cartesian point on the LAST tile of `walk` back to walk[0]'s anchor
    frame, by reflecting across the successive shared creases e_{n-2} .. e_0 in that order."""
    creases = [lat.shared_edge(walk[i], walk[i + 1]) for i in range(len(walk) - 1)]

    def foldM(p):
        for (a, b) in reversed(creases):          # e_{n-2} first ... e_0 last
            p = reflect_point(p, a, b)
        return p

    return foldM


# --------------------------------------------------------------------------- tree fold
def tree_fold(lat, tiles, root):
    """Fold a dual-CONNECTED body of tiles (e.g. a rigid 2-chain, whose canonical strand is NOT a
    walk) as a rigid unit. Returns (parent, foldM) where foldM(p, tid) maps a point attached to tile
    `tid` back to `root`'s frame by composing the reflections on tid's tree-path up to root.

    Degenerates to fold_transform when `tiles` happen to form a path."""
    tset = set(tiles)
    parent = {root: None}
    pcrease = {}
    q = deque([root])
    while q:
        x = q.popleft()
        for y in lat.adj[x]:
            if y in tset and y not in parent:
                parent[y] = x
                pcrease[y] = lat.shared_edge(x, y)
                q.append(y)
    if len(parent) != len(tset):
        raise ValueError("tree_fold: body of %d tiles is not dual-connected (reached %d)"
                         % (len(tset), len(parent)))

    def foldM(p, tid):
        cur = tid
        while parent[cur] is not None:
            a, b = pcrease[cur]
            p = reflect_point(p, a, b)
            cur = parent[cur]
        return p

    return parent, foldM


# --------------------------------------------------------------------------- folded polygons + keys
def folded_polygon(lat, foldM, tid):
    """Cartesian polygon of tile `tid` after a WALK fold (foldM takes one point)."""
    return [foldM(p) for p in lat.vertices_cart(tid)]


def folded_polygon_tree(lat, foldM, tid):
    """Cartesian polygon of tile `tid` after a TREE fold (foldM takes (point, tid))."""
    return [foldM(p, tid) for p in lat.vertices_cart(tid)]


def _poly_key(pts):
    """Order-independent key for a folded polygon (a tile's vertex set), rounded like fold.py."""
    return tuple(sorted((round(x, 6), round(y, 6)) for x, y in pts))


def _edge_key(seg):
    """Order-independent key for a folded crease segment (a crease has no intrinsic orientation
    once it is reached from two different reflection compositions). Rounded to 6 dp."""
    (x0, y0), (x1, y1) = seg
    a = (round(x0, 6), round(y0, 6))
    b = (round(x1, 6), round(y1, 6))
    return tuple(sorted((a, b)))


# --------------------------------------------------------------------------- self-check
def _selfcheck():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tri"))
    import trilattice as TL  # noqa: E402

    # (1) accordion strip: a straight U/D run folds every tile onto walk[0].
    lat = TL.TriLattice(6, 1)
    strip = []
    for i in range(6):
        strip.append((i, 0, "U"))
        strip.append((i, 0, "D"))
    strip = [t for t in strip if t in lat.adj]
    # keep only a genuine dual-walk prefix
    walk = [strip[0]]
    for t in strip[1:]:
        if t in lat.adj[walk[-1]]:
            walk.append(t)
    M = fold_transform(lat, walk)
    home = _poly_key(folded_polygon(lat, M, walk[-1])) == _poly_key(lat.vertices_cart(walk[0]))
    print("accordion strip len=%d folds end->start: %s" % (len(walk), home))

    # (2) tree fold sanity: a single rhombus (U+D) rooted at U folds D's shared edge consistently.
    lat2 = TL.TriLattice(2, 2)
    u, d = (0, 0, "U"), (0, 0, "D")
    if d in lat2.adj[u]:
        parent, f2 = tree_fold(lat2, [u, d], root=u)
        e = lat2.shared_edge(u, d)
        seg_u = e  # u-frame: identity (u is the root, so its shared edge is unreflected)
        seg_d = (f2(e[0], d), f2(e[1], d))
        print("tree-fold rhombus shared edge coincides:", _edge_key(seg_u) == _edge_key(seg_d))


if __name__ == "__main__":
    _selfcheck()
