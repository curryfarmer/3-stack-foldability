"""test_killtree_reap.py — coverage for scripts/run_tests._killtree (whole-tree orphan reap).

The reaping machinery (_killtree + the timeout path in _run_suite) is what stops a hung suite
from orphaning its multiprocessing workers -- the multi-hour-hang / stray-python bug. It had ZERO
tests and could regress silently (a `/T` dropped from taskkill, a POSIX pkill typo), so this pins
the one property that matters: killing the target reaps its spawned descendants too, not just the
target itself.

Mechanism (borrowed from test_physical_suite.py's orphan test): every process in the tree writes an
incrementing counter to its own heartbeat file every ~50ms. A LIVE process's counter keeps climbing;
a reaped one's freezes. So "gone" is proved without process enumeration -- a survivor would keep its
heartbeat advancing after _killtree returned, and that is exactly what fails the test.

Tree shape (a genuine grandchild, not just a direct child):
    pytest  ->  parent script (proc, the "child")  ->  grandchild (spawned by the parent script)
_killtree(proc.pid) must freeze BOTH beats. On Windows `taskkill /F /T` reaps arbitrary depth; on
POSIX _killtree does `pkill -9 -P <pid>` (the grandchild is a direct child of proc.pid) plus
os.kill(proc.pid), so this 2-level tree is reaped on both platforms.

Cleanup is force-by-PID in a finally, using a private copy of the kill logic (NOT the SUT), so a red
assertion -- or a genuinely broken _killtree -- never leaves the spawned tree running.
"""
import os
import subprocess
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)              # so `scripts` resolves regardless of pytest invocation

from scripts.run_tests import _killtree    # noqa: E402  (the function under test; imports no engine)


# A single script that plays both roles: run as "parent" it spawns a TRUE grandchild (itself, as
# "grandchild") and records that pid, then every process beats its own counter file forever.
_TREE_SRC = '''
import os, sys, subprocess, time

role = sys.argv[1]
beat_dir = os.environ["BEAT_DIR"]

if role == "parent":
    gc = subprocess.Popen([sys.executable, "-u", __file__, "grandchild"], env=os.environ.copy())
    with open(os.path.join(beat_dir, "grandchild.pid"), "w") as f:
        f.write(str(gc.pid))

beat = os.path.join(beat_dir, role + "_beat.txt")
i = 0
while True:
    with open(beat, "w") as f:      # truncate+write+close each tick: a reader always sees the latest
        f.write(str(i))
    i += 1
    time.sleep(0.05)
'''


def _read_int(path):
    """Read a small int from a beat/pid file, tolerating a mid-write truncated (empty) read.

    I/O: (pathlib.Path) -> int | None."""
    for _ in range(6):
        try:
            txt = path.read_text(encoding="utf-8").strip()
        except OSError:
            txt = ""
        if txt:
            try:
                return int(txt)
            except ValueError:
                pass
        time.sleep(0.02)
    return None


def _wait_advancing(path, deadline=6.0):
    """Poll until path's counter is observed to INCREASE -- proves its writer process is live.

    Guards against a false pass: a fixture that never really started would have a frozen beat, which
    must not be mistaken for a successful reap. I/O: (Path, float) -> bool."""
    t0 = time.time()
    while time.time() - t0 < deadline:
        a = _read_int(path)
        time.sleep(0.15)
        b = _read_int(path)
        if a is not None and b is not None and b > a:
            return True
    return False


def _wait_frozen(path, deadline=8.0, window=0.6):
    """Poll until path's counter holds still across `window` (>=10 missed ticks) -- proves its writer
    is dead. Bounded by `deadline` to allow the kill a moment to settle. I/O: (Path, float, float) ->
    bool."""
    t0 = time.time()
    while time.time() - t0 < deadline:
        a = _read_int(path)
        time.sleep(window)
        b = _read_int(path)
        if a is not None and a == b:
            return True
    return False


def _force_kill(pid):
    """Best-effort force-kill a pid AND its tree, for cleanup only. A deliberate private copy of the
    kill logic (NOT _killtree) so teardown works even when the SUT is the thing that's broken. Never
    raises. I/O: (int) -> None."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True, text=True)
        else:
            subprocess.run(["pkill", "-9", "-P", str(pid)], capture_output=True, text=True)
            try:
                os.kill(pid, 9)
            except OSError:
                pass
    except Exception:
        pass


def test_killtree_reaps_whole_process_tree(tmp_path):
    """_killtree(target) must freeze BOTH the direct child's and the grandchild's heartbeats.

    Fast (<10s) and cross-platform: the tree is 2 levels deep, which both the Windows (/T) and POSIX
    (pkill -P + os.kill) branches of _killtree reap."""
    beat_dir = tmp_path / "beats"
    beat_dir.mkdir()
    script = tmp_path / "tree.py"
    script.write_text(_TREE_SRC, encoding="utf-8")
    env = dict(os.environ, BEAT_DIR=str(beat_dir))

    parent_beat = beat_dir / "parent_beat.txt"          # the direct child (proc) itself
    grand_beat = beat_dir / "grandchild_beat.txt"       # the true grandchild
    gc_pid_file = beat_dir / "grandchild.pid"

    proc = subprocess.Popen([sys.executable, "-u", str(script), "parent"], env=env)
    grandchild_pid = None
    try:
        # 1) prove the whole tree came alive (both beats advancing) before we kill anything.
        assert _wait_advancing(parent_beat), "fixture never started: parent heartbeat never advanced"
        assert _wait_advancing(grand_beat), "fixture never started: grandchild heartbeat never advanced"
        grandchild_pid = _read_int(gc_pid_file)
        assert grandchild_pid, "fixture never recorded a grandchild pid"

        # 2) the call under test.
        _killtree(proc.pid)

        # 3) both must go quiet within the bound -- a survivor keeps its counter climbing.
        assert _wait_frozen(parent_beat), "the direct child survived _killtree"
        assert _wait_frozen(grand_beat), \
            "the GRANDCHILD survived _killtree -- whole-tree reap regressed (a /T or -P was dropped)"
    finally:
        # Force-kill the tree by PID regardless of outcome, so a red test never leaks orphans.
        _force_kill(proc.pid)
        if grandchild_pid:
            _force_kill(grandchild_pid)
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
