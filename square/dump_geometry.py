#!/usr/bin/env python3
"""dump_geometry.py — emit the SQUARE tiling's drawable geometry as fold-geometry/1 JSON.

The desktop GUI (gui/) never re-implements the tilings' inverse coordinate maps. Instead each
engine DUMPS its geometry -- {tile id -> boundary polygon, dual adjacency} -- and the GUI renders
those polygons and hit-tests clicks against them, one uniform code path for all five geometries.
This is the square half of that dump; triangle/tri/dump_geometry.py is the triangle half.

  python square/dump_geometry.py --m 3 --n 3     # -> fold-geometry/1 on stdout

The `ids` are the SquareLattice's native (x, y) tile ids -- exactly the ids a fold-grid/1 `cells`
list carries (docs/schema/fold-grid-1.md), so a drawn subset of `ids` round-trips straight into
scripts/fold_grid.py. Native ids are tuples, which cannot be JSON object keys, so `adj` is emitted
as i<j index pairs into the sorted `ids` list (see docs/schema/fold-geometry-1.md).

Reads the lattice only via the shared Lattice.vertices_cart / .adj surface -- it edits nothing under
engine|lattice|twist, so it flips no oracle fingerprint (square/dump_geometry.py is not one of the
_SEARCH_SOURCES). Emits raw +y-down square coords; the GUI records orientation, not this dump.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # square/ on path
import _bootstrap  # noqa: E402,F401  (puts square/{engine,twist,render} on sys.path)

from lattice import SquareLattice  # noqa: E402

SCHEMA = "fold-geometry/1"
_NDP = 9  # round Cartesian coords so the committed golden never flakes on float noise


def emit_geometry(lat, tiling, bounds):
    """Pure builder: a Lattice + its label/bounds -> a fold-geometry/1 dict. Uses only the shared
    Lattice surface (tiles / vertices_cart / adj), so it is byte-identical in the triangle dump.

    Deterministic: `ids` sorted, `adj` is each undirected edge once as a canonical (i<j) index pair
    into `ids` -- so the golden compare is stable. I/O: (Lattice, str, dict) -> dict."""
    ids = sorted(lat.tiles)
    idx = {tid: k for k, tid in enumerate(ids)}
    polys = [[[round(x, _NDP), round(y, _NDP)] for (x, y) in lat.vertices_cart(t)] for t in ids]
    pairs = sorted({(min(idx[a], idx[b]), max(idx[a], idx[b]))
                    for a in ids for b in lat.adj[a]})
    return {
        "schema": SCHEMA,
        "tiling": tiling,
        "bounds": bounds,
        "ids": [list(t) for t in ids],
        "polys": polys,
        "adj": [list(p) for p in pairs],
    }


def build(m, n):
    """(m, n) -> the fold-geometry/1 dict for a full m x n square block."""
    return emit_geometry(SquareLattice(m, n), "square", {"m": m, "n": n})


def main(argv=None):
    ap = argparse.ArgumentParser(description="dump the square tiling geometry as fold-geometry/1 JSON")
    ap.add_argument("--m", type=int, required=True, help="columns of the ambient block")
    ap.add_argument("--n", type=int, required=True, help="rows of the ambient block")
    args = ap.parse_args(argv)
    print(json.dumps(build(args.m, args.n)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
