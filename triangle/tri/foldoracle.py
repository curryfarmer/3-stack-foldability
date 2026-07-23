"""foldoracle.py — a geometry-exact SECOND OPINION on whether a drawn region flat-folds into an
N-cell stack, and (when it does not fold the way the shipped engine searches) WHY.

WHY THIS EXISTS. `foldgrid_tri.enumerate_folds` only ever finds one shape of fold: three
edge-connected chains seated on a trapezoid hub (a mid tile plus two of its NON-adjacent neighbours),
each chain accordioning back onto its hub tile. That is a real, verifiable family — but it is not
every flat fold. The six equilateral triangles round a single vertex fold in half into a 3-stack, yet
the engine returns nothing: the fold pivots ABOUT THE CENTRE POINT, so one of its three columns pairs
two tiles that touch only at that vertex, never sharing an edge. No accordion of shared creases builds
that column, so no hub seats it. The engine's "no fold" is true only of its own search family, and a
bare "no fold" reads to a user as "this shape is impossible" when it is not.

This module answers the STRONGER question directly. A flat fold is an assignment of a plane isometry
to every tile such that across every shared crease the two tiles' isometries differ by either the
identity (crease left flat — the tiles stay edge-adjacent) or the reflection across that crease
(crease folded — one tile mirrors onto the other side). `admits_stack` searches for such an assignment
whose images occupy exactly `cells` footprint positions, each covered by K = |region| / cells layers.

  region  ->  admits_stack(lat, cells=3)  ->  (verdict, witness columns)  ->  diagnose(...) -> reason

SIDE MATCHING IS FREE HERE, BY CONSTRUCTION (the property the user asked us to guarantee). Every
tile's image is an EXACT isometry of the real triangle, so two tiles share a footprint cell only when
they are congruent AND identically placed — all three edge lengths coincide. A short leg can never
land where a long hypotenuse was. `side_match_ok` states that guarantee as a checkable predicate over
a shipped engine record, so "no reported fold glues mismatched sides" is a test, not a hope.

WHAT THIS DOES AND DOES NOT PROVE. The search is over the fold MAP (a piecewise isometry with a
consistent crease pattern). A NO verdict is definitive: no flat-fold map into `cells` cells exists at
all, so the shape genuinely cannot be folded that way. A YES verdict exhibits a real map; for K <= 2
layers it is also a physical fold (two layers always admit a non-crossing order), which covers every
K=2 case a user hits (six-round-a-point is K=2). For K >= 3 a YES means the map exists but a
non-crossing LAYER ORDER is not separately verified (that ordering problem is NP-hard in general);
`diagnose` says so rather than overclaiming. The engine's own folds are always a subset of the maps
found here (an engine fold IS such a map), so this only ever ADDS folds the engine missed, never
contradicts one it found.

Pure geometry over lattice.reflect + lat.{vertices_cart, shared_edge, adj, tris}, so it is identical
on equilateral / righttri / scalene / hex. Imports NO search code and does not touch the frozen
closure gate. sys.path is set by the importer (generate.py / the triangle test conftest).
"""
import collections
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lattice.reflect import reflect_point  # noqa: E402  the single reflection of record

# The exact-cover backtracker is worst-case exponential; a drawn sheet is small, but a pathological
# region should time out to UNKNOWN rather than wedge the GUI. Nodes, not seconds, so it is
# deterministic across machines (a slow CI must not turn a real YES/NO into a flaky UNKNOWN).
_NODE_CAP = 4_000_000

# admits_stack verdicts.
FOLDS = "folds"          # a flat-fold map into `cells` cells exists (witness returned)
NO_FOLD = "no-fold"      # provably none exists
UNKNOWN = "unknown"      # search hit the node cap before deciding


# --------------------------------------------------------------------------- affine (2x3) helpers
# An isometry is stored as (a, b, c, d, e, f): x' = a*x + b*y + e, y' = c*x + d*y + f.
_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _reflection_matrix(p, q):
    """The isometry that reflects across the line through Cartesian points p, q, as a 6-tuple.
    Derived by mapping the reflection's action on the origin and the two unit points (reflect_point
    is the single primitive; this just packages it as a reusable matrix)."""
    o = reflect_point((0.0, 0.0), p, q)
    x = reflect_point((1.0, 0.0), p, q)
    y = reflect_point((0.0, 1.0), p, q)
    return (x[0] - o[0], y[0] - o[0], x[1] - o[1], y[1] - o[1], o[0], o[1])


