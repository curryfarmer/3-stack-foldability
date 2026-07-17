"""render_twist_111.py — twist-calc diagram for a 1+1+1 (or n-singleton) square solution.

The 1+1+1 analog of render_twist_2plus1 (the 2+1 jump-strand loop), so EVERY square fold produces a
twist diagram — the second half of the standardised two-image bundle (schematic + twist). Each
singleton chain folds to a strand; for every pair (i, j) the reduced twist loop = strand_i +
reversed(strand_j) is scored with the SAME Model-B math (twist_jump.loop_terms / tw_of: doubled
signed-turn angles under the alternating loop-index sigma). One panel per pair (AB / BC / AC for the
three chains), each on the sigma = (-1)^(x+y) parity checkerboard, with per-vertex sigma*gamma labels
and the Tw verdict. Foldable-flat <=> every pairwise Tw == 0. This is the exact construction the
triangle track's render_twist uses for its 1+1+1 theta-graph loops, in the square (+y down) convention.

Store-free: consumes the stored `detail_json` sol dict only (footprint + chains). Palette / grid /
legend / save come from figstyle, the single source of truth shared across the square renderers.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # square/ on path
import _bootstrap  # noqa: E402,F401  (puts square/{engine,twist,render} on sys.path)

import figstyle as fs          # noqa: E402  (shared palette/grid/legend/save)
import twist_jump as tj        # noqa: E402  (replay / strand_path / loop_terms / tw_of / is0)


def _pairs(n):
    """All unordered chain pairs (i < j) — the pairwise twist loops (3 for a 1+1+1)."""
    return [(i, j) for i in range(n) for j in range(i + 1, n)]


def _letter(i):
    return chr(ord("A") + i)


def _setup_grid(ax, m, n):
    """Grid axis in the viewer convention (origin top-left, +y DOWN), no ticks — one panel."""
    ax.set_xlim(-0.5, m + 0.5)
    ax.set_ylim(n + 0.5, -0.5)                              # inverted y -> +y down
    ax.set_aspect("equal")
    ax.axis("off")


def _strands(sol, m, n):
    """Replay every chain to its fold-path strand (one cell-centre per placement). I/O: -> [path,...]."""
    strands = []
    for ch in sol.get("chains", []):
        placements = tj.replay(ch.get("baseCells", []), ch.get("foldArrows", []), m, n)
        strands.append(tj.strand_path(placements, 0))      # singleton -> cell index 0
    return strands


def _draw_loop(ax, m, n, sol, ci, cj, path_i, path_j):
    """Draw the pairwise reduced loop strand_i + reversed(strand_j) on one panel; return its Tw."""
    from matplotlib.patches import FancyArrowPatch

    _setup_grid(ax, m, n)
    fs.draw_grid_cells(ax, m, n, checker=True)              # sigma = (-1)^(x+y) red/blue parity tint
    fs.draw_footprint(ax, (sol.get("footprint") or {}).get("cells", []))
    ic, jc = fs.chain_color(ci), fs.chain_color(cj)

    loop = list(path_i) + list(reversed(path_j))           # closed loop, len K_i + K_j
    terms = tj.loop_terms(loop)
    tw = tj.tw_of(terms)
    nloop = len(loop)
    K = len(path_i)
    seams = {K - 1, nloop - 1}                              # the two hub-seam edges (loop closure)

    for k in range(nloop):
        p, q = loop[k], loop[(k + 1) % nloop]
        col = fs.SEAM if k in seams else (ic if k < K - 1 else jc)
        ax.plot([p[0], q[0]], [p[1], q[1]], color=col, lw=2.0, zorder=4, alpha=0.9,
                solid_capstyle="round")
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=11,
                                     color=col, lw=0, zorder=6))
    for k, p in enumerate(path_i):
        ax.plot(p[0], p[1], "o", ms=4.0, color=ic, zorder=8)
    for p in path_j:
        ax.plot(p[0], p[1], "o", ms=3.0, color=jc, zorder=8)

    # per-turn sigma*gamma labels (only turning vertices move the total)
    for k in range(nloop):
        gamma = terms[k]
        if abs(gamma) < 1e-6:
            continue
        contrib = (1 if k % 2 else -1) * gamma
        piv = loop[(k + 1) % nloop]
        ax.annotate(fs.pi_label(contrib), (piv[0], piv[1]), textcoords="offset points",
                    xytext=(4, -10), fontsize=7.5, fontweight="bold",
                    color=fs.POS if contrib > 0 else fs.NEG, zorder=10)

    badge = fs.FOLD_BADGE if tj.is0(tw) else fs.JAM_BADGE
    ax.set_title("%s%s loop   Tw = %s   %s" % (_letter(ci), _letter(cj), fs.pi_label(tw),
                 "FOLD (flat)" if tj.is0(tw) else "JAM"), color=badge, fontsize=9, fontweight="bold")
    return tw


def render_twist_111(uid, sol, m, n, out_path):
    """Render the 1+1+1 (or n-singleton) pairwise twist-loop diagram to out_path (PNG). One panel per
    chain pair; foldable-flat iff every pairwise Tw == 0. I/O: (uid, sol, m, n, out_path) -> path."""
    from matplotlib import pyplot as plt

    strands = _strands(sol, m, n)
    pairs = _pairs(len(strands)) or [(0, 0)]                # guard: degenerate single-chain record
    fig, axes = plt.subplots(1, len(pairs), figsize=(max(4.5, m * 0.55 + 1.6) * len(pairs),
                                                      max(3.6, n * 0.55 + 1.4)), squeeze=False)
    tws = []
    for ax, (ci, cj) in zip(axes[0], pairs):
        if ci == cj:                                       # only one chain: nothing to pair
            _setup_grid(ax, m, n)
            fs.draw_grid_cells(ax, m, n, checker=True)
            ax.set_title("single chain — no pairwise loop", color=fs.INK, fontsize=9)
            continue
        tws.append(_draw_loop(ax, m, n, sol, ci, cj, strands[ci], strands[cj]))

    flat = all(tj.is0(t) for t in tws)
    verdict = "FOLD (all Tw=0)" if flat else "JAM (some Tw!=0)"
    badge = fs.FOLD_BADGE if flat else fs.JAM_BADGE
    fig.suptitle("TWIST — %s  %dx%d  1+1+1 pairwise loops:  Tw = Σ(σ·γ)  →  %s"
                 % (uid, m, n, verdict), color=badge, fontsize=11, fontweight="bold")
    return fs.save(fig, out_path)
