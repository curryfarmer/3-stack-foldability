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
import tempfile

import search as Search

_ENTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_engine_entry.py")

# Wall-clock cap for the PyPy child so a wedged interpreter can't hang the parent forever. Generous
# by default (real searches run for hours); override via FOLD_PYPY_TIMEOUT (seconds) for shorter caps.
_PYPY_TIMEOUT_DEFAULT_S = 14400.0  # 4 hours

# On POSIX, put the child in its OWN session/process group so _killtree can killpg the whole group on
# timeout and reap ProcessPoolExecutor grandchildren (FOLD_JOBS>1); a plain kill()/`pkill -P` reaps
# only the direct child. Windows reaps the tree with `taskkill /F /T`, so it needs no spawn flag.
_CHILD_KW = {} if os.name == "nt" else {"start_new_session": True}


def _killtree(pid):
    """Kill pid AND its whole descendant tree so orphaned FOLD_JOBS grandchildren can't run forever.
    Windows: `taskkill /F /T`. POSIX: killpg the child's own session (see _CHILD_KW). I/O: (int) -> None."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True, text=True)      # tiny, bounded output: PIPE is fine here
    else:
        try:
            os.killpg(os.getpgid(pid), 9)                   # 9 = SIGKILL to the whole process group
        except OSError:
            try:
                os.kill(pid, 9)                             # group lookup failed: at least the child
            except OSError:
                pass


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


def _pypy_timeout_s():
    """Resolve the PyPy child timeout: env FOLD_PYPY_TIMEOUT (seconds) if a positive number, else the
    default. Empty / non-numeric / <= 0 all fall back to the default. I/O: () -> float."""
    try:
        v = float(os.environ.get("FOLD_PYPY_TIMEOUT", ""))
    except (TypeError, ValueError):
        return _PYPY_TIMEOUT_DEFAULT_S
    return v if v > 0 else _PYPY_TIMEOUT_DEFAULT_S


def _run_under_pypy(pypy, opts):
    """Marshal opts -> PyPy subprocess -> (solutions, ctx, err). The child inherits the environment
    (so FOLD_JOBS still applies) but with FOLD_PY cleared to avoid recursion. A timeout kills a wedged
    child, and any child failure (timeout, nonzero exit, unparseable stdout) is translated into a
    RETURNED err string -- consistent with the in-process (solutions, ctx, err) contract -- never a
    raised exception. I/O: (pypy path, opts) -> (solutions, ctx, err).

    Subprocess I/O contract: opts JSON is fed to the child's stdin from a temp file; the child's merged
    stdout+stderr is captured to a temp FILE (never a PIPE, so ProcessPoolExecutor grandchildren under
    FOLD_JOBS>1 can't hold a pipe write-handle and wedge a post-timeout read); a timeout reaps the whole
    process group/tree via _killtree, so the wall-clock cap actually bounds and workers never orphan."""
    child_env = {**os.environ, "FOLD_PY": ""}
    timeout = _pypy_timeout_s()
    in_fd, in_path = tempfile.mkstemp(prefix="pypy_in_", suffix=".json")
    out_fd, out_path = tempfile.mkstemp(prefix="pypy_out_", suffix=".json")
    os.close(out_fd)
    try:
        with os.fdopen(in_fd, "w", encoding="utf-8") as fin:
            fin.write(json.dumps(opts))
        with open(out_path, "w", encoding="utf-8") as fw, \
                open(in_path, "r", encoding="utf-8") as fin_r:
            try:
                proc = subprocess.Popen([pypy, _ENTRY], stdin=fin_r, stdout=fw,
                                        stderr=subprocess.STDOUT, env=child_env, **_CHILD_KW)
            except OSError as exc:
                return [], {}, f"pypy engine failed to start: {exc}"     # mirror run_tests.py spawn guard
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _killtree(proc.pid)                                     # reap child + FOLD_JOBS grandchildren
                try:
                    proc.wait(timeout=30)                               # after the killtree, not instead of it
                except subprocess.TimeoutExpired:
                    pass
                return [], {}, f"pypy engine timed out after {timeout}s (FOLD_PYPY_TIMEOUT)"
        with open(out_path, "r", encoding="utf-8", errors="replace") as f:
            captured = f.read()                                         # merged stdout+stderr of the child
    finally:
        for _p in (in_path, out_path):
            try:
                os.remove(_p)
            except OSError:
                pass
    if proc.returncode != 0:
        return [], {}, f"pypy engine failed (rc={proc.returncode}): {captured.strip()}"
    try:
        out = json.loads(captured)
        result = out["solutions"], out["ctx"], out["err"]
    except (ValueError, KeyError, TypeError):
        return [], {}, "pypy engine produced no parseable result on stdout"
    return result
