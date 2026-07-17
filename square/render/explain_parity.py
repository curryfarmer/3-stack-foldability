"""explain_parity.py — reference diagrams for the orientation-aware vector-parity simplification.

Companion to the report section that reduces YYR vector parity to a parity check on two integers
(nH, nV) per sub-chain. Four figures, square track, all styled via figstyle (the single source of
truth shared with render_square / render_twist_2plus1):

  PARITY_1_involution.png   P1 — two same-axis folds restore the crease vector (componentwise flip
                            cancels in pairs; net effect depends only on nH mod 2, nV mod 2).
  PARITY_2_orientation.png  the rule — the footprint orientation fixes the A/B seam axis, which fixes
                            which fold count must be even (parallel_fold_axis; py/lattice/square.py).
  PARITY_3_worked.png       a real foldable 2+1 (6x6 #19): K=11 odd, both sub-chains nH even / nV odd
                            — the cross-chain lemma made concrete on engine data.
  PARITY_4_crosschain.png   the lemma — the four parity classes send the shared seam vector to four
                            distinct images, so alignment (P2) forces equal parity across sub-chains.

Convention here is math-style (+y UP, axis off) for the schematic panels (1, 2, 4); the worked
example (3) uses the viewer convention (+y down) via figstyle so it matches the foldsheets.

Run: .venv/Scripts/python.exe square/render/explain_parity.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # square/ on path
import _bootstrap  # noqa: E402,F401  (puts square/{engine,twist,render} on sys.path)
import figstyle as fs                                             # noqa: E402
import matplotlib.pyplot as plt                                   # noqa: E402  (Agg set by figstyle)
from matplotlib.patches import Rectangle, FancyArrowPatch         # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "report", "parity")
EXAMPLE = os.path.join(ROOT, "results", "2+1 testing", "to_fold", "6x6_19.json")

PANEL = "#444"                                                    # side-text colour (matches figstyle subnotes)


# ------------------------------------------------------------------ helpers ----

def _cell(ax, x, y, *, fc="white", ec=fs.GRID_EDGE, lw=0.9, z=1, alpha=1.0):
    ax.add_patch(Rectangle((x, y), 1, 1, facecolor=fc, edgecolor=ec, lw=lw, zorder=z, alpha=alpha))


def _vec(ax, p, q, *, color=fs.INK, lw=2.6, z=6, ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=15, color=color, lw=lw,
                                 ls=ls, zorder=z, shrinkA=0, shrinkB=0))


def _mirror(ax, x, y0, y1):
    """A vertical mirror (fold crease line) as a dashed grey rule."""
    ax.plot([x, x], [y0, y1], color="#999", lw=1.6, ls=fs.DASH, zorder=4)


def _panel(ax, x, y, text, *, size=9.5):
    ax.text(x, y, text, fontsize=size, va="top", ha="left", family="monospace",
            color=fs.INK, zorder=10)


def _title(ax, x, y, text, *, size=15):
    ax.text(x, y, text, fontsize=size, fontweight="bold", va="top", ha="left", zorder=10)


# ---------------------------------------------------- FIG 1: involution (P1) ----

def fig_involution():
    """Horizontal crease vector through two L-folds: reversed, then restored. A horizontal fold
    reflects across a vertical line, flipping the horizontal component; two flips cancel."""
    fig, ax = plt.subplots(figsize=(11.0, 5.4))
    # three states of a stacked cell-pair carrying a horizontal crease vector (top shared edge).
    # state s sits at x-offset ox; the crease vector spans the top edge of the lower cell.
    states = [(0, "R", "start:  w"), (3.4, "L", "after 1 L-fold:  reversed"),
              (6.8, "R", "after 2 L-folds:  restored")]
    for ox, d, _ in states:
        _cell(ax, ox, 0)                                         # lower cell
        _cell(ax, ox, 1)                                         # upper cell -> shared edge at y=1
        if d == "R":
            _vec(ax, (ox + 0.08, 1), (ox + 0.92, 1), color=fs.JUMP)
        else:
            _vec(ax, (ox + 0.92, 1), (ox + 0.08, 1), color=fs.JUMP)
    _mirror(ax, 2.2, -0.2, 2.2)                                  # first fold crease
    _mirror(ax, 5.6, -0.2, 2.2)                                  # second fold crease
    ax.text(2.2, 2.35, "fold", color="#999", ha="center", fontsize=8.5, style="italic")
    ax.text(5.6, 2.35, "fold", color="#999", ha="center", fontsize=8.5, style="italic")
    for ox, _, lab in states:
        ax.text(ox + 0.5, -0.5, lab, ha="center", fontsize=8.5, color=fs.INK)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_xlim(-0.4, 19.6); ax.set_ylim(-1.2, 4.2)
    _title(ax, 10.0, 4.0, "P1 — SAME-AXIS FOLDS ARE INVOLUTIVE")
    _panel(ax, 10.0, 3.35,
           "A fold reflects the strip across the crease.\n"
           "A horizontal (L/R) fold reflects across a\n"
           "vertical line, so it REVERSES the horizontal\n"
           "component of every crease vector; a vertical\n"
           "(U/D) fold reverses the vertical component.\n\n"
           "Reversals cancel in pairs, so the net effect\n"
           "of a sub-chain on a crease vector depends only\n"
           "on the PARITIES of its fold counts:\n\n"
           "   (nH mod 2,  nV mod 2)\n\n"
           "not on their sizes or the order of the folds.\n"
           "Here two L-folds (nH = 2, even) return w to its\n"
           "starting direction.")
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, "PARITY_1_involution.png"), dpi=fs.DPI, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------- FIG 2: orientation fixes the axis ----

def _footprint_row(ax, ox, oy, horizontal):
    """Draw a 3-cell footprint (horizontal or vertical) with the central A/B seam edge in green,
    and one parallel + one perpendicular fold crease to contrast them."""
    if horizontal:
        cells = [(ox, oy), (ox + 1, oy), (ox + 2, oy)]
    else:
        cells = [(ox, oy), (ox, oy + 1), (ox, oy + 2)]
    for (x, y) in cells:
        _cell(ax, x, y, ec="#888", lw=1.2)
        ax.add_patch(Rectangle((x, y), 1, 1, facecolor=fs.FOOTPRINT_EDGE, alpha=0.10, zorder=1))
    # the A/B seam = the shared edge between the two adjacent base cells (cells[0]|cells[1]).
    if horizontal:                                              # vertical seam at x=ox+1
        ax.plot([ox + 1, ox + 1], [oy, oy + 1], color=fs.SEAM, lw=4.0, zorder=6)
    else:                                                       # horizontal seam at y=oy+1
        ax.plot([ox, ox + 1], [oy + 1, oy + 1], color=fs.SEAM, lw=4.0, zorder=6)


def fig_orientation():
    fig, ax = plt.subplots(figsize=(11.4, 5.8))
    _footprint_row(ax, 0.0, 3.0, horizontal=True)
    ax.text(1.5, 2.7, "bases differ in x  ->  axis H", ha="center", fontsize=8.5, color=fs.INK)
    ax.text(1.5, 2.35, "vertical A/B crease (green)\nL/R folds run PARALLEL to it\n=> require nH even",
            ha="center", va="top", fontsize=8.0, color=fs.SEAM)
    _footprint_row(ax, 0.0, -2.0, horizontal=False)
    ax.text(2.2, 0.5, "bases differ in y  ->  axis V", ha="left", fontsize=8.5, color=fs.INK)
    ax.text(2.2, 0.1, "horizontal A/B crease (green)\nU/D folds run PARALLEL to it\n=> require nV even",
            ha="left", va="top", fontsize=8.0, color=fs.SEAM)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_xlim(-0.5, 15.5); ax.set_ylim(-2.4, 4.4)
    _title(ax, 5.6, 4.2, "THE RULE — ORIENTATION FIXES THE EVEN AXIS")
    _panel(ax, 5.6, 3.5,
           "parallel_fold_axis reads the seam straight from\n"
           "the two adjacent base cells (square.py:78):\n\n"
           "   bases differ in x  -> axis H -> nH even\n"
           "   bases differ in y  -> axis V -> nV even\n\n"
           "The folds that must be even are exactly those\n"
           "whose crease lines run PARALLEL to the A/B seam\n"
           "(YYR's vector-parity condition for that seam).\n"
           "The free (perpendicular) count is forced odd by\n"
           "P3 below, so only ONE clause is ever checked.\n\n"
           "1+1+1 has no single 2+1 A/B adjacency, so it\n"
           "falls back to the orientation-blind legacy rule\n"
           "  nH even AND nV odd   (vector_parity_check).")
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, "PARITY_2_orientation.png"), dpi=fs.DPI, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------- FIG 3: worked real example (6x6 #19) ----

def _seam_edge(ax, a, b):
    """Highlight the shared lattice edge between two manhattan-adjacent cells a, b (the A/B seam).
    Viewer convention: cell (x,y) spans [x,x+1] x [y,y+1], +y down."""
    if a[0] != b[0]:                                            # vertical seam between columns
        xe, y = max(a[0], b[0]), a[1]
        ax.plot([xe, xe], [y, y + 1], color=fs.SEAM, lw=4.5, zorder=8, solid_capstyle="round")
    else:                                                       # horizontal seam between rows
        x, ye = a[0], max(a[1], b[1])
        ax.plot([x, x + 1], [ye, ye], color=fs.SEAM, lw=4.5, zorder=8, solid_capstyle="round")


def fig_worked():
    d = json.load(open(EXAMPLE))
    m, n = d["m"], d["n"]
    fig, ax = fs.new_grid_axes(m, n, extra_w=4.8, ticklabels=False)
    fs.draw_grid_cells(ax, m, n)
    fs.draw_footprint(ax, fs.cells(d["footprint"]["cells"]))
    # base cells + letters, no fold-arrow glyphs (the fold sequence goes in the panel as text)
    rows, bases = [], []
    for ci, ch in enumerate(d["chains"]):
        letter = chr(ord("A") + ci)
        base = fs.cells(ch["baseCells"])
        bases.append((letter, base))
        fs.draw_base_cells(ax, base, fs.chain_color(ci), letter)
        rows.append((letter, ch["kind"], ch["foldArrows"], ch["nH"], ch["nV"]))
    # the A/B seam = the shared edge of the adjacent base-cell pair (mirrors parallel_fold_axis)
    (_, A), (_, B) = bases
    for a in A:
        for b in B:
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1:
                _seam_edge(ax, a, b)
    ax.set_title("6x6 #19 — foldable 2+1   (exit/parity/reflection all pass -> FOLD)",
                 color=fs.INK, fontsize=10)
    K = len(d["chains"][0]["foldArrows"])
    tx = m + 0.5
    lines = [
        f"K = mn/3 - 1 = {m*n}/3 - 1 = {K}   (odd)",
        "",
        "chain      folds (L/R/U/D)",
        "---------  -------------------------",
    ]
    for letter, kind, arrows, _, _ in rows:
        lines.append(f"{letter} {kind:<7}  {' '.join(arrows)}")
    lines += ["", "chain      nH   nV   (nH,nV) mod 2", "---------  ---  ---  -------------"]
    for letter, kind, _, nH, nV in rows:
        lines.append(f"{letter} {kind:<7}  {nH:>2}   {nV:>2}    ({nH % 2}, {nV % 2})")
    lines += [
        "",
        "green seam: bases differ in x -> axis H",
        "  -> require nH even -> 4, 8 PASS",
        "",
        "K odd => exactly one axis odd per chain;",
        "the SAME axis (V) is odd in both -> the",
        "horizontal footprint fixes V as that axis.",
    ]
    ax.text(tx, -0.1, "\n".join(lines), transform=ax.transData, va="top", ha="left",
            fontsize=8.0, family="monospace", color=fs.INK, zorder=10)
    return fs.save(fig, os.path.join(OUT, "PARITY_3_worked.png"))


# ------------------------------------------- FIG 4: cross-chain lemma (Klein four) ----

def fig_crosschain():
    """The four parity classes act on the shared seam vector as the Klein four-group {I, H, V, HV};
    each image is distinct, so two adjacent chains can only agree by sharing a parity class."""
    fig, ax = plt.subplots(figsize=(11.6, 5.8))
    # 2x2 of unit cells, each carrying the image of a generic seam vector under one parity class.
    classes = [
        (0, 3, "(even, even) = I", (0.15, 0.15), (0.85, 0.85), fs.CHAIN[2]),
        (2.2, 3, "(odd, even) = H-flip", (0.85, 0.15), (0.15, 0.85), fs.JUMP),
        (0, 0.4, "(even, odd) = V-flip", (0.15, 0.85), (0.85, 0.15), fs.CHAIN[0]),
        (2.2, 0.4, "(odd, odd) = half-turn", (0.85, 0.85), (0.15, 0.15), fs.FOOTPRINT_EDGE),
    ]
    for ox, oy, lab, p, q, col in classes:
        _cell(ax, ox, oy, ec="#888", lw=1.2)
        _vec(ax, (ox + p[0], oy + p[1]), (ox + q[0], oy + q[1]), color=col, lw=2.8)
        ax.text(ox + 0.5, oy - 0.18, lab, ha="center", va="top", fontsize=8.0, color=col,
                fontweight="bold")
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_xlim(-0.5, 14.6); ax.set_ylim(-0.9, 4.4)
    _title(ax, 4.0, 4.2, "CROSS-CHAIN LEMMA — ALIGNMENT FORCES EQUAL PARITY")
    _panel(ax, 4.0, 3.5,
           "Two sub-chains A, B meet at a shared crease;\n"
           "let w be the crease vector seeded there.\n\n"
           "By P1 each chain carries w to one of FOUR\n"
           "images, set by its parity class (left): the\n"
           "group generated by a horizontal and a vertical\n"
           "reflection. The four images are DISTINCT.\n\n"
           "P2 forces A's image and B's image of w to\n"
           "coincide, so A and B must share a parity class:\n\n"
           "   nH(A) = nH(B)  (mod 2)\n\n"
           "P3 (K odd) makes nV the opposite parity inside\n"
           "each chain, so the vertical counts match too.\n"
           "The three chains join through the hub, so the\n"
           "single parity pattern propagates to all of them.")
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, "PARITY_4_crosschain.png"), dpi=fs.DPI, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    fig_involution(); print("wrote PARITY_1_involution.png")
    fig_orientation(); print("wrote PARITY_2_orientation.png")
    fig_worked(); print("wrote PARITY_3_worked.png")
    fig_crosschain(); print("wrote PARITY_4_crosschain.png")
    print(f"-> {OUT}")
