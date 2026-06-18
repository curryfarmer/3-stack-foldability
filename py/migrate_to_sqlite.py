#!/usr/bin/env python3
"""migrate_to_sqlite.py — one-shot, idempotent seed of results/folddb.sqlite3 from the existing JSON.

Seeds what already exists:
  * every 3-stack results/*.json (post-gate survivors) -> runs + patterns
  * results/foldfindings.json                          -> finding (+ any tri-state tags -> tag)

Idempotent: re-running REPLACES each run by params_key and UPSERTs findings/tags, so it is safe to
run repeatedly. This is a SEED, not the full Phase-A covered set — run `generate.py --store-all`
per grid afterward to backfill the complete D4-deduped covered set (keyed by the same
canonical_hash, so findings stay joined).

  python py/migrate_to_sqlite.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import store as Store  # noqa: E402


def migrate_results(conn):
    """Seed runs+patterns from every committed 3-stack result file. I/O: (conn) -> (n_runs, n_pat)."""
    n_runs = n_pat = 0
    for e in Store.load_manifest():
        if e.get("opts", {}).get("stacks", 3) != 3:
            continue   # 2-stack sols have a different shape (no footprint/chains) — not a patterns row
        path = os.path.join(Store.RESULTS_DIR, e["file"])
        if not os.path.exists(path):
            continue
        with open(path) as f:
            data = json.load(f)
        meta = data["meta"]
        opts = dict(meta["opts"])
        opts["m"], opts["n"] = meta["m"], meta["n"]
        run_id = Store.upsert_run(conn, opts, meta.get("counts", {}), "square", "rect")
        n_pat += Store.insert_patterns(conn, run_id, data["solutions"], "square", meta["m"], meta["n"])
        n_runs += 1
    return n_runs, n_pat


def migrate_findings(conn):
    """Seed finding (physical ground truth) + tag (tri-state hypotheses) from foldfindings.json.
    foldable not None => physically observed => is_ground_truth=1. I/O: (conn) -> n_findings."""
    import findings as F
    recs = F.load_db()
    for rec in recs:
        nh = F._norm_hash(rec["canonicalHash"])
        foldable = rec.get("foldable")
        conn.execute(
            "INSERT INTO finding(norm_hash,rec_json,foldable,provenance,is_ground_truth,by_who,date) "
            "VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(norm_hash) DO UPDATE SET rec_json=excluded.rec_json,"
            "foldable=excluded.foldable,provenance=excluded.provenance,"
            "is_ground_truth=excluded.is_ground_truth,by_who=excluded.by_who,date=excluded.date",
            (nh, json.dumps(rec, separators=(",", ":")), Store._b(foldable),
             "physical", 1 if foldable is not None else 0, rec.get("by"), rec.get("date")))
        for key, val in (rec.get("tags") or {}).items():
            conn.execute(
                "INSERT INTO tag(norm_hash,key,val_bool,provenance,by_who,date) "
                "VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(norm_hash,key) DO UPDATE SET val_bool=excluded.val_bool",
                (nh, key, Store._b(val), "handmath", rec.get("by"), rec.get("date")))
    return len(recs)


def main():
    conn = Store.connect()
    try:
        Store.init_schema(conn)
        runs, pats = migrate_results(conn)
        finds = migrate_findings(conn)
        conn.commit()
        print(f"migrated {runs} run(s), {pats} pattern(s), {finds} finding(s) -> {Store.SQLITE_PATH}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
