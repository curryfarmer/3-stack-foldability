#!/usr/bin/env python3
"""Per-corner twist LEDGER on real Hamiltonian circuits — the M4 teaching figure.

For a chosen HC it walks every vertex and exposes, corner by corner:
    cell · parity (x+y) · σ=(−1)^{x+y} · turn (L/R) · γ=±180 · g=σγ · running cumulative Σg
then Tw = Σg / 720°  (= (1/4π)Σg with γ in radians).

Reuses `lib` (drawing) + `py/twostack.py` (`twist_value`, `reflection_cut`) and ASSERTS the
hand-walked Σg equals the reference `twist_value`, so the ledger is provably the same invariant.

Run:  python3 teach_twist.py      # prints ledgers to stdout, writes svg/PNG to ./svg/
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "py"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import lib as L
from lib import PALETTE as C
import twostack as ts


# --------------------------------------------------------------------------
# the ledger: decompose twist_value() one corner at a time
# --------------------------------------------------------------------------
def corner_ledger(circuit):
    """Return (rows, total_deg, tw). One row per L-corner (straights omitted).

    Corner sits at p2 = circuit[i+1]; γ sign = turn handedness (cross product);
    σ = (−1)^{x+y} of the corner cell; g = σ·γ; running = cumulative Σg.
    """
    n = len(circuit)
    rows = []
    run = 0
    for i in range(n):
        p1, p2, p3 = circuit[i], circuit[(i + 1) % n], circuit[(i + 2) % n]
        v1 = (p2[0] - p1[0], p2[1] - p1[1])
        v2 = (p3[0] - p2[0], p3[1] - p2[1])
        cross = v1[0] * v2[1] - v1[1] * v2[0]
        if cross > 0:
            gamma, turn = 180, "L"
        elif cross < 0:
            gamma, turn = -180, "R"
        else:
            continue  # straight pass-through: γ = 0, contributes nothing
        sigma = 1 if (p2[0] + p2[1]) % 2 == 0 else -1
        g = sigma * gamma
        run += g
        rows.append(dict(i=i, cell=p2, turn=turn, sigma=sigma, gamma=gamma, g=g, run=run))
    total = run
    # sanity: the hand-walk MUST equal the reference invariant
    ref = ts.twist_value(circuit)
    assert total == ref, f"ledger Σg={total} != twist_value={ref}"
    return rows, total, total / 720.0


def print_ledger(name, circuit):
    rows, total, tw = corner_ledger(circuit)
    print(f"\n=== {name}  ({len(circuit)} cells, {len(rows)} corners) ===")
    print("  #  cell     parity  σ   turn  γ      g      Σg(run)")
    for k, r in enumerate(rows, 1):
        par = (r["cell"][0] + r["cell"][1]) % 2
        print(f"  {k:>2} {str(tuple(r['cell'])):>7}    {par}    {r['sigma']:+d}   {r['turn']}"
              f"   {r['gamma']:+4d}   {r['g']:+4d}    {r['run']:+5d}")
    verdict = "Tw = 0  ✓ foldable" if total == 0 else f"Tw = {tw:+.0f}  ✗ twisted"
    print(f"  ---> Σg = {total:+d}°   Tw = Σg/720 = {tw:+.3f}   {verdict}")
    return rows, total, tw


# --------------------------------------------------------------------------
# drawing: grid with σ checkerboard + HC path + corner g-stamps, beside a ledger
# --------------------------------------------------------------------------
def draw(name, circuit, m, n, title, outfile):
    rows, total, tw = corner_ledger(circuit)
    cells = ts_cells = [(x, y) for x in range(m) for y in range(n)]
    cellset = set(map(tuple, (tuple(c) for c in circuit)))
    fig, (axg, axl) = plt.subplots(
        1, 2, figsize=(6.0 + 0.42 * len(rows) ** 0.0 + m * 0.55, max(n * 0.7 + 1.2, 4.2)),
        gridspec_kw={"width_ratios": [m + 1.5, 5.0]})

    # ---- left: the grid ----
    axg.set_aspect("equal")
    axg.axis("off")
    # checkerboard σ (only over cells the HC actually uses, for ring/hole cases)
    L.checkerboard(axg, [tuple(c) for c in circuit], signs=True)
    L.hc_path(axg, [tuple(c) for c in circuit], closed=True, marker=True)
    # corner stamps: order# + g, colored by sign
    for k, r in enumerate(rows, 1):
        cx, cy = L.center(*r["cell"])
        col = C["valley"] if r["g"] > 0 else C["mountain"]
        axg.text(cx, cy + 0.16, f"{r['g']:+d}", ha="center", va="center",
                 color=col, fontsize=8.5, fontweight="bold", zorder=12)
        axg.text(cx, cy - 0.22, f"#{k}", ha="center", va="center",
                 color=C["ink"], fontsize=6.5, zorder=12)
    axg.set_title(title, fontsize=12, color=C["ink"], pad=8)
    axg.set_xlim(-0.4, m + 0.4)
    axg.set_ylim(-0.6, n + 0.4)

    # ---- right: the ledger ----
    axl.axis("off")
    axl.set_xlim(0, 1)
    axl.set_ylim(0, 1)
    lines = [" #  cell    σ  turn  γ     g     Σg"]
    lines.append(" " + "─" * 33)
    for k, r in enumerate(rows, 1):
        lines.append(f"{k:>2} {str(tuple(r['cell'])):>7} {r['sigma']:+d}   {r['turn']}"
                     f"  {r['gamma']:+4d}  {r['g']:+4d}  {r['run']:+5d}")
    y = 0.97
    axl.text(0.0, y, "per-corner ledger", fontsize=10.5, fontweight="bold",
             va="top", family="monospace", color=C["ink"])
    y -= 0.06
    for ln in lines:
        axl.text(0.0, y, ln, fontsize=8.2, va="top", family="monospace",
                 color=C["ink"])
        y -= 0.045
    y -= 0.02
    vcol = C["cut"] if total == 0 else C["mountain"]
    vtxt = (f"Σg = {total:+d}°   Tw = {tw:+.0f}\n"
            + ("✓ foldable (Tw=0)" if total == 0 else "✗ twisted (Tw≠0)"))
    axl.text(0.0, y, vtxt, fontsize=11, fontweight="bold", va="top",
             family="monospace", color=vcol)

    os.makedirs(L.SVG_DIR, exist_ok=True)
    svg = os.path.join(L.SVG_DIR, outfile + ".svg")
    png = os.path.join(L.SVG_DIR, outfile + ".png")
    fig.savefig(svg, bbox_inches="tight")
    fig.savefig(png, bbox_inches="tight", dpi=110)
    plt.close(fig)
    return svg, png


# --------------------------------------------------------------------------
# the three 2-stack cases (M4)
# --------------------------------------------------------------------------
# T1 — 2x4 perimeter loop (paper Fig 13b, foldable)
T1 = [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (2, 1), (1, 1), (0, 1)]

# T3 — 3x3 ring, centre removed (paper Fig 13a, twisted Tw=+1)
T3 = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2), (1, 2), (0, 2), (0, 1)]

# T2 — a real, min-corner foldable 6x6 HC (from ts.enumerate_hc(6,6), Tw=0 & reflection-ok)
T2 = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (5, 1), (4, 1), (3, 1), (2, 1),
      (1, 1), (1, 2), (2, 2), (3, 2), (4, 2), (5, 2), (5, 3), (4, 3), (3, 3), (2, 3),
      (1, 3), (1, 4), (2, 4), (3, 4), (4, 4), (5, 4), (5, 5), (4, 5), (3, 5), (2, 5),
      (1, 5), (0, 5), (0, 4), (0, 3), (0, 2), (0, 1)]


def main():
    print_ledger("T1 — 2×4 perimeter (foldable)", T1)
    print_ledger("T2 — real 6×6 snake HC (foldable)", T2)
    print_ledger("T3 — 3×3 ring, hole (twisted)", T3)

    figs = [
        draw("T1", T1, 4, 2, "T1 — 2×4 perimeter: Tw = 0 (foldable)", "T1_ledger_2x4"),
        draw("T2", T2, 6, 6, "T2 — real 6×6 HC: Tw = 0 (foldable)", "T2_ledger_6x6"),
        draw("T3", T3, 3, 3, "T3 — 3×3 ring (hole): Tw = +1 (twisted)", "T3_ledger_ring"),
    ]
    print("\nwrote:")
    for svg, png in figs:
        print("  ", os.path.basename(svg), "/", os.path.basename(png))


if __name__ == "__main__":
    main()
