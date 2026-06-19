"""test_sqlite_store.py — the SQLite source-of-truth layer (store.py) + migrate_to_sqlite.

Covers Phase-A store-all persistence, the stable distinct-pattern uid, the non-destructive verdict
columns, the EAV tag side-table (add/remove/sort custom columns with no migration), the ground-truth
finding table, the engine-vs-physical v_compare `agree` flag, and the one-way JSON export round-trip.
Every test uses an isolated tmp DB (never the committed results/folddb.sqlite3).
"""
import json

import findings as F   # noqa: E402  (sys.path set in conftest.py)
import search as Search  # noqa: E402
import store as Store    # noqa: E402


def _opts(store_all=True):
    return {"m": 3, "n": 2, "stacks": 3,
            "shapes": {"L": True, "Rect": True},
            "decomps": {"2+1": True, "1+1+1": True},
            "allowNonCorner": True, "dedup": True, "jobs": 1, "storeAll": store_all}


def _seed(tmp_path, store_all=True):
    """Run a 3x2 search and persist it to a fresh tmp SQLite DB. -> (db_path, run_id, solutions)."""
    db = str(tmp_path / "folddb.sqlite3")
    opts = _opts(store_all)
    sols, ctx, err = Search.run(opts)
    assert err is None
    rid = Store.save_sqlite(opts, sols, ctx, lattice="square", region="rect", path=db)
    return db, rid, sols


# ---------- persistence + verdict columns ----------

def test_save_sqlite_persists_all_with_verdict_columns(tmp_path):
    db, rid, sols = _seed(tmp_path, store_all=True)
    conn = Store.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0] == len(sols)
    # every non-destructive verdict column is present and populated (0/1/None, never missing)
    cols = ("arithmetic", "exit_footprint", "parity", "vector_parity", "reflection", "twist")
    for r in conn.execute(f"SELECT {','.join(cols)} FROM patterns").fetchall():
        for c in cols:
            assert r[c] in (0, 1, None)
    # store-all really stored gate-FAILERS too (proof gates are columns, not pruners)
    assert conn.execute("SELECT COUNT(*) FROM patterns WHERE reflection=0").fetchone()[0] > 0
    conn.close()


def test_no_dedup_store_all_keeps_all_rows(tmp_path):
    """Regression: under --no-dedup, distinct candidates can share a D4 canonical_hash; Phase-A must
    store ALL of them (identity is (run_id,seq), not canonical_hash, so none are silently dropped)."""
    db = str(tmp_path / "folddb.sqlite3")
    opts = dict(_opts(store_all=True), dedup=False)
    sols, ctx, err = Search.run(opts)
    assert err is None
    Store.save_sqlite(opts, sols, ctx, lattice="square", region="rect", path=db)
    conn = Store.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0] == len(sols)   # nothing dropped
    # the collision really exists (else this test proves nothing): fewer distinct hashes than rows
    distinct = conn.execute("SELECT COUNT(DISTINCT canonical_hash) FROM patterns").fetchone()[0]
    assert distinct < len(sols)
    assert conn.execute("SELECT COUNT(*) FROM patterns WHERE seq IS NULL").fetchone()[0] == 0
    conn.close()


def test_run_row_carries_lattice_and_region(tmp_path):
    db, rid, _ = _seed(tmp_path)
    conn = Store.connect(db)
    run = conn.execute("SELECT lattice, region, m, n FROM runs WHERE id=?", (rid,)).fetchone()
    assert (run["lattice"], run["region"], run["m"], run["n"]) == ("square", "rect", 3, 2)
    conn.close()


# ---------- distinct-pattern uid ----------

def test_pattern_uid_distinct_and_stable(tmp_path):
    db, _, sols = _seed(tmp_path)
    conn = Store.connect(db)
    uids = [r[0] for r in conn.execute("SELECT pattern_uid FROM patterns").fetchall()]
    assert len(uids) == len(set(uids)) == len(sols)          # each distinct pattern -> unique id
    # stable: recomputing from (lattice, grid, canonical_hash) reproduces the stored uid
    for r in conn.execute("SELECT pattern_uid, canonical_hash FROM patterns").fetchall():
        assert Store.pattern_uid("square", 3, 2, r["canonical_hash"]) == r["pattern_uid"]
    conn.close()


def test_norm_hash_matches_findings(tmp_path):
    db, _, _ = _seed(tmp_path)
    conn = Store.connect(db)
    r = conn.execute("SELECT canonical_hash, norm_hash FROM patterns LIMIT 1").fetchone()
    assert Store._norm_hash(r["canonical_hash"]) == F._norm_hash(r["canonical_hash"]) == r["norm_hash"]
    conn.close()