def _compose(g, h):
    """g after h: the isometry applying h then g."""
    a, b, c, d, e, f = g
    A, B, C, D, E, F = h
    return (a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D,
            a * E + b * F + e, c * E + d * F + f)


def _close(g, h):
    return all(abs(p - q) < 1e-9 for p, q in zip(g, h))


def _cellkey(g, lat, tid):
    """The footprint-cell key of tile `tid` under isometry `g`: its transformed vertex SET, rounded
    like the engine's _poly_key. Two tiles share a key iff they land as the exact same triangle."""
    a, b, c, d, e, f = g
    return tuple(sorted((round(a * x + b * y + e, 6) + 0.0, round(c * x + d * y + f, 6) + 0.0)
                        for x, y in lat.vertices_cart(tid)))


# --------------------------------------------------------------------------- the oracle
def admits_stack(lat, cells=3, node_cap=_NODE_CAP):
    """Does `lat` flat-fold into exactly `cells` footprint cells, each a K = |tiles|/cells layer stack?

    Returns (verdict, witness) where verdict is FOLDS / NO_FOLD / UNKNOWN and witness is a
    {tile -> isometry} dict on FOLDS (else None). Assigns each tile an isometry by BFS, forcing every
    shared crease to resolve as flat (equal isometries) or folded (differ by that crease's
    reflection), and prunes the moment the image would exceed `cells` distinct cells or K layers."""
    tiles = lat.tris
    n = len(tiles)
    if cells <= 0 or n % cells:
        return NO_FOLD, None
    layers = n // cells

    # BFS visitation order: every tile after the first has an already-placed neighbour to anchor on.
    order = [tiles[0]]
    seen = {tiles[0]}
    dq = collections.deque([tiles[0]])
    while dq:
        t = dq.popleft()
        for u in lat.adj[t]:
            if u not in seen:
                seen.add(u)
                order.append(u)
                dq.append(u)
    if len(order) != n:                      # a disconnected region has no single flat fold
        return NO_FOLD, None

    refl = {}
    for t in tiles:
        for u in lat.adj[t]:
            p, qq = lat.shared_edge(t, u)
            refl[(t, u)] = _reflection_matrix(p, qq)

    g = {order[0]: _IDENTITY}
    count = collections.Counter({_cellkey(_IDENTITY, lat, order[0]): 1})
    nodes = [0]
    witness = [None]

    def place(i):
        nodes[0] += 1
        if nodes[0] > node_cap:
            raise _Capped
        if i == n:
            if all(v == layers for v in count.values()):
                witness[0] = dict(g)
                return True
            return False
        u = order[i]
        anchor = next(t for t in lat.adj[u] if t in g)
        for gu in (g[anchor], _compose(g[anchor], refl[(anchor, u)])):
            # every ALREADY-placed neighbour must resolve as flat or folded across their shared crease
            if any(t in g and not (_close(gu, g[t]) or _close(gu, _compose(g[t], refl[(t, u)])))
                   for t in lat.adj[u]):
                continue
            key = _cellkey(gu, lat, u)
            if count[key] + 1 > layers:              # cell already full to K layers
                continue
            if key not in count and len(count) + 1 > cells:   # would open a 4th footprint cell
                continue
            g[u] = gu
            count[key] += 1
            if place(i + 1):
                return True
            del g[u]
            count[key] -= 1
            if not count[key]:
                del count[key]
        return False

    try:
        return (FOLDS, witness[0]) if place(1) else (NO_FOLD, None)
    except _Capped:
        return UNKNOWN, None


class _Capped(Exception):
    """Internal: the node cap was hit; surfaced as the UNKNOWN verdict."""


def witness_columns(lat, witness):
    """The footprint columns of a FOLDS witness: a list of tile-lists, one per cell, each the tiles
    that stack on that cell. I/O: (Lattice, dict) -> list[list[tid]]."""
    col = collections.defaultdict(list)
    for tid, g in witness.items():
        col[_cellkey(g, lat, tid)].append(tid)
    return [sorted(c) for c in col.values()]


def _has_point_pivot_column(lat, columns):
    """True iff some column stacks two tiles that are NOT edge-adjacent in the region — i.e. the fold
    brings them together by pivoting about a shared point, the exact move the engine's edge-chains
    cannot express. This is what makes such a fold real yet unfindable by the shipped search."""
    for col in columns:
        for i in range(len(col)):
            for j in range(i + 1, len(col)):
                if col[j] not in lat.adj[col[i]]:
                    return True
    return False


