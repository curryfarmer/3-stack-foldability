"""test_write_api.py — live write-back: store.py helpers (upsert_tag / upsert_finding) and the
serve.py write routes (POST /api/tag, POST /api/findings SQLite mirror).

The finding POST mocks findings.submit_record so the test exercises only the SQLite mirror + v_compare,
not the slow engine predict(). Every test uses an isolated tmp DB.
"""
import functools
import http.client
import json
import os
import sys
import threading
from http.server import HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import findings as F   # noqa: E402
import search as Search  # noqa: E402
import serve            # noqa: E402
import store as Store   # noqa: E402


def _seed(tmp_path):
    db = str(tmp_path / "folddb.sqlite3")
    opts = {"m": 3, "n": 2, "stacks": 3,
            "shapes": {"L": True, "Rect": True}, "decomps": {"2+1": True, "1+1+1": True},
            "allowNonCorner": True, "dedup": True, "jobs": 1, "storeAll": True}
    sols, ctx, err = Search.run(opts)
    assert err is None
    Store.save_sqlite(opts, sols, ctx, lattice="square", region="rect", path=db)
    return db, sols


# ---------- store helpers ----------

def test_upsert_tag_insert_update_delete(tmp_path):
    db, sols = _seed(tmp_path)
    conn = Store.connect(db)
    ch = sols[0]["canonicalHash"]
    nh = Store.upsert_tag(conn, ch, "hyp", True, provenance="handmath", by_who="me")
    row = conn.execute("SELECT val_bool,provenance,by_who FROM tag WHERE norm_hash=? AND key='hyp'",
                       (nh,)).fetchone()
    assert (row["val_bool"], row["provenance"], row["by_who"]) == (1, "handmath", "me")
    Store.upsert_tag(conn, ch, "hyp", False)                          # update in place
    assert conn.execute("SELECT val_bool FROM tag WHERE norm_hash=? AND key='hyp'",
                        (nh,)).fetchone()["val_bool"] == 0
    Store.upsert_tag(conn, ch, "hyp", None)                           # None = un-toggle/delete
    assert conn.execute("SELECT COUNT(*) FROM tag WHERE norm_hash=? AND key='hyp'",
                        (nh,)).fetchone()[0] == 0
    conn.close()


def test_upsert_finding_ground_truth_flag(tmp_path):
    db, sols = _seed(tmp_path)
    conn = Store.connect(db)
    ch = sols[0]["canonicalHash"]
    nh = Store.upsert_finding(conn, {"canonicalHash": ch, "foldable": True, "by": "me", "date": "2026-01-01"})
    r = conn.execute("SELECT foldable,is_ground_truth,provenance FROM finding WHERE norm_hash=?",
                     (nh,)).fetchone()
    assert (r["foldable"], r["is_ground_truth"], r["provenance"]) == (1, 1, "physical")
    Store.upsert_finding(conn, {"canonicalHash": ch, "foldable": None})   # untested -> not ground truth
    r = conn.execute("SELECT foldable,is_ground_truth FROM finding WHERE norm_hash=?", (nh,)).fetchone()
    assert r["foldable"] is None and r["is_ground_truth"] == 0
    conn.close()


def test_upsert_finding_provenance_gates_ground_truth(tmp_path):
    """Only a PHYSICAL fold is ground truth; a hand-math verdict is recorded but is_ground_truth=0,
    so it never outranks the engine in v_compare."""
    db, sols = _seed(tmp_path)
    conn = Store.connect(db)
    ch = sols[0]["canonicalHash"]
    nh = Store.upsert_finding(conn, {"canonicalHash": ch, "foldable": True, "provenance": "handmath"})
    r = conn.execute("SELECT foldable,is_ground_truth,provenance FROM finding WHERE norm_hash=?",
                     (nh,)).fetchone()
    assert (r["foldable"], r["is_ground_truth"], r["provenance"]) == (1, 0, "handmath")
    Store.upsert_finding(conn, {"canonicalHash": ch, "foldable": True, "provenance": "physical"})
    assert conn.execute("SELECT is_ground_truth FROM finding WHERE norm_hash=?",
                        (nh,)).fetchone()["is_ground_truth"] == 1
    conn.close()


# ---------- HTTP write routes ----------

