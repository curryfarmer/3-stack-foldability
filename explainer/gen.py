#!/usr/bin/env python3
"""Generate the first-principles twist-theory diagram set (SVG).

Run:  python3 gen.py        # renders every figure to ./svg/ and prints a manifest

Track A (A1-A12): 2-stack, the foundation.
Track B (B1-B5):  3-stack 1+1+1, the extension.
All schematics are idealized (hand-placed), independent of the fold engine.
"""

import numpy as np
import matplotlib.pyplot as plt

import lib as L
from lib import PALETTE as C
from matplotlib.patches import Rectangle, Polygon, Arc, FancyBboxPatch


# --------------------------------------------------------------------------
# local helpers
# --------------------------------------------------------------------------
def frame(ax, xlim, ylim):
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)


def bezier(ax, p0, p1, p2, color, lw=2.4, dashes=None, z=4, n=80):
    t = np.linspace(0, 1, n)[:, None]
    pts = (1 - t) ** 2 * np.array(p0) + 2 * (1 - t) * t * np.array(p1) + t ** 2 * np.array(p2)
    kw = dict(color=color, linewidth=lw, zorder=z, solid_capstyle="round")
    if dashes:
        kw["dashes"] = dashes
    ax.plot(pts[:, 0], pts[:, 1], **kw)


def hub(ax, c, w=0.9, h=2.6, label=None, sub=None):
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((c[0] - w / 2, c[1] - h / 2), w, h,
                                boxstyle="round,pad=0.04,rounding_size=0.12",
                                facecolor="#efeaf8", edgecolor=C["hub"],
                                linewidth=2.2, zorder=6))
    if label:
        ax.text(c[0], c[1], label, ha="center", va="center", color=C["hub"],
                fontsize=15, fontweight="bold", zorder=8)
    if sub:
        ax.text(c[0], c[1] - h / 2 - 0.28, sub, ha="center", va="top",
                color=C["hub"], fontsize=9.5, zorder=8)


def creases_slits_of_hc(cells):
    """Return (creases, slits) edge lists for a closed HC over `cells`."""
    cellset = set(cells)
    used = set()
    n = len(cells)
    for i in range(n):
        a, b = cells[i], cells[(i + 1) % n]
        used.add(frozenset((a, b)))
    # all interior adjacencies among the cells
    creases, slits = [], []
    seen = set()
    for (x, y) in cells:
        for (dx, dy) in ((1, 0), (0, 1)):
            nb = (x + dx, y + dy)
            if nb in cellset:
                e = frozenset(((x, y), nb))
                if e in seen:
                    continue
                seen.add(e)
                (creases if e in used else slits).append(((x, y), nb))
    return creases, slits


# ==========================================================================
# TRACK A — 2-STACK
# ==========================================================================
def A1_grid_to_graph():
    fig, ax = L.new_ax((5.4, 3.8))
    cells = L.rect_cells(3, 2)
    L.grid(ax, cells, fc="#f7f7f7", lw=1.3)
    # nodes + graph edges
    cset = set(cells)
    for (x, y) in cells:
        for (dx, dy) in ((1, 0), (0, 1)):
            nb = (x + dx, y + dy)
            if nb in cset:
                L.line(ax, L.center(*[float(v) for v in (x, y)]),
                       L.center(*[float(v) for v in nb]),
                       color=C["node"], lw=1.6, z=4)
    for (x, y) in cells:
        L.node(ax, L.center(x, y), r=0.11, color=C["node"], z=8)
    L.text(ax, *L.center(1, 1), "", fs=1)
    L.text(ax, 1.5, -0.42, "panel = node   ·   shared side = edge",
           fs=12, color=C["ink"])
    cx, cy = L.center(0, 0)
    L.text(ax, cx, cy + 0.30, r"$P_i$", fs=11, color=C["node"])
    ex, ey = (1.0, 0.5)
    L.text(ax, ex - 0.0, ey + 0.30, "edge", fs=10, color=C["node"])
    L.title(ax, "Tessellation → grid graph")
    frame(ax, (-0.5, 3.5), (-0.8, 2.4))
    return L.save(fig, "A1_grid_to_graph")


