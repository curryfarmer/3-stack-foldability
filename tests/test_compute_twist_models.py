"""test_compute_twist_models.py — the 2+1 twist-model backfill (compute_twist_models.py + twist_models).

Proves the registry-driven prediction layer: every registered hypothesis is recomputed on each 2+1
solution and written as a '<model>_pred' tag (provenance='engine', pass in val_bool, raw tw in val_int,
class in val_text, a version stamp in notes); the run is idempotent; --dry-run writes nothing; the
default scope is the gate-valid subset; --prune drops preds for hypotheses no longer in the registry;
and a changed hypothesis version re-stamps. A fast 3x2 store-all DB seeds it (2 computable 2+1, 1
gate-valid) — never the committed results/folddb.sqlite3.
"""
import compute_twist_models as CTM   # noqa: E402  (sys.path set in conftest.py)
import search as Search              # noqa: E402
import store as Store                # noqa: E402
import twist_models                  # noqa: E402

_MODELS = list(twist_models.MODELS)            # ['modelA','modelB','modelC'] (+ any added later)


def _opts():
    return {"m": 3, "n": 2, "stacks": 3,
            "shapes": {"L": True, "Rect": True},
            "decomps": {"2+1": True, "1+1+1": True},
            "allowNonCorner": True, "dedup": True, "jobs": 1, "storeAll": True}


def _seed(tmp_path):
    """Fast 3x2 store-all DB. -> db_path."""
    db = str(tmp_path / "folddb.sqlite3")
    sols, ctx, err = Search.run(_opts())
    assert err is None
    Store.save_sqlite(_opts(), sols, ctx, lattice="square", region="rect", path=db)
    return db


def _pred_rows(db):
    """All '<model>_pred' tag rows. -> list[sqlite3.Row]."""
    conn = Store.connect(db)
    try:
        return conn.execute("SELECT * FROM tag WHERE substr(key,-5)='_pred'").fetchall()
    finally:
        conn.close()


# ---------- the backfill writes well-formed engine predictions ----------

def test_backfill_writes_pred_tags(tmp_path):
    db = _seed(tmp_path)
    assert CTM.main(["--db", db, "--all-2plus1"]) == 0

    conn = Store.connect(db)
    twoplus1 = conn.execute("SELECT norm_hash FROM patterns WHERE decomposition='2+1'").fetchall()
    assert twoplus1                                              # the 3x2 grid really has 2+1 folds
    # every computable 2+1 pattern got one pred row per registered model, all engine-owned
    for nh in (r["norm_hash"] for r in twoplus1):
        for key in (f"{m}_pred" for m in _MODELS):
            row = conn.execute("SELECT * FROM tag WHERE norm_hash=? AND key=?", (nh, key)).fetchone()
            assert row is not None
            assert row["val_bool"] in (0, 1)                    # pass/fail materialised
            assert row["val_int"] is None or isinstance(row["val_int"], int)   # rounded tw
            assert row["provenance"] == "engine" and row["by_who"] == "engine"
            assert "v=" in (row["notes"] or "")                 # version-stamped for change detection
    conn.close()


def test_modelA_carries_class_text(tmp_path):
    """Model A (partial-decomp) returns a class string -> it lands in val_text; B/C have none."""
    db = _seed(tmp_path)
    CTM.main(["--db", db, "--all-2plus1"])
    conn = Store.connect(db)
    a_classes = [r["val_text"] for r in
                 conn.execute("SELECT val_text FROM tag WHERE key='modelA_pred'").fetchall()]
    assert a_classes and all(c in ("flat", "overhang", "twisted", "mixed") for c in a_classes)
    # B/C carry no class
    for r in conn.execute("SELECT val_text FROM tag WHERE key IN ('modelB_pred','modelC_pred')").fetchall():
        assert r["val_text"] is None
    conn.close()


# ---------- idempotent + scoped + safe ----------

def test_idempotent_rerun(tmp_path):
    db = _seed(tmp_path)
    CTM.main(["--db", db, "--all-2plus1"])
    n1 = len(_pred_rows(db))
    CTM.main(["--db", db, "--all-2plus1"])                       # second run must overwrite, not duplicate
    assert len(_pred_rows(db)) == n1 > 0


def test_dry_run_writes_nothing(tmp_path):
    db = _seed(tmp_path)
    assert CTM.main(["--db", db, "--all-2plus1", "--dry-run"]) == 0
    assert _pred_rows(db) == []                                 # not a single pred row written


def test_default_scope_is_gate_valid_subset(tmp_path):
    """Default scope (gate-valid 2+1) writes preds for FEWER patterns than --all-2plus1 (3x2: 1 vs 2)."""
    db = _seed(tmp_path)
    CTM.main(["--db", db])                                      # gate-valid only
    gate_valid = len(_pred_rows(db)) // len(_MODELS)
    CTM.main(["--db", db, "--all-2plus1"])                      # superset
    all_2p1 = len(_pred_rows(db)) // len(_MODELS)
    assert 0 < gate_valid < all_2p1


def test_prune_drops_stale_model(tmp_path):
    db = _seed(tmp_path)
    CTM.main(["--db", db, "--all-2plus1"])
    conn = Store.connect(db)
    nh = conn.execute("SELECT norm_hash FROM patterns WHERE decomposition='2+1' LIMIT 1").fetchone()[0]
    conn.execute("INSERT INTO tag(norm_hash,key,val_bool,provenance) VALUES(?,?,?,?)",
                 (nh, "modelZZ_pred", 1, "engine"))             # a retired hypothesis' leftover
    conn.commit()
    conn.close()
    CTM.main(["--db", db, "--all-2plus1", "--prune"])
    conn = Store.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM tag WHERE key='modelZZ_pred'").fetchone()[0] == 0
    # the live models survive the prune
    assert conn.execute("SELECT COUNT(*) FROM tag WHERE key='modelA_pred'").fetchone()[0] > 0
    conn.close()


def test_changed_hypothesis_restamps(tmp_path, monkeypatch):
    """When a model's source-hash changes (a rewritten hypothesis), re-running re-stamps its notes."""
    db = _seed(tmp_path)
    CTM.main(["--db", db, "--all-2plus1"])
    before = {r["norm_hash"]: r["notes"] for r in
              Store.connect(db).execute("SELECT norm_hash,notes FROM tag WHERE key='modelA_pred'")}
    assert before
    real = twist_models.model_version
    monkeypatch.setattr(twist_models, "model_version",
                        lambda k: "ffffffff" if k == "modelA" else real(k))
    CTM.main(["--db", db, "--all-2plus1"])
    after = {r["norm_hash"]: r["notes"] for r in
             Store.connect(db).execute("SELECT norm_hash,notes FROM tag WHERE key='modelA_pred'")}
    assert all(after[h] != before[h] and "v=ffffffff" in after[h] for h in before)
