"""test_gui_storage.py -- the S12 opt-in result storage. Fast + Tk-guarded (no real fold): drives
App._resolve_out_dir / _cleanup_temp_dirs / close and checks the on-disk effect. Save OFF -> a fresh
tracked temp dir that is auto-cleaned; Save ON -> the user's chosen dir, never tracked, never deleted.
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
    """A headless App on a hidden Tk root. Teardown guards double-destroy since close() may already
    have destroyed the root."""
    root = require_tk()
    a = App(root, out_dir=str(tmp_path / "out"))
    yield a
    try:
        root.destroy()
    except Exception:
        pass


def test_save_off_creates_tracked_temp_then_cleans(app):
    d = app._resolve_out_dir()
    assert os.path.isdir(d)
    assert os.path.basename(d).startswith("foldgui_")
    assert d in app._temp_dirs
    app._cleanup_temp_dirs()
    assert not os.path.exists(d)
    assert app._temp_dirs == []


def test_save_on_uses_chosen_dir_untracked(app, tmp_path):
    target = tmp_path / "mysaves"
    app._save_var.set(True)
    app._save_dir.set(str(target))
    d = app._resolve_out_dir()
    assert d == os.path.abspath(str(target))          # abspath of the chosen dir
    assert d not in app._temp_dirs                    # a user dir is never auto-deleted


def test_consecutive_resolve_cleans_prior(app):
    d1 = app._resolve_out_dir()
    d2 = app._resolve_out_dir()
    assert d1 != d2
    assert not os.path.exists(d1)                     # the prior unsaved run was cleaned
    assert os.path.isdir(d2)
    assert app._temp_dirs == [d2]


def test_close_cleans_temp(app):
    d = app._resolve_out_dir()
    assert os.path.isdir(d)
    app.close()                                       # destroys the root -> called last
    assert not os.path.exists(d)
