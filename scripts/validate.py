"""scripts/validate.py — thin dispatcher: run the triangle and square regression-proof scripts,
each in its OWN subprocess, and report both summaries.

WHY SUBPROCESS ISOLATION (not a plain import). `triangle/` and `square/` are independent
installable subpackages that each put their own bare-named `lattice` module on `sys.path` (see
`triangle/_bootstrap.py` / `square/_bootstrap.py`). Importing both `validate_triangle` and
`validate_square` into the SAME interpreter would race whichever `_bootstrap` ran second — the
second `import lattice` anywhere downstream would silently resolve to the wrong package's
`lattice/`. This module therefore never imports either validate_* module directly; it only
`subprocess.Popen([sys.executable, ...])`s them, exactly as instructed.

WINDOWS ORPHAN TRAP (why this uses Popen + a file, never subprocess.run + PIPE, and always a
timeout). `subprocess.run(capture_output=True)` with no timeout cannot bound validate_square's
multi-hour cold run, and its PIPE cannot be reaped: killing the child orphans any
ProcessPoolExecutor grandchildren, which inherited the pipe's write handle and hold it — and the
run — open forever. Redirecting to a FILE means there is no pipe to hold, and `taskkill /F /T` reaps
the whole tree. Pattern lifted from scripts/phystest/check.py and scripts/run_tests.py.

Exit code: nonzero if either subprocess exited nonzero (a real mismatch, a hard failure, or a
timeout), OR if BOTH ground-truth sources are absent (nothing was validated at all). A single skip
(fresh clone missing one gitignored local source) is reported distinctly but does not by itself
fail the run.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent

_DEFAULT_TIMEOUT = 4 * 60 * 60      # 4h. Bounds a genuine hang; validate_square's cold run is
                                    # dominated by the big grids and can run for hours. Not a
                                    # performance expectation — warm runs take seconds.
_POLL_SECONDS = 2

# On POSIX, put the child in its OWN session/process group so _killtree can killpg the whole group
# on timeout and reap ProcessPoolExecutor grandchildren (`pkill -P` catches only direct children).
# Windows reaps the tree with `taskkill /F /T`, so it needs no extra spawn flag.
_CHILD_KW = {} if os.name == "nt" else {"start_new_session": True}


def _killtree(pid):
    """Kill pid AND its whole descendant tree. I/O: (int) -> None.

    A plain proc.kill() (or `pkill -P`, which reaps only DIRECT children) leaves multiprocessing
    grandchildren (jobs=N spawns N of them) orphaned, so they run forever. Windows: `taskkill /F /T`
    reaps the whole tree. POSIX: the child is launched in its own session (see _CHILD_KW), so a
    single killpg on its process group takes out the child AND every inherited grandchild at once."""
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


def _run_one(name, script, timeout):
    """Run one validate_*.py in its own interpreter, bounded and orphan-free, streaming its output.

    Never raises: a crash/timeout becomes a structured result so one broken engine can't hang the
    whole report. I/O: (str, Path, seconds) -> dict."""
    fd, out_path = tempfile.mkstemp(prefix="validate_%s_" % name, suffix=".out")
    os.close(fd)
    timed_out = False
    t0 = time.time()
    print(f"\n=== {name} ({script.name}) ".ljust(78, "=") + "\n", flush=True)
    try:
        # stdout AND stderr to a FILE (never PIPE) so no grandchild can hold a pipe open; -u so the
        # file has content even if we have to kill the tree.
        with open(out_path, "w", encoding="utf-8") as fw:
            try:
                proc = subprocess.Popen([sys.executable, "-u", str(script)],
                                        stdout=fw, stderr=subprocess.STDOUT, **_CHILD_KW)
            except OSError as exc:
                # Couldn't even launch the interpreter (missing exe, EMFILE, ...). Report it as a
                # failed engine instead of letting it abort the whole aggregating run. (finally
                # below still removes out_path; no child was created, so nothing is orphaned.)
                print(f"\n{name}: could not start ({exc})", flush=True)
                return {"name": name, "returncode": -1, "skipped": False,
                        "seconds": round(time.time() - t0, 1)}
            # Separate read handle tails the same file, so a multi-hour run reports progress live
            # instead of going silent and then dumping everything at the end.
            with open(out_path, "r", encoding="utf-8", errors="replace") as fr:
                while True:
                    chunk = fr.read()
                    if chunk:
                        sys.stdout.write(chunk)
                        sys.stdout.flush()
                    if proc.poll() is not None:
                        tail = fr.read()                    # drain whatever landed after the poll
                        if tail:
                            sys.stdout.write(tail)
                            sys.stdout.flush()
                        break
                    if time.time() - t0 > timeout:
                        timed_out = True
                        _killtree(proc.pid)
                        try:
                            proc.wait(timeout=30)           # after the killtree, not instead of it
                        except subprocess.TimeoutExpired:
                            pass
                        break
                    time.sleep(_POLL_SECONDS)
        with open(out_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()                              # a killed worker can truncate a
    finally:                                                # multi-byte sequence -> errors="replace"
        try:
            os.remove(out_path)
        except OSError:
            pass

    seconds = round(time.time() - t0, 1)
    if timed_out:
        print(f"\n{name}: TIMEOUT after {timeout}s (killed, tree reaped)", flush=True)
        return {"name": name, "returncode": -1, "skipped": False, "seconds": seconds}
    return {"name": name, "returncode": proc.returncode, "skipped": "SKIPPED" in content,
            "seconds": seconds}


def _parse_timeout(argv):
    """--timeout N (seconds); the default when absent. I/O: ([str]) -> int."""
    for i, a in enumerate(argv):
        if a == "--timeout" and i + 1 < len(argv):
            return int(argv[i + 1])
        if a.startswith("--timeout="):
            return int(a.split("=", 1)[1])
    return _DEFAULT_TIMEOUT


def main(argv):
    """Run both regression proofs in isolated, bounded subprocesses; aggregate to an exit code.
    I/O: ([str]) -> int."""
    timeout = _parse_timeout(argv)
    results = [
        _run_one("triangle", _SCRIPTS_DIR / "validate_triangle.py", timeout),
        _run_one("square", _SCRIPTS_DIR / "validate_square.py", timeout),
    ]

    any_failed = False
    any_skipped = False
    any_ran = False
    for r in results:
        if r["skipped"]:
            any_skipped = True
        else:
            any_ran = True
        if r["returncode"] != 0:
            any_failed = True

    print("---")
    if any_skipped and not any_ran:
        print("validate: NOTHING VALIDATED (both ground-truth sources absent -- fresh clone?)")
    elif any_skipped:
        print("validate: PARTIAL (one ground-truth source absent; see SKIPPED line above)")
    if any_failed:
        print("validate: FAIL (see mismatches above)")
    else:
        print("validate: PASS" + (" (with skip)" if any_skipped else ""))

    if any_failed:
        return 1
    if any_skipped and not any_ran:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