def A2_hc_creases_slits():
    fig, ax = L.new_ax((5.6, 3.6))
    # 4x2 perimeter HC (all 8 cells)
    cells = L.rect_cells(4, 2)
    order = [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (2, 1), (1, 1), (0, 1)]
    L.grid(ax, cells, fc="white", lw=1.3)
    creases, slits = creases_slits_of_hc(order)
    for e in slits:
        L.slit_edge(ax, *e)
    for e in creases:
        L.crease_edge(ax, *e)
    L.hc_path(ax, order, closed=True, marker=True)
    L.legend(ax, [(C["hc"], "dot", "HC path"),
                  (C["crease"], "solid", "crease (crossed)"),
                  (C["slit"], "dash", "slit (uncrossed)")],
             x=4.35, y=1.7)
    L.title(ax, "Hamiltonian circuit: creases vs slits")
    frame(ax, (-0.4, 7.2), (-0.5, 2.5))
    return L.save(fig, "A2_hc_creases_slits")


def A3_fold_is_reflection():
    fig, ax = L.new_ax((5.6, 3.4))
    # P_i at (0,0); crease at x=1; reflect onto (1,0)
    L.panel(ax, 0, 0, fc="white", lw=1.6, label=r"$P_i$", fs=13)
    # orientation marker (corner triangle) bottom-left of P_i
    ax.add_patch(Polygon([(0, 0), (0.34, 0), (0, 0.34)], closed=True,
                         facecolor=C["chainA"], edgecolor="none", zorder=3))
    # reflected ghost of P_i lands on (1,0); mirrored corner marker
    L.panel(ax, 1, 0, fc="#f0f4ea", ec=C["ghost"], lw=1.6, label=r"$P_i'$", fs=13)
    ax.add_patch(Polygon([(2, 0), (1.66, 0), (2, 0.34)], closed=True,
                         facecolor=C["chainA"], edgecolor="none", zorder=3))
    # crease (bold red) at x=1
    L.crease_edge(ax, (0, 0), (1, 0))
    # mirror line dashed
    L.mirror_line(ax, (1, -0.45), (1, 1.45))
    # curved fold arrow over the top
    L.curved_arrow(ax, (0.5, 1.06), (1.5, 1.06), rad=-0.45,
                   color=C["chevron"], lw=2.4, mut=16)
    L.text(ax, 1.0, 1.62, "reflect across crease", fs=11, color=C["chevron"])
    L.text(ax, 1.0, -0.62, "crease", fs=10, color=C["crease"])
    L.title(ax, "Folding = reflection across the shared crease")
    frame(ax, (-0.5, 2.5), (-0.9, 1.9))
    return L.save(fig, "A3_fold_is_reflection")


