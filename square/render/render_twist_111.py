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


def _hub_elbow(p, q, occ):
    """If seam p->q is a unit diagonal (the two chain bases/ends only corner-touch), return the hub
    cell that edge-connects both — the third chain's own base/end, which sits at one of the diagonal's
    two elbow corners. None when the seam is axis-aligned (bases share the hub) or no cell fills the
    elbow. Purely a DRAW hint: the reduced-loop twist is computed on the direct chord regardless, so this
    only bends the seam's polyline through the middle cell without touching Tw."""
    if abs(abs(p[0] - q[0]) - 1) > 1e-9 or abs(abs(p[1] - q[1]) - 1) > 1e-9:
        return None                                        # not a unit diagonal -> straight seam
    for c in ((p[0], q[1]), (q[0], p[1])):                 # the two elbow corners of the diagonal
        if any(abs(c[0] - o[0]) < 1e-9 and abs(c[1] - o[1]) < 1e-9 for o in occ):
            return c
    return None


def _draw_seam(ax, p, q, occ):
    """Draw one closure seam p->q in the hub-seam colour, routed through the hub cell as an L-bend when
    p,q only corner-touch (so every pairwise loop visibly passes through the middle/hub cell)."""
    from matplotlib.patches import FancyArrowPatch

    elbow = _hub_elbow(p, q, occ)
    pts = [p, elbow, q] if elbow else [p, q]
    for a, b in zip(pts, pts[1:]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=fs.SEAM, lw=2.0, zorder=4, alpha=0.9,
                solid_capstyle="round")
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=11,
                                     color=fs.SEAM, lw=0, zorder=6))


def _draw_loop(ax, m, n, sol, ci, cj, path_i, path_j, base_occ, end_occ):
    """Draw the pairwise reduced loop strand_i + reversed(strand_j) on one panel; return its Tw.
    The Tw / per-vertex labels come from the canonical direct-closure loop (engine-faithful); only the
    two closure SEAMS are drawn hub-routed (see _draw_seam / _hub_elbow) — cosmetic, Tw unchanged."""
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

    for k in range(nloop):
        p, q = loop[k], loop[(k + 1) % nloop]
        if k == nloop - 1:                                 # base seam (path_j.base -> path_i.base)
            _draw_seam(ax, p, q, base_occ)
            continue
        if k == K - 1:                                     # end seam (path_i.end -> path_j.end)
            _draw_seam(ax, p, q, end_occ)
            continue
        col = ic if k < K - 1 else jc
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
    base_occ = [s[0] for s in strands if s]                # every chain's base cell (hub-elbow lookup)
    end_occ = [s[-1] for s in strands if s]                # every chain's end cell
    pairs = _pairs(len(strands)) or [(0, 0)]               # guard: degenerate single-chain record
    fig, axes = plt.subplots(1, len(pairs), figsize=(max(4.5, m * 0.55 + 1.6) * len(pairs),
                                                      max(3.6, n * 0.55 + 1.4)), squeeze=False)
    tws = []
    for ax, (ci, cj) in zip(axes[0], pairs):
        if ci == cj:                                       # only one chain: nothing to pair
            _setup_grid(ax, m, n)
            fs.draw_grid_cells(ax, m, n, checker=True)
            ax.set_title("single chain — no pairwise loop", color=fs.INK, fontsize=9)
            continue
        tws.append(_draw_loop(ax, m, n, sol, ci, cj, strands[ci], strands[cj], base_occ, end_occ))

    flat = all(tj.is0(t) for t in tws)
    verdict = "FOLD (all Tw=0)" if flat else "JAM (some Tw!=0)"
    badge = fs.FOLD_BADGE if flat else fs.JAM_BADGE
    decomp = sol.get("decomposition") or "+".join(["1"] * len(strands))   # 1+1+1, 1+1+1+1, ...
    fig.suptitle("TWIST — %s  %dx%d  %s pairwise loops:  Tw = Σ(σ·γ)  →  %s"
                 % (uid, m, n, decomp, verdict), color=badge, fontsize=11, fontweight="bold")
    return fs.save(fig, out_path)
