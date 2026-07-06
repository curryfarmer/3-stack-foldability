"""square/_bootstrap.py — sys.path setup for the square engine's flat bare imports.
Puts square/ (for `import lattice`) and square/{engine,twist,render} on sys.path so
every module resolves regardless of caller location."""
import os, sys
_PKG = os.path.dirname(os.path.abspath(__file__))
_SUBS = ("engine", "twist", "render")
for _p in (_PKG, *(os.path.join(_PKG, _s) for _s in _SUBS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
