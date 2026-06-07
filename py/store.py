"""store.py — per-params JSON result files + a manifest index.

results/
  manifest.json          # index: list of {file, m, n, opts, count, generated}
  6x6_<hash8>.json       # {meta:{m,n,opts,generated,counts}, solutions:[...]}

The JSON shape matches the browser tool's own export (app.js exportJson) so the
'Load results' picker can consume either.
"""

import os
import json
import hashlib
import datetime

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
MANIFEST = os.path.join(RESULTS_DIR, "manifest.json")


def _canonical(opts):
    """Stable representation of the params that define a result set."""
    stacks = opts.get("stacks", 3)
    base = {
        "m": opts["m"], "n": opts["n"], "stacks": stacks,
        "dedup": bool(opts.get("dedup", True)),
    }
    if stacks == 3:
        base["shapes"] = {k: bool(v) for k, v in sorted(opts["shapes"].items())}
        base["decomps"] = {k: bool(v) for k, v in sorted(opts["decomps"].items())}
        base["allowNonCorner"] = bool(opts.get("allowNonCorner"))
    return base


def params_key(opts):
    blob = json.dumps(_canonical(opts), sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(blob.encode()).hexdigest()[:8]


def result_path(opts):
    tag = "" if opts.get("stacks", 3) == 3 else f"{opts['stacks']}stack_"
    return os.path.join(RESULTS_DIR, f"{opts['m']}x{opts['n']}_{tag}{params_key(opts)}.json")


def load_manifest():
    if not os.path.exists(MANIFEST):
        return []
    with open(MANIFEST) as f:
        return json.load(f)


def save_manifest(entries):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(MANIFEST, "w") as f:
        json.dump(entries, f, indent=2)


def find_cached(opts):
    key = params_key(opts)
    for e in load_manifest():
        if e.get("key") == key:
            return e if os.path.exists(os.path.join(RESULTS_DIR, e["file"])) else None
    return None


def save_result(opts, solutions, ctx):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = result_path(opts)
    fname = os.path.basename(path)
    generated = datetime.datetime.now().isoformat(timespec="seconds")
    counts = {k: v for k, v in ctx.items() if isinstance(v, int) and not isinstance(v, bool)}
    payload = {
        "meta": {"m": opts["m"], "n": opts["n"], "stacks": opts.get("stacks", 3),
                 "opts": _canonical(opts), "generated": generated, "counts": counts},
        "solutions": solutions,
    }
    with open(path, "w") as f:
        json.dump(payload, f, separators=(",", ":"))

    entries = [e for e in load_manifest() if e.get("key") != params_key(opts)]
    entries.append({
        "key": params_key(opts), "file": fname,
        "m": opts["m"], "n": opts["n"], "opts": _canonical(opts),
        "count": len(solutions), "generated": generated,
    })
    entries.sort(key=lambda e: (e["m"], e["n"], e["key"]))
    save_manifest(entries)
    return path
