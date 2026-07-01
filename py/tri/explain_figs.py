"""explain_figs.py — explanatory diagrams for the twist machinery:
  EXPLAIN_1_sigma.png       how sigma + alternation work (orientation 2-colouring, derived)
  EXPLAIN_2_111twist.png    the 1+1+1 theta-graph twist math (AB/BC clean, AC seam, cocycle)
  EXPLAIN_3_square2plus1.png  why the SQUARE 2+1 jump-strand works (representative alternates colour)
  EXPLAIN_4_tri2plus1.png   why the TRIANGLE 2+1 strand is an unreliable predictor (all-UP => no
                            alternation; strand<->1-chain sublattice seam => fractional Tw)

All facts here were cross-checked against the engine (workflow wf_8463c0cb-d89).
Run: .venv/Scripts/python.exe py/tri/explain_figs.py
"""
import json, os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trilattice as TL
import tritwist as TW
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle, FancyArrowPatch, Circle

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "report", "tri")
RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "results")
UP, DN = "#cfe3f7", "#f7d6d6"          # UP=+1 blue, DOWN=-1 red tints
UPK, DNK = "#1f77b4", "#d83232"
CHAIN = ["#1f77b4", "#e8820c", "#2ca02c"]
INK = "#222"


def poly(t):
    return [TL.vcart(v) for v in TL.tri_vertices(t)]


def draw_region(ax, tris, label_sigma=True, alpha=1.0):
    for t in tris:
        ax.add_patch(Polygon(poly(t), closed=True, facecolor=(UP if TL.sigma(t) > 0 else DN),
                             edgecolor="#999", lw=0.8, zorder=1, alpha=alpha))
        if label_sigma:
            cx, cy = TL.centroid(t)
            ax.text(cx, cy, "+" if TL.sigma(t) > 0 else "−", ha="center", va="center",
                    color=(UPK if TL.sigma(t) > 0 else DNK), fontsize=9, zorder=3, fontweight="bold")
    ax.set_aspect("equal"); ax.axis("off")


def walk_arrows(ax, walk, color, z=6, lw=2.2):
    c = [TL.centroid(t) for t in walk]
    for k in range(len(c) - 1):
        ax.add_patch(FancyArrowPatch(c[k], c[k + 1], arrowstyle="-|>", mutation_scale=12,
                                     color=color, lw=lw, zorder=z, shrinkA=0, shrinkB=0))
    for k, (x, y) in enumerate(c):
        ax.add_patch(Circle((x, y), 0.10, color=color, zorder=z + 1))
        ax.text(x, y, str(k), ha="center", va="center", color="white", fontsize=6.5,
                zorder=z + 2, fontweight="bold")


# ----------------------------------------------------------------- FIG 1: sigma / alternation
def fig_sigma():
    lat = TL.TriLattice(4, 3)
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    draw_region(ax, lat.tris)
    # an edge-adjacent walk: sigma must flip every step (bipartite dual)
    walk = [(0, 0, "U"), (0, 0, "D"), (1, 0, "U"), (1, 0, "D"), (2, 0, "U"), (2, 0, "D")]
    walk = [t for t in walk if t in lat.adj]
    walk_arrows(ax, walk, "#333")
    xs = [p[0] for t in lat.tris for p in poly(t)]
    ys = [p[1] for t in lat.tris for p in poly(t)]
    tx = max(xs) + 0.4
    ax.set_xlim(min(xs) - 0.3, tx + 6.4)
    ax.set_ylim(min(ys) - 0.3, max(ys) + 0.3)
    ax.text(tx, max(ys), "σ  and  ALTERNATION", fontsize=15, fontweight="bold", va="top")
    ax.text(tx, max(ys) - 0.55,
            "σ is assigned by ORIENTATION only:\n"
            "   UP triangle  → σ = +1   (blue)\n"
            "   DOWN triangle → σ = −1   (red)\n"
            "Nothing else — not position, not the loop.\n\n"
            "Alternation is NOT assigned. It is forced:\n"
            "the dual graph is bipartite — every shared\n"
            "edge joins one UP to one DOWN. So each step\n"
            "of an edge-adjacent walk FLIPS orientation:\n"
            "   σ₀, −σ₀, σ₀, −σ₀, …   =  σ₀·(−1)ᵏ\n\n"
            "The black walk 0→5 visits edge-adjacent\n"
            "triangles, so its σ reads +,−,+,−,+,−.\n\n"
            "Twist:  γₖ = 2·(turn at centroid k)\n"
            "        Tw = Σ σ(tileₖ)·γₖ\n"
            "When σ alternates, Tw = ±Σ(−1)ᵏγₖ = ±Tw_index\n"
            "— that equality is WHAT MAKES Tw the physical\n"
            "twist. Break alternation and Tw stops meaning it.",
            fontsize=9.5, va="top", family="monospace", color=INK)
    fig.savefig(os.path.join(OUT, "EXPLAIN_1_sigma.png"), dpi=140, bbox_inches="tight")
    plt.close(fig)


