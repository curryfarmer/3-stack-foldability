"""twostack.py — RSPA 2-stack search on an m x n square grid (port of the reference
hamiltonian.py + twostack.py + notwist.py, Yang-You-Rosen 2025).

Method (faithful to the paper):
  1. Enumerate Hamiltonian circuits (HCs) on the grid graph (cells = nodes, orthogonal
     adjacency = edges). Crossed edges become creases, uncrossed = slits.
  2. Vector-reflection condition (Prop 3.1): there is a cut edge such that folding from both
     ends maps the cut crease onto a common target crease (the two open ends rejoin) -> the
     loop folds into two EQUAL stacks.
  3. No-twist condition (Prop 4.1): the closed-loop turn-angle balance is zero.
  Foldable into two stacks iff (2) and (3) both hold (paper Theorem).

Cells are (x, y) integer tuples; geometry uses cell centres (x+0.5, y+0.5) and unit
cell-boundary segments (G1 edges), keyed by midpoint — matching the reference's
edge_mid_lookup.
"""

import math
from collections import defaultdict

from lattice.reflect import reflect_point


# ---------- grid graph ----------

def _adjacency(m, n):
    adj = defaultdict(list)
    for y in range(n):
        for x in range(m):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < m and 0 <= ny < n:
                    adj[(x, y)].append((nx, ny))
    return adj


def enumerate_hc(m, n):
    """All Hamiltonian circuits as ordered cell lists (each undirected cycle once).

    Fix start = (0,0); count a cycle in the single direction where its second node has a
    smaller linear index than its last node, so each undirected HC is emitted exactly once.
    """
    N = m * n
    if N % 2 != 0:
        return []            # bipartite grid graph has no balanced HC when N is odd
    adj = _adjacency(m, n)
    start = (0, 0)
    idx = lambda c: c[1] * m + c[0]
    circuits = []
    path = [start]
    visited = {start}

    def backtrack():
        if len(path) == N:
            if start in adj[path[-1]] and idx(path[1]) < idx(path[-1]):
                circuits.append(list(path))
            return
        for nb in adj[path[-1]]:
            if nb not in visited:
                visited.add(nb)
                path.append(nb)
                backtrack()
                path.pop()
                visited.discard(nb)

    backtrack()
    return circuits


# ---------- G1 edge lookup (unit cell-boundary segments by midpoint) ----------

def _round4(p):
    return (round(p[0], 4), round(p[1], 4))


def _build_edge_lookup(m, n):
    lookup = {}
    for x in range(m):
        for y in range(n + 1):                      # horizontal segments
            seg = ((x, y), (x + 1, y))
            lookup[_round4(((x + x + 1) / 2, y))] = seg
    for x in range(m + 1):
        for y in range(n):                          # vertical segments
            seg = ((x, y), (x, y + 1))
            lookup[_round4((x, (y + y + 1) / 2))] = seg
    return lookup


# ---------- reflection geometry ----------
# The line-reflection primitive lives in lattice/reflect.py (one reflection of record);
# imported as reflect_point at the top of this module.


def _reflect_edge(edge, mirror):
    return (reflect_point(edge[0], mirror[0], mirror[1]),
            reflect_point(edge[1], mirror[0], mirror[1]))


def _pt_close(a, b, tol=1e-4):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def _edge_same_oriented(e1, e2):
    return _pt_close(e1[0], e2[0]) and _pt_close(e1[1], e2[1])


def _edge_same_unordered(e1, e2):
    return _edge_same_oriented(e1, e2) or (_pt_close(e1[0], e2[1]) and _pt_close(e1[1], e2[0]))


def _center(c):
    return (c[0] + 0.5, c[1] + 0.5)


def _mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _reflect_along(edge, path_centers, lookup):
    cur = edge
    for i in range(len(path_centers) - 1):
        key = _round4(_mid(path_centers[i], path_centers[i + 1]))
        g1 = lookup.get(key)
        if g1 is not None:
            cur = _reflect_edge(cur, g1)
    return cur


