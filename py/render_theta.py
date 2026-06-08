"""render_theta.py — draw the theta-graph abstraction of a 1+1+1 decomposition.

A 1+1+1 split is three 1-chains meeting at the two rigid footprint hubs (start S and
end E, each a fused ABC base). Abstractly that is a *theta graph*: two vertices joined
by three internally-disjoint arcs. Its first Betti number (cycle rank) is 2, so the
cycle space is spanned by two independent pairwise loops (here L_AB, L_BC); the third
(L_AC) is their sum, not independent. Foldability = Tw(L_ij)=0 on the loops.

Output: report/theta_111.png  (and .svg)

Usage:  .\.venv\Scripts\python.exe py/render_theta.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "explainer"))
import lib  # noqa: E402  (palette + matplotlib primitives)
import numpy as np  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "report")

CHAIN = [lib.PALETTE["chainA"], lib.PALETTE["chainB"], lib.PALETTE["chainC"]]
LABELS = ["A", "B", "C"]


def arc_points(p, q, bow, n=200):
    """Quadratic arc from p to q, bowing perpendicular by `bow` at the midpoint."""
    p, q = np.array(p, float), np.array(q, float)
    mid = (p + q) / 2.0
    d = q - p
    perp = np.array([-d[1], d[0]])
    nrm = np.hypot(*perp)
    perp = perp / nrm if nrm else perp
    ctrl = mid + perp * bow
    t = np.linspace(0, 1, n)[:, None]
    pts = (1 - t) ** 2 * p + 2 * (1 - t) * t * ctrl + t ** 2 * q
    return pts, ctrl


def main():
    fig, ax = lib.new_ax(figsize=(8.4, 5.6))

    S, E = (0.0, 0.0), (5.0, 0.0)
    bows = [1.7, 0.0, -1.7]          # A up, B straight, C down

    # --- three chain arcs (the theta's three edges) ---
    chain_ctrl = []
    for ci, bow in enumerate(bows):
        pts, ctrl = arc_points(S, E, bow)
        ax.plot(pts[:, 0], pts[:, 1], color=CHAIN[ci], lw=3.4,
                solid_capstyle="round", zorder=4)
        chain_ctrl.append(ctrl)
        # chain label near the apex
        lab = pts[len(pts) // 2]
        off = 0.34 if bow >= 0 else -0.34
        ax.text(lab[0], lab[1] + off, LABELS[ci], ha="center", va="center",
                color=CHAIN[ci], fontsize=18, fontweight="bold", zorder=8)

    # --- the two rigid fused hubs ---
    for c, name, sub in [(S, "S", "start footprint"), (E, "E", "end footprint")]:
        lib.node(ax, c, r=0.30, color=lib.PALETTE["hub"], z=9, label=name,
                 fs=16, lab_dy=0.0)
        ax.text(c[0], c[1] - 0.62, f"{sub}\n(fused ABC base)", ha="center",
                va="top", fontsize=9, color="#555", zorder=9)

    # --- independent pairwise loops L_AB, L_BC (curved arrows in each face) ---
    def loop_marker(face_ctrl_a, face_ctrl_b, name, color):
        cx = (face_ctrl_a[0] + face_ctrl_b[0]) / 2.0
        cy = (face_ctrl_a[1] + face_ctrl_b[1]) / 2.0
        ax.add_patch(FancyArrowPatch((cx - 0.55, cy), (cx + 0.55, cy),
                     connectionstyle="arc3,rad=-0.9", arrowstyle="-|>",
                     color=color, lw=1.8, mutation_scale=13, zorder=6,
                     shrinkA=0, shrinkB=0, alpha=0.85))
        ax.text(cx, cy, name, ha="center", va="center", fontsize=12,
                fontweight="bold", color=color, zorder=10,
                bbox=dict(boxstyle="round,pad=0.18", fc="white", ec=color, lw=1.0))

    loop_marker(chain_ctrl[0], chain_ctrl[1], r"$L_{AB}$", lib.PALETTE["ink"])
    loop_marker(chain_ctrl[1], chain_ctrl[2], r"$L_{BC}$", lib.PALETTE["ink"])

    # --- title + caption ---
    ax.text(2.5, 2.95, "1+1+1 decomposition  =  theta graph",
            ha="center", va="center", fontsize=15, fontweight="bold",
            color=lib.PALETTE["ink"])
    ax.text(2.5, -2.55,
            "Two rigid footprint hubs, three 1-chains.  Cycle rank = 2:\n"
            r"$L_{AB},\ L_{BC}$ independent; $L_{AC}=L_{AB}+L_{BC}$ (dependent)."
            "\nFoldable  ⟺  Tw($L_{ij}$) = 0  on the pairwise loops.",
            ha="center", va="top", fontsize=10, color="#444")

    ax.set_xlim(-1.3, 6.3)
    ax.set_ylim(-3.2, 3.3)

    os.makedirs(OUT, exist_ok=True)
    png = os.path.join(OUT, "theta_111.png")
    svg = os.path.join(OUT, "theta_111.svg")
    fig.savefig(png, dpi=150, bbox_inches="tight")
    fig.savefig(svg, bbox_inches="tight")
    plt.close(fig)
    print("wrote", os.path.relpath(png))
    print("wrote", os.path.relpath(svg))


if __name__ == "__main__":
    main()
