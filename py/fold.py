"""fold.py — pure fold geometry, port of fold.js (no DOM, no I/O).

A placement is a dict:
  { cells: [(x,y), ...], parityH, parityV, foldArrow,
    creaseAxis, creaseAt, parentBounds, transformChain }
Cells are (x, y) integer tuples. Screen coords: +y is down (matches the JS tool).
"""


def bounds(cells):
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return {"xMin": min(xs), "xMax": max(xs), "yMin": min(ys), "yMax": max(ys)}


def reflect_scalar(v, c_boundary):
    # Mirror integer cell coord across continuous boundary: cell center x+0.5 mirrored
    # about c_boundary -> integer cell 2*c_boundary - 1 - v.
    return 2 * c_boundary - 1 - v


def reflect_cells(cells, axis, c_boundary):
    if axis == "h":
        return [(reflect_scalar(x, c_boundary), y) for (x, y) in cells]
    return [(x, reflect_scalar(y, c_boundary)) for (x, y) in cells]


# Vector model: {x, y, edge: 'T'|'B'|'L'|'R', sign: +1|-1}.
EDGE_FLIP_H = {"T": "T", "B": "B", "L": "R", "R": "L"}
EDGE_FLIP_V = {"T": "B", "B": "T", "L": "L", "R": "R"}


def reflect_vector(vec, axis, c_boundary):
    if axis == "h":
        return {
            "x": reflect_scalar(vec["x"], c_boundary),
            "y": vec["y"],
            "edge": EDGE_FLIP_H[vec["edge"]],
            "sign": -vec["sign"] if vec["edge"] in ("T", "B") else vec["sign"],
        }
    return {
        "x": vec["x"],
        "y": reflect_scalar(vec["y"], c_boundary),
        "edge": EDGE_FLIP_V[vec["edge"]],
        "sign": -vec["sign"] if vec["edge"] in ("L", "R") else vec["sign"],
    }


def fold_spec(direction, b):
    if direction == "R":
        return {"axis": "h", "cBoundary": b["xMax"] + 1, "arrow": "R"}
    if direction == "L":
        return {"axis": "h", "cBoundary": b["xMin"], "arrow": "L"}
    if direction == "D":
        return {"axis": "v", "cBoundary": b["yMax"] + 1, "arrow": "D"}
    if direction == "U":
        return {"axis": "v", "cBoundary": b["yMin"], "arrow": "U"}
    raise ValueError(direction)


def in_bounds(cells, m, n):
    return all(0 <= x < m and 0 <= y < n for (x, y) in cells)


def initial_placement(base_cells):
    return {
        "cells": [(x, y) for (x, y) in base_cells],
        "parityH": 0,
        "parityV": 0,
        "foldArrow": None,
        "creaseAxis": None,
        "creaseAt": None,
        "parentBounds": None,
        "transformChain": [],
    }


def make_fold(active, direction, m, n):
    """Fold `active` in `direction`; return new placement or None if it leaves the grid."""
    b = bounds(active["cells"])
    spec = fold_spec(direction, b)
    new_cells = reflect_cells(active["cells"], spec["axis"], spec["cBoundary"])
    if not in_bounds(new_cells, m, n):
        return None
    return {
        "cells": new_cells,
        "parityH": active["parityH"] ^ (1 if spec["axis"] == "h" else 0),
        "parityV": active["parityV"] ^ (1 if spec["axis"] == "v" else 0),
        "foldArrow": spec["arrow"],
        "creaseAxis": spec["axis"],
        "creaseAt": spec["cBoundary"],
        "parentBounds": b,
        "transformChain": active["transformChain"] + [{"axis": spec["axis"], "cBoundary": spec["cBoundary"]}],
    }


def project_vector(base_vec, chain):
    """Apply a chain of reflections (in order) to a base vector, returning its image."""
    v = dict(base_vec)
    for step in chain:
        v = reflect_vector(v, step["axis"], step["cBoundary"])
    return v


# --- Orientation-aware vector reflection (faithful port of twostack.py) ---
# Seed the crease SHARED by two adjacent chains as one world segment, reflect each side an
# equal number of times to its far end, and require the two images to COINCIDE as oriented grid
# segments (not as (edge,sign) labels — the B edge of cell (a,b) and the T edge of (a,b+1) are
# the same grid line). PASS iff every shared crease coincides. 2+1: the 2-chain strand cell
# adjacent to the 1-chain (one pair). 1+1+1: each footprint crease (the pairwise side-sharing).

def _hub_seed(P, Q):
    """Edge labels on cells P, Q naming their SHARED crease, as the same world segment.
    Returns (edge_on_P, edge_on_Q); sign is +1 (tangent +x for a horizontal crease, +y vertical)."""
    (px, py), (qx, qy) = P, Q
    if px == qx:                       # vertical adjacency -> horizontal crease, tangent +x
        return ("B", "T") if py < qy else ("T", "B")
    return ("R", "L") if px < qx else ("L", "R")   # horizontal adjacency -> vertical crease, +y


def _seg(v):
    """Resolve a director {x,y,edge,sign} to an oriented grid segment: (endpoints, direction)."""
    x, y, e, s = v["x"], v["y"], v["edge"], v["sign"]
    if e == "T":
        pts, d = ((x, y), (x + 1, y)), (s, 0)
    elif e == "B":
        pts, d = ((x, y + 1), (x + 1, y + 1)), (s, 0)
    elif e == "L":
        pts, d = ((x, y), (x, y + 1)), (0, s)
    else:  # R
        pts, d = ((x + 1, y), (x + 1, y + 1)), (0, s)
    return (frozenset(pts), d)


def _shared_crease_pairs(chains):
    """(i, j, Pi, Pj) for each pair of chains with adjacent (manhattan-1) base cells.
    2+1 -> one pair (2-chain strand cell adjacent to the 1-chain); 1+1+1 -> the footprint creases."""
    out = []
    for i in range(len(chains)):
        for j in range(i + 1, len(chains)):
            hit = None
            for a in chains[i]["baseCells"]:
                for b in chains[j]["baseCells"]:
                    if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1:
                        hit = (tuple(a), tuple(b))
                        break
                if hit:
                    break
            if hit:
                out.append((i, j, hit[0], hit[1]))
    return out


def reflection_verdict(chains):
    """Orientation-aware vector reflection over every shared crease.
    Returns {'pass': bool, 'pairs': [{i,j,Pi,Pj,imgI,imgJ,pass}]}."""
    pairs = []
    ok = True
    for (i, j, Pi, Pj) in _shared_crease_pairs(chains):
        eI, eJ = _hub_seed(Pi, Pj)
        a = project_vector({"x": Pi[0], "y": Pi[1], "edge": eI, "sign": 1},
                           chains[i]["placements"][-1]["transformChain"])
        b = project_vector({"x": Pj[0], "y": Pj[1], "edge": eJ, "sign": 1},
                           chains[j]["placements"][-1]["transformChain"])
        coince = (_seg(a) == _seg(b))
        pairs.append({"i": i, "j": j, "Pi": Pi, "Pj": Pj, "imgI": a, "imgJ": b, "pass": coince})
        if not coince:
            ok = False
    return {"pass": ok, "pairs": pairs}
