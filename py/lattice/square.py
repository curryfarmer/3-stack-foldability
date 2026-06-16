"""square.py — SquareLattice: the square grid as ONE lattice subclass.

Two faces, both square-specific in the same way the triangle lattices are triangle-specific:

  * GEOMETRY (from lattice.base.Lattice): each cell (x, y) is a unit-square tile with corners
    (x,y),(x+1,y),(x+1,y+1),(x,y+1); centroid (x+0.5, y+0.5); sigma the checkerboard (-1)^(x+y);
    orthogonal dual adjacency; the shared crease is the unit boundary segment; reflect_across_edge
    goes through the single lattice.reflect.reflect_point primitive. This face powers the
    per-lattice unit tests and makes "square" a peer of the triangle lattices.

  * SEARCH STRATEGY (the square-symmetry-specific pieces the generic walk cannot absorb):
    the integer cell-reflection fast-path (reflect_scalar/reflect_cells — proven equal to
    reflect_point on axis creases), the L/R/U/D fold directions + fold_spec, the nH/nV parity
    rule, the Rect/L exit-footprint classifier, and the D4 canonical dedup. These are pure
    functions of their explicit arguments, so they live here as static methods / class constants:
    a named home on the square lattice instead of free-floating module globals, with byte-identical
    bodies (1:1 with the former fold.py / search.py logic).
"""
import json

from lattice.base import Lattice


class SquareLattice(Lattice):
    # ---- geometry (base hooks) ----
    def __init__(self, m, n):
        self.m, self.n = m, n
        super().__init__([(x, y) for y in range(n) for x in range(m)])

    def _tile_vertices(self, cell):
        x, y = cell
        return [(x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1)]

    def _vkey_to_cart(self, key):
        return (key[0], key[1])          # integer corners are already Cartesian

    def _tile_sigma(self, cell):
        x, y = cell
        return 1 if (x + y) % 2 == 0 else -1

    # ---- square search strategy (relocated verbatim; pure of lattice state) ----

    # Fold directions (the four cardinal folds).
    FOLD_DIRECTIONS = ("L", "R", "U", "D")

    @staticmethod
    def fold_directions():
        return SquareLattice.FOLD_DIRECTIONS

    # Integer cell reflection across an axis-aligned crease (the exact fast-path; equals
    # reflect_point across the same line — see test_reflect_scalar_equals_reflect_point).
    @staticmethod
    def reflect_scalar(v, c_boundary):
        # Mirror integer cell coord across continuous boundary: cell center x+0.5 mirrored
        # about c_boundary -> integer cell 2*c_boundary - 1 - v.
        return 2 * c_boundary - 1 - v

    @staticmethod
    def reflect_cells(cells, axis, c_boundary):
        if axis == "h":
            return [(SquareLattice.reflect_scalar(x, c_boundary), y) for (x, y) in cells]
        return [(x, SquareLattice.reflect_scalar(y, c_boundary)) for (x, y) in cells]

    @staticmethod
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

    # nH/nV parity rule (the A/B crease parallel-fold count must be even).
    @staticmethod
    def parallel_fold_axis(chains):
        """2+1 only: 'H' => require nH even, 'V' => require nV even. Else None (legacy)."""
        if len(chains) != 2:
            return None
        A, B = chains[0]["baseCells"], chains[1]["baseCells"]
        for a in A:
            for b in B:
                if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1:
                    return "H" if a[0] != b[0] else "V"
        return None

    @staticmethod
    def parity_check(chains):
        axis = SquareLattice.parallel_fold_axis(chains)
        for c in chains:
            nH = sum(1 for a in c["foldArrows"] if a in ("L", "R"))
            nV = len(c["foldArrows"]) - nH
            c["nH"], c["nV"] = nH, nV
            if axis == "H":      # vertical A/B crease: parallel folds = nH must be even
                if nH % 2 != 0:
                    return False
            elif axis == "V":    # horizontal A/B crease: parallel folds = nV must be even
                if nV % 2 != 0:
                    return False
            else:
                if nH % 2 != 0 or nV % 2 != 1:
                    return False
        return True

    # Exit-footprint congruence classifier (Rect / L by the 3 end cells' bounding box).
    @staticmethod
    def exit_shape(cells):
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        dx, dy = max(xs) - min(xs), max(ys) - min(ys)
        if (dx == 2 and dy == 0) or (dx == 0 and dy == 2):
            return "Rect"
        if dx == 1 and dy == 1:
            return "L"
        return None

    # L footprint templates: corner at (0,0), arms; 4 rotations of D4 about the corner.
    L_BASE = [
        [(0, 0), (1, 0), (0, 1)],     # rot 0
        [(0, 0), (0, 1), (-1, 0)],    # rot 1 (90 CW)
        [(0, 0), (-1, 0), (0, -1)],   # rot 2 (180)
        [(0, 0), (0, -1), (1, 0)],    # rot 3 (270 CW)
    ]

    # D4 canonical dedup (the grid symmetry group; the golden orbit counts are D4-orbit counts).
    @staticmethod
    def apply_transform(t, x, y, m, n):
        X, Y = x, y
        if t["flip"]:
            X = m - 1 - X
        rot = t["rot"]
        if rot == 0:
            return (X, Y)
        if rot == 1:
            return (Y, m - 1 - X)
        if rot == 2:
            return (m - 1 - X, n - 1 - Y)
        return (n - 1 - Y, X)

    @staticmethod
    def transform_arrow(t, d):
        if t["flip"]:
            d = {"L": "R", "R": "L", "U": "U", "D": "D"}[d]
        for _ in range(t["rot"]):
            d = {"L": "U", "U": "R", "R": "D", "D": "L"}[d]
        return d

    @staticmethod
    def canonical_hash(footprint, chains, m, n):
        best = None
        for rot in range(4):
            for flip in range(2):
                t = {"rot": rot, "flip": flip}
                fp = sorted([list(SquareLattice.apply_transform(t, c[0], c[1], m, n))
                             for c in footprint["cells"]])
                chain_sigs = []
                for c in chains:
                    base = sorted([list(SquareLattice.apply_transform(t, b[0], b[1], m, n))
                                   for b in c["baseCells"]])
                    arrows = [SquareLattice.transform_arrow(t, a) for a in c["foldArrows"]]
                    chain_sigs.append({"kind": c["kind"], "base": base, "arrows": arrows})
                chain_sigs.sort(key=lambda s: (s["kind"], json.dumps(s["base"])))
                sig = json.dumps({"fp": fp, "chains": chain_sigs}, separators=(",", ":"))
                if best is None or sig < best:
                    best = sig
        return best
