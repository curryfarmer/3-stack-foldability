"""test_findings_migration.py — twoplus1_labels -> FoldFinding migration is lossless + schema-valid.

Every legacy record must survive migration with its identity (grid/id/canonicalHash), verdict
(foldable), and notes BYTE-IDENTICAL; the legacy shape/orient/K must reappear under `observed`; and
every migrated record must validate against the FoldFinding schema. The real results/twoplus1_labels.json
is used read-only as the corpus so the test guards the actual migration, not a toy fixture.
"""
import json
import os

import findings as F  # noqa: E402  (py/ on sys.path via conftest.py)

TWOPLUS1 = os.path.join(F.RESULTS_DIR, "twoplus1_labels.json")


def _legacy():
    with open(TWOPLUS1, encoding="utf-8") as f:
        return json.load(f)


def test_migrate_record_is_lossless():
    old = _legacy()[0]
    rec = F.migrate_record(old, date="2026-06-15")
    assert rec["grid"] == old["grid"]
    assert rec["id"] == old["id"]
    assert rec["canonicalHash"] == old["canonicalHash"]          # byte-identical
    assert rec["foldable"] == old.get("foldable")
    assert rec["notes"] == old.get("notes", "")                  # prose preserved verbatim
    assert rec["observed"] == {"shape": old["shape"], "orient": old["orient"], "K": old["K"]}
    assert rec["by"] == "(migrated)" and rec["date"] == "2026-06-15"


def test_migrate_all_validate_and_preserve_notes():
    old = _legacy()
    recs = F.migrate(old, date="2026-06-15")
    assert len(recs) == len(old)
    for o, r in zip(old, recs):
        F.validate_finding(r)                                    # schema-valid
        assert r["notes"] == o.get("notes", "")                  # every note byte-identical
        assert r["canonicalHash"] == o["canonicalHash"]
        assert r["foldable"] == o.get("foldable")


def test_migrated_db_roundtrips_and_keys_by_hash(tmp_path):
    old = _legacy()
    recs = F.migrate(old, date="2026-06-15")
    p = str(tmp_path / "foldfindings.json")
    F.save_db(recs, p)
    back = F.load_db(p)
    assert back == recs                                          # JSON round-trip stable
    # Distinct legacy hashes -> distinct DB keys (no collision swallows a record).
    keys = {F._norm_hash(r["canonicalHash"]) for r in back}
    assert len(keys) == len(old)


def test_deciders_survive_migration():
    recs = F.migrate(_legacy(), date="2026-06-15")
    deciders = {(r["grid"], r["id"]): r for r in recs if r["foldable"] is False}
    assert ("6x5", 1) in deciders and ("6x6", 1) in deciders and ("6x7", 8) in deciders
