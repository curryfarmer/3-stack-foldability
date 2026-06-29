"""experimental/common.py — shared geometry + twist primitives for the 4 candidate 2+1 engines.

Lifted verbatim (math-identical) from tests/analyze_twist_2plus1_compare.py so the experimental
engines reproduce the validated harness numbers. Nothing here mutates engine state; it only replays
chains through py/fold.py and sums doubled-turn angles around the closed 2-chain<->1-chain loop.

Each engine differs ONLY in how it turns the rigid 2-chain into the loop "body":
  no_decomp      -> full_centroid_path  (one domino centroid per placement; the 936 approach)
  jump_decomp    -> strand_path         (one kept-strand cell; short-side folds = 3-jumps; Model B)
  normal_decomp  -> filled_path         (decompose fully, route the twin holes; unit steps)
  partial_decomp -> model_a_path        (lead's variable-width; centroid at short-side 2-units)

The loop = body + reversed(path1), where path1 is the 1-chain strand. Foldable-onto-same-footprint
<=> Tw == 0. partial_decomp gets a 3-way class (flat/overhang/twisted) instead of pass/fail, because
its atan(1/2) seam residual is an OVERHANG signature (fold closes but lands offset, one end sticks
out), NOT a random twist.
"""
import os
import sys
from math import atan2, degrees, hypot, isclose

# ---- bootstrap: make `import common` work from engine subfolders, and `import fold` work ----
_HERE = os.path.dirname(os.path.abspath(__file__))           # .../experimental
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)                          # experimental/ so `import common` resolves here too
sys.path.insert(0, os.path.join(_ROOT, "py"))      # py/ for _bootstrap
import _bootstrap  # noqa: E402,F401  (fold -> engine/, + every py/ subfolder + repo + tests)
import fold  # noqa: E402


# ---------- replay + path builders ----------

def replay(base_cells, fold_arrows, m, n):
    base = [(c["x"], c["y"]) for c in base_cells]
    pl = fold.initial_placement(base)
    pls = [pl]
    for d in fold_arrows:
        pl = fold.make_fold(pl, d, m, n)
        if pl is None:
            raise ValueError("fold %s left grid" % d)
        pls.append(pl)
    return pls


def cc(cell):
    return (cell[0] + 0.5, cell[1] + 0.5)


def centroid(cells):
    k = len(cells)
    return (sum(c[0] + 0.5 for c in cells) / k, sum(c[1] + 0.5 for c in cells) / k)


def strand_path(pls, idx):
    return [cc(p["cells"][idx]) for p in pls]


def full_centroid_path(pls):
    return [centroid(p["cells"]) for p in pls]


def short_incident(pls, idx):
    """Placements that are an endpoint of a length-3 strand step (a short-side / along-axis fold)."""
    cells = [p["cells"][idx] for p in pls]
    s = set()
    for k in range(len(cells) - 1):
        a, b = cells[k], cells[k + 1]
        if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 3:
            s.add(k)
            s.add(k + 1)
    return s


def model_a_path(pls, idx, force_hub_1unit=False):
    """One point per placement: 1-unit (strand cell) by default, 2-unit (centroid) at short-incident
    placements. Returns (points, kinds) with kinds[k] in {'1','2'}."""
    short = short_incident(pls, idx)
    K = len(pls)
    pts, kinds = [], []
    for k, p in enumerate(pls):
        is2 = k in short and not (force_hub_1unit and k in (0, K - 1))
        if is2:
            pts.append(centroid(p["cells"]))
            kinds.append('2')
        else:
            pts.append(cc(p["cells"][idx]))
            kinds.append('1')
    return pts, kinds


