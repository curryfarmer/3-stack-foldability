"""runner.py — engine launcher with an orthogonal PyPy toggle.

run_search(opts) runs the 3-stack engine. When FOLD_PY=pypy and a PyPy interpreter is
available (and we are not already on PyPy), it shells out to _engine_entry.py under PyPy
and marshals (solutions, ctx, err) back as JSON; otherwise it calls search.run in-process.

The multiprocessing toggle (FOLD_JOBS / opts['jobs']) lives inside search.run, so it
composes with PyPy: a PyPy child still fans work across processes. Live callbacks
(on_solution / is_cancelled) force the in-process path — they cannot cross the boundary.
"""
import json
import os
import platform
import shutil
import subprocess

import search as Search

_ENTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_engine_entry.py")


def _on_pypy():
    return platform.python_implementation() == "PyPy"


def _want_pypy():
    return os.environ.get("FOLD_PY", "").strip().lower() == "pypy"


def find_pypy():
    """Locate a PyPy interpreter: FOLD_PYPY_BIN override, then pypy / pypy3 on PATH.
    Returns an absolute path/command or None. (FOLD_PYPY_BIN lets a non-PATH install,
    e.g. a fresh winget package, be used without restarting the shell.)"""
    override = os.environ.get("FOLD_PYPY_BIN")
    if override:
        return override if (os.path.isfile(override) or shutil.which(override)) else None
    for name in ("pypy", "pypy3"):
        path = shutil.which(name)
        if path:
            return path
    return None


def pypy_available():
    """True iff a PyPy interpreter can be found (for tests / capability checks)."""
    return find_pypy() is not None


def run_search(opts, on_solution=None, is_cancelled=None):
    """Run the 3-stack search, optionally under PyPy. Returns (solutions, ctx, err)."""
    if _want_pypy() and not _on_pypy() and on_solution is None and is_cancelled is None:
        pypy = find_pypy()
        if pypy:
            return _run_under_pypy(pypy, opts)
    return Search.run(opts, on_solution, is_cancelled)


def _run_under_pypy(pypy, opts):
    """Marshal opts -> PyPy subprocess -> (solutions, ctx, err). The child inherits the
    environment (so FOLD_JOBS still applies) but with FOLD_PY cleared to avoid recursion."""
    child_env = {**os.environ, "FOLD_PY": ""}
    proc = subprocess.run(
        [pypy, _ENTRY],
        input=json.dumps(opts),
        capture_output=True,
        text=True,
        env=child_env,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"pypy engine failed (rc={proc.returncode}): {proc.stderr.strip()}")
    out = json.loads(proc.stdout)
    return out["solutions"], out["ctx"], out["err"]
