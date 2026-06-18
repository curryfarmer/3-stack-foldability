"""test_generate_db_flag.py — generate.py's --db/--test guard.

An explicit DB target only has somewhere to write on a 3-stack --store-all run (the sole path that
lands in SQLite). Without --store-all, --db/--test would suppress the legacy JSON yet write no DB row
— a silent no-op — so generate must fail fast (exit 2) and touch nothing.
"""
import os

import generate as Gen   # noqa: E402  (py/ on path via conftest)


def test_db_flag_requires_store_all(tmp_path, capsys):
    db = str(tmp_path / "scratch.sqlite3")
    rc = Gen.main(["--m", "3", "--n", "2", "--db", db])      # 3-stack, but NO --store-all
    assert rc == 2
    assert not os.path.exists(db)                            # nothing written (guard precedes the engine)
    assert "--store-all" in capsys.readouterr().err


def test_test_flag_requires_store_all(tmp_path, capsys):
    rc = Gen.main(["--m", "3", "--n", "2", "--test"])        # --test without --store-all -> same guard
    assert rc == 2
    assert "--store-all" in capsys.readouterr().err