def _server(monkeypatch, db):
    monkeypatch.setattr(Store, "SQLITE_PATH", db)
    httpd = HTTPServer(("127.0.0.1", 0),
                       functools.partial(serve.FindingHandler, directory=serve.ROOT))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _post(port, path, body):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("POST", path, json.dumps(body), {"Content-Type": "application/json"})
    r = c.getresponse()
    data = json.loads(r.read())
    c.close()
    return r.status, data


def test_post_tag_roundtrip(tmp_path, monkeypatch):
    db, sols = _seed(tmp_path)
    httpd = _server(monkeypatch, db)
    try:
        port = httpd.server_address[1]
        ch = sols[0]["canonicalHash"]
        st, data = _post(port, "/api/tag", {"canonicalHash": ch, "key": "h", "value": True})
        assert st == 200 and data["ok"]
        conn = Store.connect(db)
        assert conn.execute("SELECT val_bool FROM tag WHERE key='h'").fetchone()["val_bool"] == 1
        conn.close()
        st, data = _post(port, "/api/tag", {"canonicalHash": ch, "key": "h", "value": None})  # delete
        assert st == 200
        conn = Store.connect(db)
        assert conn.execute("SELECT COUNT(*) FROM tag WHERE key='h'").fetchone()[0] == 0
        conn.close()
    finally:
        httpd.shutdown()


def test_post_tag_validation(tmp_path, monkeypatch):
    db, sols = _seed(tmp_path)
    httpd = _server(monkeypatch, db)
    try:
        port = httpd.server_address[1]
        st, data = _post(port, "/api/tag", {"key": "h", "value": True})            # missing hash
        assert st == 400 and not data["ok"]
        st, data = _post(port, "/api/tag",
                         {"canonicalHash": sols[0]["canonicalHash"], "key": "h", "value": "maybe"})
        assert st == 400 and not data["ok"]                                        # bad value
        st, data = _post(port, "/api/tag", {"canonicalHash": "not-json", "key": "h", "value": True})
        assert st == 400 and not data["ok"]                                        # unparseable hash -> 400 not 500
    finally:
        httpd.shutdown()


def test_post_findings_mirrors_to_sqlite(tmp_path, monkeypatch):
    db, sols = _seed(tmp_path)
    ch = sols[0]["canonicalHash"]
    # mock the engine: submit_record normally validates + predicts + writes JSON; we only test the mirror
    canned = {"canonicalHash": ch, "foldable": True, "by": "me", "date": "2026-01-01",
              "grid": "3x2", "id": sols[0]["id"], "predicted": {"matched": True, "foldable": False}}
    monkeypatch.setattr(F, "submit_record", lambda payload: canned)
    httpd = _server(monkeypatch, db)
    try:
        port = httpd.server_address[1]
        st, data = _post(port, "/api/findings",
                         {"canonicalHash": ch, "foldable": True, "grid": "3x2", "id": sols[0]["id"]})
        assert st == 200 and data["ok"]
        nh = Store._norm_hash(ch)
        conn = Store.connect(db)
        r = conn.execute("SELECT foldable,is_ground_truth FROM finding WHERE norm_hash=?", (nh,)).fetchone()
        assert r["foldable"] == 1 and r["is_ground_truth"] == 1
        # engine predicted not-foldable, physical folds -> v_compare flags the disagreement (bug suspect)
        agree = conn.execute("SELECT agree FROM v_compare WHERE norm_hash=?", (nh,)).fetchone()["agree"]
        assert agree == 0
        conn.close()
    finally:
        httpd.shutdown()


def test_post_findings_non_json_hash_400(tmp_path, monkeypatch):
    """A schema-valid finding whose canonicalHash is a string but NOT valid JSON must 400 (client
    error), not 500: submit_record raises JSONDecodeError at norm_finding (before any write/engine)."""
    db, sols = _seed(tmp_path)
    httpd = _server(monkeypatch, db)
    try:
        port = httpd.server_address[1]
        st, data = _post(port, "/api/findings",
                         {"canonicalHash": "not-json", "foldable": True, "grid": "3x2", "id": 0,
                          "by": "me", "date": "2026-01-01"})
        assert st == 400 and not data["ok"]
    finally:
        httpd.shutdown()