# ---------- EAV tags: add / remove / sort custom columns with no migration ----------

def test_tag_eav_add_remove_sort(tmp_path):
    db, _, _ = _seed(tmp_path)
    conn = Store.connect(db)
    rows = conn.execute("SELECT norm_hash FROM patterns ORDER BY seq").fetchall()
    # add an arbitrary custom column "myHypothesis" on two patterns (no schema change)
    for i, r in enumerate(rows[:2]):
        conn.execute("INSERT INTO tag(norm_hash,key,val_bool,provenance) VALUES(?,?,?,?)",
                     (r["norm_hash"], "myHypothesis", i % 2, "handmath"))
    conn.commit()
    assert [k[0] for k in conn.execute("SELECT DISTINCT key FROM tag").fetchall()] == ["myHypothesis"]
    # sort patterns by the custom tag value (LEFT JOIN the EAV row)
    sortable = conn.execute(
        "SELECT p.seq, t.val_bool FROM patterns p "
        "LEFT JOIN tag t ON t.norm_hash=p.norm_hash AND t.key='myHypothesis' "
        "ORDER BY t.val_bool DESC NULLS LAST, p.seq").fetchall()
    assert sortable[0]["val_bool"] == 1
    # remove the column (delete its rows) -> key disappears, no migration
    conn.execute("DELETE FROM tag WHERE key='myHypothesis'")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM tag WHERE key='myHypothesis'").fetchone()[0] == 0
    conn.close()


# ---------- engine-vs-physical comparison (v_compare) ----------

def test_v_compare_agree_flags_disagreement(tmp_path):
    db, _, _ = _seed(tmp_path)
    conn = Store.connect(db)
    nh = conn.execute("SELECT norm_hash FROM patterns LIMIT 1").fetchone()[0]

    def put(foldable, predicted):
        rec = {"foldable": foldable, "predicted": {"foldable": predicted}}
        conn.execute("INSERT OR REPLACE INTO finding(norm_hash,rec_json,foldable,provenance,"
                     "is_ground_truth) VALUES(?,?,?,?,1)", (nh, json.dumps(rec), Store._b(foldable),
                     "physical"))
        conn.commit()
        return conn.execute("SELECT agree FROM v_compare WHERE norm_hash=?", (nh,)).fetchone()["agree"]

    assert put(True, False) == 0     # physical FOLD vs engine not-foldable -> disagreement (bug suspect)
    assert put(True, True) == 1      # agreement
    assert put(None, True) is None   # untested -> no verdict
    conn.close()


# ---------- engine twist-model predictions (upsert_engine_pred + model_compare view) ----------

def test_upsert_engine_pred_roundtrip(tmp_path):
    db, _, _ = _seed(tmp_path)
    conn = Store.connect(db)
    nh = conn.execute("SELECT norm_hash FROM patterns LIMIT 1").fetchone()[0]
    # pass=True with a fractional tw rounds into val_int; class lands in val_text; engine-owned + stamped
    Store.upsert_engine_pred(conn, nh, "modelA_pred", True, tw=2.6, cls="overhang", version="abc123")
    r = conn.execute("SELECT * FROM tag WHERE norm_hash=? AND key='modelA_pred'", (nh,)).fetchone()
    assert r["val_bool"] == 1 and r["val_int"] == 3 and r["val_text"] == "overhang"
    assert r["provenance"] == "engine" and r["by_who"] == "engine" and "v=abc123" in r["notes"]
    # re-upsert overwrites in place (idempotent on the PK), not a second row; None tw -> NULL val_int
    Store.upsert_engine_pred(conn, nh, "modelA_pred", False, tw=None, cls=None, version="def456")
    assert conn.execute("SELECT COUNT(*) FROM tag WHERE norm_hash=? AND key='modelA_pred'",
                        (nh,)).fetchone()[0] == 1
    r = conn.execute("SELECT * FROM tag WHERE norm_hash=? AND key='modelA_pred'", (nh,)).fetchone()
    assert r["val_bool"] == 0 and r["val_int"] is None and r["val_text"] is None and "v=def456" in r["notes"]
    conn.close()


