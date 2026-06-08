"""render_reduction.py — visualise the half-tile (strand) reduction of a 2+1 solution.

Companion figure to hypothesis_2plus1_reduction.md / analyze_2plus1_reduction.py: shows the
holey grid left after deleting the non-canonical strand of the rigid 2-chain — the kept
representative strand as a numbered lattice walk, the original 1-chain, the deleted cells as
holes (ghost path), the fused-hub loop-closure seams, and the checkerboard sigma on every
surviving path cell. The loop L = strand (S->E) + 1-chain (E->S); Tw(L)=0 is the 2+1 criterion.

Usage:  python render_reduction.py <resultsfile> <id> [out.png]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "explainer"))
import analyze_2plus1_reduction as a2   # noqa: E402  (replay + loop/twist primitives)
import lib                              # noqa: E402  (matplotlib + grid.js palette)
import matplotlib.pyplot as plt         # noqa: E402

OUT_DIR = os.path.join(HERE, "..", "report", "foldsheets")


def reduce_solution(sol, m, n):
    """Replay a 2+1 solution, pick the canonical strand (non-DIAG seams), return geometry."""
    two = next(c for c in sol["chains"] if len(c["baseCells"]) == 2)
    one = next(c for c in sol["chains"] if len(c["baseCells"]) == 1)
    pls2 = a2.replay_placements(two["baseCells"], two["foldArrows"], m, n)
    pls1 = a2.replay_placements(one["baseCells"], one["foldArrows"], m, n)
    one_cells = [p["cells"][0] for p in pls1]
    out = {}
    for label, idx in (("P", 0), ("Q", 1)):
        cells = [p["cells"][idx] for p in pls2]
        centers = [(x + 0.5, y + 0.5) for (x, y) in cells]
        ones = [(x + 0.5, y + 0.5) for (x, y) in one_cells]
        loop = centers + list(reversed(ones))
        K = len(centers)
        seams = (a2.classify_step(loop[K - 1], loop[K]),
                 a2.classify_step(loop[2 * K - 1], loop[0]))
        tw = a2.tw_from_terms(a2.loop_turns(loop))
        out[label] = {"cells": cells, "seams": seams, "tw": tw}
    canon = next(k for k in ("P", "Q") if "DIAG" not in out[k]["seams"])
    other = "Q" if canon == "P" else "P"
    return {"kept": out[canon], "deleted": out[other], "one": one_cells,
            "canon": canon, "other": other}


def render(red, m, n, meta, out_path):
    kept, holes, one = red["kept"]["cells"], red["deleted"]["cells"], red["one"]
    K = len(kept)
    fig, ax = plt.subplots(figsize=(m * 0.78 + 6.4, max(n * 0.78 + 1.4, 5.0)))
    ax.set_aspect("equal")
    ax.axis("off")

    C = lib.PALETTE
    cen = {c: (c[0] + 0.5, c[1] + 0.5) for c in set(kept) | set(holes) | set(one)}

    # cells
    for (x, y) in [(x, y) for y in range(n) for x in range(m)]:
        if (x, y) in holes:
            lib.panel(ax, x, y, fc="#f3f3f3", ec="#d8d8d8", lw=0.8)
            ax.text(x + 0.5, y + 0.5, "×", ha="center", va="center",
                    color="#c4c4c4", fontsize=15, zorder=2)
        elif (x, y) in kept:
            lib.panel(ax, x, y, fc=C["tintA"], ec="#bbb", lw=0.8)
        elif (x, y) in one:
            lib.panel(ax, x, y, fc=C["tintB"], ec="#bbb", lw=0.8)
        else:
            lib.panel(ax, x, y, fc="white", ec="#ccc", lw=0.8)

    # checkerboard sigma on surviving path cells (corner mark)
    for c in list(kept) + list(one):
        sym, col = ("+", C["valley"]) if (c[0] + c[1]) % 2 == 0 else ("−", C["mountain"])
        ax.text(c[0] + 0.14, c[1] + 0.24, sym, ha="center", va="center",
                color=col, fontsize=8, fontweight="bold", zorder=8)

    # ghost path of the deleted strand (lockstep twin)
    gx, gy = zip(*[cen[c] for c in holes])
    ax.plot(gx, gy, color=C["ghost"], lw=1.3, dashes=(1, 2.4), zorder=3)

    # kept strand walk + 1-chain walk, numbered
    for cells, col in ((kept, C["chainA"]), (one, C["chainB"])):
        xs, ys = zip(*[cen[c] for c in cells])
        ax.plot(xs, ys, color=col, lw=2.6, solid_capstyle="round", zorder=5)
        for k, c in enumerate(cells):
            ax.text(cen[c][0], cen[c][1] - 0.24, str(k), ha="center", va="center",
                    color=col, fontsize=7.5, fontweight="bold", zorder=9,
                    bbox=dict(boxstyle="round,pad=0.13", fc="white", ec="none", alpha=0.85))

    # hub seams closing the loop (start: one[0]->kept[0]; end: kept[-1]->one[-1])
    for a, b in ((one[0], kept[0]), (kept[-1], one[-1])):
        ax.plot([cen[a][0], cen[b][0]], [cen[a][1], cen[b][1]],
                color=C["ink"], lw=2.0, dashes=(4, 2.6), zorder=6)
    # hub outlines: start footprint solid, exit footprint dashed (deleted cells greyed)
    for c, solid in ((kept[0], True), (one[0], True), (holes[0], True),
                     (kept[-1], False), (one[-1], False), (holes[-1], False)):
        kw = dict(fc="none", ec=C["hub"], lw=2.4)
        r = plt.Rectangle((c[0], c[1]), 1, 1, facecolor="none",
                          edgecolor=C["hub"] if solid else C["cut"],
                          lw=2.4, zorder=7, linestyle="-" if solid else (0, (3, 2)))
        ax.add_patch(r)

    ax.set_xlim(-0.6, m + 0.4)
    ax.set_ylim(n + 0.4, -0.6)   # engine convention: +y down

    # ---- side panel ----
    tx = m + 0.8
    tw_k, tw_d = red["kept"]["tw"], red["deleted"]["tw"]
    ax.text(tx, -0.2, "%dx%d  #%s   half-tile reduction (2+1)" % (m, n, meta["id"]),
            ha="left", va="top", fontsize=13, fontweight="bold", color=C["ink"])
    lines = [
        "kept strand %s (canonical: seams %s)" % (red["canon"], "/".join(red["kept"]["seams"])),
        "deleted strand %s -> %d holes (ghost dotted)" % (red["other"], K),
        "loop L = strand 0..%d  +  1-chain %d..0  (hub seams dashed)" % (K - 1, K - 1),
        "",
        "Tw(L) = %g   =>   PREDICTED %s" % (tw_k, "FOLDABLE" if tw_k == 0 else "TWISTED"),
        "(deleted-strand loop: %g — diagonal-seam artifact, ignored)" % tw_d,
    ]
    yy = 0.8
    for ln in lines:
        ax.text(tx, yy, ln, ha="left", va="top", fontsize=9.5, color=C["ink"])
        yy += 0.62
    yy += 0.2
    lib.legend(ax, [
        (C["chainA"], "solid", "kept strand walk (2-chain rep.)"),
        (C["chainB"], "solid", "1-chain walk"),
        (C["ghost"], "dot", "deleted strand (ghost)"),
        (C["ink"], "dash", "hub seam (loop closure)"),
        (C["hub"], "solid", "start footprint"),
        (C["cut"], "dash", "exit footprint"),
    ], tx, yy, dy=-0.62, fs=9)   # dy negative: y axis is inverted
    ax.text(tx, yy + 6 * 0.62 + 0.3,
            "+/− = checkerboard sigma (x+y mod 2); steps of length 3\n"
            "hop the holes — turns stay 90-degree multiples.",
            ha="left", va="top", fontsize=8, color="#555")

    os.makedirs(OUT_DIR, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", dpi=160)
    plt.close(fig)
    return out_path


def main(results_file, sid, out=None):
    data = json.load(open(results_file))
    m, n = data["meta"]["m"], data["meta"]["n"]
    sol = next(s for s in data["solutions"]
               if s["id"] == sid and s["decomposition"] == "2+1")
    red = reduce_solution(sol, m, n)
    out = out or os.path.join(OUT_DIR, "%dx%d_%d_reduced.png" % (m, n, sid))
    print("wrote", render(red, m, n, {"id": sid}, out))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None)
