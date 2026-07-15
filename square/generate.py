#!/usr/bin/env python3
"""generate.py — CLI to run the square 3-stack/2-stack search and write each result as a
self-contained on-disk bundle: <out>/<uid>/{<uid>.json, foldsheet_<uid>.png[, twist_<uid>.png]}.

Examples:
  python3 generate.py --m 6 --n 6
  python3 generate.py --m 6 --n 5 --decomps 2+1 --allow-non-corner
  python3 generate.py --stacks 2 --m 6 --n 5     # RSPA 2-stack (Hamiltonian circuits)
  python3 generate.py --m 6 --n 6 --out scratch/  # write bundles under scratch/ instead of out/
  python3 generate.py --list                      # print a summary of --out's bundles

Stateless: every run re-derives and overwrites its bundles (no cache, no database). uid is a
12-hex sha1 of (lattice, MxN, canonical content) — same fold -> same id across runs, so re-running
generate with the same params is idempotent (mirrors triangle's gen_testset.fold_uid convention).
"""

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # square/ on path
import _bootstrap  # noqa: E402,F401  (puts square/{engine,twist,render} on sys.path)

import runner as Runner            # noqa: E402
import search as Search            # noqa: E402  (decomp key naming only)
import twostack as TwoStack        # noqa: E402
import render_bundle as RenderB    # noqa: E402

LATTICE_3STACK = "square"
LATTICE_2STACK = "square2stack"


def parse_args(argv):
    p = argparse.ArgumentParser(description="square folding search -> out/<uid>/ JSON+PNG bundles")
    p.add_argument("--m", type=int, help="columns")
    p.add_argument("--n", type=int, help="rows")
    p.add_argument("--stacks", type=int, default=3, choices=(2, 3),
                   help="2 = RSPA Hamiltonian-circuit 2-stack; 3 = footprint/decomp engine (default)")
    p.add_argument("--panels", type=int, default=3,
                   help="footprint panel count / chain count for the 3-stack-family engine "
                        "(default 3; use e.g. 4 or 5 for an all-singleton 1+1+1+...+1 n-stack). "
                        "--decomps '2+1' is only defined at --panels 3.")
    p.add_argument("--shapes", default="L,Rect", help="comma list: L,Rect (3-stack-family only)")
    p.add_argument("--decomps", default=None,
                   help="comma list, e.g. 2+1,1+1+1 (default: '2+1,1+1+1' at --panels 3, else "
                        "the all-singleton decomp for --panels N, e.g. '1+1+1+1' at N=4)")
    p.add_argument("--allow-non-corner", action="store_true")
    p.add_argument("--store-all", action="store_true",
                   help="Phase A: emit EVERY covered candidate (deduped up to the sheet's symmetry) "
                        "with non-destructive gate verdicts as columns, instead of pruning to "
                        "gate-survivors")
    p.add_argument("--jobs", type=int, default=None,
                   help="parallel worker processes (default 1; env FOLD_JOBS as fallback)")
    p.add_argument("--no-dedup", action="store_true",
                   help="disable canonical dedup (D4 on a square sheet, D2 otherwise)")
    p.add_argument("--force", action="store_true",
                   help="(accepted for CLI compat; a no-op now -- generate is stateless and always "
                        "re-derives + overwrites its bundles)")
    p.add_argument("--out", default="out", help="output directory for <uid>/ bundles (default: out/)")
    p.add_argument("--list", action="store_true", help="print a summary of --out's bundles and exit")
    return p.parse_args(argv)


def build_opts(args):
    if args.stacks == 2:
        return {"m": args.m, "n": args.n, "stacks": 2, "dedup": not args.no_dedup}
    if args.panels < 3:
        raise ValueError(f"--panels must be >= 3 (got {args.panels})")
    all_singleton_key = Search._all_singleton_decomp_key(args.panels)
    default_decomps = f"2+1,{all_singleton_key}" if args.panels == 3 else all_singleton_key
    decomps_str = args.decomps if args.decomps is not None else default_decomps
    shapes = {s: (s in args.shapes.split(",")) for s in ("L", "Rect")}
    decomps = {d: (d in decomps_str.split(",")) for d in ("2+1", all_singleton_key)}
    return {
        "m": args.m, "n": args.n, "stacks": 3, "panels": args.panels,
        "shapes": shapes, "decomps": decomps,
        "allowNonCorner": args.allow_non_corner,
        "dedup": not args.no_dedup,
        "jobs": args.jobs,
        "storeAll": args.store_all,
    }