# --------------------------------------------------------------------------- diagnosis for humans
def diagnose(lat, engine_folds, cells=3, node_cap=_NODE_CAP):
    """Explain a drawn region's fold result. `engine_folds` is the shipped engine's record list for
    this region (possibly empty). Returns a dict {kind, message, certain, columns} where kind is a
    stable machine tag and message is one honest sentence. Never raises on a valid lattice.

      engine found folds        -> kind 'engine-folds'      (defer to the engine's own verdicts)
      engine empty, oracle NO   -> kind 'no-fold'           (definitive: cannot 3-stack at all)
      engine empty, oracle YES  -> kind 'fold-outside-model'(a real fold the search does not cover)
      engine empty, oracle ?    -> kind 'undetermined'      (search budget exhausted)
    """
    n = len(lat.tris)
    layers = n // cells if cells and n % cells == 0 else None

    if engine_folds:
        return {"kind": "engine-folds", "certain": True, "columns": None,
                "message": "%d fold(s) found by the standard search." % len(engine_folds)}

    verdict, witness = admits_stack(lat, cells, node_cap=node_cap)

    if verdict == NO_FOLD:
        return {"kind": "no-fold", "certain": True, "columns": None,
                "message": "no fold: this region cannot be flat-folded into a %d-stack at all "
                           "(no consistent fold exists, not merely none that this program searches)."
                           % cells}

    if verdict == UNKNOWN:
        return {"kind": "undetermined", "certain": False, "columns": None,
                "message": "no fold found by the standard search; a full flat-fold check did not "
                           "finish within budget, so whether some other fold exists is undetermined."}

    columns = witness_columns(lat, witness)
    point_pivot = _has_point_pivot_column(lat, columns)
    # K <= 2 layers is always physically realizable (two layers admit a non-crossing order); a
    # deeper stack has a real fold MAP here but its layer ordering is not separately checked.
    certain = layers is not None and layers <= 2
    how = (" It folds about a shared point — two tiles that only touch at a corner end up stacked, "
           "which the edge-chain search cannot express." if point_pivot else
           " It is outside the family of folds this program enumerates.")
    tail = ("" if certain else " (The fold map exists; a non-crossing layer order for %d layers is "
            "not separately verified.)" % layers)
    return {"kind": "fold-outside-model", "certain": certain, "columns": columns,
            "message": "a genuine %d-stack fold of this shape exists, but the standard search does "
                       "not find it.%s%s" % (cells, how, tail)}


# --------------------------------------------------------------------------- side-match guarantee
def _edge_lengths(pts):
    """Sorted edge-length multiset of a polygon given as Cartesian vertices (boundary order)."""
    m = len(pts)
    return tuple(sorted(round(((pts[i][0] - pts[(i + 1) % m][0]) ** 2
                               + (pts[i][1] - pts[(i + 1) % m][1]) ** 2) ** 0.5, 6) for i in range(m)))


def side_match_ok(lat, rec):
    """True iff every tile of every chain in a shipped 1+1+1 record `rec` folds onto its hub cell as
    an EXACT congruent copy — same vertex set AND same edge-length multiset. This is the "no
    mismatched sides get glued" property, verified directly on the engine's own fold rather than
    trusted from the closure gate. Reuses only lattice.reflect via a local chain fold, so it is an
    INDEPENDENT check of foldclose, not a call back into it."""
    chains = [[tuple(t) for t in c] for c in rec["chains"]]
    for w in chains:
        hub_key = _cellkey(_IDENTITY, lat, w[0])
        hub_len = _edge_lengths(lat.vertices_cart(w[0]))
        g = _IDENTITY
        for j in range(len(w)):
            if j:                                    # compose the crease reflection walking outward
                p, qq = lat.shared_edge(w[j - 1], w[j])
                g = _compose(g, _reflection_matrix(p, qq))
            folded = [(_apply(g, v)) for v in lat.vertices_cart(w[j])]
            if _cellkey(g, lat, w[j]) != hub_key or _edge_lengths(folded) != hub_len:
                return False
    return True


def _apply(g, pt):
    a, b, c, d, e, f = g
    return (a * pt[0] + b * pt[1] + e, c * pt[0] + d * pt[1] + f)
