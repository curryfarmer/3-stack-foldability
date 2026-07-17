"""twist_jump.py — shipped jump-strand (Model B) twist for 2+1 patterns.

The 2-chain is a rigid 1x2 domino; over its K folds keep ONE strand cell per placement (the twin is
a hole), so a short-side / along-axis fold appears as an axis-aligned 3-jump and every turn stays a
90-multiple -> integer Tw in {0, +-720}. The closed loop = body (the 2-chain strand) + reversed(path1)
(the 1-chain strand). Foldable-onto-the-same-footprint <=> Tw == 0; Tw = +-720 is a self-twist jam,
sign = handedness. The canonical strand is the one whose two hub seams (the loop-closure edges) are
non-diagonal -- cosmetic, Tw is idx-independent, but pinned so the labelling is deterministic.

This is the validated Model B (originally prototyped in the retired experimental/ hypothesis
scaffolding, now the sole shipped implementation), promoted into the shipped engine so
search.twist_check DECIDES 2+1 instead of returning NULL. The math: float atan2 doubled-turn
angles, sigma = (-1)^(i+1) along the loop, and the sum rounded to 6 dp ONLY (never per term).

twist_2plus1_from_chains(chains) is the live-engine entry (reads each chain's in-memory `placements`).
twist_2plus1_from_sol(sol, m, n) re-replays a stored blob (no placements) for the same computation.
"""
from math import atan2, degrees, hypot

import fold as Fold


def cc(cell):
    """Cell -> its center (half-integer point). Cells are (x, y) int pairs."""
    return (cell[0] + 0.5, cell[1] + 0.5)


def strand_path(placements, idx):
    """One kept-strand cell-center per placement; idx in {0, 1} selects the domino cell."""
    return [cc(p["cells"][idx]) for p in placements]


def loop_terms(pts):
    """Doubled signed turn angle (degrees) at each vertex of the closed polyline `pts`."""
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


def tw_of(terms):
    """Tw = sum sigma_i * term_i, sigma = (-1)^(i+1) along the loop (odd -> +, even -> -). Round the
    SUM only (per-term rounding would diverge from the JS twin)."""
    t = 0.0
    for i, x in enumerate(terms):
        t += (1 if i % 2 else -1) * x
    return round(t, 6)


def loop_tw(body, path1):
    return tw_of(loop_terms(body + list(reversed(path1))))


def is0(x):
    return abs(x) < 1e-6


def _is_diag(p, q):
    """True iff the step between consecutive loop points is a diagonal -- the only distinction the
    cosmetic canon-idx pick consumes. I/O: (p, q) points -> bool."""
    dx, dy = abs(q[0] - p[0]), abs(q[1] - p[1])
    return dx == 1 and dy == 1


def pick_canon_idx(placements2, path1):
    """Canonical strand = the domino cell whose two hub seams (loop-closure edges) are non-diagonal.
    Cosmetic (Tw is idx-independent) but pinned so JS and Python label the same strand. I/O:
    (placements2, path1) -> idx in {0, 1}; falls back to 0 when both strands have a diagonal seam."""
    for idx in (0, 1):
        sp = strand_path(placements2, idx)
        k = len(sp)
        loop = sp + list(reversed(path1))
        seam_hub = _is_diag(loop[k - 1], loop[k])      # 2-chain end -> 1-chain end
        seam_close = _is_diag(loop[-1], loop[0])       # 1-chain start -> 2-chain start (length-agnostic)
        if not (seam_hub or seam_close):
            return idx
    return 0


def twist_2plus1_from_placements(placements2, placements1):
    """Core reduction: (idx, tw) from the two chains' replayed placements."""
    path1 = strand_path(placements1, 0)
    idx = pick_canon_idx(placements2, path1)
    tw = loop_tw(strand_path(placements2, idx), path1)
    return idx, tw


def _split_2plus1(chains):
    """(i2, i1) = list indices of the 2-chain and the 1-chain, or None if `chains` is not a 2+1 pair."""
    if len(chains) != 2:
        return None
    lens = [len(c["baseCells"]) for c in chains]
    if sorted(lens) != [1, 2]:
        return None
    i2 = 0 if lens[0] == 2 else 1
    return i2, 1 - i2


def twist_2plus1_from_chains(chains):
    """Live-engine entry: read each chain's in-memory `placements` (cells are (x, y) tuples) and
    return the twist verdict in twist_check's shape. Foldable <=> Tw == 0. Returns undecided (the
    legacy shape) for anything that is not a 2-chain + 1-chain pair."""
    split = _split_2plus1(chains)
    if split is None:
        return {"decided": False, "pass": None, "pairs": [], "tw": None, "idx": None}
    i2, i1 = split
    idx, tw = twist_2plus1_from_placements(chains[i2]["placements"], chains[i1]["placements"])
    return {"decided": True, "pass": is0(tw), "tw": tw, "idx": idx,
            "pairs": [{"i": i2, "j": i1, "tw": tw}]}


def replay(base_cells, fold_arrows, m, n):
    """Standalone replay (base + one placement per fold) for a stored chain blob whose baseCells are
    {"x":, "y":} dicts. Used by twist_2plus1_from_sol to re-replay a stored blob (no placements)."""
    base = [(c["x"], c["y"]) for c in base_cells]
    pl = Fold.initial_placement(base)
    placements = [pl]
    for d in fold_arrows:
        pl = Fold.make_fold(pl, d, m, n)
        if pl is None:
            raise ValueError("fold %s left grid" % d)
        placements.append(pl)
    return placements


def twist_2plus1_from_sol(sol, m, n):
    """Re-replay a stored solution blob (chains carry baseCells/foldArrows, NOT placements) and return
    {"pass", "tw"} -- the twist_models.modelB shape -- for cross-checking. I/O: (sol, m, n) -> dict."""
    two = next(c for c in sol["chains"] if len(c["baseCells"]) == 2)
    one = next(c for c in sol["chains"] if len(c["baseCells"]) == 1)
    pls2 = replay(two["baseCells"], two["foldArrows"], m, n)
    pls1 = replay(one["baseCells"], one["foldArrows"], m, n)
    _, tw = twist_2plus1_from_placements(pls2, pls1)
    return {"pass": is0(tw), "tw": tw}
