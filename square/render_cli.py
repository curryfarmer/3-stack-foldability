#!/usr/bin/env python3
"""render_cli.py — sq-render CLI: render a generate.py/twostack.py record (JSON) into its full
out/<uid>/ bundle (JSON + schematic PNG + twist PNG) without re-running the search. Schema-sniffs
"circuit" (2-stack) vs "chains"+"footprint" (3-stack).

Usage:
  python square/render_cli.py <record.json> [--out DIR]
  python square/render_cli.py <DIR-of-json-records> [--out DIR]

NOTE on the name: square/render/ is already a package (the low-level plotting modules:
render_square.py / render_twostack.py / figstyle.py / ...). A package shadows a same-named
sibling file for DOTTED imports (`square.render` resolves to the package, not a same-named file),
which breaks a `square.render:main` console-script entry point -- hence this CLI lives at
render_cli.py instead of render.py. The actual shared logic lives in render_bundle.py (inside
square/render/, imported by both this CLI and generate.py); this file only owns argument parsing /
file discovery / CLI output.
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
    """Yield (path, rec_dict) for a single JSON file or every *.json in a directory.
    I/O: (target path) -> iterator of (path, record dict). Raises ValueError on a missing target and
    ValueError/OSError on an unreadable/unparseable JSON file -- main() maps those to a clean exit 2."""
    if os.path.isdir(target):
        paths = sorted(glob.glob(os.path.join(target, "*.json")))
    elif os.path.isfile(target):
        paths = [target]
    else:
        raise ValueError(f"no such file or directory: {target}")
    for path in paths:
        with open(path, encoding="utf-8") as f:
            yield path, json.load(f)


def main(argv=None):
    p = argparse.ArgumentParser(description="Render a square-engine record (JSON) to its PNG bundle.")
    p.add_argument("target", help="a record .json file, or a directory of *.json records")
    p.add_argument("--out", default="out", help="output directory for <uid>/ bundles (default: out/)")
    args = p.parse_args(sys.argv[1:] if argv is None else argv)

    try:                                        # validate target + parse every JSON up front so a
        records = list(_iter_records(args.target))  # bad path / malformed file is a clean exit 2,
    except (ValueError, OSError) as exc:         # not a FileNotFound/JSONDecodeError traceback (exit
        print(f"error: {exc}", file=sys.stderr)  # 1); matches generate.py's return-2 usage-error path
        return 2

    n_ok = 0
    for path, rec in records:
        uid = rec.get("uid")
        if not uid:
            print(f"error: {path} has no 'uid' -- records must be pre-stamped by "
                  f"generate.py/twostack.py (refusing to silently recompute one)", file=sys.stderr)
            return 2
        produced = RenderB.render_record(rec, args.out)
        kind = "3-stack" if RenderB.is_3stack(rec) else "2-stack"
        print(f"  [{uid}] {kind}  {path} -> {produced.get('schematic', produced['json'])}")
        n_ok += 1
    print(f"rendered {n_ok} record(s) -> {args.out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
