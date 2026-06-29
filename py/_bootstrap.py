"""_bootstrap.py — single source of truth for the engine's flat-import sys.path.

After the py/ reorg into purpose subfolders (engine/twist/storage/findings/render/export), the
modules still import each other by bare name (`import search`, `import store`, `import fold`).
Importing this module puts py/, every py/ subfolder, the repo root (for `import serve`) and
tests/ (for the lazy `enginelib` predict helper) on sys.path, so those bare imports resolve no
matter which subfolder the caller lives in.

Entry points (CLIs in py/<sub>/, plus serve.py / conftest.py / experimental scripts) do:
    sys.path.insert(0, <py/ dir>)
    import _bootstrap   # noqa: E402,F401
"""
import os
import sys

_PY = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_PY)
_SUBS = ("engine", "twist", "storage", "findings", "render", "export", "tri")
for _p in (_REPO, os.path.join(_REPO, "tests"), _PY,
           *(os.path.join(_PY, _s) for _s in _SUBS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
