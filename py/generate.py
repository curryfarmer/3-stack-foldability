#!/usr/bin/env python3
"""generate.py — CLI to run the 3-stack search and cache results as JSON.

Examples:
  python3 generate.py --m 6 --n 6
  python3 generate.py --m 6 --n 5 --decomps 2+1 --allow-non-corner
  python3 generate.py --m 6 --n 6 --force        # ignore cache, regenerate
  python3 generate.py --stacks 2 --m 6 --n 5     # RSPA 2-stack (Hamiltonian circuits)
  python3 generate.py --list                     # show the manifest

Results land in ../results/ (per-params JSON + manifest.json). A matching cached
run is reused unless --force is given.
"""

import argparse
import sys

import search as Search
import twostack as TwoStack
import store as Store


def parse_args(argv):
    p = argparse.ArgumentParser(description="3-stack folding search → JSON cache")
    p.add_argument("--m", type=int, help="columns")
    p.add_argument("--n", type=int, help="rows")
    p.add_argument("--stacks", type=int, default=3, choices=(2, 3),
                   help="2 = RSPA Hamiltonian-circuit 2-stack; 3 = footprint/decomp 3-stack (default)")
    p.add_argument("--shapes", default="L,Rect", help="comma list: L,Rect (3-stack only)")
    p.add_argument("--decomps", default="2+1,1+1+1", help="comma list: 2+1,1+1+1")
    p.add_argument("--allow-non-corner", action="store_true")
    p.add_argument("--no-dedup", action="store_true", help="disable D4 dedup")
    p.add_argument("--force", action="store_true", help="regenerate even if cached")
    p.add_argument("--list", action="store_true", help="print manifest and exit")
    return p.parse_args(argv)


def build_opts(args):
    if args.stacks == 2:
        return {"m": args.m, "n": args.n, "stacks": 2, "dedup": not args.no_dedup}
    shapes = {s: (s in args.shapes.split(",")) for s in ("L", "Rect")}
    decomps = {d: (d in args.decomps.split(",")) for d in ("2+1", "1+1+1")}
    return {
        "m": args.m, "n": args.n, "stacks": 3,
        "shapes": shapes, "decomps": decomps,
        "allowNonCorner": args.allow_non_corner,
        "dedup": not args.no_dedup,
    }


def main(argv):
    args = parse_args(argv)

    if args.list:
        for e in Store.load_manifest():
            o = e["opts"]
            stacks = o.get("stacks", 3)
            if stacks == 2:
                detail = "stacks=2 (HC)"
            else:
                detail = (f"stacks=3 shapes={[k for k,v in o['shapes'].items() if v]} "
                          f"decomps={[k for k,v in o['decomps'].items() if v]} "
                          f"nonCorner={o['allowNonCorner']}")
            print(f"  {e['m']}x{e['n']}  count={e['count']:<5} {detail}  -> {e['file']}  ({e['generated']})")
        return 0

    if args.m is None or args.n is None:
        print("error: --m and --n required (or use --list)", file=sys.stderr)
        return 2

    opts = build_opts(args)

    if not args.force:
        cached = Store.find_cached(opts)
        if cached:
            print(f"cached: {cached['count']} solutions -> results/{cached['file']} "
                  f"({cached['generated']})  [use --force to regenerate]")
            return 0

    engine = TwoStack if opts["stacks"] == 2 else Search
    solutions, ctx, err = engine.run(opts)
    if err:
        print(f"rejected: {err}", file=sys.stderr)
        return 1
    path = Store.save_result(opts, solutions, ctx)
    fname = path.split('/')[-1]
    if opts["stacks"] == 2:
        foldable = sum(1 for s in solutions if s["verdict"]["foldable"])
        print(f"generated {len(solutions)} HC patterns (foldable 2-stack: {foldable}) "
              f"-> results/{fname}")
    else:
        twist0 = sum(1 for s in solutions if s["verdict"]["twist"] is True)
        print(f"generated {len(solutions)} solutions (Tw=0 decided: {twist0}) "
              f"-> results/{fname}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
