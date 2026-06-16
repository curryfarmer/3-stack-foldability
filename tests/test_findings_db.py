"""test_findings_db.py — findings DB load/save round-trip + pure upsert keyed by canonical hash.

upsert is the only place a finding enters the DB; it must (a) be pure (no input mutation),
(b) replace-by-normalized-hash so a re-submit never duplicates, and (c) append a genuinely new
hash. load_db/save_db must round-trip a list unchanged. All I/O confined to tmp_path.
"""
import json

import findings as F  # noqa: E402  (py/ on sys.path via conftest.py)


def _rec(h, **kw):
    base = {"grid": "6x5", "id": 1, "canonicalHash": h, "foldable": None,
            "by": "x", "date": "2026-06-15"}
    base.update(kw)
    return base


def test_load_db_missing_returns_empty(tmp_path):
    assert F.load_db(str(tmp_path / "nope.json")) == []


def test_save_then_load_roundtrip(tmp_path):
    p = str(tmp_path / "db.json")
    recs = [_rec('{"a":1}', notes="one"), _rec('{"b":2}', id=2, notes="two")]
    F.save_db(recs, p)
    assert F.load_db(p) == recs
    assert json.load(open(p, encoding="utf-8")) == recs   # plain JSON list on disk


def test_upsert_appends_new_hash():
    recs = [_rec('{"a":1}')]
    out = F.upsert(recs, _rec('{"b":2}', id=2))
    assert len(out) == 2
    assert len(recs) == 1                                  # input untouched (pure)


def test_upsert_replaces_same_hash():
    recs = [_rec('{"a":1}', notes="old")]
    out = F.upsert(recs, _rec('{"a":1}', notes="new"))
    assert len(out) == 1
    assert out[0]["notes"] == "new"


def test_upsert_replaces_across_hash_string_forms():
    # Same logical hash, different key order / spacing -> normalized key matches -> replace.
    recs = [_rec('{"a":1,"b":2}', notes="old")]
    out = F.upsert(recs, _rec('{"b":2,"a":1}', notes="new"))
    assert len(out) == 1 and out[0]["notes"] == "new"


def test_upsert_does_not_mutate_inputs():
    recs = [_rec('{"a":1}', notes="old")]
    rec = _rec('{"a":1}', notes="new")
    F.upsert(recs, rec)
    assert recs[0]["notes"] == "old"                      # original list/record unchanged
    assert rec["notes"] == "new"
