"""check.py — the physical-testing acceptance ORACLE.

Re-derives a fresh engine verdict for every physically-folded record and confirms it still agrees
with the observed outcome, for BOTH engines. Implemented as a subprocess fan-out over the existing
regression proofs (scripts/validate_square.py --json, scripts/validate_triangle.py --json): each
runs in its own interpreter, so the square and triangle packages are never co-imported (they each
put a bare `lattice` on sys.path). Reuses every bit of their gate-recompute logic — this module
only aggregates.

Verdict — note that INFRA FAILURE AND DATA DISAGREEMENT ARE DIFFERENT ANSWERS:
  PASS              — every physically-folded record's fresh verdict matches the observed outcome.
  PASS (with skip)  — one engine's ground-truth data is absent (fresh clone), the other passed.
  NOTHING VALIDATED — both engines' ground-truth data absent.
  FAIL              — at least one record DISAGREES. A real regression. (exit 1)
  ERROR             — a checker timed out / produced no parseable output / hard-failed. Nothing was
                      proven either way; this is a broken harness, not a broken engine. (exit 2)
Conflating those two is what made this oracle untrustworthy: a 30-min timeout against a checker that
needs hours looked exactly like a regression. If both occur, FAIL wins — a real disagreement is the
more actionable answer — and `anyError` still reports the infra problem.

WINDOWS ORPHAN TRAP (why this file uses Popen + a file, never subprocess.run + PIPE):
`subprocess.run(capture_output=True, timeout=...)` cannot bound a child that spawns a
ProcessPoolExecutor. kill() reaps only the direct child; the grandchildren inherited the stdout pipe
write handles, so the post-kill communicate() blocks until the search finishes naturally — which is
both the multi-hour hang and the ~50 orphaned workers. Redirecting to a FILE means no pipe to hold
open, and `taskkill /F /T` reaps the whole tree. Pattern lifted from scratch_examples/hunt_n4n5.py.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.dirname(_HERE)

_CHECKERS = {
    "square": os.path.join(_SCRIPTS_DIR, "validate_square.py"),
    "triangle": os.path.join(_SCRIPTS_DIR, "validate_triangle.py"),
}

# Mismatch kinds that mean "the harness broke", not "the engine disagrees". Everything else —
# including any kind added later that we don't recognise — counts as DATA and fails the gate. An
# unknown mismatch must never be silently downgraded to an infra hiccup.
_INFRA_KINDS = frozenset(("timeout", "no_output"))

_DEFAULT_TIMEOUT = 4 * 60 * 60      # 4h. The square checker's cold run is dominated by the big
                                    # grids and can run for hours; this bounds a genuine hang, it is
                                    # not a performance expectation. Warm runs take seconds.
_POLL_SECONDS = 2


def _killtree(pid):
    """Kill pid AND its whole descendant tree.

    A plain proc.kill() only kills the direct child, orphaning any multiprocessing grandchildren
    (jobs=N spawns N of them), which then keep running forever. On Windows taskkill /T is the only
    reliable way to reap them."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True, text=True)      # tiny, bounded output: PIPE is fine here
    else:
        subprocess.run(["pkill", "-9", "-P", str(pid)], capture_output=True, text=True)
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def _run_checker(engine, script, timeout):
    """Subprocess one validate_*.py --json, bounded and orphan-free, streaming its progress through.

    Never raises: a crash/timeout becomes a structured result so one broken engine can't take down
    the whole report. I/O: (str, path, seconds) -> dict."""
    fd, out_path = tempfile.mkstemp(prefix="phystest_%s_" % engine, suffix=".out")
    os.close(fd)
    timed_out = False
    t0 = time.time()
    try:
        # stdout AND stderr to a FILE (never PIPE) so no grandchild can hold a pipe open; -u so the
        # file has content even if we have to kill the tree.
        with open(out_path, "w", encoding="utf-8") as fw:
            proc = subprocess.Popen([sys.executable, "-u", script, "--json"],
                                    stdout=fw, stderr=subprocess.STDOUT)
            # Separate read handle tails the same file, so a multi-hour run reports progress live
            # instead of going silent and then dumping 132 minutes of output at the end.
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

    if timed_out:
        return {"engine": engine, "skipped": False, "nAgree": None, "nTotal": None,
                "mismatches": [{"kind": "timeout",
                                "detail": "checker exceeded %ss (killed, tree reaped)" % timeout}],
                "returncode": -1, "hardError": True, "seconds": round(time.time() - t0, 1)}

    payload = None
    for line in reversed(content.strip().splitlines()):     # the JSON is the last line; the lines
        try:                                                # above it are validate_*'s progress
            payload = json.loads(line)
            break
        except ValueError:
            continue
    if payload is None or not isinstance(payload, dict):
        return {"engine": engine, "skipped": False, "nAgree": None, "nTotal": None,
                "mismatches": [{"kind": "no_output", "detail": content.strip()[-500:]}],
                "returncode": proc.returncode, "hardError": True,
                "seconds": round(time.time() - t0, 1)}
    payload["returncode"] = proc.returncode
    payload["hardError"] = proc.returncode != 0 and not payload.get("mismatches")
    payload["seconds"] = round(time.time() - t0, 1)
    return payload


