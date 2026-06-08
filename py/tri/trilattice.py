"""trilattice.py — equilateral-triangle lattice (PoC for 3-stack folding on triangles).

A parallelogram region of M x N rhombi; each unit cell (i, j) holds an UP triangle and a
DOWN triangle, so the region has 2*M*N triangles. The triangular face-adjacency (dual) graph
is bipartite: UP (sigma = +1, "black", apex up) vs DOWN (sigma = -1, "white", apex down) — this
2-coloring is the triangle analog of the square checkerboard sigma = (-1)^(x+y).

Vertex (i, j) sits at the true equilateral position P(i, j) = (i + j/2, (sqrt3/2) * j), so all
triangles are unit-side equilateral and corner turn angles come out as multiples of 60 degrees.

Triangle id = (i, j, 'U'|'D'). A triangle stores its 3 integer vertices, its 3 edges (each an
unordered frozenset of two integer vertices), its sigma, and its Cartesian centroid. Two
triangles are dual-adjacent iff they share an edge; the shared edge is the fold crease.
"""
import math

H = math.sqrt(3.0) / 2.0   # row height


def vcart(v):
    """Integer vertex (i, j) -> Cartesian point (equilateral embedding)."""
    i, j = v
    return (i + j / 2.0, H * j)


def tri_vertices(tid):
    """The 3 integer vertices of triangle (i, j, o)."""
    i, j, o = tid
    if o == "U":
        return [(i, j), (i + 1, j), (i, j + 1)]
    return [(i + 1, j), (i, j + 1), (i + 1, j + 1)]


def _edges(verts):
    a, b, c = verts
    return [frozenset((a, b)), frozenset((b, c)), frozenset((c, a))]


def centroid(tid):
    vs = [vcart(v) for v in tri_vertices(tid)]
    return (sum(p[0] for p in vs) / 3.0, sum(p[1] for p in vs) / 3.0)


def sigma(tid):
    return 1 if tid[2] == "U" else -1


def parallelogram_cells(M, N):
    return [(i, j, o) for j in range(N) for i in range(M) for o in ("U", "D")]


def triangle_cells(s):
    """A big upward equilateral triangle of side s (s^2 small triangles)."""
    cells = []
    for j in range(s):
        for i in range(s - j):
            cells.append((i, j, "U"))
        for i in range(s - 1 - j):
            cells.append((i, j, "D"))
    return cells


def _bary(p, A, B, C):
    (px, py), (ax, ay), (bx, by), (cx, cy) = p, A, B, C
    det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    b0 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / det
    b1 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / det
    return (b0, b1, 1 - b0 - b1)


def hexagon_cells(n):
    """Regular hexagon of side n (6 n^2 triangles, balanced #UP==#DOWN).

    Built as the big triangle of side S=3n with the three side-n corner sub-triangles removed
    (a centroid whose barycentric coord exceeds 2/3 toward a corner is in that corner).
    """
    S = 3 * n
    A, B, C = vcart((0, 0)), vcart((S, 0)), vcart((0, S))  # the 3 corners of the big triangle
    out = []
    for t in triangle_cells(S):
        b = _bary(centroid(t), A, B, C)
        if max(b) <= 2.0 / 3.0 + 1e-9:
            out.append(t)
    return out


class TriLattice:
    """A triangle-lattice region with its dual (face-adjacency) graph.

    region: 'parallelogram' (M x N rhombi) by default, or pass an explicit `cells` list
    (e.g. triangle_cells / hexagon_cells) for other shapes.
    """

    def __init__(self, M=None, N=None, cells=None):
        self.M, self.N = M, N
        if cells is None:
            cells = parallelogram_cells(M, N)
        self.tris = []                    # list of triangle ids
        self.verts = {}                   # tid -> [3 int vertices]
        self.edges = {}                   # tid -> [3 frozenset edges]
        self.cent = {}                    # tid -> Cartesian centroid
        for tid in cells:
            vs = tri_vertices(tid)
            self.tris.append(tid)
            self.verts[tid] = vs
            self.edges[tid] = _edges(vs)
            self.cent[tid] = centroid(tid)
        # dual adjacency: share an edge -> (neighbor, shared edge)
        edge_owners = {}
        for tid in self.tris:
            for e in self.edges[tid]:
                edge_owners.setdefault(e, []).append(tid)
        self.adj = {tid: [] for tid in self.tris}
        self.shared = {}                  # (a, b) ordered -> shared edge frozenset
        for e, owners in edge_owners.items():
            if len(owners) == 2:
                a, b = owners
                self.adj[a].append(b)
                self.adj[b].append(a)
                self.shared[(a, b)] = e
                self.shared[(b, a)] = e

    def neighbors(self, tid):
        return self.adj[tid]

    def shared_edge_cart(self, a, b):
        """Cartesian endpoints of the crease (shared edge) between adjacent triangles a, b."""
        e = self.shared[(a, b)]
        p, q = tuple(e)
        return (vcart(p), vcart(q))

    # -- footprint: trapezoid = [arm, middle, arm] where the middle is dual-adjacent to both
    #    arms and the two arms are not adjacent to each other (same color, so never adjacent).
    #    This is the triangle analog of the square L-footprint (corner + two arms). --
    def all_trapezoids(self):
        out, seen = [], set()
        for mid in self.tris:
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


def _selfcheck():
    lat = TriLattice(2, 3)
    print("triangles:", len(lat.tris), "(expect 12)")
    # bipartite: every dual edge joins UP to DOWN
    bad = [(a, b) for a in lat.tris for b in lat.adj[a] if sigma(a) == sigma(b)]
    print("bipartite (sigma differs on every edge):", "OK" if not bad else f"FAIL {bad}")
    deg = {t: len(lat.adj[t]) for t in lat.tris}
    interior = [t for t, d in deg.items() if d == 3]
    print("degree histogram:", {d: sum(1 for x in deg.values() if x == d) for d in set(deg.values())})
    print("interior (deg 3) triangles:", len(interior))
    # vertex (1,1) should be surrounded by 6 in-region triangles
    hexring = [(1, 1, "U"), (0, 1, "U"), (1, 0, "U"), (0, 1, "D"), (0, 0, "D"), (1, 0, "D")]
    print("hex-ring around vertex (1,1) all in region:",
          all(t in lat.adj for t in hexring))
    # one trapezoid footprint, mutual linkage
    fp = lat.trapezoid(0, 0)
    mid = fp[1]
    print("trapezoid", fp, "-> middle DOWN adjacent to both arms:",
          fp[0] in lat.adj[mid] and fp[2] in lat.adj[mid],
          "| arms adjacent to each other:", fp[2] in lat.adj[fp[0]])
    print("num trapezoid footprints available:", len(lat.all_trapezoids()))


if __name__ == "__main__":
    _selfcheck()
