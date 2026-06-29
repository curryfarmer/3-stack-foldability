#!/usr/bin/env python3
"""enumerate_twist.py — make the Model B (jump-strand) twist of a 2+1 pattern VISIBLE.

Read-only. Given a pattern_uid, it pulls the pattern's detail blob + grid from the SQLite
write-master, replays both chains through the shared geometry in `experimental/common.py`, builds
the canonical jump-strand loop (`body + reversed(path1)`), and then either

  (a) TABLE mode  — prints one row per loop vertex: the turn there, the doubled-turn gamma, the
      checkerboard sign sigma, the signed contribution sigma*gamma, and the running total, ending in
      `Tw` and the FOLD/JAM verdict; it ASSERTS the total equals the stored modelB_pred twist, or

  (b) --plot PATH — renders the annotated twist-loop diagram (the picture for the writeup): the body
      strand as a directed polyline with the 3-jumps highlighted, path1 in a second colour, the two
      hub seams marked, and every turning vertex labelled with its sigma*gamma contribution.

Nothing here mutates engine or DB state. It only reads `patterns`/`runs`/`tag` and reuses
`common.{split_chains,prepare,strand_path,short_incident,loop_terms,tw_of,loop_tw,pick_canon_idx}`.

Usage:
  python experimental/enumerate_twist.py 07dff02ba5c9                 # table + verdict
  python experimental/enumerate_twist.py 4cc6f36d0ca4 --plot out.png  # table + annotated picture
  python experimental/enumerate_twist.py UID --db results/folddb.test.sqlite3 --no-assert
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))            # .../experimental
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)                          # experimental/ for `import common`
sys.path.insert(0, os.path.join(ROOT, "py"))      # py/ for _bootstrap
import _bootstrap  # noqa: E402,F401  (store -> storage/, figstyle -> render/, + repo + tests)

import common              # noqa: E402  (twist + geometry primitives, reused verbatim)
import store as Store      # noqa: E402  (DB connect / path resolve only)
import figstyle as fs      # noqa: E402  (shared report-figure style: palette/grid/legend/save)


# ---------------------------------------------------------------- DB read -----

def load_pattern(uid, db_path):
    """Pull (sol, m, n, stored_tw) for a pattern_uid. stored_tw is the modelB_pred twist (or None).
    I/O: (uid, db_path) -> (sol_dict, m, n, stored_tw|None)."""
    conn = Store.connect(db_path)
    try:
        row = conn.execute(
            "SELECT p.detail_json, r.m AS m, r.n AS n, t.val_int AS mb_tw "
            "FROM patterns p JOIN runs r ON r.id = p.run_id "
            "LEFT JOIN tag t ON t.norm_hash = p.norm_hash AND t.key = 'modelB_pred' "
            "WHERE p.pattern_uid = ? LIMIT 1", (uid,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise SystemExit(f"pattern_uid {uid} not found in {db_path}")
    return json.loads(row["detail_json"]), row["m"], row["n"], row["mb_tw"]


# ------------------------------------------------------------- loop assembly --

def build_loop(sol, m, n):
    """Replay both chains, pick the canonical strand, return everything the table/plot need.
    I/O: (sol, m, n) -> dict(body, path1, loop, K, idx, seams, terms, tw, ctx)."""
    two, one = common.split_chains(sol)
    ctx = common.prepare(two, one, m, n)
    body = common.strand_path(ctx["pls2"], ctx["idx"])       # canonical kept strand, K points
    path1 = ctx["path1"]                                     # 1-chain strand, K points
    loop = body + list(reversed(path1))                      # closed loop, 2K points
    terms = common.loop_terms(loop)                          # gamma_i = 2 * signed turn at loop[i+1]
    tw = common.tw_of(terms)                                 # == common.loop_tw(body, path1)
    return {"two": two, "one": one, "body": body, "path1": path1, "loop": loop,
            "K": len(body), "idx": ctx["idx"], "seams": ctx["seams"], "terms": terms, "tw": tw}


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


# ------------------------------------------------------------------- table ----

def print_table(uid, sol, m, n, info, stored_tw, assert_db=True):
    """Print the per-vertex twist enumeration. The turn at table row i happens at loop vertex
    j=(i+1) mod 2K (the middle of the triple loop[i],loop[i+1],loop[i+2]); tw_of weights gamma_i by
    s_i = +1 if i odd else -1 — the checkerboard sign that alternates along the loop."""
    loop, terms, K = info["loop"], info["terms"], info["K"]
    nloop = len(loop)
    fp = sol.get("footprint", {})
    print(f"\n=== twist enumeration: {uid}  ({m}x{n}, {fp.get('shape','?')}@"
          f"({fp.get('anchor',{}).get('x','?')},{fp.get('anchor',{}).get('y','?')}), "
          f"K={K - 1} folds, loop={nloop} vertices) ===")
    print(f"canonical strand idx={info['idx']}  hub seams={info['seams'][info['idx']]}")
    print("\n  i  vertex(cell)   in->out        step    turn   gamma=2T   sig  sig*gamma   running")
    print("  -- ------------   -----------    -----   -----  --------   ---  ---------   -------")
    running = 0.0
    for i in range(nloop):
        p_prev = loop[i]
        p_piv = loop[(i + 1) % nloop]
        p_next = loop[(i + 2) % nloop]
        c_prev, c_piv, c_next = _cell_of(p_prev), _cell_of(p_piv), _cell_of(p_next)
        gamma = terms[i]
        turn = gamma / 2.0
        sig = 1 if i % 2 else -1                              # tw_of sign convention
        contrib = sig * gamma
        running += contrib
        step_in = _step_kind(c_prev, c_piv)
        in_dir = (c_piv[0] - c_prev[0], c_piv[1] - c_prev[1])
        out_dir = (c_next[0] - c_piv[0], c_next[1] - c_piv[1])
        # only turns (gamma != 0) move the total; mark them so the eye finds them.
        star = "*" if abs(gamma) > 1e-6 else " "
        print(f" {star}{i:>2} ({c_piv[0]:>2},{c_piv[1]:>2})       "
              f"{str(in_dir):>7}->{str(out_dir):<7} {step_in:<5}  "
              f"{turn:>6.1f}  {gamma:>8.1f}   {sig:>+d}   {contrib:>+8.1f}   {running:>+8.1f}")
    tw = info["tw"]
    verdict = "FOLD (flat)" if common.is0(tw) else f"JAM (self-twist, {'+' if tw > 0 else '-'}1 wrap)"
    print(f"\n  Tw = sum(sigma*gamma) = {tw:+.1f} deg  ->  {verdict}")
    if stored_tw is not None:
        match = abs(tw - stored_tw) < 1e-6
        print(f"  DB modelB_pred twist = {stored_tw:+d} deg  ->  {'MATCH' if match else 'MISMATCH'}")
        if assert_db and not match:
            raise SystemExit(f"twist mismatch: computed {tw} vs stored {stored_tw}")
    elif assert_db:
        print("  (no stored modelB_pred twist to assert against)")
    return tw


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

    fig, ax = fs.new_grid_axes(m, n, pad=0.5, extra_w=2.6)
    fs.draw_grid_cells(ax, m, n, checker=True)               # sigma = (-1)^(x+y) tint
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
        ax.annotate(f"{contrib:+.0f}", (piv[0], piv[1]), textcoords="offset points",
                    xytext=(4, -10), fontsize=7.5, fontweight="bold",
                    color=fs.POS if contrib > 0 else fs.NEG, zorder=10)

    tw = info["tw"]
    verdict = "FOLD (flat)" if common.is0(tw) else f"JAM (Tw={tw:+.0f})"
    ax.set_title(f"{uid}  {m}x{n}   jump-strand loop:  Tw = Σ(σ·γ) = {tw:+.0f}°  →  {verdict}")

    handles = [
        fs.line_handle(BODY, "2-chain kept strand (body)"),
        fs.line_handle(PATH1, "1-chain strand (path1)"),
        fs.line_handle(fs.JUMP, "3-jump (along-axis fold)", ls=fs.DASH),
        fs.line_handle(fs.SEAM, "hub seam (chains rejoin)"),
    ]
    fs.legend_panel(ax, handles)
    return fs.save(fig, out_path)


# -------------------------------------------------------------------- main ----

def main(argv=None):
    p = argparse.ArgumentParser(description="Enumerate + visualise the Model B jump-strand twist.")
    p.add_argument("uid", help="pattern_uid (12-hex) to enumerate")
    p.add_argument("--db", metavar="PATH", help="DB path (default $FOLDDB_SQLITE or results/folddb.sqlite3)")
    p.add_argument("--test", action="store_true", help="use the scratch DB results/folddb.test.sqlite3")
    p.add_argument("--plot", metavar="PATH", help="also render the annotated twist-loop PNG here")
    p.add_argument("--no-assert", action="store_true", help="do not fail on computed-vs-stored mismatch")
    ns = p.parse_args(sys.argv[1:] if argv is None else argv)

    db_path = Store.resolve_db_path(ns.db, ns.test)
    sol, m, n, stored_tw = load_pattern(ns.uid, db_path)
    info = build_loop(sol, m, n)
    print_table(ns.uid, sol, m, n, info, stored_tw, assert_db=not ns.no_assert)
    if ns.plot:
        out = render_plot(ns.uid, sol, m, n, info, ns.plot)
        print(f"  plot -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