def A4_two_reflections_rotation():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.6, 3.8))
    # (a) parallel creases -> translation, gamma=0
    for x, lab in ((0, r"$P_i$"), (1, r"$P_{i+1}$"), (2, r"$P_{i+2}$")):
        L.panel(a1, x, 0, fc="white", lw=1.5, label=lab, fs=11)
    L.crease_edge(a1, (0, 0), (1, 0))
    L.crease_edge(a1, (1, 0), (2, 0))
    L.arrow(a1, (0.5, 1.35), (2.5, 1.35), color=C["hc"], lw=2.2, mut=15)
    L.text(a1, 1.5, 2.35, "(a) straight-through", fs=12, weight="bold")
    L.text(a1, 1.5, 1.80, r"creases $\parallel$ → translation, $\gamma=0$",
           fs=11, color=C["ink"])
    frame(a1, (-0.5, 3.1), (-0.6, 2.7))
    # (b) perpendicular creases -> rotation 180, gamma=+-180  (pivot = crease intersection (1,1))
    L.panel(a2, 0, 0, fc="white", lw=1.5, label=r"$P_i$", fs=11)
    L.panel(a2, 1, 0, fc="white", lw=1.5, label=r"$P_{i+1}$", fs=10)
    L.panel(a2, 1, 1, fc="#f0f4ea", ec=C["ghost"], lw=1.5, label=r"$P_{i+2}$", fs=10)
    L.crease_edge(a2, (0, 0), (1, 0))     # vertical crease x=1
    L.crease_edge(a2, (1, 0), (1, 1))     # horizontal crease y=1
    L.node(a2, (1.0, 1.0), r=0.06, color=C["chevron"])
    L.curved_arrow(a2, (0.55, 0.62), (1.42, 1.40), rad=0.42, color=C["chevron"],
                   lw=2.4, mut=16)
    L.text(a2, -0.05, 1.95, r"$2\alpha=180^\circ$ about (1,1)", fs=10.5,
           color=C["chevron"], ha="left")
    L.text(a2, 0.95, 2.55, "(b) L-turn", fs=12, weight="bold")
    L.text(a2, 0.95, -0.95, r"creases $\perp$ → rotation, $\gamma=\pm180^\circ$",
           fs=11, color=C["ink"])
    frame(a2, (-0.7, 2.6), (-1.25, 2.9))
    fig.suptitle("Two reflections = rotation by 2α  (α = angle between creases)",
                 fontsize=13, y=1.0)
    return L.save(fig, "A4_two_reflections_rotation")


def A5_gamma_square_cases():
    fig, axs = plt.subplots(1, 3, figsize=(9.2, 3.3))
    cases = [
        ("left", r"$\gamma=+180^\circ$  (s1)", C["valley"]),
        ("up", r"$\gamma=0$  (s2)", C["ink"]),
        ("right", r"$\gamma=-180^\circ$  (s3)", C["mountain"]),
    ]
    for ax, (exit_dir, lab, col) in zip(axs, cases):
        L.panel(ax, 0, 0, fc="white", lw=1.6, label=r"$P_{i+1}$", fs=11)
        # incoming from below (entered across s4)
        L.arrow(ax, (0.5, -0.85), (0.5, 0.04), color=C["hc"], lw=2.2, mut=14)
        # outgoing
        ends = {"left": (-0.85, 0.5), "up": (0.5, 1.85), "right": (1.85, 0.5)}
        starts = {"left": (-0.04, 0.5), "up": (0.5, 0.96), "right": (1.04, 0.5)}
        L.arrow(ax, starts[exit_dir], ends[exit_dir], color=col, lw=2.4, mut=15)
        ax.set_title(lab, fontsize=12, color=col)
        frame(ax, (-1.1, 2.1), (-1.1, 2.1))
    fig.suptitle("Square panel: the only rotations are γ ∈ {0, ±180°}",
                 fontsize=13)
    return L.save(fig, "A5_gamma_square_cases")


def A6_sigma_checkerboard():
    fig, ax = L.new_ax((5.6, 4.6))
    cells = L.rect_cells(5, 4)
    L.checkerboard(ax, cells, signs=True)
    # step arrow showing parity flip
    L.arrow(ax, L.center(1, 0), L.center(2, 0), color=C["chevron"], lw=2.2, mut=13)
    L.text(ax, 2.5, -0.55, "every unit step flips (x+y) mod 2", fs=11,
           color=C["chevron"])
    L.legend(ax, [(C["valley"], "fill", "even  → valley  σ=+1"),
                  (C["mountain"], "fill", "odd   → mountain σ=−1")],
             x=0.0, y=4.7, dy=0.5)
    L.title(ax, r"$\sigma=(-1)^{x+y}$ : the mountain/valley checkerboard")
    frame(ax, (-0.3, 5.3), (-0.9, 5.3))
    return L.save(fig, "A6_sigma_checkerboard")


