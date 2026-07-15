"""check.py — the physical-testing acceptance ORACLE.

Re-derives a fresh engine verdict for every physically-folded record and confirms it still agrees
with the observed outcome, for BOTH engines. Implemented as a subprocess fan-out over the existing
regression proofs (scripts/validate_square.py --json, scripts/validate_triangle.py --json): each
runs in its own interpreter, so the square and triangle packages are never co-imported (they each
put a bare `lattice` on sys.path). Reuses every bit of their gate-recompute logic — this module
only aggregates.

Verdict:
  PASS              — every physically-folded record's fresh verdict matches the observed outcome.
  PASS (with skip)  — one engine's ground-truth data is absent (fresh clone), the other passed.
  NOTHING VALIDATED — both engines' ground-truth data absent.
  FAIL              — at least one record disagrees (or a checker hard-failed).
"""
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.dirname(_HERE)

_CHECKERS = {
    "square": os.path.join(_SCRIPTS_DIR, "validate_square.py"),
    "triangle": os.path.join(_SCRIPTS_DIR, "validate_triangle.py"),
}


def _run_checker(engine, script, timeout):
    """Subprocess one validate_*.py --json. Never raises: a crash/timeout becomes a FAIL result so
    one broken engine can't take down the whole report."""
    try:
        proc = subprocess.run([sys.executable, script, "--json"],
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"engine": engine, "skipped": False, "nAgree": None, "nTotal": None,
                "mismatches": [{"kind": "timeout", "detail": "checker exceeded %ss" % timeout}],
                "returncode": -1, "hardError": True}
    payload = None
    for line in reversed(proc.stdout.strip().splitlines()):  # the JSON is the last line
        try:
            payload = json.loads(line)
            break
        except ValueError:
            continue
    if payload is None:
        return {"engine": engine, "skipped": False, "nAgree": None, "nTotal": None,
                "mismatches": [{"kind": "no_output",
                                "detail": (proc.stderr or proc.stdout or "").strip()[-500:]}],
                "returncode": proc.returncode, "hardError": True}
    payload["returncode"] = proc.returncode
    payload["hardError"] = proc.returncode != 0 and not payload.get("mismatches")
    return payload


def run_checks(engines=("square", "triangle"), timeout=1800):
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

    any_mismatch = any(r.get("mismatches") for r in per.values())
    any_hard = any(r.get("hardError") for r in per.values())
    any_skipped = any(r.get("skipped") for r in per.values())
    any_ran = any(not r.get("skipped") and not r.get("hardError") for r in per.values())
    total_agree = sum(r.get("nAgree") or 0 for r in per.values())
    total_records = sum(r.get("nTotal") or 0 for r in per.values())

    if any_mismatch or any_hard:
        verdict = "FAIL"
    elif any_skipped and not any_ran:
        verdict = "NOTHING VALIDATED"
    elif any_skipped:
        verdict = "PASS (with skip)"
    else:
        verdict = "PASS"

    return {
        "schema": "phystest-check/1",
        "engines": per,
        "totalAgree": total_agree,
        "totalRecords": total_records,
        "anyMismatch": any_mismatch or any_hard,
        "anySkipped": any_skipped,
        "anyRan": any_ran,
        "verdict": verdict,
    }


def _print_report(report):
    for eng, r in report["engines"].items():
        if r.get("skipped"):
            print("  %-9s SKIPPED (%s)" % (eng, r.get("note", "no ground-truth data present")))
        elif r.get("hardError"):
            print("  %-9s ERROR   %s" % (eng, r.get("mismatches")))
        else:
            print("  %-9s %d/%d agree%s" % (eng, r.get("nAgree") or 0, r.get("nTotal") or 0,
                  ("  MISMATCHES: %s" % r["mismatches"]) if r.get("mismatches") else ""))
    print("phystest check: %s (%d/%d records agree)"
          % (report["verdict"], report["totalAgree"], report["totalRecords"]))


def main(argv):
    as_json = "--json" in argv
    report = run_checks()
    if as_json:
        print(json.dumps(report))
    else:
        _print_report(report)
    # Exit nonzero only on a genuine failure. A skip (missing local data) is not a failure by
    # itself unless NOTHING could be validated at all.
    if report["anyMismatch"]:
        return 1
    if report["verdict"] == "NOTHING VALIDATED":
        return 1
    return 0
