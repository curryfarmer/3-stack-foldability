"""test_findings_roundtrip.py — submit() validates FIRST, then persists exactly once.

submit() is the one write path (CLI / HTTP POST / test all wrap it). It must: (a) refuse a malformed
payload BEFORE touching disk — DB and LAB_LOG untouched; (b) on a valid finding, write one DB row
keyed by the normalized canonical hash plus one dated LAB_LOG block; (c) re-submit overwrites rather
than duplicates. Engine prediction is exercised in test_findings_matcher.py; here engine_predict=False
so the round-trip stays pure-IO and fast. All I/O confined to tmp_path.
"""
import json
import os

import pytest
from jsonschema import ValidationError

import findings as F  # noqa: E402  (py/ on sys.path via conftest.py)


VALID = {
    "grid": "6x5",
    "id": 1,
    "canonicalHash": '{"b":2,"a":1}',          # deliberately unsorted -> normalized on store
    "foldable": False,
    "by": "john",
    "date": "2026-06-15",
    "notes": "physical JAM",
}


def _write(tmp_path, rec, name="finding.json"):
    p = tmp_path / name
    p.write_text(json.dumps(rec), encoding="utf-8")
    return str(p)


def _paths(tmp_path):
    return {"db_path": str(tmp_path / "db.json"),
            "lab_log_path": str(tmp_path / "LAB_LOG.md")}


def test_submit_writes_db_and_lablog(tmp_path):
    paths = _paths(tmp_path)
    out = F.submit(_write(tmp_path, VALID), engine_predict=False, **paths)
    assert out["canonicalHash"] == '{"a":1,"b":2}'          # normalized on store

    db = F.load_db(paths["db_path"])
    assert len(db) == 1
    assert db[0]["canonicalHash"] == '{"a":1,"b":2}'        # DB key = normalized hash
    assert db[0]["notes"] == "physical JAM"

    log = open(paths["lab_log_path"], encoding="utf-8").read()
    assert "physical finding: 6x5#1" in log
    assert '`{"a":1,"b":2}`' in log                         # normalized hash surfaced in the log


def test_invalid_payload_writes_nothing(tmp_path):
    paths = _paths(tmp_path)
    bad = dict(VALID)
    del bad["foldable"]                                     # required key missing
    with pytest.raises(ValidationError):
        F.submit(_write(tmp_path, bad), engine_predict=False, **paths)
    assert not os.path.exists(paths["db_path"])             # validation ran first -> no write
    assert not os.path.exists(paths["lab_log_path"])


def test_resubmit_upserts_not_duplicates(tmp_path):
    paths = _paths(tmp_path)
    F.submit(_write(tmp_path, VALID), engine_predict=False, **paths)
    again = dict(VALID, notes="reflowed JAM", canonicalHash='{"a":1,"b":2}')   # same logical hash
    F.submit(_write(tmp_path, again, name="finding2.json"), engine_predict=False, **paths)

    db = F.load_db(paths["db_path"])
    assert len(db) == 1                                     # replaced, not appended
    assert db[0]["notes"] == "reflowed JAM"

    log = open(paths["lab_log_path"], encoding="utf-8").read()
    assert log.count("physical finding: 6x5#1") == 1        # same (hash,date,by) marker -> one block


def test_resubmit_different_hash_appends(tmp_path):
    paths = _paths(tmp_path)
    F.submit(_write(tmp_path, VALID), engine_predict=False, **paths)
    other = dict(VALID, id=2, canonicalHash='{"c":3}')
    F.submit(_write(tmp_path, other, name="finding3.json"), engine_predict=False, **paths)
    assert len(F.load_db(paths["db_path"])) == 2            # genuinely new hash -> appended


def test_submit_with_sqlite_path_writes_db_master(tmp_path):
    """When a sqlite_path is given (the CLI path), the finding lands in the SQLite master too — not
    just the JSON export. This is what lets foldfindings.json be wiped while findings persist."""
    import store as Store
    paths = _paths(tmp_path)
    db = str(tmp_path / "folddb.sqlite3")
    rec = dict(VALID, canonicalHash='{"a":1,"b":2}')        # already normalized JSON
    F.submit_record(rec, engine_predict=False, sqlite_path=db, **paths)
    conn = Store.connect(db)
    try:
        nh = F._norm_hash(rec["canonicalHash"])
        row = conn.execute("SELECT foldable, provenance FROM finding WHERE norm_hash=?", (nh,)).fetchone()
    finally:
        conn.close()
    assert row is not None and row["foldable"] == 0          # physical JAM persisted to the DB master
    assert F.load_db(paths["db_path"])                       # JSON export written in sync too


def test_submit_without_sqlite_path_skips_db(tmp_path):
    """The pure path (no sqlite_path — how serve.py + unit tests call it) writes NO DB row; serve.py
    mirrors separately, and tests stay isolated to their tmp JSON."""
    import store as Store
    paths = _paths(tmp_path)
    monkey_db = str(tmp_path / "should_not_exist.sqlite3")
    F.submit_record(dict(VALID), engine_predict=False, **paths)   # no sqlite_path
    assert not os.path.exists(monkey_db)                          # nothing wrote a DB
