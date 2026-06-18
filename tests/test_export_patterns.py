"""test_export_patterns.py — the matplotlib fold-pattern renderer + the export CLI.

Pins: render() writes a non-empty image from a detail blob; export_patterns reuses the API
sort/filter vocabulary, drops one PNG per matching pattern plus an index.csv cross-ref sheet, honors
--filter / --limit, and never silently truncates. Every test uses an isolated tmp DB + tmp out dir.
"""
import csv
import os

import export_patterns as EP   # noqa: E402  (sys.path set in conftest.py)
import render_square as RS      # noqa: E402
import search as Search         # noqa: E402
import store as Store           # noqa: E402


def _opts():
    return {"m": 3, "n": 2, "stacks": 3, "shapes": {"L": True, "Rect": True},
            "decomps": {"2+1": True, "1+1+1": True},
            "allowNonCorner": True, "dedup": True, "jobs": 1, "storeAll": True}


def _seed(tmp_path):
    db = str(tmp_path / "folddb.sqlite3")
    opts = _opts()
    sols, ctx, err = Search.run(opts)
    assert err is None
    Store.save_sqlite(opts, sols, ctx, lattice="square", region="rect", path=db)
    return db, sols


# ---------- renderer ----------

def test_render_writes_image(tmp_path):
    _, sols = _seed(tmp_path)
    out = str(tmp_path / "p.png")
    path = RS.render(sols[0], 3, 2, out, title="t")
    assert os.path.exists(path) and os.path.getsize(path) > 1000   # a real PNG, not an empty stub


def test_verdict_line_maps_pass_fail_undecided():
    line = RS._verdict_line({"arithmetic": True, "parity": False, "twist": None})
    assert "arith=✓" in line and "par=✗" in line and "twist=–" in line


# ---------- export CLI ----------

def test_export_all_writes_png_per_pattern_plus_index(tmp_path):
    db, sols = _seed(tmp_path)
    out = str(tmp_path / "batch")
    assert EP.main(["--out", out, "--db", db]) == 0
    pngs = [f for f in os.listdir(out) if f.endswith(".png")]
    assert len(pngs) == len(sols)
    with open(os.path.join(out, "index.csv"), newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len(sols)
    assert {"pattern_uid", "canonical_hash", "reflection", "twist", "image"} <= set(rows[0].keys())
    # every index image actually exists on disk
    assert all(os.path.exists(os.path.join(out, r["image"])) for r in rows)


def test_export_filter_narrows_the_set(tmp_path):
    db, _ = _seed(tmp_path)
    out_all = str(tmp_path / "all")
    out_refl = str(tmp_path / "refl")
    EP.main(["--out", out_all, "--db", db])
    EP.main(["--out", out_refl, "--db", db, "--filter", "reflection:true"])
    n_all = len([f for f in os.listdir(out_all) if f.endswith(".png")])
    n_refl = len([f for f in os.listdir(out_refl) if f.endswith(".png")])
    assert 0 < n_refl < n_all                                      # the filter dropped some patterns


def test_export_limit_caps_and_reports(tmp_path, capsys):
    db, _ = _seed(tmp_path)
    out = str(tmp_path / "capped")
    EP.main(["--out", out, "--db", db, "--limit", "1"])
    pngs = [f for f in os.listdir(out) if f.endswith(".png")]
    assert len(pngs) == 1
    assert "not exported" in capsys.readouterr().out             # truncation announced, never silent


def test_export_missing_db_errors(tmp_path):
    assert EP.main(["--out", str(tmp_path / "x"), "--db", str(tmp_path / "nope.sqlite3")]) == 1
