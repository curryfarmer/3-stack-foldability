"""test_gui_thumbs.py — gui/thumbs.load, both the Pillow path and the pure-Tk fallback.

Drives a real fixture PNG (48x36) through both code paths against a hidden Tk root; asserts the
returned Tk image is bounded by max_px.
"""
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from gui import thumbs   # noqa: E402

_PNG = os.path.join(_REPO, "smoketest", "fixtures", "bundle", "fixtureaaaa1",
                    "sq11aa22bb33", "foldsheet_sq11aa22bb33.png")


@pytest.fixture
def tk_root():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_load_pillow_path(tk_root):
    img = thumbs.load(_PNG, master=tk_root, max_px=24, use_pillow=True)
    assert img.width() <= 24 and img.height() <= 24


def test_load_tk_fallback(tk_root):
    # 48x36 downscaled to fit 24 -> integer subsample factor 2 -> 24x18
    img = thumbs.load(_PNG, master=tk_root, max_px=24, use_pillow=False)
    assert img.width() <= 24 and img.height() <= 24
