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
from functools import lru_cache

from lattice.base import Lattice


def sheet_connected(cells):
    """True iff `cells` is a single 4-connected polyomino (empty -> False). I/O: (iterable of (x,y)) -> bool.

    The one flood-fill of record for square-grid 4-connectivity: the 3-stack engine (search.run's
    drawn-sheet guard), the 2-stack engine (twostack._validate_sheet), and exit_congruent all call
    it. It lives on the shared lattice layer because search.py and twostack.py must not import each
    other (twostack must stay clear of the engine search closure)."""
    cs = set(cells)
    if not cs:
        return False
    seen = {next(iter(cs))}
    stack = list(seen)
    while stack:
        cx, cy = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (cx + dx, cy + dy)
            if nb in cs and nb not in seen:
                seen.add(nb)
                stack.append(nb)
    return len(seen) == len(cs)


class SquareLattice(Lattice):
    # ---- geometry (base hooks) ----
    def __init__(self, m, n, cells=None):
        # cells=None synthesizes the full m x n rectangle (byte-identical to the historic behaviour);
        # pass an explicit cell list for an arbitrary connected polyomino (mirrors TriLattice). m, n
        # are still stored as the bounding box either way -- reflection math + the renderer need them.
        self.m, self.n = m, n
        if cells is None:
            cells = [(x, y) for y in range(n) for x in range(m)]
        super().__init__(cells)

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
    def set_fold_counts(chains):
        """Annotate every chain with nH (L/R folds) and nV (U/D folds). Unconditional: unlike
        parity_check this never returns early, so all chains carry nH/nV even when a gate fails —
        required by the store-all path, which emits a solution for every covered candidate."""
        for c in chains:
            nH = sum(1 for a in c["foldArrows"] if a in ("L", "R"))
            c["nH"], c["nV"] = nH, len(c["foldArrows"]) - nH

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

    @staticmethod
    def vector_parity_check(chains):
        """Legacy (orientation-UNaware) vector parity: every chain needs nH even AND nV odd.

        This is the fixed rule parity_check falls back to when there is no 2+1 A/B adjacency
        (the 1+1+1 case, square.py parity_check `else` branch). Exposed as its own verdict
        column so the orientation-aware `parity` and this legacy `vectorParity` can be compared
        side-by-side. Self-contained (recomputes counts) so it is valid before set_fold_counts."""
        for c in chains:
            arrows = c["foldArrows"]
            nH = sum(1 for a in arrows if a in ("L", "R"))
            nV = len(arrows) - nH
            if nH % 2 != 0 or nV % 2 != 1:
                return False
        return True

    # Exit-footprint bbox PRE-FILTER (Rect / L by the N end cells' bounding box). This only screens
    # by bounding box, which is a bijection with the true shape at panels==3 but NOT at panels>=4 —
    # an S-tetromino and some disconnected sets share the L bbox. Callers must confirm real congruence
    # via exit_congruent; exit_shape alone is a cheap reject only. I/O: (cells, panels) -> 'L'|'Rect'|None.
    @staticmethod
    def exit_shape(cells, panels=3):
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        dx, dy = max(xs) - min(xs), max(ys) - min(ys)
        a, b = SquareLattice._l_arm_split(panels)
        if (dx == panels - 1 and dy == 0) or (dx == 0 and dy == panels - 1):
            return "Rect"
        if (dx == a and dy == b) or (dx == b and dy == a):
            return "L"
        return None

    @staticmethod
    def _canonical_polyomino(cells):
        """Translation + D4 invariant fingerprint of a cell set: the lexicographic-minimum,
        origin-normalized, sorted tuple over the 8 D4 orientations. Two sets are congruent iff their
        fingerprints are equal. I/O: (iterable of (x,y)) -> tuple[(x,y), ...]."""
        best = None
        for flip in (False, True):
            pts = [(-x if flip else x, y) for (x, y) in cells]
            for _ in range(4):                       # 4 rotations (the 4th brings us back to identity)
                pts = [(-b, a) for (a, b) in pts]    # rotate 90 degrees about the origin
                mnx = min(p[0] for p in pts)
                mny = min(p[1] for p in pts)
                norm = tuple(sorted((p[0] - mnx, p[1] - mny) for p in pts))
                if best is None or norm < best:
                    best = norm
        return best

    @staticmethod
    def exit_congruent(cells, start_shape, panels):
        """True iff the exit cells are ONE 4-connected polyomino D4-congruent to the start template of
        `start_shape`. This is the exact test the bbox `exit_shape` only approximates for panels>=4,
        where the L bbox also admits non-congruent (S-tetromino) and disconnected cell sets.
        I/O: (cells, 'L'|'Rect', panels) -> bool."""
        if not sheet_connected(cells):
            return False
        template = (SquareLattice.l_template(panels)[0] if start_shape == "L"
                    else SquareLattice.rect_template(panels, "H"))
        return (SquareLattice._canonical_polyomino(cells)
                == SquareLattice._canonical_polyomino(template))

    @staticmethod
    def _l_arm_split(panels):
        """Two straight-arm lengths (a, b), split as evenly as possible, a+b = panels-1.
        panels=3 -> (1, 1) (the classic corner tromino: one arm cell each way)."""
        a = (panels - 1) // 2
        return a, (panels - 1) - a

    @staticmethod
    def l_template(panels):
        """4 rotations of a corner + two straight arms (lengths from _l_arm_split), corner at
        (0,0). panels=3 is the classic corner tromino: arms of length 1 each, one along +x,
        one along +y."""
        a, b = SquareLattice._l_arm_split(panels)
        base = [(0, 0)] + [(i, 0) for i in range(1, a + 1)] + [(0, j) for j in range(1, b + 1)]

        def rot90(cells):
            return [(-y, x) for (x, y) in cells]

        rots = [base]
        for _ in range(3):
            rots.append(rot90(rots[-1]))
        return rots

    @staticmethod
    def rect_template(panels, orient):
        """Straight line of `panels` cells from (0,0); orient 'H' along +x, 'V' along +y."""
        if orient == "H":
            return [(i, 0) for i in range(panels)]
        return [(0, i) for i in range(panels)]

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

    # NOTE: transform_arrow is INTENTIONALLY not replay-equivariant with apply_transform on odd
    # rotations (rot in {1,3}, square grids only): rotating a fold's cells by 90/270 deg and rotating
    # its arrows through here does NOT reproduce the same physical fold, so a hash is a dedup key, not
    # a replayable path (see test_physical_deciders.py:9-11). Making it equivariant would only churn
    # cosmetic arrow labels; canonical_hash CLASS COUNTS and gate verdicts are unaffected, because by
    # Burnside no 3-stack sheet-covering fold has 90-deg symmetry, so no orbit merges or splits.
    @staticmethod
    def transform_arrow(t, d):
        if t["flip"]:
            d = {"L": "R", "R": "L", "U": "U", "D": "D"}[d]
        for _ in range(t["rot"]):
            d = {"L": "U", "U": "R", "R": "D", "D": "L"}[d]
        return d

    @staticmethod
    @lru_cache(maxsize=None)
    def automorphisms(m, n, cells=None):
        """The subgroup of D4 that maps the sheet onto itself, as a tuple of transforms.

        Derived rather than special-cased: keep t iff t(S) == S over the sheet's own cell set.
        cells=None => the full m x n rectangle (the historic behaviour): square -> all 8 (D4),
        non-square -> the 4 with rot in {0, 2} (D2), because apply_transform's odd rotations land on
        the TRANSPOSED n x m sheet and so are not symmetries of this one. Pass an explicit frozenset
        for an arbitrary sheet: the SAME t(S)==S filter then yields the true Aut(S). This matters --
        minimizing canonical_hash over a D4 element that is NOT a symmetry of an arbitrary S would
        over-merge distinct folds and silently drop solutions. Matches twostack._canonical.
        Cached: canonical_hash calls this once per candidate (hundreds of thousands per search)."""
        if cells is None:
            cells = frozenset((x, y) for x in range(m) for y in range(n))
        keep = []
        for rot in range(4):
            for flip in range(2):
                t = {"rot": rot, "flip": flip}
                if frozenset(SquareLattice.apply_transform(t, x, y, m, n) for (x, y) in cells) == cells:
                    keep.append(t)
        return tuple(keep)

    @staticmethod
    def _hash_over(elements, footprint, chains, m, n):
        """Minimal fold signature over `elements` (a subset of D4). Shared body so canonical_hash
        and any caller needing a different group (e.g. the S3 migrator reconstructing the historic
        all-of-D4 hash) cannot drift apart."""
        best = None
        for t in elements:
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

    @staticmethod
    def canonical_hash(footprint, chains, m, n, sheet=None):
        """Dedup key: the minimal signature over the sheet's automorphism subgroup.

        sheet=None => the m x n rectangle's automorphisms (byte-identical historic behaviour). Pass an
        explicit frozenset of cells for an arbitrary sheet so the group is the true Aut(S), not the
        rectangle's -- otherwise dedup over-merges distinct folds and drops solutions (see automorphisms).

        Minimizing over all 8 of D4 (the historic behaviour) does NOT over-merge -- a 3-stack fold
        covers the whole m x n sheet, so a transposed image covers n x m and can never be a legal
        m x n candidate; for m != n, D4-merge and D2-merge coincide, and the orbit COUNTS are the
        same either way. What it does do is let the minimum be attained at a non-automorphism, so
        the representative describes a fold on the transposed sheet and can sit off-grid -- which
        breaks any consumer that reads this string back as geometry on m x n. Restricting to the
        automorphisms keeps the same classes and makes the representative on-grid by construction."""
        return SquareLattice._hash_over(
            SquareLattice.automorphisms(m, n, sheet), footprint, chains, m, n)
