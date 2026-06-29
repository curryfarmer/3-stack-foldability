#!/usr/bin/env python3
"""ingest_findings.py — bulk-record PHYSICAL fold results for a whole 2+1 family at once.

The web-app search emits the gate-survivors (exit+parity+reflection) of a grid; a physical
campaign folds them and reports family-level verdicts ("all 9 of 6x5 fold; one of 6x7 jams").
This CLI turns such a campaign into per-pattern FoldFinding rows WITHOUT hand-POSTing each one,
reusing the existing pipeline (findings.submit_record -> validate -> store.upsert_finding ->
foldfindings.json export -> LAB_LOG), so SQLite stays the findings master and nothing here
re-implements the write path.

Two input modes pick the candidate set; a verdict spec then labels each candidate:

  # from a web-app exportJson file (carries canonicalHash per case):
  python py/ingest_findings.py --export sixfive.json --grid 6x5 --by john --date 2026-06-22 --all-fold

  # straight from the DB's gate-survivors (the same set the search shows) — no export file needed:
  python py/ingest_findings.py --from-survivors --grid 6x4 --by john --date 2026-06-22 --all-fold
  python py/ingest_findings.py --from-survivors --grid 6x7 --by john --date 2026-06-22 \
         --all-fold --jam-uid 1a2b3c4d5e6f          # all fold EXCEPT this one (a JAM)

Verdict spec (applied after the candidate set is chosen):
  --all-fold            default verdict FOLD for every candidate
  --all-jam             default verdict JAM for every candidate
  --untested            default verdict untested (foldable=null)
  --fold-uid UID ...    override individual patterns to FOLD (by pattern_uid)
  --jam-uid  UID ...    override individual patterns to JAM
  --untested-uid UID .. override individual patterns to untested

Provenance is always 'physical' (these are hand-folds = ground truth). Before a physical finding is
overwritten with a DIFFERENT verdict, the old record is appended to results/findings_archive.jsonl
(audit trail) — we flag actual-vs-theoretical, we do not silently lose a prior observation. For each
finding we also write <model>_actual twist tags (= the physical foldable) so store.model_compare can
flag every twist model whose prediction disagrees with reality.
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # py/ on path
import _bootstrap  # noqa: E402,F401  (puts every py/ subfolder + repo + tests on sys.path)

import store as Store            # noqa: E402
import findings as F             # noqa: E402

ARCHIVE_PATH = os.path.join(Store.RESULTS_DIR, "findings_archive.jsonl")
TWIST_MODELS = ("modelA", "modelB", "modelC")


def _parse_grid(grid):
    m, n = grid.lower().split("x")
    return int(m), int(n)


def _survivor_candidates(conn, m, n):
    """Pull the 2+1 gate-survivors (exit+parity+reflection all pass) for a grid from the newest
    'nc-2+1' run, one row per distinct pattern_uid. I/O: (conn, m, n) -> [{id, canonicalHash}]."""
    run = conn.execute(
        "SELECT id FROM runs WHERE m=? AND n=? AND label='nc-2+1' ORDER BY id DESC LIMIT 1",
        (m, n)).fetchone()
    if run is None:
        raise SystemExit(
            f"no non-corner 2+1 run for {m}x{n} (label 'nc-2+1'); generate it first:\n"
            f"  python py/generate.py --m {m} --n {n} --decomps 2+1 --allow-non-corner --store-all --label nc-2+1")
    rows = conn.execute(
        "SELECT seq, canonical_hash, pattern_uid FROM patterns "
        "WHERE run_id=? AND decomposition='2+1' "
        "AND exit_footprint=1 AND parity=1 AND reflection=1 "
        "GROUP BY pattern_uid ORDER BY seq", (run["id"],)).fetchall()
    return [{"id": r["seq"], "canonicalHash": r["canonical_hash"], "pattern_uid": r["pattern_uid"]}
            for r in rows]


def _export_candidates(path):
    """Pull candidates from a web-app exportJson file ({meta, solutions:[{id, canonicalHash, ...}]}).
    I/O: (path) -> [{id, canonicalHash}]."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    sols = data.get("solutions", data if isinstance(data, list) else [])
    return [{"id": s.get("id"), "canonicalHash": s["canonicalHash"]} for s in sols]


def _predicted_from_patterns(conn, canonical_hash):
    """Build the engine `predicted` block from the already-computed patterns gate columns (no
    re-enumeration). For 2+1 the gate verdict = exit & parity & reflection (twist is undecided, so
    non-filtering). Returns {'matched': False} when the pattern is not in the DB.
    I/O: (conn, canonicalHash) -> predicted block dict."""
    nh = F._norm_hash(canonical_hash)
    row = conn.execute(
        "SELECT exit_footprint, parity, reflection FROM patterns WHERE norm_hash=? LIMIT 1",
        (nh,)).fetchone()
    if row is None:
        return {"matched": False}
    fails = []
    if not row["parity"]:
        fails.append("parity")
    if not row["reflection"]:
        fails.append("refl")
    return {"foldable": bool(row["exit_footprint"] and row["parity"] and row["reflection"]),
            "failingGates": fails, "matched": True}


def _verdict_for(cand, default, overrides):
    """Resolve a candidate's foldable: an explicit pattern_uid override beats the family default.
    I/O: (cand, default(bool|None), {uid: bool|None}) -> bool|None."""
    uid = cand.get("pattern_uid")
    if uid is None:                                   # export rows have no uid; compute it on demand
        uid = cand["_uid"]
    return overrides.get(uid, default)


