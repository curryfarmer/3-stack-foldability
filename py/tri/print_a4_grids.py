"""print_a4_grids.py — blank, scale-accurate A4 tessellation sheets for physical cutting.

One PDF per tiling (equilateral, right 45-45-90, scalene 30-60-90, hexagon). Every tile is scaled
so all four shapes have the SAME AREA (~the area of an equilateral triangle at --edge mm), so
cutting effort is even across shapes. The page IS A4 (210x297 mm), so printing at "Actual size /
100%" (NOT "fit to page") reproduces the exact dimensions on paper. No fills, labels, shading, or
fold marks — literally just the grid; you isolate the tiles you want by hand.

Reuses the shared lattice interface (lat.vertices_cart) and the per-shape grid factories from
trilattice / righttri / scalene / hexlattice. No existing code is touched.

  python py/tri/print_a4_grids.py [--edge 35] [--margin 8]
                                  [--shapes equilateral right scalene hex] [--out report/grids_a4]
"""
import argparse
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402
from matplotlib.patches import Polygon                       # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages         # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))           # py/tri
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, ".."))                # py  (for lattice.base)
REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))          # repo root

import trilattice                                            # noqa: E402
import righttri                                              # noqa: E402
import scalene                                               # noqa: E402
import hexlattice                                            # noqa: E402
from trilattice import TriLattice                            # noqa: E402
from righttri import RightTriLattice                         # noqa: E402
from scalene import ScaleneLattice                           # noqa: E402
from hexlattice import HexLattice                            # noqa: E402

A4_W, A4_H = 210.0, 297.0            # mm, portrait
H = math.sqrt(3.0) / 2.0            # equilateral row height (abstract units)


# ------------------------------------------------------------------ geometry helpers
def shoelace(pts):
    """Polygon area from ordered (x, y) vertices."""
    a = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def edge_lengths(pts):
    """Consecutive-vertex side lengths (closed polygon)."""
    n = len(pts)
    return [math.dist(pts[i], pts[(i + 1) % n]) for i in range(n)]


# ------------------------------------------------------------------ per-shape builders
# Each builder returns a Lattice covering at least a `Ux` x `Uy` unit rectangle (abstract units),
# generously over-sized because the sheared/axial grids overhang a rectangle; clipping trims it.
def build_equilateral(Ux, Uy):
    N = math.ceil(Uy / H) + 2
    M = math.ceil(Ux + N / 2.0) + 2                      # cover width even after the N/2 shear
    return TriLattice(cells=trilattice.parallelogram_cells(M, N))


def build_right(Ux, Uy):
    M = math.ceil(Ux) + 2
    N = math.ceil(Uy) + 2
    return RightTriLattice(cells=righttri.solid_block(M, N))


def build_scalene(Ux, Uy):
    N = math.ceil(Uy / H) + 2
    M = math.ceil(Ux + N / 2.0) + 2
    faces = trilattice.parallelogram_cells(M, N)
    return ScaleneLattice(cells=scalene.subdivide(faces))


def build_hex(Ux, Uy):
    M = math.ceil(Ux / 1.5) + 4                          # x-extent ~ 1.5*M
    N = math.ceil(Uy / hexlattice.SQRT3 + M / 2.0) + 4   # y-extent ~ sqrt3*(N + M/2)
    return HexLattice(cells=hexlattice.hex_rect(M, N))


SHAPES = {
    "equilateral": dict(build=build_equilateral, out="equilateral_grid_a4.pdf",
                        title="Equilateral triangles"),
    "right":       dict(build=build_right,       out="right45_grid_a4.pdf",
                        title="Right triangles (45-45-90)"),
    "scalene":     dict(build=build_scalene,     out="scalene_grid_a4.pdf",
                        title="Scalene triangles (30-60-90)"),
    "hex":         dict(build=build_hex,         out="hex_grid_a4.pdf",
                        title="Hexagons"),
}

# Scalene tiles are the awkward slivers, so by default they get a smaller edge target than the
# other three (this factor times --edge); override with --scalene-edge for an explicit mm value.
SCALENE_EDGE_FACTOR = 0.5


# ------------------------------------------------------------------ scale / place / clip
def unit_scale(build, target_area):
    """mm-per-abstract-unit so that one tile's area == target_area (equal-area normalization)."""
    lat = build(2.0, 2.0)                                # tiny sample grid
    a0 = shoelace(lat.vertices_cart(lat.tiles[0]))       # one tile's abstract area
    return math.sqrt(target_area / a0)


def scaled_polys(lat, scale):
    return {t: [(x * scale, y * scale) for (x, y) in lat.vertices_cart(t)] for t in lat.tiles}


