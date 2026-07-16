"""fold.py — pure fold geometry, port of fold.js (no DOM, no I/O).

A placement is a dict:
  { cells: [(x,y), ...], parityH, parityV, foldArrow,
    creaseAxis, creaseAt, parentBounds, transformChain }
Cells are (x, y) integer tuples. Screen coords: +y is down (matches the JS tool).
"""
from lattice.reflect import reflect_point
from lattice.square import SquareLattice

# Square cell-reflection and fold-direction geometry now live on SquareLattice (the square is one
# lattice subclass). These module-level names are thin re-exports so callers — and tests that
# resolve Fold.reflect_scalar / Fold.reflect_cells / Fold.fold_spec by name — keep working.
reflect_scalar = SquareLattice.reflect_scalar
reflect_cells = SquareLattice.reflect_cells
fold_spec = SquareLattice.fold_spec


def bounds(cells):
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return {"xMin": min(xs), "xMax": max(xs), "yMin": min(ys), "yMax": max(ys)}


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


def make_fold(active, direction, m, n, sheet=None):
    """Fold `active` in `direction`; return new placement or None if it leaves the grid.

    sheet=None: reject a fold whose image leaves the m x n rectangle (historic behaviour). Pass a
    frozenset of the sheet's cells for an arbitrary polyomino: the image must land on cells of S
    (rejecting both out-of-bbox cells AND in-bbox holes)."""
    b = bounds(active["cells"])
    spec = fold_spec(direction, b)
    new_cells = reflect_cells(active["cells"], spec["axis"], spec["cBoundary"])
    if sheet is not None:
        if not all(c in sheet for c in new_cells):
            return None
    elif not in_bounds(new_cells, m, n):
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


# --- Orientation-aware crease reflection (single reflect_point primitive) ---
# Seed the crease SHARED by two adjacent chains as one world segment, reflect each side an
# equal number of times to its far end, and require the two images to COINCIDE as oriented grid
# segments (not as (edge,sign) labels — the B edge of cell (a,b) and the T edge of (a,b+1) are
# the same grid line). PASS iff every shared crease coincides. 2+1: the 2-chain strand cell
# adjacent to the 1-chain (one pair). 1+1+1: each footprint crease (the pairwise side-sharing).

def _crease_segment(P, Q):
    """Oriented Cartesian endpoints of the crease shared by adjacent base cells P, Q.
    Horizontal crease -> tangent +x; vertical crease -> tangent +y (the sign=+1 seed convention)."""
    (px, py), (qx, qy) = P, Q
    if px == qx:                       # vertical adjacency -> horizontal crease, tangent +x
        yc = max(py, qy)
        return ((px, yc), (px + 1, yc))
    xc = max(px, qx)                   # horizontal adjacency -> vertical crease, tangent +y
    return ((xc, py), (xc, py + 1))


def _axis_line(step):
    """Two points on the mirror line for one transformChain step (axis reflection at cBoundary)."""
    c = step["cBoundary"]
    if step["axis"] == "h":            # reflect x across the vertical line x = c
        return ((c, 0), (c, 1))
    return ((0, c), (1, c))            # reflect y across the horizontal line y = c


def _reflect_pt_through(p, chain):
    """Reflect point p across every step's crease line, in order (the single reflect_point)."""
    for step in chain:
        a, b = _axis_line(step)
        p = reflect_point(p, a, b)
    return p


def _reflect_cell_through(cell, chain):
    """Image of a base cell after the chain's folds (integer fast-path, == reflect_point on cells)."""
    cells = [cell]
    for step in chain:
        cells = reflect_cells(cells, step["axis"], step["cBoundary"])
    return cells[0]


def _seg_director(seg, cell):
    """Read back the {edge,sign} director an oriented crease segment makes on its reflected base
    `cell` — the exact label the old vector model carried, recovered from geometry. A horizontal
    segment is the cell's T edge (at y=cy) or B edge (y=cy+1); vertical is L (x=cx) or R (x=cx+1);
    sign is the segment's tangent direction (+x for T/B, +y for L/R)."""
    (x0, y0), (x1, y1) = seg
    cx, cy = cell
    if abs(y1 - y0) < abs(x1 - x0):                # horizontal segment -> T / B
        edge = "T" if round(y0) == cy else "B"
        sign = 1 if x1 > x0 else -1
    else:                                          # vertical segment -> L / R
        edge = "L" if round(x0) == cx else "R"
        sign = 1 if y1 > y0 else -1
    return {"edge": edge, "sign": sign}


def _seg_key(seg):
    """Hashable oriented-segment key (ordered endpoints), tolerant of float reflection dust."""
    (x0, y0), (x1, y1) = seg
    return (round(x0, 6), round(y0, 6), round(x1, 6), round(y1, 6))


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
    """Orientation-aware crease reflection over every shared crease, via the single reflect_point.

    Seed each shared crease as one oriented world segment; reflect it through each chain's fold
    transform chain; the fold is valid for that crease iff the two images COINCIDE as oriented
    segments (the B edge of cell (a,b) and the T edge of (a,b+1) are the same grid line, so the
    comparison is geometric, not by (edge,sign) label). finalVector (edge,sign) is read back off
    each image relative to its reflected base cell. Returns
    {'pass': bool, 'pairs': [{i,j,Pi,Pj,imgI,imgJ,pass}]}."""
    pairs = []
    ok = True
    for (i, j, Pi, Pj) in _shared_crease_pairs(chains):
        seed = _crease_segment(Pi, Pj)
        chain_i = chains[i]["placements"][-1]["transformChain"]
        chain_j = chains[j]["placements"][-1]["transformChain"]
        seg_i = (_reflect_pt_through(seed[0], chain_i), _reflect_pt_through(seed[1], chain_i))
        seg_j = (_reflect_pt_through(seed[0], chain_j), _reflect_pt_through(seed[1], chain_j))
        imgI = _seg_director(seg_i, _reflect_cell_through(Pi, chain_i))
        imgJ = _seg_director(seg_j, _reflect_cell_through(Pj, chain_j))
        coince = _seg_key(seg_i) == _seg_key(seg_j)
        pairs.append({"i": i, "j": j, "Pi": Pi, "Pj": Pj, "imgI": imgI, "imgJ": imgJ,
                      "segI": seg_i, "segJ": seg_j, "pass": coince})
        if not coince:
            ok = False
    return {"pass": ok, "pairs": pairs}
