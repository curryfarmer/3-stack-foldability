"""scripts/port_from_revamp.py — retarget a commit's diff from the `revamp` branch's old flat
`py/` tree onto `main`'s restructured `triangle/` + `square/` packages.

WHY THIS EXISTS. `main` (this package's clean layout) and `revamp` (the pre-cleanup dirty
branch, kept around for ongoing physical-fold testing) share a common ancestor but have since
diverged in directory structure: most math-critical files moved verbatim to new paths (e.g.
`py/tri/foldsim.py` -> `triangle/tri/foldsim.py`), a few were duplicated into both packages (the
shared `lattice/base.py` + `lattice/reflect.py`), and a handful were intentionally rewritten
(`py/generate.py`, `py/twostack.py`, the two `_bootstrap.py`s, both `lattice/__init__.py`s, the
salvaged `experimental/*` renders). A bugfix made on `revamp` needs the SAME fix mirrored onto
`main` at the new path(s) -- this script does the mechanical part of that (find the diff, rewrite
the path headers, try to apply it), and clearly flags the files where a mechanical patch can't
work so those get ported by hand instead.

This tool is pure git plumbing: it never imports triangle/ or square/, and never edits the
mapping table's target files except via `git apply` on an explicit request.

Usage:
  python scripts/port_from_revamp.py <revamp-commit-ish>            # dry run (default, always safe)
  python scripts/port_from_revamp.py <revamp-commit-ish> --apply    # write into the working tree
                                                                     # (leaves changes UNSTAGED for
                                                                     #  you to review + commit)
"""
import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# --- mapping table (built from a verified `git diff revamp:<path> main:<dest>` audit) ----------

_TRI_FILES = [
    "domino21.py", "foldclose.py", "foldsheet_tri.py", "foldsim.py", "hexlattice.py",
    "render_general.py", "righttri.py", "scalene.py", "seam_filter.py", "trilattice.py",
    "trirender.py", "trisearch.py", "tritwist.py", "find_example.py", "gen_testset.py",
    "hunt_foldable.py", "prove_obstruction.py", "render_fold.py", "render_reflection.py",
    "render_twist.py", "solve_foldable.py", "sidematch_scan.py",
]

# revamp path -> [main destination path(s)], verbatim / near-verbatim (mechanically portable)
MAPPING = {f"py/tri/{name}": [f"triangle/tri/{name}"] for name in _TRI_FILES}
MAPPING.update({
    "py/lattice/base.py": ["triangle/lattice/base.py", "square/lattice/base.py"],
    "py/lattice/reflect.py": ["triangle/lattice/reflect.py", "square/lattice/reflect.py"],
    "py/lattice/foldwalk.py": ["triangle/lattice/foldwalk.py"],
    "py/lattice/square.py": ["square/lattice/square.py"],
    "py/engine/fold.py": ["square/engine/fold.py"],
    "py/engine/runner.py": ["square/engine/runner.py"],
    "py/engine/_engine_entry.py": ["square/engine/_engine_entry.py"],
    "py/engine/search.py": ["square/engine/search.py"],
    "py/twist/twist_jump.py": ["square/twist/twist_jump.py"],
    "py/render/explain_parity.py": ["square/render/explain_parity.py"],
    "py/render/figstyle.py": ["square/render/figstyle.py"],
    "py/render/render_square.py": ["square/render/render_square.py"],
    "py/render/render_twostack.py": ["square/render/render_twostack.py"],
})

# revamp path -> reason a mechanical patch can't work (diverged content; port by hand)
NOT_PORTABLE = {
    "py/generate.py": "square/generate.py has diverged (SQLite calls stripped, uid stamping added)",
    "py/twostack.py": "square/twostack.py has diverged (uid stamping added)",
    "py/lattice/__init__.py": "triangle/lattice/__init__.py + square/lattice/__init__.py were both "
                               "rewritten and have diverged from each other",
    "py/_bootstrap.py": "triangle/_bootstrap.py + square/_bootstrap.py were both rewritten with "
                         "package-specific _SUBS tuples",
    "experimental/enumerate_twist.py": "salvaged/rewritten into square/render/render_twist_2plus1.py",
    "experimental/make_fold_bundle.py": "salvaged/rewritten into square/render/render_bundle.py",
}


def _git(*args, check=True):
    proc = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError("git %s failed:\n%s" % (" ".join(args), proc.stderr))
    return proc


def _changed_files(commit):
    proc = _git("show", "--name-only", "--pretty=format:", commit)
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _retarget_patch(patch_text, src_path, dst_path):
    """Rewrite a unified diff's a/<src> b/<src> headers to a/<dst> b/<dst>."""
    out = []
    for line in patch_text.splitlines(keepends=True):
        if line.startswith("diff --git "):
            out.append("diff --git a/%s b/%s\n" % (dst_path, dst_path))
        elif line.startswith("--- a/"):
            out.append("--- a/%s\n" % dst_path)
        elif line.startswith("+++ b/"):
            out.append("+++ b/%s\n" % dst_path)
        else:
            out.append(line)
    return "".join(out)


def _preflight():
    branch = _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    dirty = _git("status", "--short").stdout.strip()
    if dirty:
        raise SystemExit("refusing to run: working tree is not clean (git status --short):\n%s" % dirty)
    is_main_ancestor = _git("merge-base", "--is-ancestor", "main", "HEAD", check=False).returncode == 0
    if branch != "main" and not is_main_ancestor:
        raise SystemExit("refusing to run: checked out branch %r does not contain main's history "
                          "(expected to be run on main, or a branch descended from it)" % branch)


def port(commit, apply):
    _preflight()
    files = _changed_files(commit)
    if not files:
        print("no files changed in %s" % commit)
        return 0

    any_conflict = False
    for src in files:
        if src in NOT_PORTABLE:
            print("MANUAL PORT NEEDED: %s -- %s" % (src, NOT_PORTABLE[src]))
            continue
        dests = MAPPING.get(src)
        if dests is None:
            print("UNKNOWN file (not in mapping), port by hand: %s" % src)
            any_conflict = True
            continue
        diff = _git("diff", "%s^..%s" % (commit, commit), "--", src).stdout
        if not diff:
            print("(no-op) %s: empty diff in this commit" % src)
            continue
        for dst in dests:
            patch = _retarget_patch(diff, src, dst)
            check = subprocess.run(["git", "apply", "--check", "-"], cwd=REPO_ROOT,
                                   input=patch, capture_output=True, text=True)
            if check.returncode != 0:
                print("CONFLICT: %s -> %s\n  %s" % (src, dst, check.stderr.strip().replace("\n", "\n  ")))
                any_conflict = True
                continue
            if apply:
                subprocess.run(["git", "apply", "-"], cwd=REPO_ROOT, input=patch, text=True, check=True)
                print("applied: %s -> %s" % (src, dst))
            else:
                print("portable (dry run): %s -> %s" % (src, dst))

    if not apply:
        print("---\ndry run only; re-run with --apply to write these into the working tree "
              "(review + commit yourself -- this script never commits)")
    return 1 if any_conflict else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("commit", help="commit-ish on revamp to port (e.g. a short sha)")
    ap.add_argument("--apply", action="store_true", help="write the retargeted patch into the working tree")
    args = ap.parse_args(argv)
    return port(args.commit, args.apply)


if __name__ == "__main__":
    sys.exit(main())