def make_uid(lattice_name, m, n, canonical_hash):
    """12-hex sha1 content id. Same convention as triangle's gen_testset.fold_uid(): a stable id
    tied to (lattice, grid size, canonical fold identity), so re-running generate on the same
    params reproduces the same uid (and thus overwrites, not duplicates, the same bundle)."""
    payload = f"{lattice_name}|{m}x{n}|{canonical_hash}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _print_manifest(out_dir):
    if not os.path.isdir(out_dir):
        print(f"(no manifest -- {out_dir}/ does not exist yet)")
        return
    entries = []
    for uid in sorted(os.listdir(out_dir)):
        rec_path = os.path.join(out_dir, uid, f"{uid}.json")
        if not os.path.isfile(rec_path):
            continue
        with open(rec_path, encoding="utf-8") as f:
            entries.append(json.load(f))
    if not entries:
        print(f"(no records found under {out_dir}/)")
        return
    for rec in entries:
        lattice = rec.get("lattice", "?")
        m, n = rec.get("m", "?"), rec.get("n", "?")
        if lattice == LATTICE_2STACK:
            verdict = "FOLD" if rec.get("verdict", {}).get("foldable") else "JAM"
        else:
            tw = rec.get("verdict", {}).get("twist")
            verdict = "FOLD" if tw is True else ("JAM" if tw is False else "?")
        print(f"  {rec.get('uid')}  {lattice}  {m}x{n}  {verdict}")
    print(f"{len(entries)} record(s) under {out_dir}/")


def main(argv=None):
    args = parse_args(argv)

    if args.list:
        _print_manifest(args.out)
        return 0

    if args.m is None or args.n is None:
        print("error: --m and --n required (or use --list)", file=sys.stderr)
        return 2

    opts = build_opts(args)

    if opts["stacks"] == 2:
        solutions, ctx, err = TwoStack.run(opts)
    else:
        solutions, ctx, err = Runner.run_search(opts)  # PyPy + multiprocessing toggles
    if err:
        print(f"rejected: {err}", file=sys.stderr)
        return 1

    m, n = args.m, args.n
    for sol in solutions:
        sol["m"], sol["n"] = m, n
        if opts["stacks"] == 2:
            sol["lattice"] = LATTICE_2STACK
            sol["stacks"] = 2
            # uid already stamped by twostack.run() (no canonicalHash concept for 2-stack)
        else:
            sol["lattice"] = LATTICE_3STACK
            sol["stacks"] = opts.get("panels", 3)
            sol["uid"] = make_uid(LATTICE_3STACK, m, n, sol["canonicalHash"])
        produced = RenderB.render_record(sol, args.out)
        print(f"  [{sol['uid']}] -> {produced.get('foldsheet', produced['json'])}")

    if opts["stacks"] == 2:
        print(f"search: {ctx['hcCount']} Hamiltonian circuit(s) -> reflection {ctx['reflectionPass']}, "
              f"twist {ctx['twistPass']}, foldable {ctx['foldable']}")
        print(f"generated {len(solutions)} HC patterns (foldable 2-stack: {ctx['foldable']}) "
              f"-> {args.out}/ ({len(solutions)} bundles)")
    else:
        print(f"search: {ctx['footprintsTried']}/{ctx['footprintsTotal']} footprint(s), "
              f"{ctx['decompCount']} decomposition(s) explored -> exit {ctx['exitPass']}, "
              f"parity {ctx['parityPass']}, reflection {ctx['reflPass']}, "
              f"after-dedup {ctx['afterDedup']}, twist-FOLD {ctx['twistPass']}")
        twist0 = sum(1 for s in solutions if s["verdict"]["twist"] is True)
        print(f"generated {len(solutions)} solutions (Tw=0 decided: {twist0}) "
              f"-> {args.out}/ ({len(solutions)} bundles)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
