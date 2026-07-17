"""dispatch.py — run the S7 orchestrator (scripts/fold_grid.py) for the GUI, orphan-free.

Routes ALL compute through fold_grid.py rather than the per-engine generate.py: fold_grid is the only
thing that resolves per-tiling dispatch, writes the `proven` bundle gui/results.py reads, AND already
file-redirects + taskkill-reaps its engine grandchildren. So gui/ imports NO engine here -- it only
subprocesses (mirrors gui/geometry_client, preserving the never-co-import invariant).

tk-agnostic on purpose: `fold_once` is a plain synchronous function (unit-testable without a display);
`Dispatch` wraps it on a worker thread and marshals nothing to tk itself -- the app hops the on_done
result back to the UI thread via root.after. A GUI Cancel that kills fold_grid must reap the tree
itself: fold_grid's own killtree only fires on its --timeout / Ctrl-C, not on being terminated. So
Dispatch.cancel() runs taskkill /F /T on the fold_grid pid (which /T-reaps the --jobs grandchildren).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from collections import namedtuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FOLD_GRID = os.path.join(_REPO, "scripts", "fold_grid.py")
_POLL_SECONDS = 0.25
_GRID_UID_RE = re.compile(r"gridUid=(\w+)")

# (returncode, bundle_path|None, grid_uid|None, output)
DispatchResult = namedtuple("DispatchResult", "returncode bundle_path grid_uid output")


def _killtree(pid):
    """Kill pid AND its descendant tree (a --jobs pool spawns grandchildren; taskkill /T is the only
    reliable Windows reap). Byte-identical to scripts/fold_grid.py:_killtree."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, text=True)
    else:
        subprocess.run(["pkill", "-9", "-P", str(pid)], capture_output=True, text=True)
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def write_grid_file(tiling, cells, stacks, path):
    """Write a fold-grid/1 file. `cells` are native ids straight from a dumped Geometry.ids (S8 proved
    they ARE fold-grid/1 cells). I/O: (str, list, list|None, str) -> str (the path)."""
    spec = {"schema": "fold-grid/1", "tiling": tiling, "cells": [list(c) for c in cells]}
    if stacks:
        spec["stacks"] = list(stacks)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(spec, f)
    return path


def build_argv(grid_file, out_dir, stacks=None, jobs=None, timeout=None, first=False, decomps=None):
    """The fold_grid.py command (interpreter + script + args). out_dir should be absolute so the bundle
    location is CWD-independent. `first` -> find-example mode; `decomps` -> restrict the square
    decompositions searched (e.g. "2+1"). I/O: (...) -> list[str]."""
    argv = [sys.executable, "-u", _FOLD_GRID, grid_file, "--out", out_dir]
    if stacks:
        argv += ["--stacks", ",".join(str(s) for s in stacks)]
    if jobs:
        argv += ["--jobs", str(jobs)]
    if first:
        argv += ["--first"]
    if decomps:
        argv += ["--decomps", decomps]
    if timeout is not None:
        argv += ["--timeout", str(timeout)]
    return argv


def parse_grid_uid(text):
    """The gridUid fold_grid flushes to stdout before any engine runs, or None. I/O: (str) -> str|None."""
    m = _GRID_UID_RE.search(text or "")
    return m.group(1) if m else None


def fold_once(tiling, cells, *, out_dir, stacks=None, jobs=None, timeout=None, first=False,
              decomps=None, on_line=None, on_proc=None, is_cancelled=None):
    """Run one fold_grid job to completion, orphan-free, tailing output live to `on_line`. Writes the
    grid-file into `out_dir`. `first` -> find-example mode; `decomps` -> restrict the square
    decompositions searched. `on_proc(proc)` (if given) receives the Popen so a caller can reap it on
    cancel; `is_cancelled()` (if given) is polled to kill early. Returns a DispatchResult; bundle_path
    is set only when rc==0 and the bundle exists. I/O: (...) -> DispatchResult."""
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    grid_file = write_grid_file(tiling, cells, stacks, os.path.join(out_dir, "_grid.json"))
    argv = build_argv(grid_file, out_dir, stacks=stacks, jobs=jobs, timeout=timeout,
                      first=first, decomps=decomps)

    fd, out_path = tempfile.mkstemp(prefix="gui_dispatch_", suffix=".out")
    os.close(fd)
    buf = []
    try:
        with open(out_path, "w", encoding="utf-8") as fw:
            proc = subprocess.Popen(argv, cwd=_REPO, stdout=fw, stderr=subprocess.STDOUT)
            if on_proc:
                on_proc(proc)
            with open(out_path, "r", encoding="utf-8", errors="replace") as fr:
                while True:
                    chunk = fr.read()
                    if chunk:
                        buf.append(chunk)
                        if on_line:
                            on_line(chunk)
                    if proc.poll() is not None:
                        tail = fr.read()
                        if tail:
                            buf.append(tail)
                            if on_line:
                                on_line(tail)
                        break
                    if is_cancelled and is_cancelled():
                        _killtree(proc.pid)
                        try:
                            proc.wait(timeout=30)
                        except subprocess.TimeoutExpired:
                            pass
                        break
                    time.sleep(_POLL_SECONDS)
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass

    output = "".join(buf)
    grid_uid = parse_grid_uid(output)
    bundle_path = None
    if proc.returncode == 0 and grid_uid:
        cand = os.path.join(out_dir, grid_uid, "bundle.json")
        if os.path.isfile(cand):
            bundle_path = cand
    return DispatchResult(proc.returncode, bundle_path, grid_uid, output)


class Dispatch:
    """Runs fold_once on a daemon worker thread and delivers the DispatchResult to on_done. cancel()
    taskkill-reaps the fold_grid process tree. Not thread-safe against concurrent start()s -- the GUI
    disables Fold while a run is in flight."""

    def __init__(self):
        self._proc = None
        self._cancelled = False
        self._thread = None

    def start(self, tiling, cells, *, out_dir, stacks=None, jobs=None, timeout=None, first=False,
              decomps=None, on_line=None, on_done):
        """Launch a background fold. `first` -> find-example mode; `decomps` -> restrict the square
        decompositions searched. on_done(DispatchResult) runs on the WORKER thread -- the app must
        marshal it to the UI thread (root.after). I/O: (...) -> None."""
        self._cancelled = False
        self._proc = None

        def _worker():
            result = fold_once(tiling, cells, out_dir=out_dir, stacks=stacks, jobs=jobs,
                               timeout=timeout, first=first, decomps=decomps, on_line=on_line,
                               on_proc=self._set_proc, is_cancelled=lambda: self._cancelled)
            on_done(result)

        self._thread = threading.Thread(target=_worker, name="fold-dispatch", daemon=True)
        self._thread.start()

    def _set_proc(self, proc):
        self._proc = proc

    def cancel(self):
        """Reap the in-flight fold_grid tree (taskkill /F /T). Safe to call when idle. I/O: () -> None."""
        self._cancelled = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            _killtree(proc.pid)

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()