def place_and_fill(polys, margin):
    """Shift the block so its bbox centre sits at the page centre, then keep every tile that even
    touches the printable rectangle. Interior tiles stay whole; boundary tiles overhang and get
    trimmed to the page edge by the clip in make_figure — so the rectangle fills completely with no
    internal whitespace (only the intended outer margin remains)."""
    pts = [p for poly in polys.values() for p in poly]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    dx = A4_W / 2.0 - (min(xs) + max(xs)) / 2.0
    dy = A4_H / 2.0 - (min(ys) + max(ys)) / 2.0
    lo_x, hi_x = margin, A4_W - margin
    lo_y, hi_y = margin, A4_H - margin
    kept = {}
    for t, poly in polys.items():
        shifted = [(x + dx, y + dy) for (x, y) in poly]
        bx = [p[0] for p in shifted]
        by = [p[1] for p in shifted]
        if max(bx) >= lo_x and min(bx) <= hi_x and max(by) >= lo_y and min(by) <= hi_y:
            kept[t] = shifted                        # bbox overlaps the printable rect -> keep
    return kept


# ------------------------------------------------------------------ render
def make_figure(kept, margin, lw=0.5):
    """A4 page whose data coordinates ARE millimetres (aspect equal, axes fill the page). Tiles are
    clipped to the printable rectangle so the boundary ring is trimmed flush to the page edge."""
    from matplotlib.patches import Rectangle
    fig = plt.figure(figsize=(A4_W / 25.4, A4_H / 25.4))     # A4 in inches
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, A4_W)
    ax.set_ylim(0, A4_H)
    ax.set_aspect("equal")
    ax.axis("off")
    clip = Rectangle((margin, margin), A4_W - 2 * margin, A4_H - 2 * margin,
                     transform=ax.transData, facecolor="none", edgecolor="none")
    ax.add_patch(clip)
    for poly in kept.values():
        patch = Polygon(poly, closed=True, facecolor="none", edgecolor="black",
                        lw=lw, joinstyle="miter")
        patch.set_clip_path(clip)
        ax.add_patch(patch)
    return fig


def build_sheet(name, edge_mm, margin):
    """Returns (fig, stats) for one shape at the given equal-area target."""
    spec = SHAPES[name]
    target_area = (math.sqrt(3.0) / 4.0) * edge_mm ** 2      # equilateral-at-edge area, in mm^2
    scale = unit_scale(spec["build"], target_area)
    # over-generate to cover the full A4 page (not just printable) before centring+clipping
    lat = spec["build"](A4_W / scale, A4_H / scale)
    kept = place_and_fill(scaled_polys(lat, scale), margin)
    # report a fully-interior tile so the printed dims describe a real whole (cuttable) tile
    lo_x, hi_x, lo_y, hi_y = margin, A4_W - margin, margin, A4_H - margin
    inside = [p for p in kept.values()
              if all(lo_x <= x <= hi_x and lo_y <= y <= hi_y for (x, y) in p)]
    sample = (inside or list(kept.values()))[0]
    stats = dict(scale=scale, count=len(kept),
                 area=shoelace(sample), sides=sorted(edge_lengths(sample)))
    return make_figure(kept, margin), stats


def main():
    ap = argparse.ArgumentParser(description="A4 tessellation grids for physical cutting.")
    ap.add_argument("--edge", type=float, default=35.0,
                    help="equilateral-equivalent edge in mm; sets the equal-area target (default 35)")
    ap.add_argument("--scalene-edge", type=float, default=None,
                    help="explicit equilateral-equivalent edge (mm) for scalene only; default is "
                         "%.2f x --edge (scalene tiles run smaller than the other three)"
                         % SCALENE_EDGE_FACTOR)
    ap.add_argument("--margin", type=float, default=8.0, help="page margin in mm (default 8)")
    ap.add_argument("--shapes", nargs="+", default=list(SHAPES),
                    choices=list(SHAPES), help="which tilings to render (default: all four)")
    ap.add_argument("--out", default="report/grids_a4",
                    help="output dir (relative paths resolve against the repo root)")
    args = ap.parse_args()

    out_dir = args.out if os.path.isabs(args.out) else os.path.join(REPO_ROOT, args.out)
    os.makedirs(out_dir, exist_ok=True)

    combined = os.path.join(out_dir, "all_grids_a4.pdf")
    print("A4 tessellation grids  (equal-area, edge=%.1f mm target -> %.0f mm^2/tile)"
          % (args.edge, (math.sqrt(3.0) / 4.0) * args.edge ** 2))
    scalene_edge = args.scalene_edge if args.scalene_edge is not None else args.edge * SCALENE_EDGE_FACTOR
    with PdfPages(combined) as pdf:
        for name in args.shapes:
            edge_mm = scalene_edge if name == "scalene" else args.edge
            fig, st = build_sheet(name, edge_mm, args.margin)
            path = os.path.join(out_dir, SHAPES[name]["out"])
            fig.savefig(path)
            pdf.savefig(fig)
            plt.close(fig)
            sides = ", ".join("%.1f" % s for s in st["sides"])
            print("  %-11s %4d tiles | edge %.1f | area %.0f mm^2 | sides [%s] mm -> %s"
                  % (name, st["count"], edge_mm, st["area"], sides, os.path.basename(path)))
    print("combined: %s" % combined)


if __name__ == "__main__":
    main()
