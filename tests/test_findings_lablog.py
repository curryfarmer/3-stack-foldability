"""test_findings_lablog.py — LAB_LOG append is newest-first and idempotent.

A submitted finding must add exactly one dated block at the TOP of the log (below the intro,
above the newest prior entry) and must NOT double-write when the same finding is re-submitted.
All I/O confined to a tmp_path copy of the log header.
"""
import findings as F  # noqa: E402  (py/ on sys.path via conftest.py)

HEADER = (
    "# Lab Log\n\n"
    "Running log. Newest entry on top.\n\n"
    "---\n\n"
    "## 2026-06-09 — prior entry\n\n"
    "Some prose.\n"
)


def _rec(**kw):
    base = {"grid": "6x5", "id": 1, "canonicalHash": '{"a":1,"b":2}', "foldable": False,
            "by": "john", "date": "2026-06-10", "notes": "physical JAM",
            "jam": {"atFold": 7, "crease": [[3, 5], [4, 5]], "reason": "reflection"},
            "predicted": {"foldable": False, "failingGates": ["refl"], "matched": True}}
    base.update(kw)
    return base


def test_append_writes_block_newest_first(tmp_path):
    p = tmp_path / "LAB_LOG.md"
    p.write_text(HEADER, encoding="utf-8")
    assert F.append_lab_log(_rec(), str(p)) is True
    txt = p.read_text(encoding="utf-8")
    # The new finding header appears before the prior entry (newest-first).
    assert txt.index("physical finding: 6x5#1") < txt.index("prior entry")
    # Intro/header survives above everything.
    assert txt.index("# Lab Log") < txt.index("physical finding")
    assert "- canonicalHash: `{\"a\":1,\"b\":2}`" in txt
    assert "fails: refl" in txt


def test_append_is_idempotent(tmp_path):
    p = tmp_path / "LAB_LOG.md"
    p.write_text(HEADER, encoding="utf-8")
    assert F.append_lab_log(_rec(), str(p)) is True
    first = p.read_text(encoding="utf-8")
    assert F.append_lab_log(_rec(), str(p)) is False        # same (hash,date,by) marker -> skip
    assert p.read_text(encoding="utf-8") == first           # byte-identical, no double-write


def test_append_to_empty_path(tmp_path):
    p = tmp_path / "fresh.md"
    assert F.append_lab_log(_rec(), str(p)) is True
    assert "physical finding: 6x5#1" in p.read_text(encoding="utf-8")


def test_resubmit_different_date_adds_second_entry(tmp_path):
    p = tmp_path / "LAB_LOG.md"
    p.write_text(HEADER, encoding="utf-8")
    F.append_lab_log(_rec(date="2026-06-10"), str(p))
    F.append_lab_log(_rec(date="2026-06-11"), str(p))       # different marker -> distinct entry
    txt = p.read_text(encoding="utf-8")
    assert txt.count("physical finding: 6x5#1") == 2