def A7_local_rotation_g():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.4, 3.6))

    def stack(ax, order, title_txt):
        # order: list of (label, color) bottom->top
        for k, (lab, col) in enumerate(order):
            ax.add_patch(Rectangle((0, k * 0.5), 2.4, 0.42, facecolor=col,
                                   edgecolor="#333", linewidth=1.2, zorder=2))
            ax.text(1.2, k * 0.5 + 0.21, lab, ha="center", va="center",
                    color="white", fontsize=11, zorder=3, fontweight="bold")
        ax.set_title(title_txt, fontsize=11)
        frame(ax, (-0.4, 2.8), (-0.3, 2.0))

    stack(a1, [(r"$P_i$", C["chainA"]), (r"$P_{i+1}$", "#888"),
               (r"$P_{i+2}$", C["chainC"])],
          "valley → mountain:  $P_i$ ends UNDER")
    stack(a2, [(r"$P_{i+2}$", C["chainC"]), (r"$P_{i+1}$", "#888"),
               (r"$P_i$", C["chainA"])],
          "mountain → valley:  $P_i$ ends OVER")
    fig.suptitle(r"$g(i)=\sigma_i\,\gamma_i$ : same |rotation|, opposite twist sign",
                 fontsize=13)
    return L.save(fig, "A7_local_rotation_g")


def A8_odd_reflection_flip():
    fig, ax = L.new_ax((6.4, 3.4))
    # unfolded strip, alternating face-up / face-down
    for k in range(6):
        even = k % 2 == 0
        L.panel(ax, k, 1.4, fc=C["tintA"] if even else C["tintB"], lw=1.4,
                label=("up" if even else "dn"), fs=9,
                label_color=C["valley"] if even else C["mountain"])
        L.text(ax, k + 0.5, 2.05, f"k={k}", fs=9, color=C["ink"])
    L.text(ax, 3.0, 2.55, r"strip: reflection count $k$ at each panel", fs=11)
    # folded accordion cross-section -> two layers
    y0 = 0.0
    zig = [(0, y0), (0, y0 + 0.5)]
    xs = [0.3, 1.3, 2.3, 3.3, 4.3, 5.3]
    for i in range(6):
        yy = y0 + (0.0 if i % 2 == 0 else 0.42)
        L.panel(ax, xs[i] - 0.3, yy, s=0.6, fc=C["tintA"] if i % 2 == 0 else C["tintB"],
                lw=1.2)
    L.text(ax, 3.0, -0.5, "folded: even k → top stack (face-up) · odd k → bottom stack (face-down)",
           fs=10.5, color=C["ink"])
    L.text(ax, 3.0, -0.95, r"$\det=(-1)^k$  →  the two stacks ARE the even/odd classes",
           fs=11, color=C["ink"])
    L.title(ax, "Odd # reflections = flip = which of the two stacks")
    frame(ax, (-0.4, 6.6), (-1.3, 2.9))
    return L.save(fig, "A8_odd_reflection_flip")


def A9_even_loop_bipartite():
    fig, ax = L.new_ax((5.6, 3.4))
    cells = L.rect_cells(4, 2)
    order = [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (2, 1), (1, 1), (0, 1)]
    L.checkerboard(ax, cells, signs=True)
    L.hc_path(ax, order, closed=True, marker=True)
    L.text(ax, 2.0, -0.6, r"closed HC visits $2n$ panels (even, bipartite)", fs=11)
    L.text(ax, 2.0, -1.0, "→ even reflections → returns proper (face-up), loop closes",
           fs=10.5)
    L.title(ax, "A valid loop is always even-length")
    frame(ax, (-0.4, 4.4), (-1.3, 2.4))
    return L.save(fig, "A9_even_loop_bipartite")