# ----------------------------------------------------------------- FIG 2: 1+1+1 twist math
def fig_111():
    d = json.load(open(os.path.join(RES, "tri_K10_1plus1_all.json")))
    rec = d["records"][0]
    chains = [[tuple(t) for t in c] for c in rec["chains"]]
    region = sorted(set().union(*[set(c) for c in chains]))
    sub = TL.TriLattice(cells=region)
    fig, ax = plt.subplots(figsize=(11.2, 6.4))
    draw_region(ax, sub.tris, label_sigma=False)
    names = ["A (arm)", "B (mid)", "C (arm)"]
    for ci, w in enumerate(chains):
        for t in w:
            ax.add_patch(Polygon(poly(t), closed=True, facecolor=CHAIN[ci], alpha=0.22,
                                 edgecolor="none", zorder=2))
        walk_arrows(ax, w, CHAIN[ci], z=6)
    # start + end trapezoids
    start_fp = [w[0] for w in chains]
    end_fp = [w[-1] for w in chains]
    for fp, lab in ((start_fp, "START hub S"), (end_fp, "END hub")):
        for t in fp:
            ax.add_patch(Polygon(poly(t), closed=True, facecolor="none", edgecolor="#6f4fb0",
                                 lw=2.4, zorder=8))
    xs = [p[0] for t in sub.tris for p in poly(t)]
    ys = [p[1] for t in sub.tris for p in poly(t)]
    tx = max(xs) + 0.4
    ax.set_xlim(min(xs) - 0.3, tx + 7.6)
    ax.set_ylim(min(ys) - 0.3, max(ys) + 0.3)
    tw = rec["tw_named"]
    ax.text(tx, max(ys), "1+1+1 TWIST  (θ-graph)", fontsize=15, fontweight="bold", va="top")
    ax.text(tx, max(ys) - 0.5,
            "Three 1-chains A, B, C from the start hub\n"
            "(a trapezoid) to an end hub. Foldable ⇔ the\n"
            "paper has zero twist on EVERY pairwise loop:\n\n"
            "  loop AB = A + reverse(B)\n"
            "  loop BC = B + reverse(C)\n"
            "  loop AC = A + reverse(C)\n"
            "  γₖ = 2·turnₖ ,   Tw = Σ σₖ·γₖ\n\n"
            "  FOLDABLE ⇔ Tw(AB)=Tw(BC)=Tw(AC)=0\n"
            "  cocycle:  Tw(AC) = Tw(AB) + Tw(BC)\n\n"
            "AB, BC are fully edge-adjacent → σ ALTERNATES,\n"
            "every γ = ±120 (clean).\n"
            "AC closes across the two NON-adjacent hub\n"
            "cells → σ does NOT alternate, carries ±60 γ\n"
            "(they pair up; Tw stays a multiple of 360).\n\n"
            "THIS fold (K=10):\n"
            "  Tw(AB)=%+d   Tw(BC)=%+d   Tw(AC)=%+d\n"
            "  AB,BC ≠ 0  →  JAM (cannot flat-fold)."
            % (tw["AB"], tw["BC"], tw["AC"]),
            fontsize=9.5, va="top", family="monospace", color=INK)
    fig.savefig(os.path.join(OUT, "EXPLAIN_2_111twist.png"), dpi=140, bbox_inches="tight")
    plt.close(fig)


