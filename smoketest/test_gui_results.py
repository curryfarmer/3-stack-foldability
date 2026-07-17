"""test_gui_results.py — gui/results.py bundle parsing + the ttk verdict view.

parse_bundle is pure -> tested off the committed fixture bundle (smoketest/fixtures/bundle/), which
carries the three shapes that matter: a proven square record ({json, foldsheet}), an UNPROVEN hex
record (full triangle set incl. reflect), and a proven equilateral record with NO reflect. ResultsView
is exercised against a hidden Tk root.
"""
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from gui import results   # noqa: E402

_BUNDLE = os.path.join(_REPO, "smoketest", "fixtures", "bundle", "fixtureaaaa1", "bundle.json")


def test_parse_bundle_rows_and_gate():
    rows, gate = results.parse_bundle(_BUNDLE)
    assert len(rows) == 3
    assert [r["proven"] for r in rows] == [True, False, True]
    assert gate is True                              # any(not proven) -> unproven bundle
    # every row's foldsheet thumb resolves to a real file (foldsheet preferred over overlay)
    for r in rows:
        assert r["thumb"] and os.path.isfile(r["thumb"])
        assert os.path.basename(r["thumb"]).startswith("foldsheet_")


def test_pick_thumb_preference_and_fallback():
    # foldsheet wins over overlay
    assert os.path.basename(results._pick_thumb("/b", "d",
        {"json": "x.json", "overlay": "o.png", "foldsheet": "f.png"})) == "f.png"
    # no known-visual key -> first non-json artifact
    assert os.path.basename(results._pick_thumb("/b", "d",
        {"json": "x.json", "weird": "w.png"})) == "w.png"
    # only json -> None
    assert results._pick_thumb("/b", "d", {"json": "x.json"}) is None
    assert results._pick_thumb("/b", "d", {}) is None


def test_results_view_populates(tk_root):
    rows, gate = results.parse_bundle(_BUNDLE)
    view = results.ResultsView(tk_root)
    view.show(rows, gate)
    assert view.rows() == rows
    assert view.badge_visible is True
    assert len(view.tree.get_children()) == 3
    # a proven-only bundle hides the badge
    view.show([r for r in rows if r["proven"]], False)
    assert view.badge_visible is False


@pytest.fixture
def tk_root():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()
