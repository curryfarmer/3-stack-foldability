"""Export census records as rendered foldsheets — a browsable folder of the actual patterns.

The census (census.py) stores every closing candidate as a compact JSONL row: tile ids, footprints,
twist, verdict. That is the right shape for counting and for the offline cross-decomposition scan, but
it is not something you can *look* at. This turns any slice of it back into the repo's standard per-fold
artefacts, the same ones gen_testset --quadrants emits:

    report/tri/census/<tiling>_<decomp>_K<k>/
        overlay_<uid>.png       the unfolded sheet: chains, creases, footprints
        foldsheet_<uid>.png     the printed sheet (fold this one)
        folds/<uid>.json        self-contained tri-fold/1 record (identity + topology + geometry)

`uid` is gen_testset.fold_uid, so a fold exported here carries the SAME id it would get anywhere else
in the stack: the census, the testset and the physical ground-truth log all agree on what to call it.

By default only FLAT folds (Tw=0) are exported — the census holds ~30k of them and ~2.5M jams, and the
jams are the boring half. --jams flips that; --all takes both.

Usage:
    python -m triangle.tri.export_census --decomp 2plus1              # every 2+1 fold, all tilings (57)
    python -m triangle.tri.export_census --tiling hex --kmax 5
    python -m triangle.tri.export_census --limit 3                    # 3 per cell, the whole census
"""
import argparse
import glob
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_example as FE       # noqa: E402  build_lat, render_case, set_outdir, GEN
import gen_testset as GT        # noqa: E402  fold_uid, _fold_record (the tri-fold/1 writer)
import hunt_foldable as HF      # noqa: E402  holes
import seam_filter as SFILT     # noqa: E402  apply (seam gate), tile_chirality
import solve_foldable as SF     # noqa: E402  record_111 (equilateral render rec)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CENSUS = os.path.join(REPO, "results", "census")


def _t(x):
    return tuple(x)


def cand_from_record(lat, tiling, decomp, K, r):
    """Census JSONL row -> the `cand` dict the renderers and the fold-record writer expect. This must
    reproduce find_example.gen_111/gen_21/gen_eq's yielded shape exactly, or the uid will not match."""
    fp = [_t(t) for t in r["footprint"]]
    efp = [_t(t) for t in r["end_footprint"]]

    if decomp == "2plus1":
        strand = [_t(t) for t in r["strand"]]
        one_chain = [_t(t) for t in r["one_chain"]]
        partners = [_t(t) for t in r["partners"]]
        two_tris = [_t(t) for t in r["two_tris"]]
        tw = r["tw"]
        return {"decomp": "2plus1", "chains": [strand, one_chain],
                "strand": strand, "one_chain": one_chain,
                "partners": partners, "two_tris": two_tris,
                "footprint": fp, "end_footprint": efp,
                "region": set(two_tris) | set(one_chain), "tw": tw,
                "foldable": bool(r["foldable"]), "tw_desc": "Tw(path)=%g" % tw}

    chains = [[_t(t) for t in c] for c in r["chains"]]
    region = set().union(*(set(c) for c in chains))
    tw = r["tw"]
    cand = {"decomp": "1plus1plus1", "chains": chains,
            "footprint": fp, "end_footprint": efp,
            "region": region, "tw": tw, "foldable": bool(r["foldable"]),
            "tw_desc": "Tw AB=%+d BC=%+d AC=%+d" % tuple(tw)}
    if tiling == "equilateral":
        # the equilateral 1+1+1 renderer draws from a solve_foldable record, not from `chains`
        cand["rec"] = SF.record_111(lat, chains[0], chains[1], chains[2], K)
    return cand


