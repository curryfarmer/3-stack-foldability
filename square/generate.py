#!/usr/bin/env python3
"""generate.py — CLI to run the square 3-stack/2-stack search and write each result as a
self-contained on-disk bundle: <out>/<uid>/{<uid>.json, schematic_<uid>.png, twist_<uid>.png}.

Examples:
  python3 generate.py --m 6 --n 6
  python3 generate.py --m 6 --n 5 --decomps 2+1 --allow-non-corner
  python3 generate.py --stacks 2 --m 6 --n 5     # RSPA 2-stack (Hamiltonian circuits)
  python3 generate.py --stacks 4 --m 4 --n 8     # 4-stack (all-singleton 1+1+1+1)
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

import nstack as NStack            # noqa: E402  (build_opts delegation + decomp key naming)
import runner as Runner            # noqa: E402
import twostack as TwoStack        # noqa: E402
import render_bundle as RenderB    # noqa: E402
import gridfile as GridFile        # noqa: E402  (fold-grid/1 ingest)

LATTICE_3STACK = "square"
LATTICE_2STACK = "square2stack"


def parse_args(argv):
    p = argparse.ArgumentParser(description="square folding search -> out/<uid>/ JSON+PNG bundles")
    p.add_argument("--m", type=int, help="columns (rectangle sheet; mutually exclusive with --grid-file)")
    p.add_argument("--n", type=int, help="rows (rectangle sheet; mutually exclusive with --grid-file)")
    p.add_argument("--grid-file", default=None,
                   help="path to a fold-grid/1 JSON file describing an arbitrary connected polyomino "
                        "sheet (see docs/schema/fold-grid-1.md); ingested to non-corner. Mutually "
                        "exclusive with --m/--n.")
    # Both default to None (the "not given" sentinel), NOT to 3 -- resolve_stacks() below must be
    # able to tell `--panels 4` (alone) from an explicit `--stacks 3 --panels 4` (a contradiction).
    p.add_argument("--stacks", type=int, default=None,
                   help="chain/stack count. 2 = RSPA Hamiltonian-circuit 2-stack; N>=3 = "
                        "footprint/decomp engine with N chains (default 3). N>3 is an n-stack: "
                        "the all-singleton 1+1+...+1 decomposition.")
    p.add_argument("--panels", type=int, default=None,
                   help="DEPRECATED back-compat alias for --stacks at N>=3. Prefer --stacks. "
                        "Giving both is an error unless they agree.")
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
    p.add_argument("--first", action="store_true",
                   help="stop at the FIRST foldable example instead of enumerating all (find-example "
                        "mode). Forces the serial 3-stack path (early stop can't cross workers).")
    p.add_argument("--no-dedup", action="store_true",
                   help="disable canonical dedup (D4 on a square sheet, D2 otherwise)")
    p.add_argument("--force", action="store_true",
                   help="(accepted for CLI compat; a no-op now -- generate is stateless and always "
                        "re-derives + overwrites its bundles)")
    p.add_argument("--out", default="out", help="output directory for <uid>/ bundles (default: out/)")
    p.add_argument("--list", action="store_true", help="print a summary of --out's bundles and exit")
    return p.parse_args(argv)


def resolve_stacks(stacks, panels):
    """Reconcile --stacks with its deprecated alias --panels -> the chain count N.

    --stacks USED to be capped at choices=(2, 3), so n-stack was only reachable through the separate
    --panels knob; --stacks is now the one knob and --panels is kept working for existing callers.
    Precedence (both None means "not given"):
        neither          -> 3         (the historical default)
        --panels P only  -> P         (back-compat: `--panels 4` alone must keep working)
        --stacks S only  -> S
        both, S == P     -> S
        both, S != P     -> error     (a contradiction; refuse rather than silently pick one)
    2-stack is a different engine with no panel concept, so --panels alongside --stacks 2 is an
    error too. I/O: (stacks|None, panels|None) -> int N. Raises ValueError."""
    if stacks == 2:
        if panels is not None:
            raise ValueError("--panels is meaningless with --stacks 2 (the 2-stack engine has no "
                             "panel decomposition); drop --panels")
        return 2
    if stacks is not None and panels is not None and stacks != panels:
        raise ValueError(f"--stacks {stacks} contradicts --panels {panels} (--panels is a "
                         f"deprecated alias for --stacks); pass only --stacks")
    n = stacks if stacks is not None else (panels if panels is not None else 3)
    if n < 3:
        # stacks==2 already returned above, so a 2 here came from `--panels 2`: the 2-stack engine
        # is a different code path, not a 2-panel decomposition.
        raise ValueError(f"invalid stack count {n}: use --stacks 2 for the RSPA 2-stack engine, "
                         f"or --stacks N with N >= 3 for the decomposition engine")
    return n


def _grid_stacks_hint(raw):
    """Interpret a fold-grid/1 'stacks' hint -> a single chain count, or None to defer to the default.

    Accepts "auto"/absent (-> None), a bare int, or the schema's list form ([N] -> N). A multi-count
    hint like [2, 3] can't be resolved to a single run, and a malformed value is rejected outright.
    I/O: (raw hint) -> int | None. Raises ValueError on an unresolvable/ill-typed hint."""
    if raw is None or raw == "auto":
        return None
    if isinstance(raw, bool):
        raise ValueError(f"fold-grid: 'stacks' hint must be a count or list of counts, got {raw!r}")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, list):
        ints = [v for v in raw if isinstance(v, int) and not isinstance(v, bool)]
        if len(raw) == 1 and len(ints) == 1:
            return ints[0]
        raise ValueError(f"fold-grid: 'stacks' hint {raw!r} does not name a single count -- pass "
                         f"--stacks explicitly to pick one")
    raise ValueError(f"fold-grid: 'stacks' hint must be a count, list of counts, or \"auto\", "
                     f"got {raw!r}")


def build_opts(args):
    """Map parsed CLI args (+ an optional --grid-file) -> the opts dict the search/2-stack engines take.
    I/O: (argparse.Namespace) -> dict. Loads --grid-file (a malformed file raises ValueError)."""
    # A grid-file supplies the sheet (a LIST) + its bounding box m,n; --m/--n supply a rectangle.
    grid = GridFile.load_grid(args.grid_file) if args.grid_file else None
    # Stack count: an explicit CLI --stacks/--panels always wins; otherwise a grid-file's 'stacks'
    # hint is consumed (a drawn grid can request e.g. a 4-stack with no CLI flag). "auto"/absent =>
    # the historical 3-stack default.
    stacks_arg = args.stacks
    if stacks_arg is None and args.panels is None and grid is not None:
        stacks_arg = _grid_stacks_hint(grid.get("stacks"))
    n_stacks = resolve_stacks(stacks_arg, args.panels)
    if grid is not None:
        m, n, sheet = grid["m"], grid["n"], grid["sheet"]
    else:
        m, n, sheet = args.m, args.n, None
    if n_stacks == 2:
        # 2-stack now ingests a drawn sheet too (twostack.run re-derives the bbox + guards the
        # sheet); a rectangle keeps opts["sheet"] absent -> the byte-identical historic path.
        ignored = [f for f, given in (("--store-all", args.store_all),
                                      ("--shapes", args.shapes != "L,Rect"),
                                      ("--decomps", args.decomps is not None),
                                      ("--jobs", args.jobs is not None)) if given]
        if ignored:
            print(f"warning: --stacks 2 ignores {', '.join(ignored)} (the RSPA 2-stack engine has no "
                  f"footprint/decomposition/store-all/parallel phase)", file=sys.stderr)
        opts = {"m": m, "n": n, "stacks": 2, "dedup": not args.no_dedup, "first": args.first}
        if sheet is not None:
            opts["sheet"] = sheet
        return opts
    panels = n_stacks
    all_singleton_key = NStack.all_singleton_decomp_key(panels)
    default_decomps = f"2+1,{all_singleton_key}" if panels == 3 else all_singleton_key
    decomps_str = args.decomps if args.decomps is not None else default_decomps
    shapes = {s: (s in args.shapes.split(",")) for s in ("L", "Rect")}
    decomps = {d: (d in decomps_str.split(",")) for d in ("2+1", all_singleton_key)}
    # The m/n/panels/allowNonCorner/dedup/jobs skeleton is identical to the n-stack front door;
    # delegate it to nstack.build_opts (single source of truth) so the two can't drift, then layer
    # the generate-specific extras on top. An arbitrary sheet has no canonical corner, so it is
    # always searched to non-corner (the engine drops the corner special-case whenever a sheet is
    # present regardless of this flag; passed here too so opts is self-describing -- corner-only
    # understates/hides foldability).
    opts = NStack.build_opts(m, n, panels,
                             allow_non_corner=args.allow_non_corner or (sheet is not None),
                             dedup=not args.no_dedup,
                             jobs=args.jobs)
    # generate configures shapes/decomps from the CLI (nstack fixes them to the frozen-oracle
    # values); override those two, then add the engine keys nstack's row schema deliberately omits.
    opts["shapes"] = shapes
    opts["decomps"] = decomps
    opts["stacks"] = 3
    opts["storeAll"] = args.store_all
    opts["first"] = args.first
    if sheet is not None:
        opts["sheet"] = sheet
    return opts


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

    if args.grid_file and (args.m is not None or args.n is not None):
        print("error: --grid-file is mutually exclusive with --m/--n", file=sys.stderr)
        return 2
    if not args.grid_file and (args.m is None or args.n is None):
        print("error: --m and --n required (or --grid-file, or --list)", file=sys.stderr)
        return 2

    try:
        opts = build_opts(args)                 # loads the grid-file too (a bad file raises ValueError)
    except (ValueError, OSError) as exc:        # a bad --stacks/--panels combo or grid-file is a USAGE
        print(f"error: {exc}", file=sys.stderr)  # error, not a crash -- argparse used to catch this
        return 2                                 # itself via choices=(2, 3)

    if opts["stacks"] == 2:
        solutions, ctx, err = TwoStack.run(opts)
    else:
        solutions, ctx, err = Runner.run_search(opts)  # PyPy + multiprocessing toggles
    if err:
        print(f"rejected: {err}", file=sys.stderr)
        return 1

    m, n = opts["m"], opts["n"]      # bbox when a grid-file sheet was ingested; args.m/args.n otherwise
    for sol in solutions:
        sol["m"], sol["n"] = m, n
        if opts.get("sheet") is not None:
            # arbitrary drawn region S (origin-normalized, same frame as the renderer + bundle
            # sheetCells) -> render_square masks the grid to S. Absent for rectangle sheets.
            sol["sheetCells"] = opts["sheet"]
        if opts["stacks"] == 2:
            sol["lattice"] = LATTICE_2STACK
            sol["stacks"] = 2
            # uid already stamped by twostack.run() (no canonicalHash concept for 2-stack)
        else:
            sol["lattice"] = LATTICE_3STACK
            sol["stacks"] = opts.get("panels", 3)
            sol["uid"] = make_uid(LATTICE_3STACK, m, n, sol["canonicalHash"])
        produced = RenderB.render_record(sol, args.out)
        print(f"  [{sol['uid']}] -> {produced.get('schematic', produced['json'])}")

    if opts["stacks"] == 2:
        print(f"search: {ctx['hcCount']} Hamiltonian circuit(s) -> reflection {ctx['reflectionPass']}, "
              f"twist {ctx['twistPass']}, foldable {ctx['foldable']}")
        print(f"generated {len(solutions)} HC patterns (foldable 2-stack: {ctx['foldable']}) "
              f"-> {args.out}/ ({len(solutions)} bundles)")
    else:
        print(f"search: {ctx['footprintsTried']}/{ctx['footprintsTotal']} footprint(s), "
              f"{ctx['decompCount']} decomposition(s) explored, "
              f"{ctx['coveredCount']} candidate(s) tried -> exit {ctx['exitPass']}, "
              f"parity {ctx['parityPass']}, reflection {ctx['reflPass']}, "
              f"after-dedup {ctx['afterDedup']}, twist-FOLD {ctx['twistPass']}")
        twist0 = sum(1 for s in solutions if s["verdict"]["twist"] is True)
        print(f"generated {len(solutions)} solutions (Tw=0 decided: {twist0}) "
              f"-> {args.out}/ ({len(solutions)} bundles)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