def A10_tw_zero_2x4():
    fig, ax = L.new_ax((5.8, 3.6))
    cells = L.rect_cells(4, 2)
    order = [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (2, 1), (1, 1), (0, 1)]
    L.checkerboard(ax, cells, signs=False)
    L.hc_path(ax, order, closed=True, marker=True)
    # mark the 4 corner turns with g(i)=sigma*gamma : even/valley +pi, odd/mountain -pi
    for cell in ((0, 0), (3, 0), (3, 1), (0, 1)):
        even = (cell[0] + cell[1]) % 2 == 0
        lab = r"$+\pi$" if even else r"$-\pi$"
        col = C["valley"] if even else C["mountain"]
        cx, cy = L.center(*cell)
        L.text(ax, cx, cy + 0.24, lab, fs=11, color=col, weight="bold")
    L.text(ax, 2.0, 2.24, r"corner labels are $g(i)=\sigma_i\,\gamma_i$", fs=9.5,
           color=C["ink"])
    L.text(ax, 2.0, -0.55,
           r"Odd$(\mathcal{P})=-2\pi$,  Even$(\mathcal{P})=+2\pi$  →  $\sum g=0$",
           fs=11.5)
    L.text(ax, 2.0, -0.98,
           r"$Tw=\frac{1}{4\pi}\sum_i g(i)=0$   ✓  foldable",
           fs=12.5, color=C["cut"])
    L.title(ax, "Worked: 2×4 squares → Tw = 0")
    frame(ax, (-0.4, 4.4), (-1.3, 2.4))
    return L.save(fig, "A10_tw_zero_2x4")


def A11_tw_nonzero_hole():
    fig, ax = L.new_ax((5.4, 3.8))
    # 3x3 ring (center removed)
    ring = [(x, y) for x in range(3) for y in range(3) if (x, y) != (1, 1)]
    order = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2), (1, 2), (0, 2), (0, 1)]
    L.checkerboard(ax, ring, signs=False)
    # hole
    L.text(ax, *L.center(1, 1), "hole", fs=10, color=C["slit"])
    L.hc_path(ax, order, closed=True, marker=True)
    L.text(ax, 1.5, -0.55,
           r"Odd$(\mathcal{P})=0$,  Even$(\mathcal{P})=+4\pi$  →  $\sum g=4\pi$",
           fs=11)
    L.text(ax, 1.5, -0.98, r"$Tw=+1$   ✗  twisted (not foldable)",
           fs=12.5, color=C["mountain"])
    L.title(ax, "Worked: square ring (internal hole) → Tw = +1")
    frame(ax, (-0.4, 3.4), (-1.3, 3.3))
    return L.save(fig, "A11_tw_nonzero_hole")


def A12_cwf_band():
    fig, axs = plt.subplots(1, 3, figsize=(9.8, 3.8))
    th = np.linspace(0, 2 * np.pi, 200)

    # (a) flat annulus: Lk=0
    ax = axs[0]
    for r in (0.7, 1.0):
        ax.plot(r * np.cos(th), r * np.sin(th), color=C["hub"], lw=2.4)
    L.text(ax, 0, -1.55, r"flat:  $Lk=0$", fs=12)
    frame(ax, (-1.4, 1.4), (-1.95, 1.4))

    # (b) twisted band: Tw=1, Wr=0  (annulus with a crossing mark)
    ax = axs[1]
    for r in (0.7, 1.0):
        ax.plot(r * np.cos(th), r * np.sin(th), color=C["hub"], lw=2.4)
    ax.plot([-0.18, 0.18], [1.18, 0.82], color=C["mountain"], lw=3)
    ax.plot([-0.18, 0.18], [0.82, 1.18], color=C["mountain"], lw=3)
    L.text(ax, 0, 1.52, r"add $2\pi$ twist", fs=10, color=C["mountain"])
    L.text(ax, 0, -1.55, r"$Tw=1,\ Wr=0$", fs=12)
    frame(ax, (-1.4, 1.4), (-1.95, 1.95))

    # (c) coiled: Tw=0, Wr=1 (a coiled loop)
    ax = axs[2]
    t = np.linspace(0, 2 * np.pi, 300)
    x = np.cos(t) + 0.32 * np.cos(3 * t)
    y = np.sin(t) + 0.32 * np.sin(3 * t)
    ax.plot(x, y, color=C["hub"], lw=2.6)
    L.text(ax, 0, -1.95, r"relax:  $Tw=0,\ Wr=1$", fs=12)
    frame(ax, (-1.7, 1.7), (-2.35, 1.6))

    fig.suptitle(r"Călugăreanu–White–Fuller:  $Lk=Tw+Wr$  — invariant (no cutting)."
                 "\nFlat stacks need Wr = 0  →  must keep Tw = 0", fontsize=12, y=1.04)
    return L.save(fig, "A12_cwf_band")


