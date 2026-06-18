"""test_read_api.py — serve.py read API (GET /api/runs, GET /api/patterns).

Covers the SQL-whitelist surface (paging, sort dir, pattern/tag filters, tag pivot, injection
falls back to seq) at the query-helper level, plus a live in-thread HTTP smoke of the route
dispatch and the missing-DB JSON fallback. Every test uses an isolated tmp DB.
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
    sys.path.insert(0, ROOT)                              # repo root for serve.py

import search as Search   # noqa: E402  (sys.path set in conftest.py)
import serve              # noqa: E402
import store as Store     # noqa: E402


def _seed(tmp_path):
    """Run a 3x2 store-all search into a fresh tmp DB. -> (db_path, run_id, solutions)."""
    db = str(tmp_path / "folddb.sqlite3")
    opts = {"m": 3, "n": 2, "stacks": 3,
            "shapes": {"L": True, "Rect": True}, "decomps": {"2+1": True, "1+1+1": True},
            "allowNonCorner": True, "dedup": True, "jobs": 1, "storeAll": True}
    sols, ctx, err = Search.run(opts)
    assert err is None
    rid = Store.save_sqlite(opts, sols, ctx, lattice="square", region="rect", path=db)
    return db, rid, sols


def _q(**kw):
    """Build a parse_qs-style dict (every value is a list, like urllib gives serve)."""
    return {k: (v if isinstance(v, list) else [str(v)]) for k, v in kw.items()}


# ---------- query-helper level: paging / sort / filter / tags / injection ----------

def test_patterns_total_and_paging(tmp_path):
    db, _, sols = _seed(tmp_path)
    conn = Store.connect(db)
    assert serve.query_patterns(conn, _q())["total"] == len(sols)
    page = serve.query_patterns(conn, _q(limit=2, offset=0))
    assert len(page["rows"]) == 2 and page["total"] == len(sols)
    page2 = serve.query_patterns(conn, _q(limit=2, offset=2))
    assert page["rows"][0]["seq"] != page2["rows"][0]["seq"]      # offset advances the window
    conn.close()


def test_patterns_sort_dir(tmp_path):
    db, _, _ = _seed(tmp_path)
    conn = Store.connect(db)
    asc = [r["seq"] for r in serve.query_patterns(conn, _q(sort="seq", dir="asc"))["rows"]]
    desc = [r["seq"] for r in serve.query_patterns(conn, _q(sort="seq", dir="desc"))["rows"]]
    assert asc == sorted(asc) and desc == sorted(asc, reverse=True)
    conn.close()


def test_patterns_filter_pattern_col(tmp_path):
    db, _, _ = _seed(tmp_path)
    conn = Store.connect(db)
    res = serve.query_patterns(conn, _q(filter=["reflection:false"]))
    assert res["total"] > 0 and all(r["reflection"] == 0 for r in res["rows"])
    conn.close()


def test_patterns_unknown_sort_falls_back_no_injection(tmp_path):
    db, _, _ = _seed(tmp_path)
    conn = Store.connect(db)
    # a non-whitelisted sort key must neither error nor execute as SQL -> seq fallback, table intact
    res = serve.query_patterns(conn, _q(sort="seq; DROP TABLE patterns"))
    assert res["total"] > 0
    assert conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0] == res["total"]
    conn.close()


def test_patterns_tag_pivot_and_filter(tmp_path):
    db, _, _ = _seed(tmp_path)
    conn = Store.connect(db)
    nh = conn.execute("SELECT norm_hash FROM patterns ORDER BY seq LIMIT 1").fetchone()[0]
    conn.execute("INSERT INTO tag(norm_hash,key,val_bool,provenance) VALUES(?,?,1,'handmath')",
                 (nh, "myHyp"))
    conn.commit()
    res = serve.query_patterns(conn, _q())
    assert "myHyp" in res["tagKeys"]
    assert [r for r in res["rows"] if r["norm_hash"] == nh][0]["tags"].get("myHyp") == 1
    only = serve.query_patterns(conn, _q(filter=["tag:myHyp:true"]))
    assert only["total"] == 1 and only["rows"][0]["norm_hash"] == nh
    conn.close()


def test_rows_carry_render_blob(tmp_path):
    db, _, _ = _seed(tmp_path)
    conn = Store.connect(db)
    r = serve.query_patterns(conn, _q(limit=1))["rows"][0]
    assert r["detail"]["canonicalHash"] and r["detail"]["chains"]   # exact sol blob for the viewer
    conn.close()


def test_runs_listing(tmp_path):
    db, _, sols = _seed(tmp_path)
    conn = Store.connect(db)
    runs = serve.list_runs(conn)
    assert len(runs) == 1
    assert runs[0]["n_patterns"] == len(sols) and runs[0]["m"] == 3
    assert runs[0]["lattice"] == "square" and isinstance(runs[0]["opts"], dict)
    conn.close()


# ---------- live HTTP smoke: route dispatch + missing-DB fallback ----------

def _server(tmp_path, monkeypatch, db):
    monkeypatch.setattr(Store, "SQLITE_PATH", db)
    httpd = HTTPServer(("127.0.0.1", 0),
                       functools.partial(serve.FindingHandler, directory=serve.ROOT))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", path)
    r = c.getresponse()
    body = json.loads(r.read())
    c.close()
    return r.status, body


def test_http_routes(tmp_path, monkeypatch):
    db, _, sols = _seed(tmp_path)
    httpd = _server(tmp_path, monkeypatch, db)
    try:
        port = httpd.server_address[1]
        st, body = _get(port, "/api/runs")
        assert st == 200 and len(body["runs"]) == 1
        st, body = _get(port, "/api/patterns?limit=3&sort=parity&dir=desc")
        assert st == 200 and len(body["rows"]) == 3 and body["total"] == len(sols)
    finally:
        httpd.shutdown()


def test_http_missing_db_fallback(tmp_path, monkeypatch):
    httpd = _server(tmp_path, monkeypatch, str(tmp_path / "nope.sqlite3"))
    try:
        st, body = _get(httpd.server_address[1], "/api/patterns")
        assert st == 200 and body["dbMissing"] is True and body["rows"] == []
    finally:
        httpd.shutdown()


def test_http_malformed_numeric_params_400(tmp_path, monkeypatch):
    db, _, _ = _seed(tmp_path)
    httpd = _server(tmp_path, monkeypatch, db)
    try:
        port = httpd.server_address[1]
        for bad in ("/api/patterns?limit=abc", "/api/patterns?run=xyz", "/api/patterns?offset=-q"):
            st, body = _get(port, bad)
            assert st == 400 and body["ok"] is False, bad          # graceful 400, not a 500 crash
    finally:
        httpd.shutdown()