def _data_mismatches(r):
    """The mismatches that mean the ENGINE disagrees with physical reality (vs. a broken harness)."""
    return [m for m in (r.get("mismatches") or []) if m.get("kind") not in _INFRA_KINDS]


def _is_infra_error(r):
    """True when this engine's checker failed to produce a trustworthy answer at all."""
    return bool(r.get("hardError")) or any(m.get("kind") in _INFRA_KINDS
                                           for m in (r.get("mismatches") or []))


def run_checks(engines=("square", "triangle"), timeout=_DEFAULT_TIMEOUT):
    """Structured acceptance report over the requested engines. Pure data; no process exit."""
    per = {}
    for eng in engines:
        script = _CHECKERS[eng]
        if not os.path.isfile(script):
            per[eng] = {"engine": eng, "skipped": True, "nAgree": None, "nTotal": None,
                        "mismatches": [], "returncode": 0, "hardError": False,
                        "note": "checker script missing"}
            continue
        per[eng] = _run_checker(eng, script, timeout)

    any_mismatch = any(_data_mismatches(r) for r in per.values())
    any_error = any(_is_infra_error(r) for r in per.values())
    any_skipped = any(r.get("skipped") for r in per.values())
    any_ran = any(not r.get("skipped") and not _is_infra_error(r) for r in per.values())
    total_agree = sum(r.get("nAgree") or 0 for r in per.values())
    total_records = sum(r.get("nTotal") or 0 for r in per.values())

    if any_mismatch:                        # a real disagreement outranks a broken harness
        verdict = "FAIL"
    elif any_error:
        verdict = "ERROR"
    elif any_skipped and not any_ran:
        verdict = "NOTHING VALIDATED"
    elif any_skipped:
        verdict = "PASS (with skip)"
    else:
        verdict = "PASS"

    return {
        "schema": "phystest-check/2",
        "engines": per,
        "totalAgree": total_agree,
        "totalRecords": total_records,
        "anyMismatch": any_mismatch,        # DATA: the engine disagrees -> FAIL
        "anyError": any_error,              # INFRA: nothing was proven -> ERROR
        "anySkipped": any_skipped,
        "anyRan": any_ran,
        "verdict": verdict,
    }


def _print_report(report):
    for eng, r in report["engines"].items():
        if r.get("skipped"):
            print("  %-9s SKIPPED (%s)" % (eng, r.get("note", "no ground-truth data present")))
        elif _is_infra_error(r):
            print("  %-9s ERROR   %s" % (eng, r.get("mismatches")))
        else:
            cache = r.get("cache")
            print("  %-9s %d/%d agree%s%s" % (
                eng, r.get("nAgree") or 0, r.get("nTotal") or 0,
                ("  [cache: %s]" % ", ".join("%s=%s" % kv for kv in sorted(cache.items()))) if cache else "",
                ("  MISMATCHES: %s" % r["mismatches"]) if r.get("mismatches") else ""))
    print("phystest check: %s (%d/%d records agree)"
          % (report["verdict"], report["totalAgree"], report["totalRecords"]))


def _parse_timeout(argv):
    """--timeout N (seconds). Returns the default when absent."""
    for i, a in enumerate(argv):
        if a == "--timeout" and i + 1 < len(argv):
            return int(argv[i + 1])
        if a.startswith("--timeout="):
            return int(a.split("=", 1)[1])
    return _DEFAULT_TIMEOUT


def main(argv):
    as_json = "--json" in argv
    report = run_checks(timeout=_parse_timeout(argv))
    if as_json:
        print(json.dumps(report))
    else:
        _print_report(report)
    # Distinct exit codes: a broken harness (2) must not read as a regression (1). A skip (missing
    # local data) is not a failure by itself unless NOTHING could be validated at all.
    if report["anyMismatch"]:
        return 1
    if report["anyError"]:
        return 2
    if report["verdict"] == "NOTHING VALIDATED":
        return 1
    return 0