# ==========================================================================
# TRACK B — 3-STACK 1+1+1
# ==========================================================================
def draw_theta(ax, highlight=None, dim_third=True, labels=True):
    """2 hubs S,E + 3 chains A(top) B(mid) C(bot). highlight=('A','B', dir...)."""
    S, E = (0.0, 0.0), (4.0, 0.0)
    ctrl = {"A": (2.0, 1.7), "B": (2.0, 0.0), "C": (2.0, -1.7)}
    col = {"A": C["chainA"], "B": C["chainB"], "C": C["chainC"]}
    for key in ("A", "B", "C"):
        active = highlight is None or key in highlight
        lw = 3.0 if active else 2.0
        color = col[key] if active else "#d7d9dc"
        bezier(ax, S, ctrl[key], E, color=color, lw=lw, z=4 if active else 3)
        if labels and active:
            ax.text(ctrl[key][0], ctrl[key][1] + (0.28 if key != "C" else -0.34),
                    key, ha="center", va="center", color=col[key],
                    fontsize=13, fontweight="bold", zorder=9)
    hub(ax, S, label="S")
    hub(ax, E, label="E")


def B1_structures_compared():
    fig, axs = plt.subplots(1, 3, figsize=(10.2, 3.4))
    th = np.linspace(0, 2 * np.pi, 120)
    # (a) simple loop
    ax = axs[0]
    ax.plot(1.1 * np.cos(th), 1.1 * np.sin(th), color=C["hc"], lw=2.8)
    for k in range(8):
        a = 2 * np.pi * k / 8
        L.node(ax, (1.1 * np.cos(a), 1.1 * np.sin(a)), r=0.10, color=C["node"])
    ax.set_title("2-stack: simple loop\n(rank 1)", fontsize=11)
    frame(ax, (-1.6, 1.6), (-1.6, 1.6))
    # (b) theta = 1+1+1
    ax = axs[1]
    draw_theta(ax)
    ax.set_title("1+1+1: theta graph\n3 chains, 2 hubs (rank 2)", fontsize=11)
    frame(ax, (-1.1, 5.1), (-2.4, 2.4))
    # (c) 2+1
    ax = axs[2]
    draw_theta(ax, labels=False)
    # thicken chain A to show 2-chain (double line)
    bezier(ax, (0, 0), (2.0, 1.7), (4, 0), color=C["chainA"], lw=5.0, z=5)
    bezier(ax, (0, 0), (2.0, 1.4), (4, 0), color="white", lw=1.6, z=6)
    ax.text(2.0, 2.0, "2-chain", ha="center", color=C["chainA"], fontsize=11)
    ax.set_title("2+1: theta,\none chain is a 2-chain", fontsize=11)
    frame(ax, (-1.1, 5.1), (-2.4, 2.6))
    fig.suptitle("Fold structures: loop vs theta graph", fontsize=13)
    return L.save(fig, "B1_structures_compared")


def B2_theta_anatomy():
    fig, ax = L.new_ax((6.6, 4.2))
    draw_theta(ax)
    hub(ax, (0, 0), label="S", sub="start footprint\n(fused, rigid)")
    hub(ax, (4, 0), label="E", sub="exit footprint\n(fused, rigid)")
    L.text(ax, 2.0, -2.55, r"cycle rank $= E-V+1 = 3-2+1 = 2$", fs=12)
    L.text(ax, 2.0, 2.55, "each chain A, B, C runs S → E", fs=11.5,
           color=C["ink"])
    L.title(ax, "1+1+1 = theta graph: 2 rigid hubs + 3 chains")
    frame(ax, (-1.4, 5.4), (-3.1, 3.0))
    return L.save(fig, "B2_theta_anatomy")


