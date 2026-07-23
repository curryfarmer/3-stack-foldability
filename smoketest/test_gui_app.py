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
    # A triangle tiling constructs its canvas + locks the stack count to 3 (triangle engines are
    # 3-stack / 1+1+1 only). A single cell is below the fold minimum; the full connected block clears
    # the size gate iff its cell count is a multiple of 3 -- the same divisibility the engine enforces.
    app.pick("equilateral", 2, 2)
    assert len(app.geometry.ids) == 8
    assert app._stacks_n() == 3
    app.select([0])
    assert app.fold_enabled is False
    app.select(list(range(len(app.geometry.ids))))
    assert app.fold_enabled is (len(app.geometry.ids) % 3 == 0)


def test_preview_popup_enlarges(app):
    """Double-clicking the preview opens a Toplevel holding the selected record's image at (up to) full
    resolution, with the image pinned so Tk does not GC it out of the window."""
    import tkinter as tk
    from gui import results as results_mod
    bundle = os.path.join(_REPO, "smoketest", "fixtures", "bundle", "fixtureaaaa1", "bundle.json")
    rows, _, _diag = results_mod.parse_bundle(bundle)
    row = next(r for r in rows if r.get("files"))
    try:
        app._on_row(row)                        # populate preview state (picks a default image kind)
        top = app._open_preview_popup()
    except tk.TclError:
        pytest.skip("no display / Tk image unavailable")
    assert top is not None and top.winfo_exists()
    assert app._popup_img is not None           # enlarged image kept alive
    assert top.winfo_children()                 # the image label is packed into the popup
    top.destroy()


def test_preview_popup_noop_without_image(app):
    """No selected record -> double-click is a harmless no-op (no window, no error)."""
    app._on_row(None)
    assert app._open_preview_popup() is None


def test_announce_no_fold_routes_title_by_kind(app):
    """The no-fold popup keys its title on the oracle's kind (a real fold the search can't reach reads
    differently from a genuine impossibility) and falls back to a plain message with no diagnosis.
    Routed through the injectable notifier, so nothing modal blocks the test."""
    seen = []
    app._notify = lambda title, msg: seen.append((title, msg))
    app._announce_no_fold({"kind": "no-fold", "message": "cannot at all"})
    app._announce_no_fold({"kind": "fold-outside-model", "message": "exists, missed"})
    app._announce_no_fold({"kind": "undetermined", "message": "budget"})
    app._announce_no_fold(None, fallback="hard fail")
    app._announce_no_fold(None)
    assert seen[0] == ("Cannot fold", "cannot at all")
    assert seen[1] == ("Folds — but the search can't reach it", "exists, missed")
    assert seen[2] == ("Fold undetermined", "budget")
    assert seen[3] == ("No fold", "hard fail")
    assert seen[4][0] == "No fold"                       # generic body when no diagnosis + no fallback


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


@pytest.mark.slow
def test_no_fold_region_pops_the_verdict(app):
    """A drawn region the search cannot fold pops its verdict as a message box, not only the bottom
    status line. A 1x6 strip 3-stacks by folding in half, which the footprint search misses, so the
    oracle's reason reaches the notifier."""
    seen = []
    app._notify = lambda title, msg: seen.append((title, msg))
    app.pick("square", 6, 1)
    app.select(list(range(len(app.geometry.ids))))       # the whole 1x6 strip
    assert app.fold_enabled
    app.fold(timeout=180, wait=True)
    assert app.results.rows() == []                      # nothing folded
    assert seen, "no-fold popup never fired"
    title, msg = seen[-1]
    assert title == "Folds — but the search can't reach it"
    assert "genuine 3-stack fold of this shape exists" in msg
