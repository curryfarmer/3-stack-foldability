"""render_square.py — matplotlib rendering of a square-lattice fold pattern from its detail blob.

Draws one candidate's STARTING footprint on the m×n grid: the three base cells colored + lettered by
chain, the footprint outlined, each chain's fold sequence (L/R/U/D) shown as a fanned arrow glyph and
spelled out, plus a verdict line. This is the printable to-test sheet — what a person folds from — not
a simulation of the folded result. Faithful to the viewer's convention (origin top-left, +x right,
+y down) but not pixel-identical; the index.csv beside the images carries the exact hashes.

Pure of engine state: it consumes the stored `detail_json` sol dict only (footprint + chains +
verdict), so no re-run is needed. Mirrors py/tri/trirender.py (figure -> patches -> savefig -> close).
"""
import os

import matplotlib
matplotlib.use("Agg")                       # headless: no display needed
import matplotlib.pyplot as plt             # noqa: E402
from matplotlib.patches import Rectangle, FancyArrow  # noqa: E402

CHAIN = ["#1f77b4", "#e8820c", "#2ca02c"]   # A / B / C (same palette as the tri track)
FOOTPRINT_EDGE = "#6f4fb0"
GRID_EDGE = "#dddddd"
INK = "#222222"
# Fold-direction unit vectors in SCREEN coords (+y is DOWN, matching the viewer / fold.py).
ARROW = {"L": (-1, 0), "R": (1, 0), "U": (0, -1), "D": (0, 1)}


def _cells(seq):
    """Normalize a list of {x,y} dicts (or [x,y] pairs) to (x, y) tuples."""
    out = []
    for c in seq:
        out.append((c["x"], c["y"]) if isinstance(c, dict) else (c[0], c[1]))
    return out


def _verdict_line(verdict):
    """One-line verdict summary: PASS/FAIL/–(undecided) per gate. I/O: (verdict dict) -> str."""
    order = [("arithmetic", "arith"), ("exitFootprint", "exit"), ("parity", "par"),
             ("vectorParity", "vpar"), ("reflection", "refl"), ("twist", "twist")]
    bits = []
    for key, label in order:
        v = verdict.get(key)
        bits.append(f"{label}={'–' if v is None else ('✓' if v else '✗')}")
    return "  ".join(bits)


def render(detail, m, n, out_path, *, title=None, dpi=150):
    """Render one fold pattern (the detail_json sol dict) on an m×n grid to out_path (PNG/PDF by
    extension). Returns out_path. I/O: (detail, m, n, out_path, ...) -> path."""
    fig, ax = plt.subplots(figsize=(max(4.5, m * 0.7 + 2.5), max(3.5, n * 0.7 + 1.6)))
    try:
        # base grid
        for y in range(n):
            for x in range(m):
                ax.add_patch(Rectangle((x, y), 1, 1, facecolor="white", edgecolor=GRID_EDGE,
                                       lw=0.8, zorder=1))

        # footprint outline (the tromino's three cells) — tolerate a detail blob missing it
        for (x, y) in _cells((detail.get("footprint") or {}).get("cells", [])):
            ax.add_patch(Rectangle((x, y), 1, 1, facecolor="none", edgecolor=FOOTPRINT_EDGE,
                                   lw=2.6, zorder=5))

        # chains: fill + letter the base cells, fan out the fold-sequence arrows from each chain centroid
        chain_notes = []
        for ci, ch in enumerate(detail.get("chains", [])):
            color = CHAIN[ci % len(CHAIN)]
            letter = chr(ord("A") + ci)
            base = _cells(ch.get("baseCells", []))
            for (x, y) in base:
                ax.add_patch(Rectangle((x, y), 1, 1, facecolor=color, edgecolor="none",
                                       alpha=0.32, zorder=2))
                ax.text(x + 0.5, y + 0.5, letter, ha="center", va="center", color=color,
                        fontsize=12, fontweight="bold", zorder=6)
            arrows = ch.get("foldArrows", [])
            if base:                                         # skip the arrow fan for an empty chain (no centroid)
                cx = sum(x for x, _ in base) / len(base) + 0.5
                cy = sum(y for _, y in base) / len(base) + 0.5
                for k, a in enumerate(arrows):
                    dx, dy = ARROW.get(a, (0, 0))
                    if (dx, dy) == (0, 0):                       # unknown direction: keep it in the note, skip the glyph
                        continue
                    off = 0.12 * (k - (len(arrows) - 1) / 2)     # fan multiple arrows so they don't overlap
                    ax.add_patch(FancyArrow(cx + (off if dx == 0 else 0), cy + (off if dy == 0 else 0),
                                            dx * 0.34, dy * 0.34, width=0.015, head_width=0.16,
                                            head_length=0.12, length_includes_head=True,
                                            color=color, zorder=7, alpha=0.9))
            chain_notes.append(f"{letter} ({ch.get('kind', '?')}): {'→'.join(arrows) or '·'}")

        ax.set_xlim(-0.3, m + 0.3)
        ax.set_ylim(n + 0.3, -0.3)                           # invert y -> +y down (viewer convention)
        ax.set_aspect("equal")
        ax.set_xticks(range(m + 1)); ax.set_yticks(range(n + 1))
        ax.tick_params(labelsize=6, length=0)
        ax.set_title(title or "", fontsize=10, fontweight="bold", color=INK)

        sub = f"{detail.get('decomposition', '?')}   " + "   ".join(chain_notes)
        ax.text(0.5, -0.02, sub, transform=ax.transAxes, ha="center", va="top", fontsize=7,
                color="#444", family="monospace")
        ax.text(0.5, -0.09, _verdict_line(detail.get("verdict", {})), transform=ax.transAxes,
                ha="center", va="top", fontsize=7, color="#444", family="monospace")

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    finally:
        plt.close(fig)                                       # always release the figure, even on error
    return out_path
