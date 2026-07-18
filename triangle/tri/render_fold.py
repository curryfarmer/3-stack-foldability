"""render_fold.py — re-render a saved 3-stack fold sheet + overlay from its self-contained data file.

Each fold in the MVP matrix (gen_testset.py --quadrants) is written to
report/tri/<matrix>/folds/<uid>.json with everything needed to redraw it. This entry makes that file
the RENDER SOURCE OF TRUTH: it rebuilds the ambient lattice for (tiling, decomp, K), restores the
candidate (tile ids -> tuples; equilateral 1+1+1 rebuilds its solver `rec` from the saved chains),
and calls find_example.render_case — so the sheet a uid re-renders to is the exact one the matrix
generated (the matrix generator itself renders through the same render_case path).

  python -m triangle.tri.render_fold --uid <uid> [--matrix mvp_matrix] [--outdir <sub>]
  python -m triangle.tri.render_fold --json report/tri/mvp_matrix/folds/<uid>.json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_example as FE     # noqa: E402  build_lat / render_case / GEN / set_outdir
import solve_foldable as SF   # noqa: E402  record_111 (equilateral 1+1+1 rec rebuild)


def _cand_from_record(rec, lat, K):
    """Restore the in-memory candidate render_case consumes from a folds/<uid>.json record: tile ids
    back to tuples, region back to a set, seam verdict fields restored (so verdict_text reproduces),
    and — for equilateral 1+1+1 only — its solver `rec` rebuilt from the saved chains."""
    tiling, decomp = rec["tiling"], rec["decomp"]
    chains = [[tuple(t) for t in c] for c in rec["chains"]]
    cand = {
        "decomp": decomp,
        "chains": chains,
        "footprint": [tuple(t) for t in rec["footprint"]],
        "end_footprint": [tuple(t) for t in rec["end_footprint"]],
        "region": set(tuple(t) for t in rec["region"]),
        "foldable": rec["foldable"],
        "tw": rec.get("tw"), "tw_desc": rec.get("tw_desc"),
        "holes": rec.get("holes", 0),
    }
    for k in ("seam_ok", "seam_detail", "seam_note"):        # restore post-apply seam state
        if rec.get(k) is not None:
            cand[k] = rec[k]
    if "partners" in rec:
        cand["partners"] = [tuple(t) for t in rec["partners"]]
    if "two_tris" in rec:
        cand["two_tris"] = [tuple(t) for t in rec["two_tris"]]
    if tiling == "equilateral" and decomp == "1plus1plus1":  # SF.render_111 path needs the solver rec
        cand["rec"] = SF.record_111(lat, chains[0], chains[1], chains[2], K)
    return cand


def render_fold(json_path, out_sub=None, schematic_only=False, chrome=True):
    """Load a folds/<uid>.json and redraw it. Returns (overlay, sheet, verdict) — with
    schematic_only=True the overlay is None and the sheet is the single folding schematic
    (creases + footprints + foldpath), named schematic_<uid>.png (the per-fold bundle path).
    chrome=False renders the sheet BARE (no title/legend/notes) for report montages.
    Output goes to report/tri/<out_sub> (default: the matrix folder that holds this fold)."""
    with open(json_path) as f:
        rec = json.load(f)
    tiling, decomp, K, uid = rec["tiling"], rec["decomp"], rec["K"], rec["uid"]
    if out_sub is None:                                      # .../<sub>/folds/<uid>.json -> <sub>
        out_sub = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(json_path))))
    FE.set_outdir(out_sub)
    lat = FE.build_lat(tiling, decomp, K)
    cand = _cand_from_record(rec, lat, K)
    return FE.render_case(tiling, decomp, rec.get("holes_mode", "allow"),
                          lat, K, cand, name_stem=uid, schematic_only=schematic_only, chrome=chrome)


def main():
    ap = argparse.ArgumentParser(description="re-render a saved 3-stack fold from its data file")
    ap.add_argument("--uid", help="fold uid (resolves to report/tri/<matrix>/folds/<uid>.json)")
    ap.add_argument("--json", help="explicit path to a folds/<uid>.json")
    ap.add_argument("--matrix", default="mvp_matrix",
                    help="matrix subdir under report/tri to resolve --uid (default mvp_matrix)")
    ap.add_argument("--outdir", help="write PNGs under report/tri/<outdir> (default: the matrix dir)")
    args = ap.parse_args()
    if args.json:
        path = args.json
    elif args.uid:
        path = os.path.join(FE._REPORT_BASE, args.matrix, "folds", "%s.json" % args.uid)
    else:
        ap.error("give --uid or --json")
    over, sheet, verdict = render_fold(path, out_sub=args.outdir)
    print("uid %s" % os.path.splitext(os.path.basename(path))[0])
    print("  overlay:  %s" % os.path.relpath(over))
    print("  foldsheet:%s" % os.path.relpath(sheet))
    print("  verdict:  %s" % verdict)


if __name__ == "__main__":
    main()
