"""test_runner_pypy.py — runner._run_under_pypy translates every child failure mode WITHOUT hanging.

No real PyPy is needed: we monkeypatch runner._ENTRY to a STUB script (run under this same interpreter,
which _run_under_pypy invokes as `[pypy, _ENTRY]`) that simulates each mode. The stub reads opts from
stdin exactly like the real _engine_entry.py, so the whole stdin-file -> child -> stdout-file bridge is
exercised. The timeout case proves the Windows orphan/hang fix: the wall-clock cap actually bounds and
the child is reaped (no post-kill communicate() blocking on a held stdout pipe).
"""
import json
import os
import subprocess
import sys
import time

import runner


def _write_stub(tmp_path, name, body):
    """Write a stub interpreter-target script and return its path. I/O: (Path, str, str) -> str."""
    p = tmp_path / name
    p.write_text("import json, os, sys, time\n" + body, encoding="utf-8")
    return str(p)


def _pid_alive(pid):
    """Best-effort cross-platform liveness probe. I/O: (int) -> bool."""
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/NH"],
                             capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def test_success_returns_parsed_result(tmp_path, monkeypatch):
    # Stub echoes opts back inside ctx and exits 0 -> function returns the parsed (solutions, ctx, err).
    stub = _write_stub(tmp_path, "ok.py",
                       "opts = json.load(sys.stdin)\n"
                       "json.dump({'solutions': [1, 2], 'ctx': {'echo': opts}, 'err': None}, sys.stdout)\n")
    monkeypatch.setattr(runner, "_ENTRY", stub)
    monkeypatch.setenv("FOLD_PYPY_TIMEOUT", "15")
    solutions, ctx, err = runner._run_under_pypy(sys.executable, {"grid": "2x2"})
    assert solutions == [1, 2]
    assert ctx == {"echo": {"grid": "2x2"}}
    assert err is None


def test_unparseable_stdout_is_translated(tmp_path, monkeypatch):
    # Stub prints garbage but exits 0 -> unparseable-stdout error string, NOT a crash.
    stub = _write_stub(tmp_path, "garbage.py", "sys.stdout.write('not json {{{')\n")
    monkeypatch.setattr(runner, "_ENTRY", stub)
    monkeypatch.setenv("FOLD_PYPY_TIMEOUT", "15")
    solutions, ctx, err = runner._run_under_pypy(sys.executable, {})
    assert (solutions, ctx) == ([], {})
    assert err == "pypy engine produced no parseable result on stdout"


def test_wrong_shape_json_is_translated(tmp_path, monkeypatch):
    # Stub prints VALID json of the WRONG shape and exits 0. The dict-access that unpacks
    # solutions/ctx/err must be guarded too: a missing-key dict (KeyError), a bare `null`
    # (None not subscriptable -> TypeError) and a list (list indices must be int -> TypeError)
    # all translate to the same unparseable-result error, never a raised exception.
    for name, payload in (("misskey.py", "{'solutions': []}"),
                          ("nulljson.py", "None"),
                          ("listjson.py", "[1, 2, 3]")):
        stub = _write_stub(tmp_path, name,
                           "json.dump(%s, sys.stdout)\n" % payload)
        monkeypatch.setattr(runner, "_ENTRY", stub)
        monkeypatch.setenv("FOLD_PYPY_TIMEOUT", "15")
        solutions, ctx, err = runner._run_under_pypy(sys.executable, {})
        assert (solutions, ctx) == ([], {}), name
        assert err == "pypy engine produced no parseable result on stdout", name


def test_nonzero_exit_is_translated(tmp_path, monkeypatch):
    # Stub exits nonzero -> rc!=0 error string carrying the child's output.
    stub = _write_stub(tmp_path, "boom.py", "sys.stderr.write('boom detail'); sys.exit(3)\n")
    monkeypatch.setattr(runner, "_ENTRY", stub)
    monkeypatch.setenv("FOLD_PYPY_TIMEOUT", "15")
    solutions, ctx, err = runner._run_under_pypy(sys.executable, {})
    assert (solutions, ctx) == ([], {})
    assert err.startswith("pypy engine failed (rc=3):")
    assert "boom detail" in err


def test_timeout_is_bounded_and_reaped(tmp_path, monkeypatch):
    # Stub records its pid then sleeps far longer than the cap. The call must return the timeout error
    # within a few seconds (wall-clock bound) and leave no live child (tree reaped).
    pid_file = tmp_path / "child.pid"
    stub = _write_stub(tmp_path, "sleeper.py",
                       "open(os.environ['STUB_PID_FILE'], 'w').write(str(os.getpid()))\n"
                       "sys.stdout.flush()\n"
                       "time.sleep(30)\n")
    monkeypatch.setattr(runner, "_ENTRY", stub)
    monkeypatch.setenv("FOLD_PYPY_TIMEOUT", "2")
    monkeypatch.setenv("STUB_PID_FILE", str(pid_file))

    t0 = time.time()
    solutions, ctx, err = runner._run_under_pypy(sys.executable, {})
    elapsed = time.time() - t0

    assert (solutions, ctx) == ([], {})
    assert err.startswith("pypy engine timed out after")
    assert elapsed < 15, "timeout did not bound wall-clock (took %.1fs)" % elapsed

    # Best-effort: the child (pid it self-reported) must be gone shortly after the reap.
    if pid_file.exists():
        child_pid = int(pid_file.read_text().strip())
        for _ in range(20):
            if not _pid_alive(child_pid):
                break
            time.sleep(0.1)
        assert not _pid_alive(child_pid), "child %d orphaned after timeout" % child_pid
