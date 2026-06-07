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
