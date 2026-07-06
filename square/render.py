#!/usr/bin/env python3
"""render.py — sq-render CLI: render a generate.py/twostack.py record (JSON) into its full
out/<uid>/ bundle (JSON + foldsheet PNG [+ twist PNG for 3-stack 2+1]) without re-running the
search. Schema-sniffs "circuit" (2-stack) vs "chains"+"footprint" (3-stack).

Usage:
  python square/render.py <record.json> [--out DIR]
  python square/render.py <DIR-of-json-records> [--out DIR]

NOTE on the name: this file is meant to be *run directly* (python square/render.py ...), not
imported as a module. square/render/ is already a package of the same name (the low-level
plotting modules: render_square.py / render_twostack.py / figstyle.py / ...), and a package
shadows a same-named sibling file in Python's import system -- `import render` from anywhere
with square/ on sys.path resolves to THAT package, not this file. The actual shared logic lives
in render_bundle.py (inside square/render/, imported by both this CLI and generate.py) precisely
to sidestep that collision; this file only owns argument parsing / file discovery / CLI output.
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # square/ on path
import _bootstrap  # noqa: E402,F401  (puts square/{engine,twist,render} on sys.path)

import render_bundle as RenderB  # noqa: E402


def _iter_records(target):
    """Yield (path, rec_dict) for a single JSON file or every *.json in a directory."""
    if os.path.isdir(target):
        paths = sorted(glob.glob(os.path.join(target, "*.json")))
    else:
        paths = [target]
    for path in paths:
        with open(path, encoding="utf-8") as f:
            yield path, json.load(f)


def main(argv=None):
    p = argparse.ArgumentParser(description="Render a square-engine record (JSON) to its PNG bundle.")
    p.add_argument("target", help="a record .json file, or a directory of *.json records")
    p.add_argument("--out", default="out", help="output directory for <uid>/ bundles (default: out/)")
    args = p.parse_args(sys.argv[1:] if argv is None else argv)

    n_ok = 0
    for path, rec in _iter_records(args.target):
        uid = rec.get("uid")
        if not uid:
            raise SystemExit(f"error: {path} has no 'uid' -- records must be pre-stamped by "
                              f"generate.py/twostack.py (refusing to silently recompute one)")
        produced = RenderB.render_record(rec, args.out)
        kind = "3-stack" if RenderB.is_3stack(rec) else "2-stack"
        print(f"  [{uid}] {kind}  {path} -> {produced.get('foldsheet', produced['json'])}")
        n_ok += 1
    print(f"rendered {n_ok} record(s) -> {args.out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
