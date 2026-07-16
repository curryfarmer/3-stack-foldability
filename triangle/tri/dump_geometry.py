#!/usr/bin/env python3
"""dump_geometry.py — emit a TRIANGLE tiling's drawable geometry as fold-geometry/1 JSON.

The triangle half of the GUI geometry dump (see square/dump_geometry.py for the full rationale).
One uniform --m/--n block spec across all four tilings; the ONE genuine branch is how (m, n) maps
to each constructor (scalene takes a `faces` list, hex takes `cells`), encoded in BUILDERS below.

  python triangle/tri/dump_geometry.py --tiling equilateral --m 3 --n 3
  python triangle/tri/dump_geometry.py --tiling righttri    --m 3 --n 3
  python triangle/tri/dump_geometry.py --tiling scalene     --m 3 --n 3
  python triangle/tri/dump_geometry.py --tiling hex         --m 3 --n 3

The `ids` are each tiling's native tile ids (equilateral/righttri (i,j,o); scalene (i,j,o,vid,oid);
hex axial (q,r)) -- exactly the ids a fold-grid/1 `cells` list carries, so a drawn subset round-trips
straight into scripts/fold_grid.py. `adj` is emitted as i<j index pairs into the sorted `ids` list
(native ids are tuples -> not JSON object keys). Emits raw +y-up triangle coords; the GUI records
orientation, not this dump.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # triangle/tri on path
import trilattice as TL   # noqa: E402  parallelogram_cells (equilateral faces; scalene subdivides these)
import righttri as RT     # noqa: E402
import scalene as SC      # noqa: E402
import hexlattice as HX   # noqa: E402  hex_rect (a solid axial block)

SCHEMA = "fold-geometry/1"
_NDP = 9  # round Cartesian coords so the committed golden never flakes on float noise

# (m, n) -> ambient Lattice, one entry per tiling. The uniform --m/--n fans out here (the one branch):
# eq/righttri take (M, N) directly; scalene needs a `faces` list; hex needs a `cells` axial block.
BUILDERS = {
    "equilateral": lambda m, n: TL.TriLattice(m, n),
    "righttri":    lambda m, n: RT.RightTriLattice(m, n),
    "scalene":     lambda m, n: SC.ScaleneLattice(faces=TL.parallelogram_cells(m, n)),
    "hex":         lambda m, n: HX.HexLattice(cells=HX.hex_rect(m, n)),
}


def emit_geometry(lat, tiling, bounds):
    """Pure builder: a Lattice + its label/bounds -> a fold-geometry/1 dict. Uses only the shared
    Lattice surface (tiles / vertices_cart / adj), byte-identical to the square dump's copy.

    Deterministic: `ids` sorted, `adj` is each undirected edge once as a canonical (i<j) index pair
    into `ids`. I/O: (Lattice, str, dict) -> dict."""
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


def build(tiling, m, n):
    """(tiling, m, n) -> the fold-geometry/1 dict for that tiling's m x n ambient block."""
    if tiling not in BUILDERS:
        raise ValueError("unknown tiling %r (expected one of %s)" % (tiling, sorted(BUILDERS)))
    return emit_geometry(BUILDERS[tiling](m, n), tiling, {"m": m, "n": n})


def main(argv=None):
    ap = argparse.ArgumentParser(description="dump a triangle tiling geometry as fold-geometry/1 JSON")
    ap.add_argument("--tiling", required=True, choices=sorted(BUILDERS),
                    help="which triangle tiling to dump")
    ap.add_argument("--m", type=int, required=True, help="columns of the ambient block")
    ap.add_argument("--n", type=int, required=True, help="rows of the ambient block")
    args = ap.parse_args(argv)
    print(json.dumps(build(args.tiling, args.m, args.n)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
