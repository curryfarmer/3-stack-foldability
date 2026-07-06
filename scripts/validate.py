"""scripts/validate.py — thin dispatcher: run the triangle and square regression-proof scripts,
each in its OWN subprocess, and report both summaries.

WHY SUBPROCESS ISOLATION (not a plain import). `triangle/` and `square/` are independent
installable subpackages that each put their own bare-named `lattice` module on `sys.path` (see
`triangle/_bootstrap.py` / `square/_bootstrap.py`). Importing both `validate_triangle` and
`validate_square` into the SAME interpreter would race whichever `_bootstrap` ran second — the
second `import lattice` anywhere downstream would silently resolve to the wrong package's
`lattice/`. This module therefore never imports either validate_* module directly; it only
`subprocess.run([sys.executable, ...])`s them, exactly as instructed.

Exit code: nonzero if either subprocess exited nonzero (a real mismatch or a hard failure), OR if
BOTH ground-truth sources are absent (nothing was validated at all). A single skip (fresh clone
missing one gitignored local source) is reported distinctly but does not by itself fail the run.
"""
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent


def _run_one(name, script):
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    out = proc.stdout.strip()
    skipped = "SKIPPED" in out
    return {
        "name": name, "returncode": proc.returncode, "stdout": out, "stderr": proc.stderr.strip(),
        "skipped": skipped,
    }


def main():
    results = [
        _run_one("triangle", _SCRIPTS_DIR / "validate_triangle.py"),
        _run_one("square", _SCRIPTS_DIR / "validate_square.py"),
    ]

    any_failed = False
    any_skipped = False
    any_ran = False
    for r in results:
        if r["stdout"]:
            print(r["stdout"])
        if r["stderr"]:
            print(r["stderr"], file=sys.stderr)
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
    sys.exit(main())