def filled_path(pls, idx):
    cells = [p["cells"][idx] for p in pls]
    out = [cc(cells[0])]
    for k in range(len(cells) - 1):
        a, b = cells[k], cells[k + 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        if abs(dx) + abs(dy) == 3:                    # collinear midpoints on the 3-jump
            sx = (dx > 0) - (dx < 0)
            sy = (dy > 0) - (dy < 0)
            out.append(cc((a[0] + sx, a[1] + sy)))
            out.append(cc((a[0] + 2 * sx, a[1] + 2 * sy)))
        out.append(cc(b))
    return out


# ---------- turn / twist (float, artifact-visible) ----------

def loop_terms(pts):
    n = len(pts)
    terms = []
    for i in range(n):
        p1, p2, p3 = pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        v1 = (p2[0] - p1[0], p2[1] - p1[1])
        v2 = (p3[0] - p2[0], p3[1] - p2[1])
        ang = 0.0
        if hypot(*v1) > 1e-9 and hypot(*v2) > 1e-9:
            dot = v1[0] * v2[0] + v1[1] * v2[1]
            cross = v1[0] * v2[1] - v1[1] * v2[0]
            ang = degrees(atan2(cross, dot))
        terms.append(2 * ang)                          # doubled turn angle
    return terms


def tw_of(terms, sflip=False, gflip=False):
    t = 0.0
    for i, x in enumerate(terms):
        s = 1 if i % 2 else -1                          # odd -> +, even -> -  (== odd - even)
        if sflip:
            s = -s
        t += s * (-x if gflip else x)
    return round(t, 6)


def loop_tw(body, path1):
    return tw_of(loop_terms(body + list(reversed(path1))))


def frac_turns(terms):
    return sum(1 for t in terms if abs(t % 90) > 1e-6)


def is0(x):
    return abs(x) < 1e-6


def classify_step(p, q):
    dx, dy = abs(q[0] - p[0]), abs(q[1] - p[1])
    if dx + dy == 1:
        return "unit"
    if dx == 1 and dy == 1:
        return "DIAG"
    if (dx == 0 and dy == 2) or (dx == 2 and dy == 0):
        return "2JMP"
    return "far(%g,%g)" % (dx, dy)


def pick_canon_idx(pls2, path1):
    """Canonical jump-strand = the strand whose two hub seams are non-diagonal."""
    seams = {}
    for idx in (0, 1):
        sp = strand_path(pls2, idx)
        K = len(sp)
        loop = sp + list(reversed(path1))
        seams[idx] = (classify_step(loop[K - 1], loop[K]),
                      classify_step(loop[2 * K - 1], loop[0]))
    cands = [idx for idx in (0, 1) if "DIAG" not in seams[idx]]
    return (cands[0] if cands else 0), seams


# ---------- per-solution shared context ----------

def split_chains(sol):
    """Return (two_chain, one_chain) dicts from a cache solution record."""
    two = next(c for c in sol["chains"] if len(c["baseCells"]) == 2)
    one = next(c for c in sol["chains"] if len(c["baseCells"]) == 1)
    return two, one


def prepare(two, one, m, n):
    """Replay both chains and choose the canonical strand. All 4 engines share this."""
    pls2 = replay(two["baseCells"], two["foldArrows"], m, n)
    pls1 = replay(one["baseCells"], one["foldArrows"], m, n)
    path1 = strand_path(pls1, 0)
    idx, seams = pick_canon_idx(pls2, path1)
    return {"pls2": pls2, "pls1": pls1, "path1": path1, "idx": idx, "seams": seams}


# ---------- partial-decomp 3-way classifier ----------

# Q = 2*atan(1/2) in the doubled-turn-angle units -> the (1,2)-slope seam quantum (the overhang
# signature). Multiples of Q (53.13, 106.26, 212.52, ...) are incommensurate with multiples of 360
# (a genuine twist/jam) except at 0, so the two failure modes never collide.
Q = 2.0 * degrees(atan2(1.0, 2.0))          # ~= 53.130102


def classify_partial(tw, eps=1e-3):
    """flat / overhang / twisted / mixed for a partial-decomp Tw value (degrees, doubled-turn)."""
    if abs(tw) < eps:
        return "flat"
    kq = round(tw / Q)
    if kq != 0 and abs(tw - kq * Q) < eps:
        return "overhang"          # nonzero multiple of the atan(1/2) quantum -> sticks out, closes
    k360 = round(tw / 360.0)
    if k360 != 0 and abs(tw - k360 * 360.0) < eps:
        return "twisted"           # nonzero multiple of 360 -> genuine twist / jam
    return "mixed"                 # twist+overhang combo, or off-quantum -> flag explicitly


# ---------- checkerboard sigma / parity (independent recompute; verification Part B oracle) ----------
# These reproduce the per-chain nH/nV parity rule (SquareLattice.parity_check) from the REPLAYED
# geometry rather than from counting arrow letters, so the two can be cross-checked. The bridge:
# an L/R fold reflects x once -> flips x-parity; a U/D fold reflects y once -> flips y-parity; so the
# checkerboard sigma = (-1)^(x+y) flips on EVERY fold. The nH-even / nV-even (2+1) or nH-even &
# nV-odd (else) rule is therefore exactly "each chain's strand returns to a prescribed x/y parity" --
# the sigma-checkerboard necessary condition for the K placements to stack onto the footprint. This
# is a 2+1-engine helper (lives here, not in py/); py/ stays the read-only yardstick.

def _cells_xy(base_cells):
    """Normalize baseCells (list of {x,y} dicts OR [x,y]/(x,y) pairs) to (x, y) int tuples."""
    return [(c["x"], c["y"]) if isinstance(c, dict) else (c[0], c[1]) for c in base_cells]


def sigma_report(base_cells, fold_arrows, m, n):
    """Replay one chain; read the checkerboard parity flips off the GEOMETRY (not arrow counts).
    Parity flips are uniform across the rigid chain, so cell 0 suffices. Returns base/final cell
    parities, the geometric x/y flip bits, nH/nV (for cross-ref), and whether the flips match the
    arrow-count parities (the bridge identity)."""
    cells = _cells_xy(base_cells)
    pls = replay([{"x": x, "y": y} for (x, y) in cells], fold_arrows, m, n)
    base = pls[0]["cells"][0]
    fin = pls[-1]["cells"][0]
    nH = sum(1 for a in fold_arrows if a in ("L", "R"))
    nV = len(fold_arrows) - nH
    x_flip = (base[0] - fin[0]) % 2
    y_flip = (base[1] - fin[1]) % 2
    return {
        "nH": nH, "nV": nV,
        "base_sigma": 1 if (base[0] + base[1]) % 2 == 0 else -1,
        "final_sigma": 1 if (fin[0] + fin[1]) % 2 == 0 else -1,
        "x_flip": x_flip, "y_flip": y_flip,
        "x_flip_matches_nH": x_flip == (nH % 2),
        "y_flip_matches_nV": y_flip == (nV % 2),
    }


def _parallel_axis(chains):
    """Base-cell adjacency axis for a 2-chain+1-chain pair (mirror of SquareLattice.parallel_fold_axis)."""
    if len(chains) != 2:
        return None
    A = _cells_xy(chains[0]["baseCells"])
    B = _cells_xy(chains[1]["baseCells"])
    for a in A:
        for b in B:
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1:
                return "H" if a[0] != b[0] else "V"
    return None


def parity_predicate_geom(chains, m, n):
    """Independent parity verdict computed from the REPLAYED cell parities (the sigma route), with
    the SAME rule structure as SquareLattice.parity_check. Used to cross-check the shipped gate."""
    axis = _parallel_axis(chains)
    for c in chains:
        rep = sigma_report(c["baseCells"], c["foldArrows"], m, n)
        if axis == "H":
            if rep["x_flip"] != 0:        # nH even  <=> no net x-parity flip
                return False
        elif axis == "V":
            if rep["y_flip"] != 0:        # nV even  <=> no net y-parity flip
                return False
        else:
            if rep["x_flip"] != 0 or rep["y_flip"] != 1:   # nH even AND nV odd
                return False
    return True
