"""render_foldpath.py — make-sheets that lead with the FOLDING PATH instead of crease type.

Sibling of make_foldsheets.py. Same cut/fold data (foldpattern.pattern_for), but the primary
visual is the panel-centre *spine* of each chain — the directed walk that runs perpendicular to
every crease. Following the spine and folding at each crossing (direction alternates M/V along
the walk) reproduces the stack, so the path replaces the red/blue M/V colouring: it is the same
information, read off as an order rather than per-edge.

Domino (2-chain): each placement has two cells (strand P / strand Q) joined by a rigid rung.
Both strands are drawn so EVERY crease gets its perpendicular crossing segment, but the near
rail (strand 0) is the bold, numbered main spine and the far rail is a dimmed ghost — so the
fold order reads off one line. Along-axis folds show as a 3-jump on the far rail (it leaps the
two holes the twin strand vacated — cf. hypothesis_2plus1_reduction.md §3b).

Creases are kept as thin grey reference lines (where to fold); slits stay bold teal (CUT);
the footprint is outlined; rigid domino rungs are faint grey (keep flat).

Usage:
  python render_foldpath.py                 # render the 4 model-decider sheets -> report/foldsheets/
  python render_foldpath.py all             # render the full 13-sheet validation queue
  python render_foldpath.py <file> <id>     # one ad-hoc case
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "explainer"))
import fold as Fold        # noqa: E402
import foldpattern as fp   # noqa: E402
import lib                 # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from make_foldsheets import CURATED, CHAIN_FILL, CHAIN_INK, resolve_file, two_chain_orient  # noqa: E402
from render_vectors import edge_arrow, pat_from_label  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "report", "foldsheets")

# the four model-selection deciders (TODO priority folds), in fold-first order
DECIDERS = [("6x5", 1), ("6x7", 8), ("6x6", 13), ("6x6", 7)]


def strand_centres(ch):
    """List of strands; each strand = ordered list of (cx, cy) panel centres along the fold."""
    pls = ch["placements"]
    nstr = len(pls[0]["cells"])
    out = []
    for si in range(nstr):
        out.append([(p["cells"][si][0] + 0.5, p["cells"][si][1] + 0.5) for p in pls])
    return out


def draw_spine(ax, pts, color, lw=2.8, z=8, ghost=False):
    """Directed polyline through pts with a mid-segment arrowhead on each step."""
    a = 0.35 if ghost else 0.97
    style = dict(color=color, lw=(lw * 0.6 if ghost else lw), zorder=z, alpha=a,
                 solid_capstyle="round", solid_joinstyle="round")
    if ghost:
        style["dashes"] = (2, 2)
    ax.plot([p[0] for p in pts], [p[1] for p in pts], **style)
    if ghost:
        return
    for p, q in zip(pts[:-1], pts[1:]):
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        dx, dy = q[0] - p[0], q[1] - p[1]
        L = (dx * dx + dy * dy) ** 0.5
        if L == 0:
            continue
        ux, uy = dx / L, dy / L
        ax.annotate("", xy=(mx + ux * 0.18, my + uy * 0.18),
                    xytext=(mx - ux * 0.18, my - uy * 0.18),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                    mutation_scale=15), zorder=z + 1)


def render(pat, out_path):
    m, n = pat["m"], pat["n"]
    mta = pat["meta"]
    cell_chain = {}
    for ci, ch in enumerate(pat["chains"]):
        for c in ch["cells"]:
            cell_chain[c] = ci
    footprint = set()
    for ch in pat["chains"]:
        footprint.update(ch["baseCells"])

    fig, ax = plt.subplots(figsize=(m * 0.62 + 5.4, max(n * 0.62 + 1.6, 4.6)))
    ax.set_aspect("equal")
    ax.axis("off")

    # cells tinted by chain
    for (x, y) in [(x, y) for y in range(n) for x in range(m)]:
        ci = cell_chain.get((x, y), None)
        fc = CHAIN_FILL[ci] if ci is not None else "white"
        lib.panel(ax, x, y, fc=fc, ec="#ddd", lw=0.8)
    for (x, y) in footprint:
        lib.panel(ax, x, y, fc="none", ec=lib.PALETTE["hub"], lw=2.6)

    # rigid domino rungs (keep flat) — faint
    for e in pat["rigid"]:
        a, b = e
        p, q = lib.shared_edge(a, b)
        ax.plot([p[0], q[0]], [p[1], q[1]], color="#d8d8d8", lw=1.2, zorder=3)
    # creases — thin grey reference (where to fold; direction alternates along the path)
    for e in pat["crease"]:
        a, b = e
        p, q = lib.shared_edge(a, b)
        ax.plot([p[0], q[0]], [p[1], q[1]], color="#9aa0a6", lw=1.4,
                solid_capstyle="round", zorder=4)
    # slits — bold teal dashed CUT
    for e in pat["slit"]:
        a, b = e
        p, q = lib.shared_edge(a, b)
        ax.plot([p[0], q[0]], [p[1], q[1]], color=lib.PALETTE["cut"], lw=2.4,
                dashes=(3, 2.2), solid_capstyle="round", zorder=6)

    # ---- folding spines (both rails per chain) ----
    for ci, ch in enumerate(pat["chains"]):
        col = CHAIN_INK[ci]
        rails = strand_centres(ch)
        for si, pts in enumerate(rails):
            ghost = si > 0   # near rail = bold main spine; far rail(s) dimmed
            draw_spine(ax, pts, col, z=8 + ci, ghost=ghost)
            if ghost:
                continue
            # step numbers along the main rail (top-left of each cell)
            for k, (cx, cy) in enumerate(pts):
                ax.text(cx - 0.27, cy - 0.27, str(k), ha="center", va="center",
                        color=col, fontsize=9, fontweight="bold", zorder=11,
                        bbox=dict(boxstyle="circle,pad=0.10", fc="white", ec=col,
                                  lw=0.6, alpha=0.9))
        # start marker on first cell of first strand
        sx, sy = rails[0][0]
        ax.plot(sx, sy, "o", color=col, ms=12, zorder=12)
        ax.text(sx, sy, "ABC"[ci], ha="center", va="center", color="white",
                fontsize=10, fontweight="bold", zorder=13)

    # ---- vector reflection overlay ----
    # Seed each shared crease (small hub-coloured arrow), reflect each side to its far end, and
    # draw the two final images bold. They coincide on one grid line iff reflection PASSes.
    verdict = Fold.reflection_verdict(pat["chains"])
    for d in verdict["pairs"]:
        eI, _ = Fold._hub_seed(d["Pi"], d["Pj"])
        edge_arrow(ax, d["Pi"][0], d["Pi"][1], eI, 1, lib.PALETTE["hub"],
                   L=0.5, lw=1.8, z=14, alpha=0.85, head=9)
        edge_arrow(ax, d["imgI"]["x"], d["imgI"]["y"], d["imgI"]["edge"], d["imgI"]["sign"],
                   CHAIN_INK[d["i"]], L=0.62, lw=2.8, z=15, head=13)
        edge_arrow(ax, d["imgJ"]["x"], d["imgJ"]["y"], d["imgJ"]["edge"], d["imgJ"]["sign"],
                   CHAIN_INK[d["j"]], L=0.62, lw=2.8, z=15, head=13)

    ax.set_xlim(-0.6, m + 0.4)
    ax.set_ylim(n + 0.4, -0.6)

    # ---- side panel ----
    tx = m + 0.8
    ax.text(tx, -0.2, f"{m}×{n}  #{mta['id']}   {mta['shape']} {mta['decomp']}   K={mta['K']}",
            ha="left", va="top", fontsize=13, fontweight="bold", color=lib.PALETTE["ink"])
    pred = mta.get("pred")
    if pred:
        col = "#2ca02c" if pred.startswith("FOLD") else "#d83232"
        ax.text(tx, 0.32, f"prediction: {pred}", ha="left", va="top",
                fontsize=11, fontweight="bold", color=col)
    phys = mta.get("physical")
    if phys:
        ax.text(tx, 0.32, f"physical fold: {phys}", ha="left", va="top", fontsize=11,
                fontweight="bold", color="#2ca02c" if phys == "FOLD" else "#d83232")
    orient = two_chain_orient(pat)
    orient_str = "none (1+1+1)" if orient == "?" else orient
    ax.text(tx, 0.75, f"2-chain: {orient_str}    (numbers = fold step; arrows = path order)",
            ha="left", va="top", fontsize=8.5, color="#666")
    vp = verdict["pass"]
    ax.text(tx, 1.12, f"vector reflection: {'PASS (rejoins)' if vp else 'FAIL (jams)'}",
            ha="left", va="top", fontsize=10.5, fontweight="bold",
            color="#2ca02c" if vp else "#d83232")

    yy = 2.0
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
        (CHAIN_INK[0], "solid", "fold path — follow arrows, panel order"),
        (lib.PALETTE["cut"], "dash", "slit — CUT"),
        ("#9aa0a6", "solid", "crease — fold here (M/V alternates on path)"),
        ("#d8d8d8", "solid", "rigid — domino rung, keep flat"),
        (lib.PALETTE["hub"], "solid", "footprint + shared-crease vector seed"),
        (CHAIN_INK[1], "solid", "reflected hub vector (bold = far-end image)"),
    ]
    for i, (color, ls, lab) in enumerate(legend_items):
        ly = yy + i * 0.6
        dash = (3, 2.2) if ls == "dash" else None
        kw = dict(color=color, lw=2.8, zorder=10, clip_on=False)
        if dash:
            kw["dashes"] = dash
        ax.plot([tx, tx + 0.55], [ly, ly], **kw)
        ax.text(tx + 0.7, ly, lab, ha="left", va="center", fontsize=8.5,
                color=lib.PALETTE["ink"])
    yy += len(legend_items) * 0.6 + 0.3
    ax.text(tx, yy, "Cut slits, then fold each crease the path crosses (alternating M/V).\n"
                    "FOLDABLE = collapses flat to the 3-cell footprint stack; else JAM.\n"
                    "Record in results/twoplus1_labels.json.",
            ha="left", va="top", fontsize=8, color="#555")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", dpi=130)
    plt.close(fig)
    return out_path


def render_set(cases):
    os.makedirs(OUT_DIR, exist_ok=True)
    done = []
    for grid, sid in cases:
        f = resolve_file(grid)
        if not f:
            print(f"  skip {grid} #{sid}: no results file")
            continue
        try:
            pat = fp.pattern_for(f, sid)
        except KeyError:
            print(f"  skip {grid} #{sid}: id not found")
            continue
        out = os.path.join(OUT_DIR, f"{grid}_{sid}_path.png")
        render(pat, out)
        done.append(os.path.relpath(out))
        print(f"   {os.path.relpath(out)}")
    print(f"rendered {len(done)} folding-path sheets")
    return done


def render_labels():
    """Render every decider in results/twoplus1_labels.json — BOTH the folding-path sheet and the
    detailed vector sheet — recovered by matching the canonical hash to a grid-valid enumerated
    candidate (cache-independent; the stored hash's coords aren't replayable). One enumeration per
    grid (pat_from_label caches it), so this also emits the vectors without re-enumerating."""
    import render_vectors as rv
    labels = json.load(open(os.path.join(HERE, "..", "results", "twoplus1_labels.json")))
    os.makedirs(OUT_DIR, exist_ok=True)
    done = []
    for e in labels:
        pat = pat_from_label(e)
        out = os.path.join(OUT_DIR, f"{e['grid']}_{e['id']}_path.png")
        render(pat, out)
        rv.render(pat, os.path.join(OUT_DIR, f"vectors_{e['grid']}_{e['id']}.png"))
        done.append(os.path.relpath(out))
        print(f"   {os.path.relpath(out)}  (+ vectors)")
    print(f"rendered {len(done)} deciders (path + vector sheets) from labels")
    return done


def render_grid(grid, out_dir):
    """Render EVERY distinct (D4-deduped) solution of a grid into out_dir — the exhaustive
    vet set. Filenames: <grid>_<id>_<shape>_<decomp>.png."""
    f = resolve_file(grid)
    if not f:
        print(f"  skip {grid}: no 3-stack results file")
        return []
    data = json.load(open(f))
    os.makedirs(out_dir, exist_ok=True)
    done = []
    for s in sorted(data["solutions"], key=lambda s: s["id"]):
        pat = fp.pattern_for(f, s["id"])
        shape = pat["meta"]["shape"]
        decomp = pat["meta"]["decomp"]
        out = os.path.join(out_dir, f"{grid}_{s['id']:02d}_{shape}_{decomp}.png")
        render(pat, out)
        done.append(os.path.relpath(out))
        print(f"   {os.path.relpath(out)}")
    print(f"{grid}: {len(done)} distinct solutions (D4-deduped, exhaustive)")
    return done


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 2 and not args[0].isdigit():
        pat = fp.pattern_for(args[0], int(args[1]))
        out = os.path.join(OUT_DIR, f"adhoc_{pat['meta']['id']}_path.png")
        print("wrote", render(pat, out))
    elif args and args[0] == "all":
        render_set(CURATED)
    elif args and args[0] == "labels":
        render_labels()
    elif args and args[0] == "vet":
        grids = args[1:] or ["6x4", "6x5"]
        vet_dir = os.path.join(OUT_DIR, "vet")
        for g in grids:
            render_grid(g, vet_dir)
        print(f"\nvet set -> {os.path.relpath(vet_dir)}/")
    else:
        render_set(DECIDERS)
