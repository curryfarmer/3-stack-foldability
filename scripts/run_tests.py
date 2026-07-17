"""scripts/run_tests.py — the regression gate: run every test suite, each in its OWN interpreter.

    python scripts/run_tests.py                  # all three suites
    python scripts/run_tests.py square           # just one (or several)
    python scripts/run_tests.py --timeout 900    # per-suite wall-clock bound (default 30m)
    python scripts/run_tests.py -- -x -k lattice # everything after `--` is passed through to pytest

WHY SUBPROCESS ISOLATION (not one pytest run over all of them). `square/` and `triangle/` are
independent engines that each put a bare-named `lattice` on sys.path (square/_bootstrap.py,
triangle/_bootstrap.py, both `sys.path.insert(0, <own pkg>)`). Collecting both suites in one
interpreter races whichever bootstrap ran second: `from lattice.square import SquareLattice` would
resolve against triangle/lattice/ (which has no square.py), and `lattice.reflect` / `generate`
collide the same way. So the suites NEVER share a process. This is a sibling dispatcher to
scripts/validate.py over the same two engines.

WINDOWS ORPHAN TRAP (why this uses Popen + a file, never subprocess.run + PIPE). A plain
`subprocess.run(..., capture_output=True, text=True)` with no timeout cannot bound a child which
spawns a ProcessPoolExecutor: kill() reaps only the direct child, the grandchildren inherited the
stdout pipe write handles, and the post-kill communicate() blocks until they finish naturally. That
is both the multi-hour hang and the orphaned workers. Redirecting to a FILE means there is no pipe
to hold open, and `taskkill /F /T` reaps the whole tree. Pattern lifted verbatim from
scripts/phystest/check.py, which is the tested reference.

The suites inherit pytest.ini's `addopts = -ra -q -m "not slow"`, so expensive engine sweeps stay
deselected. Passing a suite path on the command line overrides `testpaths = smoketest` while leaving
addopts intact -- do NOT add `-m` here, since a command-line -m REPLACES the ini value rather than
ANDing with it, which would silently re-select the slow tier.
"""
import os
import subprocess
import sys
import tempfile
import time

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPTS_DIR)

# name -> path (relative to repo root). Order is cheapest-first so a broken engine surfaces fast.
_SUITES = {
    "smoketest": "smoketest",
    "square": os.path.join("square", "tests"),
    "triangle": os.path.join("triangle", "tests"),
}

_DEFAULT_TIMEOUT = 30 * 60      # Bounds a genuine hang; not a performance expectation. The whole
                                # default gate runs in ~1 minute.
_POLL_SECONDS = 1

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


def _run_suite(name, path, timeout, extra):
    """Run one suite in its own interpreter, bounded and orphan-free, streaming its output through.

    Never raises: a crash/timeout becomes a structured result so one broken suite can't take down the
    whole report. I/O: (str, str, seconds, [str]) -> dict."""
    fd, out_path = tempfile.mkstemp(prefix="run_tests_%s_" % name, suffix=".out")
    os.close(fd)
    timed_out = False
    t0 = time.time()
    print(f"\n=== {name} ({path}) ".ljust(78, "=") + "\n", flush=True)
    try:
        # stdout AND stderr to a FILE (never PIPE) so no grandchild can hold a pipe open; -u so the
        # file has content even if we have to kill the tree.
        with open(out_path, "w", encoding="utf-8") as fw:
            try:
                proc = subprocess.Popen(
                    [sys.executable, "-u", "-m", "pytest", path, "-p", "no:cacheprovider", *extra],
                    cwd=_REPO_ROOT, stdout=fw, stderr=subprocess.STDOUT, **_CHILD_KW)
            except OSError as exc:
                # Couldn't even launch the interpreter (missing exe, EMFILE, ...). Report it as a
                # failed suite instead of letting it abort the whole aggregating run.
                print(f"\n{name}: could not start ({exc})", flush=True)
                return {"suite": name, "returncode": -1, "timedOut": False,
                        "seconds": round(time.time() - t0, 1),
                        "summary": f"failed to start: {exc}"}
            # Separate read handle tails the same file, so a long run reports progress live instead
            # of going silent and then dumping everything at the end.
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
        return {"suite": name, "returncode": -1, "timedOut": True, "seconds": seconds,
                "summary": f"timeout after {timeout}s"}

    # pytest's last non-empty line is its summary ("N passed, M skipped in Xs").
    lines = [ln for ln in content.strip().splitlines() if ln.strip()]
    return {"suite": name, "returncode": proc.returncode, "timedOut": False, "seconds": seconds,
            "summary": lines[-1] if lines else "(no output)"}


def _timeout_secs(val):
    """Parse a --timeout value to int seconds, or exit with a usage error. I/O: (str) -> int."""
    try:
        return int(val)
    except ValueError:
        raise SystemExit(
            f"run_tests: --timeout wants an integer number of seconds, got {val!r}")


def _parse_argv(argv):
    """Split argv into (suite names, timeout, pytest passthrough). I/O: ([str]) -> (list, int, list).

    Everything after a bare `--` goes to pytest untouched."""
    extra = []
    if "--" in argv:
        i = argv.index("--")
        argv, extra = argv[:i], argv[i + 1:]
    timeout = _DEFAULT_TIMEOUT
    names = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--timeout" and i + 1 < len(argv):
            timeout = _timeout_secs(argv[i + 1]); i += 2; continue
        if a.startswith("--timeout="):
            timeout = _timeout_secs(a.split("=", 1)[1]); i += 1; continue
        names.append(a); i += 1
    unknown = [n for n in names if n not in _SUITES]
    if unknown:
        raise SystemExit(f"unknown suite(s) {unknown}; choose from {sorted(_SUITES)}")
    return (names or list(_SUITES)), timeout, extra


def main(argv):
    names, timeout, extra = _parse_argv(argv)
    results = [_run_suite(n, _SUITES[n], timeout, extra) for n in names]

    print("\n" + "=" * 78)
    for r in results:
        status = "FAIL" if r["returncode"] != 0 else "ok"
        print(f"  {r['suite']:<10} {status:<5} {r['seconds']:>7.1f}s  {r['summary']}")
    failed = [r["suite"] for r in results if r["returncode"] != 0]
    if failed:
        print(f"run_tests: FAIL ({', '.join(failed)})")
        return 1
    print("run_tests: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
