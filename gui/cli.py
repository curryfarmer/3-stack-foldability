"""cli.py — headless front-end: fold a drawn region (a fold-grid/1 file) and print the filtered
verdict table, with no display. Run as `python -m gui.cli --grid-file REGION.json [options]`.

Shares the GUI's exact core: gui.dispatch.fold_once runs the S7 orchestrator orphan-free (imports NO
engine -- subprocess only), gui.results.parse_bundle reads the bundle, gui.foldfilter applies the same
predicates the GUI's filter bar does. So the two front-ends fold + filter identically; this one just
renders to stdout instead of tk.

  python -m gui.cli --grid-file region.json --first --only-foldable
  python -m gui.cli --grid-file region.json --stacks 2,3 --decomp 2+1 --require reflection,twist
  python -m gui.cli --grid-file region.json --json           # machine-readable rows
"""
import argparse
import json
import os
import sys

from gui import dispatch, foldfilter, results

# gate-component aliases accepted by --require (-> the verdict-vector key)
_GATE_ALIASES = {
    "exit": "exitFootprint", "exitfootprint": "exitFootprint", "footprint": "exitFootprint",
    "parity": "parity", "reflection": "reflection", "refl": "reflection",
    "twist": "twist", "arithmetic": "arithmetic",
}
_TABLE_COLS = (("uid", 14), ("stacks", 7), ("decomp", 8), ("foldable", 9), ("proven", 7),
               ("gates", 22), ("dir", 14))


def _load_region(path):
    """Read a fold-grid/1 file -> (tiling, cells, stacks_hint). I/O: (str) -> (str, list, list|None)."""
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    if spec.get("schema") != "fold-grid/1":
        raise ValueError("grid-file schema must be 'fold-grid/1', got %r" % spec.get("schema"))
    tiling, cells = spec.get("tiling"), spec.get("cells")
    if not tiling or not isinstance(cells, list) or not cells:
        raise ValueError("grid-file must name a tiling and a non-empty 'cells' array")
    hint = spec.get("stacks")
    return tiling, cells, (hint if isinstance(hint, list) else None)


def _parse_stacks(s):
    return [int(x) for x in s.split(",") if x.strip()] if s else None


def _require_vector(s):
    """Map --require "reflection,twist" -> {"reflection": True, "twist": True}. I/O: (str|None) -> dict."""
    out = {}
    for tok in (s or "").split(","):
        tok = tok.strip().lower()
        if not tok:
            continue
        key = _GATE_ALIASES.get(tok)
        if key is None:
            raise ValueError("unknown gate %r in --require (want: %s)"
                             % (tok, ", ".join(sorted(set(_GATE_ALIASES)))))
        out[key] = True
    return out


def _reason(output):
    lines = [ln.strip() for ln in (output or "").splitlines() if ln.strip()]
    for ln in reversed(lines):
        if ln.lower().startswith(("error:", "rejected:")):
            return ln
    return lines[-1] if lines else "see console"


def _print_table(rows):
    header = "  ".join(name.ljust(w) for name, w in _TABLE_COLS)
    print(header)
    print("  ".join("-" * w for _n, w in _TABLE_COLS))
    for r in rows:
        cells = {
            "uid": str(r.get("uid") or ""), "stacks": str(r.get("stacks") or ""),
            "decomp": r.get("decomp") or "-", "foldable": str(r.get("foldable")),
            "proven": str(r.get("proven")), "gates": foldfilter.vector_summary(r.get("vector")),
            "dir": str(r.get("dir") or ""),
        }
        print("  ".join(cells[name][:w].ljust(w) for name, w in _TABLE_COLS))


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="fold-cli", description="fold a drawn region (fold-grid/1) and print the filtered verdicts")
    ap.add_argument("--grid-file", required=True, help="a fold-grid/1 JSON region to fold")
    ap.add_argument("--out", default="out", help="bundle output root (default: ./out)")
    # search-shaping (what the engine computes)
    ap.add_argument("--stacks", default=None, help="comma list of square stack counts, e.g. 2,3")
    ap.add_argument("--decomps", default=None, help="restrict SQUARE decomps searched: '2+1' or '1+1+1'")
    ap.add_argument("--first", action="store_true", help="stop at the first foldable example (fast)")
    ap.add_argument("--timeout", type=float, default=None, help="per-engine wall-clock budget (seconds)")
    # display filters (which computed rows to show) -- gui.foldfilter, shared with the GUI
    ap.add_argument("--decomp", default=None, help="show only these decomps, comma list (2+1,1+1+1)")
    ap.add_argument("--require", default=None,
                    help="show only rows PASSING these gates, comma list (exit,parity,reflection,twist)")
    ap.add_argument("--only-foldable", action="store_true", help="show only foldable rows")
    ap.add_argument("--json", action="store_true", help="emit the filtered rows as JSON, not a table")
    args = ap.parse_args(argv)

    try:
        tiling, cells, hint = _load_region(args.grid_file)
        require = _require_vector(args.require)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    stacks = _parse_stacks(args.stacks) or hint
    out_dir = os.path.abspath(args.out)
    if not args.json:
        print("folding %s |cells|=%d%s ..."
              % (tiling, len(cells), " (first example)" if args.first else ""))
    result = dispatch.fold_once(tiling, cells, out_dir=out_dir, stacks=stacks, decomps=args.decomps,
                                first=args.first, timeout=args.timeout,
                                on_line=(None if args.json else lambda s: sys.stdout.write(s)))
    if not result.bundle_path:
        print("error: no bundle (rc=%s): %s" % (result.returncode, _reason(result.output)),
              file=sys.stderr)
        return 1

    rows, gate_unproven = results.parse_bundle(result.bundle_path)
    shown = foldfilter.apply(
        rows,
        decomps=(args.decomp.split(",") if args.decomp else None),
        require_vector=(require or None),
        foldable=(True if args.only_foldable else None),
    )
    if args.json:
        json.dump({"gridUid": result.grid_uid, "gateValidityUnproven": gate_unproven,
                   "shown": len(shown), "total": len(rows), "records": shown}, sys.stdout, indent=1)
        sys.stdout.write("\n")
    else:
        print("\n%d of %d record(s)%s -> %s"
              % (len(shown), len(rows), " (unproven)" if gate_unproven else "", result.bundle_path))
        _print_table(shown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