# ----------------------------------------------------------------- FIG 3: square 2+1 (works)
def fig_square():
    fig, ax = plt.subplots(figsize=(10.6, 6.0))
    W, H = 5, 5
    for x in range(W):
        for y in range(H):
            ax.add_patch(Rectangle((x, y), 1, 1, facecolor=("#e9e9e9" if (x + y) % 2 else "#ffffff"),
                                   edgecolor="#bbb", lw=0.8))
            ax.text(x + 0.5, y + 0.5, "+" if (x + y) % 2 == 0 else "−", ha="center", va="center",
                    color=("#1f77b4" if (x + y) % 2 == 0 else "#d83232"), fontsize=8)
    # 2-chain = 4 dominoes (orange). jump-strand keeps ONE cell per domino (black). One step is a
    # 3-JUMP (across a domino) so it stays connected; unit + 3-jump are both odd-Manhattan.
    dominoes = [((1, 0), (1, 1)), ((2, 0), (2, 1)), ((3, 0), (3, 1)), ((3, 2), (3, 3))]
    for (a, b) in dominoes:
        for c in (a, b):
            ax.add_patch(Rectangle(c, 1, 1, facecolor="#fde9c8", edgecolor="#e8820c", lw=1.4,
                                   alpha=0.55, zorder=2))
    reps = [(1, 0), (2, 0), (3, 0), (3, 3)]              # one representative per domino
    cen = [(x + 0.5, y + 0.5) for (x, y) in reps]
    labels = ["unit", "unit", "3-jump"]
    for k in range(len(cen) - 1):
        ax.add_patch(FancyArrowPatch(cen[k], cen[k + 1], arrowstyle="-|>", mutation_scale=13,
                                     color="#222", lw=2.2, zorder=6))
        mx, my = (cen[k][0] + cen[k + 1][0]) / 2, (cen[k][1] + cen[k + 1][1]) / 2
        ax.text(mx + 0.28, my, labels[k], color="#222", fontsize=7.5, style="italic", zorder=9)
    for k, (x, y) in enumerate(cen):
        ax.add_patch(Circle((x, y), 0.16, color="#222", zorder=7))
        ax.text(x, y, str(k), ha="center", va="center", color="white", fontsize=7.5,
                zorder=8, fontweight="bold")
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_xlim(-0.3, W + 6.6); ax.set_ylim(-0.3, H + 0.3)
    ax.text(W + 0.3, H, "SQUARE 2+1  (works)", fontsize=15, fontweight="bold", va="top")
    ax.text(W + 0.3, H - 0.5,
            "The 2-chain is a strip of dominoes (orange).\n"
            "The jump-strand keeps ONE cell per domino\n"
            "(black path). Each within-chain step is\n"
            "odd-Manhattan (unit, or a 3-jump at a turn),\n"
            "so x+y parity FLIPS every step →\n"
            "the kept strand ALTERNATES colour (+,−,+,−…).\n\n"
            "The engine scores the loop with loop-index\n"
            "parity (−1)ⁱ  (= the colour parity here), and\n"
            "the exit/parity/reflection GATES keep only\n"
            "the clean loops → Tw ∈ {0, ±720}.\n"
            "  Tw = 0  ⇔  flat-foldable.\n\n"
            "Key: the representative alternates colour AND\n"
            "the geometry stays on the square lattice.",
            fontsize=9.5, va="top", family="monospace", color=INK)
    fig.savefig(os.path.join(OUT, "EXPLAIN_3_square2plus1.png"), dpi=140, bbox_inches="tight")
    plt.close(fig)