def _archive_if_conflict(conn, rec):
    """If a PHYSICAL finding already exists for this norm_hash with a CONFLICTING verdict (both known
    and FOLD vs JAM disagree), append the old record to the archive jsonl before it is overwritten.
    A null->known fill is not a conflict (nothing observed before). I/O: (conn, rec) -> bool."""
    nh = F._norm_hash(rec["canonicalHash"])
    old = conn.execute(
        "SELECT rec_json, foldable, provenance FROM finding WHERE norm_hash=?", (nh,)).fetchone()
    if old is None or old["provenance"] != "physical":
        return False
    new_fold = Store._b(rec.get("foldable"))
    if old["foldable"] is None or new_fold is None or old["foldable"] == new_fold:
        return False                                  # null fill or idempotent -> not a conflict
    F._ensure_parent(ARCHIVE_PATH)
    with open(ARCHIVE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"archived": datetime.datetime.now().isoformat(timespec="seconds"),
                            "reason": "overwritten by ingest_findings",
                            "old": json.loads(old["rec_json"])}, separators=(",", ":")) + "\n")
    return True


def main(argv=None):
    p = argparse.ArgumentParser(description="Bulk-record physical fold results for a 2+1 family.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--export", metavar="PATH", help="web-app exportJson file (carries canonicalHash)")
    src.add_argument("--from-survivors", action="store_true",
                     help="pull the grid's gate-survivors straight from the DB (the search's set)")
    p.add_argument("--grid", required=True, metavar="MxN", help="grid, e.g. 6x5")
    p.add_argument("--by", required=True, help="who folded (recorded on each finding)")
    p.add_argument("--date", default=datetime.date.today().isoformat(), help="ISO date (default today)")
    verdict = p.add_mutually_exclusive_group()
    verdict.add_argument("--all-fold", action="store_true", help="default verdict FOLD (default)")
    verdict.add_argument("--all-jam", action="store_true", help="default verdict JAM")
    verdict.add_argument("--untested", action="store_true", help="default verdict untested (null)")
    p.add_argument("--fold-uid", action="append", default=[], metavar="UID", help="override -> FOLD")
    p.add_argument("--jam-uid", action="append", default=[], metavar="UID", help="override -> JAM")
    p.add_argument("--untested-uid", action="append", default=[], metavar="UID", help="override -> null")
    p.add_argument("--notes", default="", help="free-text note stored on every finding")
    p.add_argument("--db", metavar="PATH", help="DB path (default $FOLDDB_SQLITE or results/folddb.sqlite3)")
    p.add_argument("--test", action="store_true", help="use the scratch DB results/folddb.test.sqlite3")
    p.add_argument("--dry-run", action="store_true", help="report what would be written; write nothing")
    ns = p.parse_args(sys.argv[1:] if argv is None else argv)

    m, n = _parse_grid(ns.grid)
    default = None if ns.untested else (False if ns.all_jam else True)   # FOLD is the default default
    overrides = {}
    overrides.update({u: True for u in ns.fold_uid})
    overrides.update({u: None for u in ns.untested_uid})
    overrides.update({u: False for u in ns.jam_uid})                    # JAM wins ties (explicit failure)

    db_path = Store.resolve_db_path(ns.db, ns.test)
    conn = Store.connect(db_path)
    try:
        Store.init_schema(conn)
        if ns.from_survivors:
            cands = _survivor_candidates(conn, m, n)
        else:
            cands = _export_candidates(ns.export)
            for c in cands:                                              # export rows need a uid for overrides
                c["_uid"] = Store.pattern_uid("square", m, n, c["canonicalHash"])

        # Resolve verdicts up front so --dry-run can show the full plan.
        plan = [(c, _verdict_for(c, default, overrides)) for c in cands]
        word = {True: "FOLD", False: "JAM", None: "untested"}
        counts = {"FOLD": 0, "JAM": 0, "untested": 0}
        for _, v in plan:
            counts[word[v]] += 1
        print(f"{ns.grid}: {len(plan)} candidate(s)  ->  "
              f"FOLD={counts['FOLD']} JAM={counts['JAM']} untested={counts['untested']}"
              f"  ({'DRY-RUN' if ns.dry_run else 'writing'})")

        unknown = set(overrides) - {c.get("pattern_uid") or c.get("_uid") for c in cands}
        if unknown:                                                     # never silently ignore a bad uid
            print(f"  ! {len(unknown)} override uid(s) matched no candidate: {', '.join(sorted(unknown))}")

        if ns.dry_run:
            for c, v in plan:
                uid = c.get("pattern_uid") or c.get("_uid")
                print(f"    {uid}  #{c['id']}  -> {word[v]}")
            return 0

        written = archived = 0
        for c, v in plan:
            rec = {"grid": ns.grid, "id": int(c["id"]) if c["id"] is not None else 0,
                   "canonicalHash": c["canonicalHash"], "foldable": v,
                   "by": ns.by, "date": ns.date, "provenance": "physical"}
            if ns.notes:
                rec["notes"] = ns.notes
            if _archive_if_conflict(conn, rec):
                archived += 1
            # Fill the engine gate prediction from the patterns gate columns (instant; no per-finding
            # re-enumeration), then submit with engine_predict=False so v_compare.pred_foldable is set.
            rec["predicted"] = _predicted_from_patterns(conn, rec["canonicalHash"])
            F.submit_record(rec, sqlite_path=db_path, engine_predict=False)
            nh = F._norm_hash(rec["canonicalHash"])                     # write <model>_actual twist tags
            for model in TWIST_MODELS:
                Store.upsert_tag(conn, rec["canonicalHash"], f"{model}_actual", v,
                                 provenance="physical", by_who=ns.by, notes="physical fold result")
            written += 1
        print(f"  wrote {written} finding(s) -> {db_path} (+ foldfindings.json, LAB_LOG); "
              f"archived {archived} overwritten label(s) -> {ARCHIVE_PATH if archived else '(none)'}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