def B3_pairwise_loops():
    fig, axs = plt.subplots(1, 3, figsize=(10.2, 3.6))
    pairs = [("A", "B"), ("A", "C"), ("B", "C")]
    names = {("A", "B"): "loop AB", ("A", "C"): "loop AC", ("B", "C"): "loop BC"}
    for ax, pr in zip(axs, pairs):
        draw_theta(ax, highlight=pr)
        # direction arrows: first chain fwd S->E, second rev E->S
        ctrl = {"A": (2.0, 1.7), "B": (2.0, 0.0), "C": (2.0, -1.7)}
        L.arrow(ax, (1.6, ctrl[pr[0]][1] * 0.62 + 0.05),
                (2.4, ctrl[pr[0]][1] * 0.62 + 0.05), color=C["ink"], lw=1.8, mut=12)
        L.arrow(ax, (2.4, ctrl[pr[1]][1] * 0.62 - 0.05),
                (1.6, ctrl[pr[1]][1] * 0.62 - 0.05), color=C["ink"], lw=1.8, mut=12)
        ax.set_title(names[pr] + f"  ({pr[0]}→ , {pr[1]}←)", fontsize=11)
        frame(ax, (-1.1, 5.1), (-2.4, 2.4))
    fig.suptitle("Pairwise loops — only 2 of 3 independent (rank 2)\n"
                 r"$Tw(\mathrm{pair})=0 \;\Leftrightarrow\; T_A=T_B=T_C$",
                 fontsize=12.5)
    return L.save(fig, "B3_pairwise_loops")


def B4_chain_end_orphan():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.2, 3.4))
    # (a) open chain: pairs of reflections, last one orphan
    cells = [(k, 0) for k in range(5)]
    L.grid(a1, cells, fc="white", lw=1.4)
    creases = [((k, 0), (k + 1, 0)) for k in range(4)]
    for e in creases:
        L.crease_edge(a1, *e)
    # pair brackets over consecutive crease-pairs
    from matplotlib.patches import Arc
    for (cx, lab, col) in [(1.0, "pair", C["ink"]), (3.0, "pair", C["ink"])]:
        a1.add_patch(Arc((cx, 1.15), 1.7, 0.7, angle=0, theta1=20, theta2=160,
                         color=col, lw=2.0, zorder=6))
        a1.text(cx, 1.65, lab, ha="center", fontsize=10, color=col)
    # orphan at the hub end
    a1.add_patch(Arc((4.0, 1.15), 0.9, 0.7, angle=0, theta1=20, theta2=160,
                     color=C["mountain"], lw=2.4, zorder=6))
    a1.text(4.1, 1.7, "orphan", ha="center", fontsize=10, color=C["mountain"])
    L.text(a1, 4.5, -0.7, "hub", fs=10, color=C["hub"])
    a1.add_patch(Rectangle((4.62, -0.1), 0.5, 1.1, facecolor="#efeaf8",
                           edgecolor=C["hub"], lw=2.0, zorder=2))
    a1.set_title("open chain end:\ndangling single reflection (improper)", fontsize=11)
    frame(a1, (-0.4, 5.6), (-1.1, 2.1))
    # (b) hub fuses two chain ends -> pair restored
    hub(a2, (2.0, 0.0), w=1.0, h=2.2, label="hub")
    L.arrow(a2, (0.6, 0.6), (1.45, 0.3), color=C["chainA"], lw=2.6, mut=14)
    L.arrow(a2, (0.6, -0.6), (1.45, -0.3), color=C["chainB"], lw=2.6, mut=14)
    L.text(a2, 0.5, 0.95, "chain end", fs=10, color=C["chainA"])
    L.text(a2, 0.5, -0.95, "chain end", fs=10, color=C["chainB"])
    L.text(a2, 2.0, -1.65, "fused hub re-pairs the orphans\n→ even, proper, Tw defined",
           fs=10.5, color=C["hub"])
    L.text(a2, 2.0, 1.42, "fused-hub closure", fs=11, weight="bold")
    frame(a2, (-0.2, 4.0), (-2.1, 1.75))
    fig.suptitle("Chain-end orphan reflection (Q8) → fused hub closes it", fontsize=13)
    return L.save(fig, "B4_chain_end_orphan")


