"""test_gui_results.py — gui/results.py bundle parsing + the ttk verdict view.

parse_bundle is pure -> tested off the committed fixture bundle (smoketest/fixtures/bundle/), which
carries the three shapes that matter: a proven square record ({json, foldsheet}), an UNPROVEN hex
record (full triangle set incl. reflect), and a proven equilateral record with NO reflect. ResultsView
is exercised against a hidden Tk root.
"""
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from gui import results   # noqa: E402

_BUNDLE = os.path.join(_REPO, "smoketest", "fixtures", "bundle", "fixtureaaaa1", "bundle.json")


def test_parse_bundle_rows_and_gate():
    rows, gate, _diag = results.parse_bundle(_BUNDLE)
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
    rows, gate, _diag = results.parse_bundle(_BUNDLE)
    view = results.ResultsView(tk_root)
    view.show(rows, gate)
    assert view.rows() == rows                         # full set stored regardless of filter
    assert view.badge_visible is True
    # Default filter is foldable-only (jams hidden): the tree shows exactly the foldable rows.
    foldable = [r for r in rows if r["foldable"] is True]
    assert len(view.tree.get_children()) == len(foldable)
    view._foldable_var.set("any")                      # opening it up reveals every record
    view._render()
    assert len(view.tree.get_children()) == 3
    # a proven-only bundle hides the badge
    view.show([r for r in rows if r["proven"]], False)
    assert view.badge_visible is False


def test_results_view_filter_bar_dedup(tk_root):
    """S12 removed the stacks/decomp DISPLAY filters (they are pre-fold search shapers in the top bar).
    The filter bar now exposes only the post-fold-only dimensions: foldable + gate vector."""
    view = results.ResultsView(tk_root)
    assert not hasattr(view, "_stacks_vars")
    assert not hasattr(view, "_decomp_vars")
    assert set(view._active_filters().keys()) == {"require_vector", "foldable"}


def test_foldable_filter_narrows_then_restores(tk_root):
    """The foldable tristate still bites: 'no' shows exactly the not-foldable rows; 'any' shows all."""
    rows, gate, _diag = results.parse_bundle(_BUNDLE)
    view = results.ResultsView(tk_root)
    view.show(rows, gate)
    not_foldable = [r for r in rows if r["foldable"] is False]
    assert not_foldable and len(not_foldable) < len(rows)   # fixture has a genuine mix
    view._foldable_var.set("no")
    view._render()
    assert len(view.tree.get_children()) == len(not_foldable)
    view._foldable_var.set("any")
    view._render()
    assert len(view.tree.get_children()) == len(rows)


# --------------------------------------------------------------------------- the empty-result diagnosis

def _write_empty_bundle(tmp_path, diagnosis):
    """A records-empty fold-bundle/1 carrying `diagnosis`, as the triangle path writes on a no-fold
    region (e.g. the hexagon-of-six). No engine subprocess -- parse_bundle is pure."""
    b = {"schema": "fold-bundle/1", "gridUid": "deadbeef", "tiling": "equilateral",
         "sheetCells": [], "stacks": [3], "configs": [{"stacks": 3, "status": "ok", "nRecords": 0}],
         "gateValidityUnproven": False, "diagnosis": diagnosis, "records": []}
    p = tmp_path / "bundle.json"
    p.write_text(json.dumps(b), encoding="utf-8")
    return str(p)


def test_parse_bundle_returns_the_diagnosis():
    """The third return value carries the reason; it is None when the bundle has no diagnosis key
    (e.g. the committed square/hex fixture), so older bundles keep parsing."""
    rows, gate, diag = results.parse_bundle(_BUNDLE)
    assert diag is None                                  # fixture predates the diagnosis field


def test_parse_bundle_surfaces_a_point_pivot_diagnosis(tmp_path):
    diag = {"kind": "fold-outside-model", "certain": True,
            "message": "a genuine 3-stack fold of this shape exists ... folds about a shared point ..."}
    rows, gate, got = results.parse_bundle(_write_empty_bundle(tmp_path, diag))
    assert rows == [] and got == diag


def test_diagnosis_headline_maps_each_kind():
    assert "cannot fold" in results.diagnosis_headline({"kind": "no-fold"})
    assert "cannot reach" in results.diagnosis_headline({"kind": "fold-outside-model"})
    assert "budget" in results.diagnosis_headline({"kind": "undetermined"})
    assert results.diagnosis_headline(None) == "0 records — nothing folded"       # plain fallback
    assert results.diagnosis_headline({"kind": "weird"}) == "0 records — nothing folded"


def test_empty_table_shows_the_diagnosis_headline(tk_root, tmp_path):
    """The view's zero-record line leads with the reason, not a bare 'nothing folded', when a
    diagnosis is present."""
    diag = {"kind": "fold-outside-model", "certain": True, "message": "…"}
    rows, gate, got = results.parse_bundle(_write_empty_bundle(tmp_path, diag))
    view = results.ResultsView(tk_root)
    view.show(rows, gate, got)
    assert "cannot reach" in view._count.cget("text")


def test_empty_table_without_diagnosis_keeps_plain_message(tk_root, tmp_path):
    rows, gate, got = results.parse_bundle(_write_empty_bundle(tmp_path, None))
    view = results.ResultsView(tk_root)
    view.show(rows, gate, got)
    assert view._count.cget("text") == "0 records — nothing folded"


# tk_root is the shared, Tk-unavailable-skipping fixture from smoketest/conftest.py.
