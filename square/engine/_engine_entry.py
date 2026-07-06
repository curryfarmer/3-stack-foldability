#!/usr/bin/env python3
"""_engine_entry.py — stdin/stdout bridge so a PyPy subprocess can run the engine.

Reads an opts dict as JSON from stdin, runs search.run, writes {solutions, ctx, err}
JSON to stdout. Import-light and guarded so it is safe to re-import under the spawn start
method (multiprocessing workers launched by search.run when jobs > 1)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # square/ on path
import _bootstrap  # noqa: E402,F401  (puts square/{engine,twist,render} on sys.path)
import search as Search  # noqa: E402


def main():
    opts = json.load(sys.stdin)
    solutions, ctx, err = Search.run(opts)
    json.dump({"solutions": solutions, "ctx": ctx, "err": err}, sys.stdout)


if __name__ == "__main__":
    main()
