"""render.py — tri-render CLI: turn a tri-fold/1 record (or a directory of them) into a self-
contained TWO-image bundle under <out>/<uid>/ (the standardised output shape, matching the square
track: one folding schematic + one twist diagram; everything non-image is JSON).

For each input record this produces:
  <out>/<uid>/<uid>.json            the record, content-preserved
  <out>/<uid>/schematic_<uid>.png   folding schematic: creases + footprints + foldpath (render_fold)
  <out>/<uid>/twist_<uid>.png       twist-enumeration diagram                       (render_twist)
  <out>/<uid>/<uid>_analysis.json   per-loop twist enumeration + seam/reflection verdict (the old
                                    stdout tables + the retired reflect_ image, now data)

  python render.py <record.json>            # single record -> out/<uid>/
  python render.py <dir-of-json>            # every *.json in the dir -> out/<uid>/ each
  python render.py <record.json> --out DIR  # write under DIR/<uid>/ instead of out/<uid>/

generate.py (tri-generate) reuses `render_record_json` below so a freshly-searched fold gets the
exact same 2-image bundle as re-rendering an existing record through this CLI.
"""
import argparse
import glob
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_fold        # noqa: E402  schematic_<uid>.png (creases + footprints + foldpath)
import render_twist       # noqa: E402  twist_<uid>.png + twist_summary (JSON)


def _analysis(json_path, uid, results):
    """Consolidated non-image analysis: the per-loop twist enumeration (render_twist.twist_summary)
    plus the seam/reflection verdict pulled from the record (the seam gate's source of truth). This
    replaces both the reflect_ image and the old per-vertex stdout tables. I/O: (path, uid, results)."""
    with open(json_path) as f:
        rec = json.load(f)
    seam = {"foldable": rec.get("foldable"), "tw": rec.get("tw"), "tw_desc": rec.get("tw_desc")}
    for k in ("seam_ok", "seam_note", "seam_detail"):
        if rec.get(k) is not None:
            seam[k] = rec[k]
    return {"uid": uid, "tiling": rec.get("tiling"), "decomp": rec.get("decomp"),
            "K": rec.get("K"), "twist": render_twist.twist_summary(results), "seam": seam}


def render_record_json(json_path, uid, out_root):
    """Render the 2-image bundle for an ALREADY-ON-DISK <uid>.json into <out_root>/<uid>/.
    Returns {'schematic':path, 'twist':path, 'analysis':path}."""
    uid_dir = os.path.abspath(os.path.join(out_root, uid))
    written = {}
    _over, sheet, _verdict = render_fold.render_fold(json_path, out_sub=uid_dir, schematic_only=True)
    written["schematic"] = sheet
    twist_png, results = render_twist.render_twist(json_path, out_sub=uid_dir)
    written["twist"] = twist_png
    apath = os.path.join(uid_dir, "%s_analysis.json" % uid)
    with open(apath, "w", encoding="utf-8") as f:
        json.dump(_analysis(json_path, uid, results), f, indent=2)
    written["analysis"] = apath
    return written


def _summary_line(uid, written):
    parts = []
    for name in ("schematic", "twist", "analysis"):
        parts.append("%s=%s" % (name, "ok" if written.get(name) else "skipped"))
    return "%s: %s" % (uid, "  ".join(parts))


def process_one(json_path, out_root):
    """Full tri-render contract for one input record file: extract uid, create <out>/<uid>/, copy
    the record verbatim into that folder, render the 4 images, print a one-line summary."""
    with open(json_path) as f:
        rec = json.load(f)
    uid = rec["uid"]
    uid_dir = os.path.abspath(os.path.join(out_root, uid))
    os.makedirs(uid_dir, exist_ok=True)
    dst = os.path.join(uid_dir, "%s.json" % uid)
    if os.path.abspath(json_path) != os.path.abspath(dst):
        shutil.copyfile(json_path, dst)          # verbatim copy, byte-for-byte
    written = render_record_json(dst, uid, out_root)
    print(_summary_line(uid, written))
    return uid, written


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="render a tri-fold/1 record (or a directory of them) into <out>/<uid>/ image bundles")
    ap.add_argument("record", help="path to a record .json, or a directory containing *.json records")
    ap.add_argument("--out", default="out", help="output root directory (default: out/)")
    args = ap.parse_args(argv)

    if os.path.isdir(args.record):
        paths = sorted(glob.glob(os.path.join(args.record, "*.json")))
        if not paths:
            print("no *.json records found in %s" % args.record)
            return 0
    else:
        paths = [args.record]

    for p in paths:
        process_one(p, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