def test_model_compare_joins_pred_and_actual(tmp_path):
    db, _, _ = _seed(tmp_path)
    conn = Store.connect(db)
    nh = conn.execute("SELECT norm_hash FROM patterns WHERE decomposition='2+1' LIMIT 1").fetchone()[0]
    Store.upsert_engine_pred(conn, nh, "modelB_pred", True, tw=0, version="v1")     # engine says pass
    # no actual yet -> LEFT JOIN keeps the row, phys_pass NULL, agree NULL
    row = conn.execute("SELECT * FROM model_compare WHERE norm_hash=? AND model_key='modelB'",
                       (nh,)).fetchone()
    assert row["model_key"] == "modelB" and row["eng_pass"] == 1
    assert row["phys_pass"] is None and row["agree"] is None
    # user records a DISAGREEING actual -> agree=0 (engine-vs-reality mismatch surfaces)
    conn.execute("INSERT INTO tag(norm_hash,key,val_bool,provenance) VALUES(?,?,?,?)",
                 (nh, "modelB_actual", 0, "physical"))
    conn.commit()
    row = conn.execute("SELECT * FROM model_compare WHERE norm_hash=? AND model_key='modelB'",
                       (nh,)).fetchone()
    assert row["phys_pass"] == 0 and row["agree"] == 0
    conn.close()


# ---------- one-way JSON export round-trip ----------

def test_export_json_round_trip(tmp_path):
    db, rid, sols = _seed(tmp_path)
    conn = Store.connect(db)
    path = Store.export_json(conn, rid, out_dir=str(tmp_path))   # tmp dir, NEVER the real results/
    conn.close()
    assert str(tmp_path) in path                                 # isolation: not written to results/
    data = json.load(open(path))
    assert len(data["solutions"]) == len(sols)
    assert data["meta"]["m"] == 3 and data["meta"]["n"] == 2
    # the exported sol blobs are the exact stored detail (canonicalHash preserved -> findings stay joined)
    assert {s["canonicalHash"] for s in data["solutions"]} == {s["canonicalHash"] for s in sols}


# ---------- run annotation + snapshot/freeze + engine-vs-old diff ----------

def test_freeze_run_preserves_snapshot_and_allows_new_live(tmp_path):
    db, rid, sols = _seed(tmp_path)
    conn = Store.connect(db)
    frozen = Store.freeze_run(conn, Store.params_key(_opts()), "old engine")
    assert frozen == rid
    fr = conn.execute("SELECT params_key, frozen, label FROM runs WHERE id=?", (rid,)).fetchone()
    assert fr["frozen"] == 1 and fr["label"] == "old engine" and fr["params_key"].endswith("#old engine")
    assert conn.execute("SELECT COUNT(*) FROM patterns WHERE run_id=?", (rid,)).fetchone()[0] == len(sols)
    conn.close()
    # a re-run with the SAME opts now creates a NEW live run beside the frozen snapshot
    sols2, ctx2, _ = Search.run(_opts())
    rid2 = Store.save_sqlite(_opts(), sols2, ctx2, lattice="square", region="rect", path=db)
    assert rid2 != rid
    conn = Store.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 2          # both coexist
    assert conn.execute("SELECT frozen FROM runs WHERE id=?", (rid2,)).fetchone()["frozen"] == 0
    conn.close()


def test_freeze_run_none_when_no_live_run(tmp_path):
    db = str(tmp_path / "folddb.sqlite3")
    conn = Store.connect(db)
    Store.init_schema(conn)
    assert Store.freeze_run(conn, "nonexistent", "x") is None
    conn.close()


def test_upsert_run_carries_forward_notes_and_label(tmp_path):
    db, rid, _ = _seed(tmp_path)
    conn = Store.connect(db)
    conn.execute("UPDATE runs SET notes=?, label=? WHERE id=?", ("hand-typed note", "exp1", rid))
    conn.commit()
    conn.close()
    sols, ctx, _ = Search.run(_opts())                       # plain re-run, same opts
    Store.save_sqlite(_opts(), sols, ctx, lattice="square", region="rect", path=db)
    conn = Store.connect(db)
    r = conn.execute("SELECT notes, label FROM runs WHERE params_key=? AND COALESCE(frozen,0)=0",
                     (Store.params_key(_opts()),)).fetchone()
    assert r["notes"] == "hand-typed note" and r["label"] == "exp1"    # survived the replace
    # an explicit new label overrides the carried-forward one
    Store.save_sqlite(_opts(), sols, ctx, lattice="square", region="rect", path=db, label="exp2")
    r = conn.execute("SELECT notes, label FROM runs WHERE params_key=? AND COALESCE(frozen,0)=0",
                     (Store.params_key(_opts()),)).fetchone()
    assert r["label"] == "exp2" and r["notes"] == "hand-typed note"
    conn.close()


