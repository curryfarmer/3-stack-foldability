"""triangle/_bootstrap.py — sys.path setup for the triangle engine's flat bare imports.

Puts triangle/ (for `import lattice`) and triangle/tri (for bare `import righttri` etc.)
on sys.path so every module resolves regardless of caller location.
"""
import os
import sys

_PKG = os.path.dirname(os.path.abspath(__file__))
_SUBS = ("tri",)
for _p in (_PKG, *(os.path.join(_PKG, _s) for _s in _SUBS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
