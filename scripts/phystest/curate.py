"""curate.py — generate a to-test BATCH: the candidates worth folding by hand + their foldsheets.

Runs the real engine on a target grid (subprocess to square/generate.py — never an in-process
import), reads back the <uid>/ bundles it writes, drops any candidate already physically folded
(so we never re-queue settled cases), applies a selection policy, and writes:

    <out>/
      raw/<uid>/{<uid>.json, foldsheet_<uid>.png[, twist_<uid>.png]}   (the engine bundles)
      batch.json                                                        (phystest-batch/1 manifest)

Each manifest item is a blank physical-test/1 record (actual.folded = None) carrying the engine's
prediction, so after folding you `phystest log` the outcome and `phystest check` confirms the
prediction held.

Square is fully supported today (rectangles via generate.py). Triangle / arbitrary-sheet curation
plugs in here once the engine's --grid-file ingest lands (see the plan): swap the generate.py
subprocess for the tiling's generator + a fold-grid/1 input, the rest is identical.
"""
import glob
import json
import os
import subprocess
import sys

import records as R

_SQUARE_GENERATE = os.path.join(R.repo_root(), "square", "generate.py")

_POLICIES = {
    "all": lambda p: True,
    "fold": lambda p: p is True,        # predicted foldable — fold to confirm it FOLDS
    "jam": lambda p: p is False,        # predicted jam      — fold to confirm it JAMS
    "undecided": lambda p: p is None,   # twist undecided    — the most informative to test
}


def _run_generate(m, n, decomps, allow_non_corner, jobs, raw_dir):
    argv = [sys.executable, _SQUARE_GENERATE, "--m", str(m), "--n", str(n),
            "--decomps", decomps, "--jobs", str(jobs), "--out", raw_dir]
    if allow_non_corner:
        argv.append("--allow-non-corner")
    proc = subprocess.run(argv, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("generate.py failed (%d):\n%s" % (proc.returncode,
                           (proc.stderr or proc.stdout)[-1500:]))
    return proc.stdout


def curate_square(m, n, decomps="2+1,1+1+1", out_dir=None, policy="all",
                  allow_non_corner=True, jobs=1):
    """Build a to-test batch for a square m x n grid. Returns the manifest dict."""
    if policy not in _POLICIES:
        raise ValueError("policy must be one of %s" % sorted(_POLICIES))
    if out_dir is None:
        out_dir = os.path.join(R.repo_root(), "out", "batch_%dx%d" % (m, n))
    raw_dir = os.path.join(out_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    gen_stdout = _run_generate(m, n, decomps, allow_non_corner, jobs, raw_dir)

    already = R.tested_square_index()
    keep = _POLICIES[policy]
    items, n_seen, n_already, n_filtered = [], 0, 0, 0
    for jpath in sorted(glob.glob(os.path.join(raw_dir, "*", "*.json"))):
        uid_dir = os.path.dirname(jpath)
        with open(jpath, encoding="utf-8") as f:
            bundle = json.load(f)
        if "canonicalHash" not in bundle:  # skip 2-stack circuit bundles etc. for this square pass
            continue
        n_seen += 1
        if R.norm_hash(bundle["canonicalHash"]) in already:
            n_already += 1
            continue
        predicted = bundle.get("verdict", {}).get("twist")
        if not keep(predicted):
            n_filtered += 1
            continue
        uid = bundle["uid"]
        foldsheet_rel = os.path.relpath(os.path.join(uid_dir, "foldsheet_%s.png" % uid), out_dir)
        items.append(R.physical_record_from_bundle(bundle, foldsheet_rel.replace(os.sep, "/")))

    manifest = {
        "schema": "phystest-batch/1",
        "engine": "square",
        "grid": "%dx%d" % (m, n),
        "decomps": decomps,
        "policy": policy,
        "allowNonCorner": allow_non_corner,
        "counts": {"generated": n_seen, "alreadyTested": n_already,
                   "policyFiltered": n_filtered, "queued": len(items)},
        "items": items,
    }
    R.save_batch(out_dir, manifest)
    return manifest, out_dir, gen_stdout


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="phystest curate",
                                 description="generate a to-test batch of foldsheets + manifest")
    ap.add_argument("--square", action="store_true", help="curate a square grid (the default engine)")
    ap.add_argument("--m", type=int, required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--decomps", default="2+1,1+1+1")
    ap.add_argument("--policy", default="all", choices=sorted(_POLICIES),
                    help="which candidates to queue for folding (default: all untested)")
    ap.add_argument("--no-allow-non-corner", dest="allow_non_corner", action="store_false")
    ap.add_argument("--jobs", type=int, default=1, help="engine parallelism (1 = safe, no orphans)")
    ap.add_argument("--out", default=None, help="batch directory (default out/batch_MxN)")
    args = ap.parse_args(argv)

    manifest, out_dir, _ = curate_square(
        args.m, args.n, decomps=args.decomps, out_dir=args.out, policy=args.policy,
        allow_non_corner=args.allow_non_corner, jobs=args.jobs)
    c = manifest["counts"]
    print("curated %s  grid=%s  policy=%s" % (out_dir, manifest["grid"], manifest["policy"]))
    print("  generated=%d  already-tested=%d  policy-filtered=%d  QUEUED=%d"
          % (c["generated"], c["alreadyTested"], c["policyFiltered"], c["queued"]))
    print("  -> print the foldsheets under %s, fold them, then: phystest log --batch %s ..."
          % (os.path.join(out_dir, "raw"), out_dir))
    return 0