def export_cell(path, args, rows):
    """Render one census cell. Returns how many sheets were written."""
    stem = os.path.basename(path)[:-len(".jsonl.gz")]
    tiling, decomp, ktag = stem.rsplit("_", 2)
    K = int(ktag[1:])
    if args.tiling and tiling not in args.tiling:
        return 0
    if args.decomp and decomp not in args.decomp:
        return 0
    if not (args.kmin <= K <= args.kmax):
        return 0

    lat = FE.build_lat(tiling, decomp, K)
    interior_deg = 6 if tiling == "hex" else 3
    FE.set_outdir(os.path.join("census", stem))          # report/tri/census/<cell>/
    folds_dir = os.path.join(FE.REPORT, "folds")
    os.makedirs(folds_dir, exist_ok=True)

    made = 0
    with gzip.open(path, "rt") as fh:
        for line in fh:
            if made >= args.limit:
                break
            if not line.strip():
                continue
            r = json.loads(line)
            want = (r["foldable"] and not args.jams) or (not r["foldable"] and (args.jams or args.all))
            if not (want or (args.all and r["foldable"])):
                continue

            cand = cand_from_record(lat, tiling, decomp, K, r)
            SFILT.apply(lat, cand)                       # seam gate — can demote a Tw=0 FOLD to a JAM
            cand["holes"] = len(HF.holes(lat, cand["region"], interior_deg))
            uid = GT.fold_uid(tiling, decomp, cand)
            try:
                over, sheet, verdict = FE.render_case(tiling, decomp, "allow", lat, K, cand,
                                                      name_stem=uid)
            except Exception as e:                       # one bad cell must not kill the export
                print("   !! render failed %s %s: %s" % (stem, uid, e), flush=True)
                continue
            tc = SFILT.tile_chirality(lat, cand)
            with open(os.path.join(folds_dir, "%s.json" % uid), "w") as f:
                json.dump(GT._fold_record(uid, tiling, decomp, K, "census", cand, tc,
                                          verdict, over, sheet), f, indent=1)
            rows.append({"uid": uid, "tiling": tiling, "decomp": decomp, "K": K,
                         "tw": cand.get("tw"), "foldable": bool(cand["foldable"]),
                         "seam_class": tc.get("klass"), "verdict": verdict,
                         "dir": os.path.relpath(FE.REPORT, REPO).replace("\\", "/")})
            made += 1
    if made:
        print("%-30s %d sheet(s) -> %s" % (stem, made, os.path.relpath(FE.REPORT, REPO)), flush=True)
    return made


def write_index(out):
    """Rebuild the index from what is ON DISK, not from this run's rows — otherwise exporting one
    decomposition silently drops the other's rows from the index."""
    root = os.path.dirname(out)
    rows = []
    for p in glob.glob(os.path.join(root, "*", "folds", "*.json")):
        d = json.load(open(p))
        rows.append({"uid": d["uid"], "tiling": d["tiling"], "decomp": d["decomp"], "K": d["K"],
                     "tw": d.get("tw"), "foldable": bool(d["foldable"]),
                     "seam_class": d.get("seam_class"), "verdict": d.get("verdict"),
                     "dir": os.path.relpath(os.path.dirname(os.path.dirname(p)),
                                            REPO).replace("\\", "/")})
    flat = [r for r in rows if r["foldable"]]
    with open(out, "w") as f:
        f.write("# Census foldsheets\n\n")
        f.write("Exported from `results/census/` by `triangle/tri/export_census.py`. "
                "%d sheet(s), %d flat.\n\n" % (len(rows), len(flat)))
        f.write("Each row: `overlay_<uid>.png` (unfolded, with creases) + `foldsheet_<uid>.png` "
                "(print this one) + `folds/<uid>.json` (complete record).\n\n")
        f.write("| uid | tiling | decomp | N_t | Tw | seam | verdict | folder |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for r in sorted(rows, key=lambda r: (r["decomp"], r["tiling"], r["K"])):
            f.write("| `%s` | %s | %s | %d | %s | %s | %s | `%s` |\n"
                    % (r["uid"], r["tiling"], r["decomp"], r["K"], r["tw"],
                       r["seam_class"], "FOLD" if r["foldable"] else "JAM", r["dir"]))
    print("\n-> %s  (%d sheets, %d flat)" % (os.path.relpath(out, REPO), len(rows), len(flat)))


def main():
    ap = argparse.ArgumentParser(description="render census records as browsable foldsheets")
    ap.add_argument("--tiling", action="append", choices=["equilateral", "righttri", "scalene", "hex"])
    ap.add_argument("--decomp", action="append", choices=["1plus1plus1", "2plus1"])
    ap.add_argument("--kmin", type=int, default=0)
    ap.add_argument("--kmax", type=int, default=99)
    ap.add_argument("--limit", type=int, default=12, help="max sheets per cell (default 12)")
    ap.add_argument("--jams", action="store_true", help="export JAMs instead of folds")
    ap.add_argument("--all", action="store_true", help="export both folds and jams")
    ap.add_argument("--census", default=CENSUS)
    args = ap.parse_args()

    rows = []
    for path in sorted(glob.glob(os.path.join(args.census, "*.jsonl.gz"))):
        export_cell(path, args, rows)
    if not rows:
        print("no records matched")
        return
    write_index(os.path.join(FE._REPORT_BASE, "census", "INDEX.md"))


if __name__ == "__main__":
    main()
