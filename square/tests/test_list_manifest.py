"""test_list_manifest.py — `sq-generate --list` over a mixed out/ directory.

WHY THIS EXISTS. Both engines default to the same `out/`, and the README's own example session runs
sq-generate and tri-generate one after the other, so a real user's out/ holds records from both. A
triangle record is shaped differently: keyed on (tiling, K) with no lattice/m/n, and carrying its
verdict as a plain STRING rather than the square engine's per-gate dict. Reading that string as a
dict raised `AttributeError: 'str' object has no attribute 'get'` and took the entire listing down
mid-print -- 104 records on disk, a traceback instead of a summary.

The triangle record below is written by hand rather than by running the triangle engine: this suite
must never import triangle (both packages ship a bare `lattice`; see conftest.py).
"""
import json
import os

import pytest

import generate  # noqa: E402  square/generate.py (sys.path set in conftest.py)


SQUARE_REC = {
    "uid": "aaaaaaaaaaaa", "lattice": "square", "m": 6, "n": 4,
    "verdict": {"twist": True, "reflection": True},
}
TWOSTACK_REC = {
    "uid": "bbbbbbbbbbbb", "lattice": "square2stack", "m": 6, "n": 5,
    "verdict": {"foldable": True},
}
TRIANGLE_REC = {
    "uid": "cccccccccccc", "tiling": "righttri", "decomp": "1plus1plus1", "K": 16,
    "verdict": "PREDICTED FOLDABLE (Tw=0)",
}


def write(out_dir, rec):
    d = os.path.join(out_dir, rec["uid"])
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "%s.json" % rec["uid"]), "w", encoding="utf-8") as fh:
        json.dump(rec, fh)


def listing(tmp_path, capsys, *recs):
    for rec in recs:
        write(str(tmp_path), rec)
    assert generate.main(["--list", "--out", str(tmp_path)]) == 0
    return capsys.readouterr().out


def test_mixed_out_dir_lists_every_record(tmp_path, capsys):
    """The regression: a triangle bundle next to square ones must not abort the listing."""
    out = listing(tmp_path, capsys, SQUARE_REC, TWOSTACK_REC, TRIANGLE_REC)
    for rec in (SQUARE_REC, TWOSTACK_REC, TRIANGLE_REC):
        assert rec["uid"] in out
    assert "3 record(s)" in out


def test_square_rows_report_lattice_grid_and_verdict(tmp_path, capsys):
    out = listing(tmp_path, capsys, SQUARE_REC, TWOSTACK_REC)
    assert "square  6x4  FOLD" in out
    assert "square2stack  6x5  FOLD" in out


def test_triangle_rows_report_tiling_K_and_the_verdict_string(tmp_path, capsys):
    """No m/n to print, so the size column carries K; the verdict is passed through verbatim rather
    than being forced into the square engine's FOLD/JAM vocabulary, which does not apply to it."""
    out = listing(tmp_path, capsys, TRIANGLE_REC)
    assert "righttri  K=16  PREDICTED FOLDABLE (Tw=0)" in out


@pytest.mark.parametrize("verdict", [None, "", [], 0])
def test_an_unreadable_verdict_prints_a_question_mark_not_a_traceback(tmp_path, capsys, verdict):
    """Anything can end up in out/ -- a truncated write, a hand-edited file, a future schema. The
    listing degrades to '?' on that one row and still reports the rest."""
    rec = dict(SQUARE_REC, uid="dddddddddddd", verdict=verdict)
    out = listing(tmp_path, capsys, rec, SQUARE_REC)
    assert "dddddddddddd" in out and SQUARE_REC["uid"] in out
    assert "2 record(s)" in out


def test_empty_and_missing_out_dirs_are_reported_not_crashed(tmp_path, capsys):
    assert generate.main(["--list", "--out", str(tmp_path)]) == 0
    assert "no records found" in capsys.readouterr().out
    assert generate.main(["--list", "--out", str(tmp_path / "nope")]) == 0
    assert "does not exist yet" in capsys.readouterr().out
