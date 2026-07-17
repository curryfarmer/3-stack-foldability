"""render_bundle.py — shared "given a stamped record, write its bundle" logic, imported by bare name
by both generate.py (auto-render immediately after producing a candidate) and render_cli.py (the
standalone sq-render CLI). The two callers keep their own argument parsing / file discovery and share
only this dispatch, so a record renders identically whether it was just generated or re-read off disk.

A record is a stamped, self-contained dict: 3-stack (has "footprint" + "chains", from search.py's
sol shape) or 2-stack (has "circuit", from twostack.py's sol shape). Both must carry "uid", "m",
"n" before being handed here.

Standardised two-image bundle (matching the triangle track): every record writes exactly
<out_dir>/<uid>/<uid>.json (verbatim) + schematic_<uid>.png (the folding schematic: footprint +
base cells + foldpath) + twist_<uid>.png (the twist-calc diagram). The twist diagram is the
jump-strand loop for 3-stack 2+1 (render_twist_2plus1), the pairwise-loop diagram for 3-stack 1+1+1
(render_twist_111), and the Hamiltonian-circuit turn-angle analysis for 2-stack
(render_twostack.render_analysis). Nothing non-image is emitted outside the JSON record.
"""
import json
import os

import render_square
import render_twostack
import render_twist_2plus1 as _rt21
import render_twist_111 as _rt111


def is_3stack(rec):
    return "chains" in rec and "footprint" in rec


def is_2stack(rec):
    return "circuit" in rec


def render_record(rec, out_dir, *, title=None):
    """Write <out_dir>/<uid>/{<uid>.json, schematic_<uid>.png, twist_<uid>.png}.

    rec must already carry 'uid', 'm', 'n' (stamped by generate.py/twostack.py, or read verbatim
    off a previously-generated record.json). Returns {"json": path, "schematic": path, "twist": path}.
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
    twist_path = os.path.join(rec_dir, f"twist_{uid}.png")
    if is_3stack(rec):
        schematic_path = os.path.join(rec_dir, f"schematic_{uid}.png")
        render_square.render(rec, m, n, schematic_path, title=label)
        produced["schematic"] = schematic_path
        # every fold gets a twist diagram: 2+1 -> jump-strand loop; 1+1+1/n-singleton -> pairwise loops
        if rec.get("decomposition") == "2+1":
            _rt21.render_twist_2plus1(uid, rec, m, n, twist_path)
        else:
            _rt111.render_twist_111(uid, rec, m, n, twist_path)
        produced["twist"] = twist_path
    elif is_2stack(rec):
        schematic_path = os.path.join(rec_dir, f"schematic_{uid}.png")
        render_twostack.render_foldsheet(rec, m, n, schematic_path, title=label)
        produced["schematic"] = schematic_path
        render_twostack.render_analysis(rec, m, n, twist_path, title=label)
        produced["twist"] = twist_path
    else:
        raise ValueError(f"record {uid} has neither 'footprint'+'chains' nor 'circuit' -- unknown schema")
    return produced
