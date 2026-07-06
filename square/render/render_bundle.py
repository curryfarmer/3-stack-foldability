"""render_bundle.py — shared "given a stamped record, write its bundle" logic used by both
generate.py (auto-render immediately after producing a candidate) and render.py (the standalone
sq-render CLI). Factored out as its own module — rather than a function inside render.py — because
square/render.py (a plain file) and square/render/ (this package, since it has __init__.py) share
a name: `import render` from anywhere with square/ on sys.path resolves to the PACKAGE, not the
file, so generate.py cannot reliably `import render`. Both callers instead import this module by
its own unambiguous name.

A record is a stamped, self-contained dict: 3-stack (has "footprint" + "chains", from search.py's
sol shape) or 2-stack (has "circuit", from twostack.py's sol shape). Both must carry "uid", "m",
"n" before being handed here.

Writes <out_dir>/<uid>/<uid>.json (verbatim) + foldsheet_<uid>.png, and for 3-stack 2+1 records
also twist_<uid>.png (the jump-strand twist-loop diagram; 1+1+1 has no analogous diagram, so it is
skipped with a printed note).
"""
import json
import os

import render_square
import render_twostack
import render_twist_2plus1 as _rt21


def is_3stack(rec):
    return "chains" in rec and "footprint" in rec


def is_2stack(rec):
    return "circuit" in rec


def render_record(rec, out_dir, *, title=None):
    """Write <out_dir>/<uid>/{<uid>.json, foldsheet_<uid>.png[, twist_<uid>.png]}.

    rec must already carry 'uid', 'm', 'n' (stamped by generate.py/twostack.py, or read verbatim
    off a previously-generated record.json). Returns {"json": path, "foldsheet": path, ["twist": path]}.
    """
    uid = rec.get("uid")
    if not uid:
        raise ValueError("record is missing 'uid' -- stamp it before calling render_record()")
    m, n = rec.get("m"), rec.get("n")
    if m is None or n is None:
        raise ValueError(f"record {uid} is missing 'm'/'n' -- stamp them before calling render_record()")

    rec_dir = os.path.join(out_dir, uid)
    os.makedirs(rec_dir, exist_ok=True)
    json_path = os.path.join(rec_dir, f"{uid}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2)
    produced = {"json": json_path}

    label = title or uid
    if is_3stack(rec):
        foldsheet_path = os.path.join(rec_dir, f"foldsheet_{uid}.png")
        render_square.render(rec, m, n, foldsheet_path, title=label)
        produced["foldsheet"] = foldsheet_path
        if rec.get("decomposition") == "2+1":
            twist_path = os.path.join(rec_dir, f"twist_{uid}.png")
            _rt21.render_twist_2plus1(uid, rec, m, n, twist_path)
            produced["twist"] = twist_path
        else:
            print(f"  [{uid}] decomposition={rec.get('decomposition')} -- no twist-loop diagram (2+1 only)")
    elif is_2stack(rec):
        foldsheet_path = os.path.join(rec_dir, f"foldsheet_{uid}.png")
        render_twostack.render_foldsheet(rec, m, n, foldsheet_path, title=label)
        produced["foldsheet"] = foldsheet_path
    else:
        raise ValueError(f"record {uid} has neither 'footprint'+'chains' nor 'circuit' -- unknown schema")
    return produced