# ----------------------------------------------------------------- FIG 4: triangle 2+1 (issue)
def fig_tri21():
    d = json.load(open(os.path.join(RES, "tri_K6_2plus1_all.json")))
    rec = next(r for r in d["records"] if r["holefree"] and not r["foldable"] and r["tw_clean"])
    strand = [tuple(t) for t in rec["strand"]]
    one = [tuple(t) for t in rec["one_chain"]]
    two = [tuple(t) for t in rec["two_tris"]]
    rib = [tuple(r) for r in rec["ribbon"]]
    region = sorted(set(two) | set(one))
    sub = TL.TriLattice(cells=region)
    fig, ax = plt.subplots(figsize=(11.6, 6.4))
    draw_region(ax, sub.tris, label_sigma=True)
    # ribbon rhombi outline
    for (i, j) in rib:
        for o in ("U", "D"):
            t = (i, j, o)
            if t in sub.adj:
                ax.add_patch(Polygon(poly(t), closed=True, facecolor="#fde9c8", alpha=0.35,
                                     edgecolor="none", zorder=2))
    # strong overlay so the story reads at a glance: strand = all UP (blue), 1-chain alternates
    for t in strand:
        ax.add_patch(Polygon(poly(t), closed=True, facecolor="#1f77b4", alpha=0.30,
                             edgecolor="none", zorder=3))
    for t in one:
        ax.add_patch(Polygon(poly(t), closed=True, facecolor="#2ca02c", alpha=0.22,
                             edgecolor="none", zorder=3))
    walk_arrows(ax, strand, "#222", z=6)
    walk_arrows(ax, one, "#2ca02c", z=6)
    sx, sy = TL.centroid(strand[len(strand) // 2])
    ax.text(sx, sy - 0.55, "strand: σ≡+1", color="#1f77b4", fontsize=8.5, ha="center",
            fontweight="bold", zorder=9)
    # the loop = strand + reversed(1-chain); its two cross-chain edges are the seams
    for (ta, tb) in ((strand[-1], one[-1]), (one[0], strand[0])):
        pa, pb = TL.centroid(ta), TL.centroid(tb)
        ax.add_patch(FancyArrowPatch(pa, pb, arrowstyle="-|>", mutation_scale=12, color="#d83232",
                                     lw=2.2, ls="dashed", zorder=7))
    pa, pb = TL.centroid(one[0]), TL.centroid(strand[0])
    ax.text((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2 + 0.22, "seams\n(off-lattice)", color="#d83232",
            fontsize=8, ha="center", fontweight="bold", zorder=9)
    xs = [p[0] for t in sub.tris for p in poly(t)]
    ys = [p[1] for t in sub.tris for p in poly(t)]
    tx = max(xs) + 0.4
    ax.set_xlim(min(xs) - 0.3, tx + 7.8)
    ax.set_ylim(min(ys) - 0.3, max(ys) + 0.3)
    ax.text(tx, max(ys), "TRIANGLE 2+1  (unreliable as computed)", fontsize=14,
            fontweight="bold", va="top")
    ax.text(tx, max(ys) - 0.55,
            "The canonical strand keeps the UP triangle of\n"
            "EVERY ribbon rhombus (black path). So along the\n"
            "strand σ ≡ +1 (all blue) — it does NOT alternate.\n\n"
            "FAILURE 1 (the model): with σ constant, the\n"
            "σ-weighting is degenerate, so Tw_σ = 0 is NOT a\n"
            "fold certificate (Tw_σ ≠ ±Tw_index here).\n\n"
            "FAILURE 2 (the geometry): strand centroids sit on\n"
            "a COARSE sublattice (spacing 1, 60° steps); the\n"
            "1-chain (green) sits on a FINE one (spacing 0.577,\n"
            "30° steps). The seam stitching them (red dashed)\n"
            "is a genuine off-lattice diagonal → fractional γ\n"
            "→ fractional Tw on turning ribbons.\n\n"
            "Both trace to the all-UP representative. A colour-\n"
            "alternating representative (like the square jump-\n"
            "strand) + a triangle gate MIGHT rescue it — open.\n"
            "The fold pattern itself is still physically valid.",
            fontsize=9.3, va="top", family="monospace", color=INK)
    fig.savefig(os.path.join(OUT, "EXPLAIN_4_tri2plus1.png"), dpi=140, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    fig_sigma(); print("wrote EXPLAIN_1_sigma.png")
    fig_111(); print("wrote EXPLAIN_2_111twist.png")
    fig_square(); print("wrote EXPLAIN_3_square2plus1.png")
    fig_tri21(); print("wrote EXPLAIN_4_tri2plus1.png")
