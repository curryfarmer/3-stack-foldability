"""test_foldfilter.py — the pure filter shared by the GUI results table and the headless CLI.

No tkinter, no engine: gui.foldfilter is plain data-in/data-out, so this pins the predicate semantics
(stacks / decomp / vector / foldable, and the vector-None drop rule) that BOTH front-ends depend on.
"""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from gui import foldfilter                       # noqa: E402  (pure, no engine/tk)


def _rows():
    """A small mixed row set spanning the shapes fold_grid emits."""
    return [
        {"uid": "a", "stacks": 3, "decomp": "2+1", "foldable": True, "proven": True,
         "vector": {"exitFootprint": True, "parity": True, "reflection": True, "twist": True}},
        {"uid": "b", "stacks": 3, "decomp": "1+1+1", "foldable": False, "proven": True,
         "vector": {"exitFootprint": True, "parity": True, "reflection": True, "twist": False}},
        {"uid": "c", "stacks": 2, "decomp": None, "foldable": True, "proven": True,
         "vector": {"reflection": True, "twist": True, "foldable": True}},
        {"uid": "d", "stacks": 3, "decomp": "1+1+1", "foldable": None, "proven": False,
         "vector": None},                          # triangle-style: no structured vector
    ]


def _uids(rows):
    return [r["uid"] for r in rows]


def test_normalize_decomp_folds_both_spellings():
    assert foldfilter.normalize_decomp("2plus1") == "2+1"
    assert foldfilter.normalize_decomp("1plus1plus1") == "1+1+1"
    assert foldfilter.normalize_decomp("2+1") == "2+1"
    assert foldfilter.normalize_decomp(None) is None
    assert foldfilter.normalize_decomp("1+1+1+1") == "1+1+1+1"   # n-stack key passes through


def test_no_predicates_returns_all():
    rows = _rows()
    assert foldfilter.apply(rows) == rows


def test_stacks_filter():
    assert _uids(foldfilter.apply(_rows(), stacks=[2])) == ["c"]
    assert _uids(foldfilter.apply(_rows(), stacks=[3])) == ["a", "b", "d"]


def test_decomp_filter_normalizes():
    # a query in EITHER spelling matches the normalized row decomp
    assert _uids(foldfilter.apply(_rows(), decomps=["2plus1"])) == ["a"]
    assert _uids(foldfilter.apply(_rows(), decomps=["1+1+1"])) == ["b", "d"]


def test_foldable_filter_is_tristate():
    assert _uids(foldfilter.apply(_rows(), foldable=True)) == ["a", "c"]
    assert _uids(foldfilter.apply(_rows(), foldable=False)) == ["b"]      # None-foldable 'd' excluded


def test_require_vector_pass_and_fail():
    assert _uids(foldfilter.apply(_rows(), require_vector={"twist": True})) == ["a", "c"]
    assert _uids(foldfilter.apply(_rows(), require_vector={"twist": False})) == ["b"]
    assert _uids(foldfilter.apply(_rows(), require_vector={"reflection": True})) == ["a", "b", "c"]


def test_require_vector_drops_rows_without_a_vector():
    # 'd' has vector None -> dropped as soon as ANY vector component is demanded
    assert "d" not in _uids(foldfilter.apply(_rows(), require_vector={"reflection": True}))


def test_predicates_compose():
    got = foldfilter.apply(_rows(), stacks=[3], decomps=["2+1"], foldable=True,
                           require_vector={"reflection": True, "twist": True})
    assert _uids(got) == ["a"]


def test_apply_does_not_mutate_input():
    rows = _rows()
    snapshot = [dict(r) for r in rows]
    foldfilter.apply(rows, stacks=[3], require_vector={"twist": True})
    assert rows == snapshot


def test_vector_summary():
    assert foldfilter.vector_summary(None) == ""
    s = foldfilter.vector_summary({"exitFootprint": True, "parity": False, "twist": None})
    assert "exit✓" in s and "par✗" in s and "tw·" in s
