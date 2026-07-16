"""canvas.py — hit-test half of the drawing canvas (the FigureCanvasTkAgg render half is S9).

hit_test maps a click point to the index of the tile whose dumped polygon contains it -- ONE code
path for all five geometries, since it only ever sees the polygons the engine dumped (no tiling has
its inverse coordinate map re-implemented here). Works in the dump's native coordinate space; the S9
event handler converts screen coords to native (respecting gui.tilings.orientation) before calling.

Importing matplotlib.path is fine -- it pulls no pyplot and forces no backend; that is an S9 concern.
"""
from matplotlib.path import Path


def hit_test(point, polys):
    """Index of the first polygon in `polys` that contains `point`, else None. Tiles in a tiling are
    disjoint, so at most one contains an interior point (e.g. a tile centroid). I/O:
    ((x, y), list[list[[x, y]]]) -> int | None."""
    for k, poly in enumerate(polys):
        if Path(poly).contains_point(point):
            return k
    return None
