"""base.py — UnitTile + Lattice ABC: the shared geometry layer for every tiling.

This is the proven TriLattice build (py/tri/trilattice.py) lifted verbatim and parameterized by
three per-lattice hooks so square and triangle lattices share ONE implementation of the dual
adjacency graph, shared-edge creases, centroids, and reflection:

  _tile_vertices(tid) -> [hashable vertex KEYS in boundary order]
  _vkey_to_cart(key)  -> (x, y) Cartesian point for a vertex key
  _tile_sigma(tid)    -> +-1 bipartite 2-coloring (checkerboard / UP-DOWN)

Everything else (neighbors, shared_edge, centroid, reflect_across_edge, all_trapezoids) is
generic. Reflection goes through the single primitive in lattice.reflect. Attribute names
(`tris`, `verts`, `edges`, `cent`, `adj`, `shared`, `shared_edge_cart`) match the triangle
engines so they keep consuming a lattice unchanged.
"""
from abc import ABC, abstractmethod

from lattice.reflect import reflect_point


def _cyclic_edges(vkeys):
    """n boundary vertex keys -> n unordered edges (consecutive pairs, wrapping). A triangle
    gives 3 edges, a square 4; two tiles sharing a boundary segment share the same frozenset."""
    n = len(vkeys)
    return [frozenset((vkeys[i], vkeys[(i + 1) % n])) for i in range(n)]


class UnitTile:
    """A read-only view of one tile: its vertex keys, edges, Cartesian centroid, and sigma."""

    __slots__ = ("id", "verts", "edges", "centroid", "sigma")

    def __init__(self, tid, verts, edges, centroid, sigma):
        self.id = tid
        self.verts = verts
        self.edges = edges
        self.centroid = centroid
        self.sigma = sigma


class Lattice(ABC):
    """A tiling region with its dual (face-adjacency) graph. Subclasses supply the three hooks;
    the base builds tiles, the bipartite adjacency, the shared-edge creases, and centroids."""

    def __init__(self, cells):
        self.tiles = []                   # list of tile ids
        self.verts = {}                   # tid -> [vertex keys, boundary order]
        self.edges = {}                   # tid -> [frozenset edges]
        self.cent = {}                    # tid -> Cartesian centroid
        self._sig = {}                    # tid -> +-1
        for tid in cells:
            vk = self._tile_vertices(tid)
            self.tiles.append(tid)
            self.verts[tid] = vk
            self.edges[tid] = _cyclic_edges(vk)
            cart = [self._vkey_to_cart(v) for v in vk]
            k = len(cart)
            self.cent[tid] = (sum(p[0] for p in cart) / k, sum(p[1] for p in cart) / k)
            self._sig[tid] = self._tile_sigma(tid)
        # dual adjacency: tiles sharing an edge are neighbors; the shared edge is the fold crease
        edge_owners = {}
        for tid in self.tiles:
            for e in self.edges[tid]:
                edge_owners.setdefault(e, []).append(tid)
        self.adj = {tid: [] for tid in self.tiles}
        self.shared = {}                  # (a, b) ordered -> shared edge frozenset
        for e, owners in edge_owners.items():
            if len(owners) == 2:
                a, b = owners
                self.adj[a].append(b)
                self.adj[b].append(a)
                self.shared[(a, b)] = e
                self.shared[(b, a)] = e
        self.tris = self.tiles            # back-compat alias for the triangle engines

    # ---- per-lattice hooks ----
    @abstractmethod
    def _tile_vertices(self, tid):
        """tid -> list of hashable vertex KEYS in boundary order."""

    @abstractmethod
    def _vkey_to_cart(self, key):
        """vertex key -> (x, y) Cartesian point."""

    @abstractmethod
    def _tile_sigma(self, tid):
        """tid -> +1 / -1 bipartite coloring."""

    # ---- shared geometry ----
    def neighbors(self, tid):
        return self.adj[tid]

    def vertices(self, tid):
        """The tile's vertex KEYS (boundary order)."""
        return self.verts[tid]

    def vertices_cart(self, tid):
        """The tile's Cartesian vertices (boundary order)."""
        return [self._vkey_to_cart(v) for v in self.verts[tid]]

    def centroid(self, tid):
        return self.cent[tid]

    def sigma(self, tid):
        return self._sig[tid]

    def tile(self, tid):
        """A UnitTile view bundling this tile's geometry."""
        return UnitTile(tid, self.verts[tid], self.edges[tid], self.cent[tid], self._sig[tid])

    def shared_edge(self, a, b):
        """Cartesian endpoints (p1, p2) of the crease (shared edge) between adjacent a, b."""
        p, q = tuple(self.shared[(a, b)])
        return (self._vkey_to_cart(p), self._vkey_to_cart(q))

    shared_edge_cart = shared_edge        # name used by righttri / scalene

    def reflect_across_edge(self, tid, edge):
        """Reflect the tile's Cartesian vertices across the crease line `edge` = (p1, p2)."""
        a, b = edge
        return [reflect_point(p, a, b) for p in self.vertices_cart(tid)]

    # -- footprint: trapezoid = [arm, middle, arm] where the middle is dual-adjacent to both
    #    arms and the two arms are not adjacent to each other. The triangle analog of the square
    #    L-footprint (corner + two arms). Lifted verbatim from TriLattice. --
    def all_trapezoids(self):
        out, seen = [], set()
        for mid in self.tiles:
            nbs = self.adj[mid]
            for a in range(len(nbs)):
                for b in range(a + 1, len(nbs)):
                    arm1, arm2 = nbs[a], nbs[b]
                    if arm2 in self.adj[arm1]:      # arms adjacent -> not a trapezoid
                        continue
                    fp = [arm1, mid, arm2]
                    key = frozenset(fp)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(fp)
        return out
