"""test_gui_nstack.py -- the S12 n-stack top-bar: the stacks spinbox, its per-N decomp row, and the
min-size fold gate. All fast + Tk-guarded (no real fold): they drive the App object headlessly and only
inspect widget state / the pure selectors, so a machine without Tk skips cleanly via conftest.require_tk.
"""
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from conftest import require_tk        # noqa: E402  (Tk-unavailable -> pytest.skip, single guard)
from gui.app import App               # noqa: E402


@pytest.fixture
def app(tmp_path):
    """A headless App on a hidden Tk root (skips where Tk is unavailable)."""
    root = require_tk()
    a = App(root, out_dir=str(tmp_path / "out"))
    yield a
    try:
        root.destroy()
    except Exception:
        pass


def test_decomp_row_children_by_n(app):
    """Setting the stacks spinbox rebuilds the decomp row: 0 children @2, 3 (label+2 boxes) @3,
    2 (label + '1+..+1' label) @>=4."""
    app._stacks.set(2)
    assert len(app._decomp_frame.winfo_children()) == 0
    app._stacks.set(3)
    assert len(app._decomp_frame.winfo_children()) == 3
    app._stacks.set(4)
    assert len(app._decomp_frame.winfo_children()) == 2


def test_selected_stacks_is_single_n(app):
    app._stacks.set(2)
    assert app._selected_stacks() == [2]
    app._stacks.set(6)
    assert app._selected_stacks() == [6]


def test_selected_decomps_only_at_n3_single_box(app):
    app._stacks.set(2)
    assert app._selected_decomps() is None            # 2-stack has no decomposition
    app._stacks.set(4)
    assert app._selected_decomps() is None            # n>=4 is always all-singleton
    app._stacks.set(3)
    assert app._selected_decomps() is None            # both boxes checked (default) -> unrestricted
    app._decomp_vars["1+1+1"].set(False)              # only 2+1 remains checked
    assert app._selected_decomps() == "2+1"


def test_min_size_gate_multiple_of_n(app):
    """An 8-cell rectangle folds at N where 8 % N == 0 (2, 4) and is gated off at N=3, with a hint."""
    app.pick("square", 2, 4)
    idx = list(range(len(app.geometry.ids)))
    assert len(idx) == 8
    app.select(idx)
    app._stacks.set(2)
    assert app.fold_enabled is True                   # 8 % 2 == 0
    app._stacks.set(4)
    assert app.fold_enabled is True                   # 8 % 4 == 0
    app._stacks.set(3)
    assert app.fold_enabled is False                  # 8 % 3 != 0
    assert "N=3" in app._status.get()
