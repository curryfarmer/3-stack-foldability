"""s3_uid_map.py — report which bundle uids the S3 canonical-hash migration invalidated.

`generate.make_uid` hashes the canonicalHash into the 12-hex bundle uid, so every record whose
hash the S3 migration rewrote also has a new uid. Any on-disk `<uid>/` bundle directory, batch
manifest, or doc citing an OLD non-square uid is now stale.

This only REPORTS. It renames nothing: the affected bundles are untracked scratch (g_*/ dirs) and
research notes, and silently rewriting either is not this session's business.

Diffs the pre-migration backups against the live files, so it must be run against a backup taken
before `migrate_canonical_hash.py --apply`.

  python scripts/s3_uid_map.py [BACKUP_DIR]      # default: results/backup_pre_s3_2026-07-16
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "square"))
import _bootstrap  # noqa: E402,F401

from generate import make_uid  # noqa: E402

DEFAULT_BACKUP = os.path.join(_ROOT, "results", "backup_pre_s3_2026-07-16")
OUT = os.path.join(_ROOT, "results", "s3_uid_map.json")

# (backup filename, live path, how to pull [(grid, hash, id)] out of it)
PAIRS = [
    ("foldfindings.json", os.path.join(_ROOT, "results", "foldfindings.json"), "findings"),
    ("twoplus1_labels.json",
     os.path.join(_ROOT, "square", "tests", "fixtures", "twoplus1_labels.json"), "labels"),
    ("to_test_folds.json", os.path.join(_ROOT, "results", "to_test_folds.json"), "to_test"),
]


def _records(path, kind):
    with open(path) as f:
        d = json.load(f)
    recs = d["folds"] if kind == "to_test" else d
    return [(r["grid"], r["canonicalHash"], r.get("id")) for r in recs]


def main():
    backup = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BACKUP
    out = {}
    for fn, live, kind in PAIRS:
        old = _records(os.path.join(backup, fn), kind)
        new = _records(live, kind)
        if len(old) != len(new):
            raise SystemExit(f"{fn}: {len(old)} backup records vs {len(new)} live — refusing to guess")
        for (g_o, h_o, id_o), (g_n, h_n, id_n) in zip(old, new):
            if (g_o, id_o) != (g_n, id_n):
                raise SystemExit(f"{fn}: record order/identity moved ({g_o}#{id_o} vs {g_n}#{id_n})")
            if h_o == h_n:
                continue
            m, n = (int(v) for v in g_o.split("x"))
            u_o, u_n = make_uid("square", m, n, h_o), make_uid("square", m, n, h_n)
            out[u_o] = {"newUid": u_n, "grid": g_o, "id": id_o, "source": kind}

    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)

    print(f"{len(out)} bundle uid(s) invalidated by the S3 migration\n")
    print("  old_uid       -> new_uid       grid   id   source")
    for u_o, r in sorted(out.items(), key=lambda kv: (kv[1]["grid"], str(kv[1]["id"]))):
        print("  %-12s  -> %-12s  %-5s  %-4s %s"
              % (u_o, r["newUid"], r["grid"], r["id"], r["source"]))
    print(f"\nwrote {os.path.relpath(OUT, _ROOT)}")

    # Which of these actually exist on disk as bundle dirs? Those are the concretely stale ones.
    stale = []
    for d in sorted(os.listdir(_ROOT)):
        full = os.path.join(_ROOT, d)
        if not os.path.isdir(full) or not d.startswith("g_"):
            continue
        for sub in os.listdir(full):
            if sub in out:
                stale.append(f"{d}/{sub}")
    print(f"\non-disk scratch bundles named by a now-stale uid: {len(stale)}")
    for s in stale:
        print(f"  {s}  -> should be {out[os.path.basename(s)]['newUid']}")


if __name__ == "__main__":
    main()