def reflection_cut(circuit, lookup):
    """Return the valid cut G1 edge (Prop 3.1) if one exists, else None.

    Tries each cut position: split the closed loop into two equal arcs; reflect the cut
    crease along each; valid if both reflections agree (orientation) and land on the target
    rejoin crease (position).
    """
    centers = [_center(c) for c in circuit]
    closed = centers + [centers[0]]
    mid = len(closed) // 2
    for i in range(mid):
        path1 = closed[i:i + mid]
        path2 = (closed[i + mid:-1] + closed[0:i])[::-1]
        if not path1 or not path2:
            continue
        node1, node2 = path1[0], path1[-1]
        node3, node4 = path2[0], path2[-1]
        start_edge = lookup.get(_round4(_mid(node1, node3)))
        target_edge = lookup.get(_round4(_mid(node2, node4)))
        if start_edge is None or target_edge is None:
            continue
        r1 = _reflect_along(start_edge, path1, lookup)
        r2 = _reflect_along(start_edge, path2, lookup)
        if _edge_same_oriented(r1, r2) and _edge_same_unordered(r1, target_edge):
            return start_edge      # the cut crease (G1 segment, corner coords)
    return None


# ---------- twist (port of notwist.py) ----------

def twist_value(circuit):
    n = len(circuit)
    odd = even = 0
    for i in range(n):
        p1, p2, p3 = circuit[i], circuit[(i + 1) % n], circuit[(i + 2) % n]
        v1 = (p2[0] - p1[0], p2[1] - p1[1])
        v2 = (p3[0] - p2[0], p3[1] - p2[1])
        dot = v1[0] * v2[0] + v1[1] * v2[1]
        cross = v1[0] * v2[1] - v1[1] * v2[0]
        ang = round(math.degrees(math.atan2(cross, dot))) * 2
        if i % 2 == 0:
            even += ang
        else:
            odd += ang
    return odd - even


# ---------- D4 + cyclic + reversal canonical key (dedup up to grid symmetry) ----------

def _canonical(circuit, m, n):
    def transforms(x, y):
        # D2 (identity, flipH, flipV, rot180) always; add the 90deg/diagonal images only when
        # m==n (otherwise they aren't symmetries of the grid and would wrongly merge HCs).
        d2 = [(x, y), (m - 1 - x, y), (x, n - 1 - y), (m - 1 - x, n - 1 - y)]
        if m != n:
            return d2
        return d2 + [(y, x), (n - 1 - y, x), (y, m - 1 - x), (n - 1 - y, m - 1 - x)]
    best = None
    K = len(circuit)
    ntrans = 8 if m == n else 4
    for t in range(ntrans):
        pts = [transforms(c[0], c[1])[t] for c in circuit]
        # all rotations + reversal of the cyclic sequence
        for r in range(K):
            rot = pts[r:] + pts[:r]
            for seq in (rot, rot[::-1]):
                key = tuple(seq)
                if best is None or key < best:
                    best = key
    return best


# ---------- top-level runner ----------

def run(opts):
    m, n = opts["m"], opts["n"]
    ctx = {"hcCount": 0, "reflectionPass": 0, "twistPass": 0, "foldable": 0}
    if (m * n) % 2 != 0:
        return [], ctx, "m*n must be even (no balanced Hamiltonian circuit otherwise)"

    lookup = _build_edge_lookup(m, n)
    circuits = enumerate_hc(m, n)
    ctx["hcCount"] = len(circuits)

    dedup = opts.get("dedup", True)
    seen = set()
    solutions = []
    next_id = 1
    for circ in circuits:
        if dedup:
            key = _canonical(circ, m, n)
            if key in seen:
                continue
            seen.add(key)
        tw = twist_value(circ)
        twist_ok = (tw == 0)
        cut = reflection_cut(circ, lookup)
        refl_ok = cut is not None
        if refl_ok:
            ctx["reflectionPass"] += 1
        if twist_ok:
            ctx["twistPass"] += 1
        foldable = refl_ok and twist_ok
        if foldable:
            ctx["foldable"] += 1
        solutions.append({
            "id": next_id,
            "circuit": [[c[0], c[1]] for c in circ],
            "cutEdge": [[cut[0][0], cut[0][1]], [cut[1][0], cut[1][1]]] if cut else None,
            "verdict": {"reflection": refl_ok, "twist": twist_ok, "foldable": foldable},
            "twistValue": tw,
        })
        next_id += 1
    return solutions, ctx, None