def B5_global_sigma_and_verdict():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 3.8))
    # (a) per-chain reset vs global checkerboard.
    # This chain starts on an ODD-parity cell, so global (x+y) and per-chain index
    # parity disagree everywhere -> the phase offset is visible.
    # global parity row (true (x+y) parity; here starts odd)
    for k in range(6):
        even = (k + 1) % 2 == 0   # chain offset by 1 -> starts "−"
        L.panel(a1, k, 1.2, fc=C["tintA"] if even else C["tintB"], lw=1.3)
        a1.text(k + 0.5, 1.4, "+" if even else "−", ha="center", va="center",
                color=C["valley"] if even else C["mountain"], fontweight="bold")
    L.text(a1, 3.0, 2.35, r"global $\sigma=(-1)^{x+y}$  (consistent)  ✓", fs=11,
           color=C["cut"])
    # per-chain reset row (index restarts at + regardless of position)
    for k in range(6):
        even = k % 2 == 0
        L.panel(a1, k, 0.0, fc=C["tintA"] if even else C["tintB"], lw=1.3)
        a1.text(k + 0.5, 0.2, "+" if even else "−", ha="center", va="center",
                color=C["valley"] if even else C["mountain"], fontweight="bold")
    L.text(a1, 3.0, -0.7, "per-chain index resets → phase offset  ✗ (old false neg.)",
           fs=10.5, color=C["mountain"])
    L.text(a1, 3.0, -1.15, "(chain starting on an odd-parity cell: rows disagree)",
           fs=9, color=C["ink"])
    a1.set_title("σ phase: global vs per-chain", fontsize=11)
    frame(a1, (-0.4, 6.4), (-1.6, 2.7))
    # (b) verdict contrast
    draw_theta(a2)
    L.text(a2, 2.0, 2.55, "pairs:  01:0   02:0   12:0", fs=11, color=C["cut"])
    L.text(a2, 2.0, -2.55, r"$T_A=T_B=T_C$   ✓ foldable", fs=12, color=C["cut"])
    L.text(a2, 2.0, -3.05, "(twisted case: one pair = 720  ✗)", fs=10,
           color=C["mountain"])
    frame(a2, (-1.1, 5.1), (-3.4, 3.1))
    fig.suptitle("Proposed 1+1+1 criterion: global-σ per-chain twist, require "
                 r"$T_A=T_B=T_C$", fontsize=12.5)
    return L.save(fig, "B5_global_sigma_and_verdict")


# ==========================================================================
FIGURES = [
    A1_grid_to_graph, A2_hc_creases_slits, A3_fold_is_reflection,
    A4_two_reflections_rotation, A5_gamma_square_cases, A6_sigma_checkerboard,
    A7_local_rotation_g, A8_odd_reflection_flip, A9_even_loop_bipartite,
    A10_tw_zero_2x4, A11_tw_nonzero_hole, A12_cwf_band,
    B1_structures_compared, B2_theta_anatomy, B3_pairwise_loops,
    B4_chain_end_orphan, B5_global_sigma_and_verdict,
]


def main():
    print(f"rendering {len(FIGURES)} figures → {L.SVG_DIR}")
    for fn in FIGURES:
        path = fn()
        print(f"  {fn.__name__:32s} → {path.split('/')[-1]}")
    print("done.")


if __name__ == "__main__":
    main()
