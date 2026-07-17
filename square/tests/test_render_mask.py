"""test_render_mask.py — an arbitrary drawn sheet draws only its region S, not the bounding rectangle.

Two levels:
  (i)  unit — figstyle.draw_grid_cells(mask=S) fills exactly the cells of S and no off-sheet cell.
  (ii) plumbing — render_square.render forwards detail["sheetCells"] to draw_grid_cells as the mask.

Contract spec'd in docs/guides/STYLE_SPEC.md §7.
"""
from matplotlib.patches import Rectangle

import figstyle as fs
import render_square

S = {(0, 0), (1, 0), (0, 1)}     # an L-tromino inside a 3x3 bounding box


def _cell_origins(ax):
    return {(int(round(p.get_x())), int(round(p.get_y())))
            for p in ax.patches if isinstance(p, Rectangle)}


def test_draw_grid_cells_masks_to_S():
    fig, ax = fs.new_grid_axes(3, 3)
    fs.draw_grid_cells(ax, 3, 3, mask=S)
    drawn = _cell_origins(ax)
    assert drawn == S, f"masked grid drew {drawn}, expected {S}"
    assert (2, 2) not in drawn, "an off-sheet cell was drawn"
    fs.plt.close(fig)


def test_draw_grid_cells_no_mask_is_full_grid():
    fig, ax = fs.new_grid_axes(3, 3)
    fs.draw_grid_cells(ax, 3, 3)             # mask=None -> the whole 3x3
    assert len(_cell_origins(ax)) == 9, "no-mask grid should draw all 9 cells (historic path)"
    fs.plt.close(fig)


def test_render_forwards_sheetcells_as_mask(tmp_path, monkeypatch):
    seen = {}

    def _recorder(ax, m, n, *, checker=False, mask=None):
        seen["mask"] = mask

    monkeypatch.setattr(render_square.fs, "draw_grid_cells", _recorder)
    detail = {"footprint": {"cells": []}, "chains": [], "verdict": {},
              "sheetCells": [[0, 0], [1, 0], [0, 1]]}
    render_square.render(detail, 3, 3, str(tmp_path / "m.png"))
    assert seen["mask"] == S, f"render did not forward sheetCells as the mask: {seen.get('mask')}"


def test_render_no_sheetcells_is_none_mask(tmp_path, monkeypatch):
    seen = {"mask": "unset"}

    def _recorder(ax, m, n, *, checker=False, mask=None):
        seen["mask"] = mask

    monkeypatch.setattr(render_square.fs, "draw_grid_cells", _recorder)
    detail = {"footprint": {"cells": []}, "chains": [], "verdict": {}}   # rectangle sheet, no sheetCells
    render_square.render(detail, 3, 3, str(tmp_path / "r.png"))
    assert seen["mask"] is None, "rectangle sheet must render the full grid (mask=None)"
