"""test_gui_verdict_tracking.py -- the verdict that comes out of a REAL fold actually tracks: the
parsed record's foldable/proven survives the display path uncorrupted, is internally consistent, and
n-stack folds carry the requested stack count. All compute goes through gui.dispatch.fold_once, which
SUBPROCESSES scripts/fold_grid.py (never imports an engine here -- the co-import trap). Known-answer
grids + expected outcomes are copied from test_orchestrator.py rather than invented.

The default-gate test uses find-example (first=True) so it stays fast (~1-2s); the n-stack fold and the
reject-tracking fold re-run the engine at full stack counts and are marked `slow`.
"""
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from gui import dispatch, results     # noqa: E402  (gui only; the engine runs in a subprocess)

# 2x3 full rectangle: the canonical all-proven, foldable square case (test_orchestrator's
# rectangle_roundtrip grid). Folds at 3-stack.
_RECT_2x3 = [[x, y] for y in range(2) for x in range(3)]
# 2x4 full rectangle: 8 cells, a clean multiple of 4 for the all-singleton n-stack path.
_RECT_2x4 = [[x, y] for y in range(2) for x in range(4)]
# The 8-cell ring (test_orchestrator's ring8): folds at 2-stack, REJECTED at 3-stack (8 % 3 != 0).
_RING8 = [[0, 0], [1, 0], [2, 0], [0, 1], [2, 1], [0, 2], [1, 2], [2, 2]]


def test_verdict_tracks_through_display_default_gate(tk_root, tmp_path):
    """DEFAULT gate, fast (first=True): a known-foldable square rectangle at 3-stack. The parsed
    verdict must survive the ResultsView display path byte-for-byte, and each row must be internally
    consistent (proven is a bool; a twist-True vector implies foldable True)."""
    res = dispatch.fold_once("square", _RECT_2x3, out_dir=str(tmp_path), stacks=[3],
                             first=True, timeout=180)
    assert res.returncode == 0, res.output
    assert res.bundle_path and os.path.isfile(res.bundle_path), res.output

    rows, gate = results.parse_bundle(res.bundle_path)
    assert len(rows) >= 1
    assert any(r["foldable"] is True for r in rows), [r["foldable"] for r in rows]
    for r in rows:
        assert isinstance(r["proven"], bool)

    # DISPLAY FIDELITY: the tree cells (Tk stores every value as its str()) must equal the parsed row.
    view = results.ResultsView(tk_root)
    view.show(rows, gate)
    shown = view._shown                              # default filter passes everything -> == rows
    assert len(view.tree.get_children()) == len(shown)
    for i, r in enumerate(shown):
        iid = str(i)
        assert view.tree.set(iid, "uid") == str(r["uid"])
        assert view.tree.set(iid, "stacks") == str(r["stacks"])
        assert view.tree.set(iid, "foldable") == str(r["foldable"])
        assert view.tree.set(iid, "proven") == str(r["proven"])

    # INTERNAL CONSISTENCY on every row.
    for r in rows:
        assert isinstance(r["proven"], bool)
        vec = r.get("vector")
        if isinstance(vec, dict) and vec.get("twist") is True:
            assert r["foldable"] is True


@pytest.mark.slow
def test_nstack_fold_tracks_requested_stack_count(tmp_path):
    """The all-singleton n-stack path: an 8-cell 2x4 rectangle at N=4 must produce a bundle whose every
    record self-reports stacks==4 and a 1+1+1+1 (or None) decomposition."""
    res = dispatch.fold_once("square", _RECT_2x4, out_dir=str(tmp_path), stacks=[4], timeout=300)
    assert res.returncode == 0, res.output
    assert res.bundle_path and os.path.isfile(res.bundle_path), res.output
    rows, _gate = results.parse_bundle(res.bundle_path)
    assert all(r["stacks"] == 4 for r in rows), [r["stacks"] for r in rows]
    assert all(r["decomp"] in ("1+1+1+1", None) for r in rows), [r["decomp"] for r in rows]


@pytest.mark.slow
def test_reject_at_n3_produces_no_foldable_records(tmp_path):
    """Mirror the orchestrator's rejection expectation: the 8-cell ring at N=3 (8 % 3 != 0) is rejected.
    A bundle is still written, but it yields no foldable record (no proven 3-stack fold)."""
    res = dispatch.fold_once("square", _RING8, out_dir=str(tmp_path), stacks=[3], timeout=300)
    assert res.returncode == 0, res.output
    assert res.bundle_path and os.path.isfile(res.bundle_path), res.output
    rows, _gate = results.parse_bundle(res.bundle_path)
    assert not any(r["foldable"] is True for r in rows), [r["foldable"] for r in rows]
