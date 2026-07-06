"""render.py — tri-render CLI: turn a tri-fold/1 record (or a directory of them) into a self-
contained image bundle under <out>/<uid>/.

For each input record this produces:
  <out>/<uid>/<uid>.json           the record, content-preserved
  <out>/<uid>/overlay_<uid>.png    chain overlay              (render_fold.render_fold)
  <out>/<uid>/foldsheet_<uid>.png  printable foldsheet         (render_fold.render_fold)
  <out>/<uid>/twist_<uid>.png      twist-enumeration diagram   (render_twist.render_twist)
  <out>/<uid>/reflect_<uid>.png    vector-reflection diagram   (render_reflection.render_reflection)
                                   — SKIPPED for equilateral 1+1+1 records (no chain-footprint
                                   geometry to fold; render_reflection raises SystemExit for that
                                   shape by design, see its module docstring).

  python render.py <record.json>            # single record -> out/<uid>/
  python render.py <dir-of-json>            # every *.json in the dir -> out/<uid>/ each
  python render.py <record.json> --out DIR  # write under DIR/<uid>/ instead of out/<uid>/

generate.py (tri-generate) reuses `render_record_json` below so a freshly-searched fold gets the
exact same 4-image bundle as re-rendering an existing record through this CLI.
"""
import argparse
import glob
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_fold        # noqa: E402  overlay_<uid>.png + foldsheet_<uid>.png
import render_twist       # noqa: E402  twist_<uid>.png
import render_reflection  # noqa: E402  reflect_<uid>.png (raises SystemExit if not applicable)


def render_record_json(json_path, uid, out_root):
    """Render the 4-image bundle for an ALREADY-ON-DISK <uid>.json into <out_root>/<uid>/.
    Returns {'overlay':path,'foldsheet':path,'twist':path,'reflect':path-or-None}."""
    uid_dir = os.path.abspath(os.path.join(out_root, uid))
    written = {}
    over, sheet, _verdict = render_fold.render_fold(json_path, out_sub=uid_dir)
    written["overlay"], written["foldsheet"] = over, sheet
    twist_png, _results = render_twist.render_twist(json_path, out_sub=uid_dir)
    written["twist"] = twist_png
    try:
        reflect_png, _chir = render_reflection.render_reflection(json_path, out_sub=uid_dir)
        written["reflect"] = reflect_png
    except SystemExit:
        # expected for equilateral 1+1+1 records: they carry a solver `rec`, not chain/footprint
        # geometry, so there is nothing for the vector-reflection diagram to fold.
        print("skipped reflect_%s.png: no chain-footprint geometry for this record" % uid)
        written["reflect"] = None
    return written


def _summary_line(uid, written):
    parts = []
    for name in ("overlay", "foldsheet", "twist", "reflect"):
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
