"""render_square.py — matplotlib FOLDSHEET of a square-lattice fold pattern from its detail blob.

Draws one 3-stack candidate's STARTING footprint on the m×n grid: the three base cells colored +
lettered by chain, the footprint outlined, each chain's fold sequence (L/R/U/D) shown as a fanned
arrow glyph and spelled out, a legend, plus a verdict line. This is the printable to-test sheet —
what a person folds from — not a simulation of the folded result. Faithful to the viewer's convention
(origin top-left, +x right, +y down) but not pixel-identical; the index.csv beside the images carries
the exact hashes.

Pure of engine state: it consumes the stored `detail_json` sol dict only (footprint + chains +
verdict), so no re-run is needed. All palette / grid / legend / save details come from figstyle, the
single source of truth shared with the 2-stack and 2+1-analysis renderers.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # square/ on path
import _bootstrap  # noqa: E402,F401  (puts square/{engine,twist,render} on sys.path)
import figstyle as fs                                            # noqa: E402
import twist_jump as tj                                          # noqa: E402  (real per-step replay)

_verdict_line = fs.verdict_line                                  # back-compat alias (gate ✓/✗/– line)


def render(detail, m, n, out_path, *, title=None, dpi=fs.DPI):
    """Render one fold pattern (the detail_json sol dict) on an m×n grid to out_path (PNG/PDF by
    extension). Returns out_path. I/O: (detail, m, n, out_path, ...) -> path."""
    fig, ax = fs.new_grid_axes(m, n, extra_w=2.2, ticklabels=False)   # foldsheet: cells locate position
    fs.draw_grid_cells(ax, m, n)
    fs.draw_footprint(ax, (detail.get("footprint") or {}).get("cells", []))

    # chains: fill + letter the base cells, fan out the fold-sequence arrows from each chain centroid
    chain_notes = []
    used_letters = []
    for ci, ch in enumerate(detail.get("chains", [])):
        color = fs.chain_color(ci)
        letter = chr(ord("A") + ci)
        used_letters.append((letter, color))
        base = fs.cells(ch.get("baseCells", []))
        fs.draw_base_cells(ax, base, color, letter)
        arrows = ch.get("foldArrows", [])
        placements = tj.replay(ch.get("baseCells", []), arrows, m, n)
        path = tj.strand_path(placements, 0)
        fs.draw_fold_path(ax, path, color)
        chain_notes.append(f"{letter} ({ch.get('kind', '?')}): {'→'.join(arrows) or '·'}")

    ax.set_title(title or "", color=fs.INK)

    # legend: one base-cell swatch per chain + footprint + the fold-direction glyph
    handles = [fs.patch_handle(color, f"base cell {letter}") for letter, color in used_letters]
    handles.append(fs.patch_handle("none", "footprint (folds-to stack)", alpha=1.0,
                                   edgecolor=fs.FOOTPRINT_EDGE))
    handles.append(fs.line_handle(fs.INK, "fold direction (L/R/U/D)"))
    fs.legend_panel(ax, handles)

    sub = f"{detail.get('decomposition', '?')}   " + "   ".join(chain_notes)
    fs.draw_subnotes(ax, [sub, fs.verdict_line(detail.get("verdict", {}))])
    return fs.save(fig, out_path, dpi=dpi)
