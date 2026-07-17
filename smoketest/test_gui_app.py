"""test_gui_app.py — the scripted end-to-end for the fold-gui shell.

Tk constructs headlessly on this Windows box, so the App object is drivable without a display: fast
tests cover pick / select / fold-gate transitions + canvas construction for square AND a triangle
tiling; the slow test runs a REAL square fold end-to-end and asserts the results table + proven badge
populate. The only thing NOT covered here is the human's visual confirmation (the manual gate).
"""
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from gui.app import App   # noqa: E402


@pytest.fixture
def app(tmp_path):
    import tkinter as tk
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display / Tk unavailable")
    root.withdraw()
    a = App(root, out_dir=str(tmp_path / "out"))
    yield a
    root.destroy()


def test_pick_select_fold_gate(app):
    app.pick("square", 3, 3)
    assert len(app.geometry.ids) == 9
    conn = [k for k, c in enumerate(app.geometry.ids) if c[0] in (0, 1)]   # connected 2x3
    app.select(conn)
    assert app.fold_enabled is True
    assert app.canvas.selected_cells() == [app.geometry.ids[k] for k in sorted(conn)]
    app.select([0, 8])                         # opposite corners -> gap
    assert app.fold_enabled is False
    app.select([])                             # empty
    assert app.fold_enabled is False
    # a triangle tiling also constructs its canvas + selects
    app.pick("equilateral", 2, 2)
    assert len(app.geometry.ids) == 8
    app.select([0])
    assert app.fold_enabled is True


@pytest.mark.slow
def test_scripted_end_to_end_square(app):
    app.pick("square", 3, 3)
    conn = [k for k, c in enumerate(app.geometry.ids) if c[0] in (0, 1)]
    app.select(conn)
    assert app.fold_enabled
    app.fold(timeout=180, wait=True)
    rows = app.results.rows()
    assert rows and isinstance(rows[0]["proven"], bool)
    assert app.badge_visible == any(not r["proven"] for r in rows)
