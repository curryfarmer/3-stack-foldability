"""test_reset_db.py — the physical-verification reset (reset_db.py) + DB->JSON findings export.

Pins: a reset clears runs (cascading patterns) + tags but PRESERVES ground-truth findings
(is_ground_truth=1) by default; --all wipes findings too; --dry-run writes nothing; and
store.export_findings round-trips the finding table back to a foldfindings.json. Every test uses an
isolated tmp DB (never the committed results/folddb.sqlite3).
"""
import json
import os

import reset_db as Reset   # noqa: E402  (sys.path set in conftest.py)
import search as Search    # noqa: E402
import store as Store      # noqa: E402


def _opts():
    return {"m": 3, "n": 2, "stacks": 3, "shapes": {"L": True, "Rect": True},
            "decomps": {"2+1": True, "1+1+1": True},
            "allowNonCorner": True, "dedup": True, "jobs": 1, "storeAll": True}


def _seed(tmp_path):
    """A tmp DB with one store-all run + a GT finding + a non-GT finding + a custom tag.
    -> (db_path, solutions)."""
    db = str(tmp_path / "folddb.sqlite3")
    opts = _opts()
    sols, ctx, err = Search.run(opts)
    assert err is None
    Store.save_sqlite(opts, sols, ctx, lattice="square", region="rect", path=db)
    conn = Store.connect(db)
    gt = sols[0]["canonicalHash"]
    # GT: physically folded with a verdict -> is_ground_truth=1
    Store.upsert_finding(conn, {"canonicalHash": gt, "foldable": True,
                                "provenance": "physical", "by": "t", "date": "2026-01-01"})
    # non-GT: handmath hypothesis, no physical observation -> is_ground_truth=0
    Store.upsert_finding(conn, {"canonicalHash": sols[1]["canonicalHash"], "foldable": None,
                                "provenance": "handmath", "by": "t", "date": "2026-01-01"})
    Store.upsert_tag(conn, gt, "modelA", True)
    conn.close()
    return db, sols


def _counts(db):
    conn = Store.connect(db)
    try:
        return Reset.counts(conn)
    finally:
        conn.close()


def test_reset_keeps_ground_truth_clears_the_rest(tmp_path):
    db, _ = _seed(tmp_path)
    before = _counts(db)
    assert before["runs"] == 1 and before["patterns"] > 0
    assert before["tag"] == 1 and before["finding"] == 2 and before["ground_truth"] == 1

    assert Reset.main(["--db", db]) == 0
    after = _counts(db)
    assert after["runs"] == 0 and after["patterns"] == 0 and after["tag"] == 0
    assert after["finding"] == 1 and after["ground_truth"] == 1   # only the GT finding survives


def test_reset_all_wipes_findings_too(tmp_path):
    db, _ = _seed(tmp_path)
    assert Reset.main(["--db", db, "--all"]) == 0
    after = _counts(db)
    assert after == {"runs": 0, "patterns": 0, "tag": 0, "finding": 0, "ground_truth": 0}


def test_dry_run_writes_nothing(tmp_path):
    db, _ = _seed(tmp_path)
    before = _counts(db)
    assert Reset.main(["--db", db, "--dry-run"]) == 0
    assert _counts(db) == before                                  # DB untouched


def test_dry_run_with_export_writes_no_file(tmp_path):
    """--dry-run means NO writes — not even the --export-findings backup (which would be a side effect)."""
    db, _ = _seed(tmp_path)
    before = _counts(db)
    out = str(tmp_path / "backup.json")
    assert Reset.main(["--db", db, "--dry-run", "--export-findings", out]) == 0
    assert not os.path.exists(out)                                # backup NOT written under dry-run
    assert _counts(db) == before                                  # DB still untouched


def test_reset_missing_db_is_an_error(tmp_path):
    assert Reset.main(["--db", str(tmp_path / "nope.sqlite3")]) == 1


def test_export_findings_round_trips(tmp_path):
    db, _ = _seed(tmp_path)
    out = str(tmp_path / "foldfindings.json")
    conn = Store.connect(db)
    try:
        path = Store.export_findings(conn, out)
    finally:
        conn.close()
    recs = json.load(open(path))
    assert len(recs) == 2                                         # both findings exported
    assert {r["provenance"] for r in recs} == {"physical", "handmath"}
    # re-importing the export into a fresh DB reproduces the same finding rows (DB<->JSON symmetry)
    db2 = str(tmp_path / "rebuilt.sqlite3")
    conn2 = Store.connect(db2)
    try:
        Store.init_schema(conn2)
        for rec in recs:
            Store.upsert_finding(conn2, rec)
        conn2.commit()
        n = conn2.execute("SELECT COUNT(*) FROM finding").fetchone()[0]
        gt = conn2.execute("SELECT COUNT(*) FROM finding WHERE is_ground_truth=1").fetchone()[0]
    finally:
        conn2.close()
    assert n == 2 and gt == 1
