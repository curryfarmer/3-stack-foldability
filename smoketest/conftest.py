"""smoketest/conftest.py — shared GUI test fixtures.

Tk is optional on the runner: a machine may have a broken/absent Tcl-Tk (`_tkinter.TclError:
Can't find a usable init.tcl`) or no display at all. A GUI test that needs a live Tk root must
SKIP there, never ERROR. `require_tk()` is the single guard used by the shared `tk_root` fixture
(and available to any future GUI fixture) so the Tk-unavailable -> SKIP conversion lives in ONE
place and can't regress per-file. It catches ONLY TclError, so a real GUI logic bug still fails.
"""
import pytest


def require_tk():
    """Build a hidden Tk root, or skip if Tk is unavailable. I/O: () -> tkinter.Tk.

    Catches ONLY tkinter.TclError (broken init.tcl / no display) and converts it to a pytest.skip.
    Any other exception propagates so genuine bugs still surface as failures."""
    import tkinter as tk
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk unavailable (no usable init.tcl / no display)")
    root.withdraw()
    return root


@pytest.fixture
def tk_root():
    """A hidden Tk root for GUI tests; skips cleanly where Tk is unavailable."""
    root = require_tk()
    yield root
    root.destroy()