def test_diff_runs_reports_verdict_flips(tmp_path):
    db, rid, sols = _seed(tmp_path)
    conn = Store.connect(db)
    Store.freeze_run(conn, Store.params_key(_opts()), "old")
    conn.close()
    sols2, ctx2, _ = Search.run(_opts())
    rid2 = Store.save_sqlite(_opts(), sols2, ctx2, lattice="square", region="rect", path=db)
    conn = Store.connect(db)
    frozen_id = conn.execute("SELECT id FROM runs WHERE frozen=1").fetchone()[0]
    d0 = Store.diff_runs(conn, frozen_id, rid2)               # identical engine -> no changes
    assert d0["changed"] == [] and d0["onlyA"] == [] and d0["onlyB"] == []
    # flip one verdict in the new run -> diff surfaces exactly that pattern_uid + column
    row = conn.execute("SELECT pattern_uid, parity FROM patterns WHERE run_id=? LIMIT 1", (rid2,)).fetchone()
    flipped = 0 if row["parity"] else 1
    conn.execute("UPDATE patterns SET parity=? WHERE run_id=? AND pattern_uid=?",
                 (flipped, rid2, row["pattern_uid"]))
    conn.commit()
    d1 = Store.diff_runs(conn, frozen_id, rid2)
    assert len(d1["changed"]) == 1
    assert d1["changed"][0]["pattern_uid"] == row["pattern_uid"]
    assert "parity" in d1["changed"][0]["deltas"]
    conn.close()


def test_snapshot_and_save_diff(tmp_path):
    db, rid, _ = _seed(tmp_path)
    sols2, ctx2, _ = Search.run(_opts())
    res = Store.snapshot_and_save(_opts(), sols2, ctx2, snapshot="old engine", path=db)
    assert res["frozen_id"] == rid and res["run_id"] != rid
    assert res["diff"]["changed"] == []                      # same engine -> identical
    # first-ever run (no prior live) -> frozen_id/diff None, still writes the run
    db2 = str(tmp_path / "fresh.sqlite3")
    sols3, ctx3, _ = Search.run(_opts())
    res2 = Store.snapshot_and_save(_opts(), sols3, ctx3, snapshot="v1", path=db2)
    assert res2["frozen_id"] is None and res2["diff"] is None and res2["run_id"]


def test_init_schema_backfills_old_runs_table(tmp_path):
    """A DB whose runs table predates the annotation columns gets them via ALTER (data preserved)."""
    db = str(tmp_path / "old.sqlite3")
    conn = Store.connect(db)
    conn.executescript(
        "CREATE TABLE runs(id INTEGER PRIMARY KEY, params_key TEXT UNIQUE, lattice TEXT, region TEXT, "
        "m INTEGER, n INTEGER, stacks INTEGER, opts_json TEXT, counts_json TEXT, generated TEXT);"
        "INSERT INTO runs(params_key,m,n,stacks) VALUES('k',6,6,3);")
    conn.commit()
    Store.init_schema(conn)
    Store.init_schema(conn)                                   # idempotent (no duplicate-column error)
    have = {r["name"] for r in conn.execute("PRAGMA table_info(runs)").fetchall()}
    assert {"label", "notes", "frozen"} <= have
    assert conn.execute("SELECT m FROM runs WHERE params_key='k'").fetchone()["m"] == 6   # data kept
    conn.close()


# ---------- migration: idempotent seed from the committed JSON ----------

def test_migration_idempotent(tmp_path):
    """Seed from the frozen tests/fixtures/ corpus (independent of the wipe-able live results/) and
    prove re-seeding neither duplicates nor mis-flags ground truth."""
    import os
    import migrate_to_sqlite as M
    fixtures = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
    findings = os.path.join(fixtures, "foldfindings.json")
    db = str(tmp_path / "folddb.sqlite3")

    def seed():
        conn = Store.connect(db)
        try:
            Store.init_schema(conn)
            M.migrate_results(conn, results_dir=fixtures)
            M.migrate_findings(conn, findings_path=findings)
            conn.commit()
        finally:
            conn.close()

    seed()
    conn = Store.connect(db)
    first_pat = conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
    first_find = conn.execute("SELECT COUNT(*) FROM finding").fetchone()[0]
    conn.close()
    assert first_pat > 0 and first_find > 0            # fixtures actually seeded something

    seed()                                             # second run must not duplicate
    conn = Store.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0] == first_pat
    assert conn.execute("SELECT COUNT(*) FROM finding").fetchone()[0] == first_find
    # every migrated finding with a known physical result is flagged ground truth
    bad = conn.execute("SELECT COUNT(*) FROM finding WHERE foldable IS NOT NULL "
                       "AND is_ground_truth!=1").fetchone()[0]
    assert bad == 0
    conn.close()
