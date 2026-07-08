"""render_twist_2plus1.py — annotated twist-loop diagram for a 2+1 (Model B jump-strand) solution.

Salvaged from the retired `experimental/enumerate_twist.py` (the rest of that file — the SQLite
`load_pattern`, the CLI `main`, and `print_table` — was hypothesis-era scaffolding tied to the
write-master DB and is not reproduced here). What's kept is the pure geometry + plotting: given an
already-parsed pattern record (the `sol` detail-blob dict + its `m, n` grid size, exactly the fields
`load_pattern()` used to pull out of SQLite), replay both chains, build the canonical jump-strand loop
(`body + reversed(path1)`), and render it — the body strand as a directed polyline with the 3-jumps
highlighted, path1 in a second colour, the two hub seams marked, and every turning vertex labelled
with its signed twist contribution.

The turn/twist math (replay, strand_path, loop_terms, tw_of, pick_canon_idx, is0, ...) used to live in
`experimental/common.py`, shared by four candidate 2+1 engines. Three of those engines were disproven
and the fourth (jump-strand / Model B) was promoted into the shipped engine as `py/twist/twist_jump.py`
— math-identical to the old common.py routines. This module reuses THAT (kept, non-experimental)
primitives module instead of re-inlining a second copy of the same geometry.

Store-free: nothing here touches SQLite, `store`, `serve`, or `findings`. Wiring this into an actual
CLI (argument parsing, DB lookup by pattern_uid) is a separate, later phase's job — see
`render_twist_2plus1(uid, sol, m, n, out_path)` below for the plain adapter a future CLI can call.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # square/ on path
import _bootstrap  # noqa: E402,F401  (puts square/{engine,twist,render} on sys.path)

import figstyle as fs          # noqa: E402  (shared palette/grid/legend/save)
import twist_jump as tj        # noqa: E402  (Model B geometry: replay/strand_path/loop_terms/tw_of/...)


# ------------------------------------------------------------- loop assembly --

def build_loop(sol, m, n):
    """Replay both chains, pick the canonical strand, return everything render_plot needs.
    I/O: (sol, m, n) -> dict(body, path1, loop, K, idx, terms, tw)."""
    two = next(c for c in sol["chains"] if len(c["baseCells"]) == 2)
    one = next(c for c in sol["chains"] if len(c["baseCells"]) == 1)
    pls2 = tj.replay(two["baseCells"], two["foldArrows"], m, n)
    pls1 = tj.replay(one["baseCells"], one["foldArrows"], m, n)
    path1 = tj.strand_path(pls1, 0)                           # 1-chain strand, K points
    idx = tj.pick_canon_idx(pls2, path1)
    body = tj.strand_path(pls2, idx)                          # canonical kept strand, K points
    loop = body + list(reversed(path1))                       # closed loop, 2K points
    terms = tj.loop_terms(loop)                                # gamma_i = 2 * signed turn at loop[i+1]
    tw = tj.tw_of(terms)                                       # == tj.loop_tw(body, path1)
    return {"body": body, "path1": path1, "loop": loop,
            "K": len(body), "idx": idx, "terms": terms, "tw": tw}


def _cell_of(pt):
    """Cell-centre (x+0.5, y+0.5) -> integer cell (x, y)."""
    return (int(round(pt[0] - 0.5)), int(round(pt[1] - 0.5)))


def _step_kind(a, b):
    """Manhattan step a->b between cell-centres: 'unit' (1), '3JMP' (along-axis short-side fold),
    '2JMP', 'diag', or 'far'."""
    dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1])
    if dx + dy == 1:
        return "unit"
    if (dx == 3 and dy == 0) or (dx == 0 and dy == 3):
        return "3JMP"
    if (dx == 2 and dy == 0) or (dx == 0 and dy == 2):
        return "2JMP"
    if dx == dy:
        return "diag"
    return "far"


# -------------------------------------------------------------------- plot ----
# Palette / grid / legend / save all come from figstyle (the single source of truth shared with
# render_square + render_twostack). Body = chain A, path1 = chain B; jump/seam/pos/neg are semantic.


def render_plot(uid, sol, m, n, info, out_path):
    """Render the annotated twist-loop diagram to out_path (PNG). Origin top-left, +y down (matches
    the viewer / render_square), styled via figstyle. I/O: (...) -> out_path."""
    from matplotlib.patches import FancyArrowPatch

    loop, terms, K = info["loop"], info["terms"], info["K"]
    nloop = len(loop)
    BODY, PATH1 = fs.CHAIN[0], fs.CHAIN[1]

    fig, ax = fs.new_grid_axes(m, n, pad=0.5, extra_w=2.6, ticklabels=False)
    fs.draw_grid_cells(ax, m, n, checker=True)               # sigma = (-1)^(x+y) red/blue parity tint
    fs.draw_footprint(ax, sol.get("footprint", {}).get("cells", []))

    def seg(p, q, color, lw, ls="-", z=4, alpha=1.0):
        ax.plot([p[0], q[0]], [p[1], q[1]], color=color, lw=lw, ls=ls, zorder=z, alpha=alpha,
                solid_capstyle="round")

    def arrow(p, q, color, z=7):
        ax.add_patch(FancyArrowPatch((p[0], p[1]), (q[0], q[1]), arrowstyle="-|>",
                                     mutation_scale=12, color=color, lw=0, zorder=z))

    seam_pairs = {(K - 1, K % nloop), (nloop - 1, 0)}        # the two hub-seam edges (by loop index)

    # draw every loop edge; body vs path1 by colour, 3-jumps dashed-red, seams green
    for i in range(nloop):
        p, q = loop[i], loop[(i + 1) % nloop]
        cp, cq = _cell_of(p), _cell_of(q)
        kind = _step_kind(cp, cq)
        if (i, (i + 1) % nloop) in seam_pairs:
            seg(p, q, fs.SEAM, 3.4, z=5)
        elif kind == "3JMP":
            seg(p, q, fs.JUMP, 3.2, ls=fs.DASH, z=5)
        else:
            on_body = i < K - 1                              # body edges are loop[0..K-1]
            seg(p, q, BODY if on_body else PATH1, 2.2, z=4)
        arrow(p, q, BODY if i < K else PATH1)

    # vertices: body cells lettered by placement index; mark base + final hubs
    for k, p in enumerate(info["body"]):
        ax.plot(p[0], p[1], "o", ms=4.5, color=BODY, zorder=8)
        ax.annotate(str(k), (p[0], p[1]), textcoords="offset points", xytext=(3, 3),
                    fontsize=6.5, color=BODY, zorder=9)
    for p in info["path1"]:
        ax.plot(p[0], p[1], "o", ms=3.2, color=PATH1, zorder=8)

    # per-turn sigma*gamma labels (only turning vertices move the total)
    for i in range(nloop):
        gamma = terms[i]
        if abs(gamma) < 1e-6:
            continue
        sig = 1 if i % 2 else -1
        contrib = sig * gamma
        piv = loop[(i + 1) % nloop]
        ax.annotate(fs.pi_label(contrib), (piv[0], piv[1]), textcoords="offset points",
                    xytext=(4, -10), fontsize=7.5, fontweight="bold",
                    color=fs.POS if contrib > 0 else fs.NEG, zorder=10)

    tw = info["tw"]
    verdict = "FOLD (flat)" if tj.is0(tw) else f"JAM (Tw={fs.pi_label(tw)})"
    ax.set_title(f"{uid}  {m}x{n}   jump-strand loop:  Tw = Σ(σ·γ) = {fs.pi_label(tw)}  →  {verdict}")

    handles = [
        fs.line_handle(BODY, "2-chain kept strand (body)"),
        fs.line_handle(PATH1, "1-chain strand (path1)"),
        fs.line_handle(fs.JUMP, "3-jump (along-axis fold)", ls=fs.DASH),
        fs.line_handle(fs.SEAM, "hub seam (chains rejoin)"),
    ]
    fs.legend_panel(ax, handles)
    return fs.save(fig, out_path)


# ----------------------------------------------------------------- adapter ----

def render_twist_2plus1(uid, sol, m, n, out_path):
    """Store-free adapter: given an already-parsed pattern record (uid + the sol detail-blob dict +
    its m, n grid size — no DB lookup performed here), build the twist-loop geometry and render the
    annotated PNG. Replaces the retired `load_pattern` (SQLite) + `main` (CLI) glue; wiring an actual
    CLI or store lookup on top of this is a separate, later phase's job.
    I/O: (uid, sol_dict, m, n, out_path) -> out_path."""
    info = build_loop(sol, m, n)
    return render_plot(uid, sol, m, n, info, out_path)
