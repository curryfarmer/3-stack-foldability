"""make_foldsheets.py — render printable "make-sheets" for a curated set of 2+1 solutions,
so the lead can cut + fold cardstock and label each foldable / non-foldable. Produces the
ground-truth set the 2+1 twist work will validate against (see FOLDING.md).

Each sheet (one PDF page per case) shows the flat m×n grid:
  - cells tinted by chain (which of the 3 stacks they fold into),
  - CREASE edges as solid lines coloured mountain (red) / valley (blue),
  - SLIT edges as bold teal dashed "cut" lines,
  - RIGID (2-chain domino internal) edges faint grey = keep attached, flat,
  - the 3 footprint/start cells outlined bold,
  - a side panel with the per-chain fold recipe + legend.

Also emits results/twoplus1_labels.json — the template the lead fills with verdicts.

Usage:  python3 make_foldsheets.py            # render curated set -> report/foldsheets/
        python3 make_foldsheets.py <file> <id>  # render one ad-hoc case
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "explainer"))
import foldpattern as fp   # noqa: E402
import lib                 # noqa: E402  (matplotlib primitives + grid.js palette)
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "report", "foldsheets")
RESULTS = os.path.join(HERE, "..", "results")

CHAIN_FILL = [lib.PALETTE["tintA"], lib.PALETTE["tintB"], "#eafaef"]
CHAIN_INK = [lib.PALETTE["chainA"], lib.PALETTE["chainB"], lib.PALETTE["chainC"]]

# Curated set: minimal, diverse, smallest-K. (file, id). Resolved against results/ by dims.
CURATED = [
    ("6x4", 1), ("6x4", 2),                          # K=8, smallest (L 2chain-H / -V)
    ("6x5", 1), ("6x5", 2), ("6x5", 3), ("6x5", 4), ("6x5", 5),  # K=10, suspected non-foldables
    ("6x6", 7), ("6x6", 1),                          # K=12 cross-check (L-H / L-V)
    ("9x4", 8),                                      # K=12, Rect footprint
    # predicted NEGATIVES by the 2+1 canonical-strand twist criterion (2026-06-07,
    # py/analyze_2plus1_reduction.py): canonical Tw=±720 — these test the criterion's
    # twisted predictions; everything above is predicted FOLDABLE (canonical Tw=0).
    ("6x6", 13), ("6x6", 18), ("6x7", 8),
]


def resolve_file(grid):
    """Find the 3-stack results file for a grid like '6x4' (skip 2-stack files)."""
    for f in sorted(__import__("glob").glob(os.path.join(RESULTS, f"{grid}_*.json"))):
        if "2stack" in os.path.basename(f):
            continue
        return f
    return None


def two_chain_orient(pat):
    for ch in pat["chains"]:
        if ch["kind"] == "2chain":
            b = ch["baseCells"]
            return "H" if b[0][0] != b[1][0] else "V"
    return "?"


def render(pat, out_path):
    m, n = pat["m"], pat["n"]
    mta = pat["meta"]
    # cell -> chain index
    cell_chain = {}
    for ci, ch in enumerate(pat["chains"]):
        for c in ch["cells"]:
            cell_chain[c] = ci
    footprint = set()
    for ch in pat["chains"]:
        footprint.update(ch["baseCells"])

    fig, ax = plt.subplots(figsize=(m * 0.62 + 5.2, max(n * 0.62 + 1.6, 4.2)))
    ax.set_aspect("equal")
    ax.axis("off")

    # cells (engine coords; +y down -> flip the y axis so it matches the live tool)
    for (x, y) in [(x, y) for y in range(n) for x in range(m)]:
        ci = cell_chain.get((x, y), None)
        fc = CHAIN_FILL[ci] if ci is not None else "white"
        lib.panel(ax, x, y, fc=fc, ec="#ccc", lw=0.8)
    # footprint outline (the 3 start cells)
    for (x, y) in footprint:
        lib.panel(ax, x, y, fc="none", ec=lib.PALETTE["hub"], lw=2.6)

    # edges
    for e in pat["slit"]:
        a, b = e
        lib.slit_edge(ax, a, b, lw=2.4)  # styled below by overdraw
        p, q = lib.shared_edge(a, b)
        ax.plot([p[0], q[0]], [p[1], q[1]], color=lib.PALETTE["cut"], lw=2.4,
                dashes=(3, 2.2), solid_capstyle="round", zorder=6)
    for e in pat["rigid"]:
        a, b = e
        p, q = lib.shared_edge(a, b)
        ax.plot([p[0], q[0]], [p[1], q[1]], color="#cfcfcf", lw=1.2, zorder=4)
    for e, meta in pat["crease"].items():
        a, b = e
        col = lib.PALETTE["mountain"] if meta["mv"] == "M" else lib.PALETTE["valley"]
        p, q = lib.shared_edge(a, b)
        ax.plot([p[0], q[0]], [p[1], q[1]], color=col, lw=3.0,
                solid_capstyle="round", zorder=7)

    # chain letters at base cells
    for ci, ch in enumerate(pat["chains"]):
        for c in ch["baseCells"]:
            cx, cy = c[0] + 0.5, c[1] + 0.5
            ax.text(cx, cy, "ABC"[ci], ha="center", va="center",
                    color=CHAIN_INK[ci], fontsize=12, fontweight="bold", zorder=9)

    ax.set_xlim(-0.6, m + 0.4)
    ax.set_ylim(n + 0.4, -0.6)   # flip: y=0 at top (screen convention)

    # ---- side panel: title, recipe, legend ----
    tx = m + 0.8
    ax.text(tx, -0.2, f"{m}×{n}  #{mta['id']}   {mta['shape']} {mta['decomp']}   K={mta['K']}",
            ha="left", va="top", fontsize=13, fontweight="bold", color=lib.PALETTE["ink"])
    ax.text(tx, 0.75, f"2-chain orientation: {two_chain_orient(pat)}",
            ha="left", va="top", fontsize=9, color="#666")

    yy = 1.7
    ax.text(tx, yy, "Fold recipe (per chain, in order):", ha="left", va="top",
            fontsize=10, fontweight="bold", color=lib.PALETTE["ink"])
    yy += 0.7
    arrowsym = {"L": "←", "R": "→", "U": "↑", "D": "↓"}
    for ci, ch in enumerate(pat["chains"]):
        seq = " ".join(arrowsym[a] for a in ch["foldArrows"])
        ax.text(tx, yy, f"{'ABC'[ci]} [{ch['kind']}] {tuple(ch['baseCells'][0])}: {seq}",
                ha="left", va="top", fontsize=9, color=CHAIN_INK[ci])
        yy += 0.6

    yy += 0.4
    legend_items = [
        (lib.PALETTE["valley"], "solid", "crease — valley (fold toward you)"),
        (lib.PALETTE["mountain"], "solid", "crease — mountain (fold away)"),
        (lib.PALETTE["cut"], "dash", "slit — CUT"),
        ("#cfcfcf", "solid", "rigid — keep attached, flat"),
        (lib.PALETTE["hub"], "solid", "start footprint (3 cells)"),
    ]
    # draw legend manually in data coords
    for i, (color, ls, lab) in enumerate(legend_items):
        ly = yy + i * 0.6
        dash = (3, 2.2) if ls == "dash" else None
        kw = dict(color=color, lw=2.8, zorder=10, clip_on=False)  # legend sits outside xlim
        if dash:
            kw["dashes"] = dash
        ax.plot([tx, tx + 0.55], [ly, ly], **kw)
        ax.text(tx + 0.7, ly, lab, ha="left", va="center", fontsize=8.5,
                color=lib.PALETTE["ink"])
    yy += len(legend_items) * 0.6 + 0.3
    ax.text(tx, yy, "Cut slits, fold creases in order, judge: collapses flat to the\n"
                    "3-cell footprint stack (FOLDABLE) vs self-blocks (NOT). Record in\n"
                    "results/twoplus1_labels.json.",
            ha="left", va="top", fontsize=8, color="#555")

    os.makedirs(OUT_DIR, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    labels = []
    rendered = []
    for grid, sid in CURATED:
        f = resolve_file(grid)
        if not f:
            print(f"  skip {grid} #{sid}: no results file")
            continue
        try:
            pat = fp.pattern_for(f, sid)
        except KeyError:
            print(f"  skip {grid} #{sid}: id not found")
            continue
        out = os.path.join(OUT_DIR, f"{grid}_{sid}.pdf")
        render(pat, out)
        rendered.append(os.path.basename(out))
        mta = pat["meta"]
        labels.append({"grid": grid, "id": sid, "canonicalHash": mta["canonicalHash"],
                       "shape": mta["shape"], "orient": two_chain_orient(pat),
                       "K": mta["K"], "foldable": None, "notes": ""})
    labels_path = os.path.join(RESULTS, "twoplus1_labels.json")
    json.dump(labels, open(labels_path, "w"), indent=2)
    print(f"rendered {len(rendered)} sheets -> {os.path.relpath(OUT_DIR)}/")
    for r in rendered:
        print(f"   {r}")
    print(f"labels template -> {os.path.relpath(labels_path)}  ({len(labels)} cases, foldable=null)")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 2:
        pat = fp.pattern_for(args[0], int(args[1]))
        out = os.path.join(OUT_DIR, f"adhoc_{pat['meta']['id']}.pdf")
        print("wrote", render(pat, out))
    else:
        main()
