"""serve.py — static frontend server + one POST route for in-page FoldFinding capture.

`python serve.py` replaces `python -m http.server 8000` for capture sessions:
  * GET/HEAD serve the repo's static frontend BYTE-IDENTICALLY (index.html / app.js / results load
    exactly as today), and
  * POST /api/findings hands the JSON body to the pure findings.submit_record() pipeline
    (validate -> upsert DB -> append LAB_LOG) and returns the persisted record (200) or the
    validation error (400).
Same origin (:8000) => no CORS, no Flask, no extra dependency. The CLI `python py/findings.py submit
<file>` and the UI "Download JSON" button remain the offline fallback; all three wrap one pure
submit path. Engine prediction enumerates closing candidates on submit, so large grids (6x7) can take
a while — that is the same cost the matcher pays.
"""
from __future__ import annotations

import functools
import json
import os
import sys
import urllib.parse as urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
# findings lives in py/; enginelib (lazy-imported by predict) in tests/. Put both on the path.
sys.path.insert(0, os.path.join(ROOT, "py"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from http.server import HTTPServer, SimpleHTTPRequestHandler  # noqa: E402

from jsonschema import ValidationError  # noqa: E402

import findings as F  # noqa: E402
import store as Store  # noqa: E402

ENDPOINT = "/api/findings"
ENDPOINT_TAG = "/api/tag"

# Findings JSON-export + lab-log targets the POST path writes (SQLite is the master, written by
# _mirror_finding). main() repoints these beside a scratch/custom DB so `serve.py --test` leaves the
# real foldfindings.json / LAB_LOG.md byte-untouched — matching `generate.py --test` isolation.
FINDINGS_JSON = F.DB_PATH
LAB_LOG_PATH = F.LAB_LOG_PATH


def _findings_targets(db_path: str, default_db: str) -> tuple[str, str]:
    """Findings JSON-export + lab-log paths for the active DB: the real ones for the default DB, else
    siblings of a scratch/custom DB so `--test`/`--db` leave the real files byte-untouched.
    I/O: (active_db_path, default_db_path) -> (findings_json, lab_log_path)."""
    if os.path.abspath(db_path) == os.path.abspath(default_db):
        return F.DB_PATH, F.LAB_LOG_PATH
    base = os.path.splitext(db_path)[0]
    return base + ".foldfindings.json", base + ".LAB_LOG.md"

# --- read-API whitelists (mandatory: sort/filter values reach SQL, so the column set is closed) ----
# Pattern columns safe to ORDER BY / WHERE (every real column of the patterns table).
_PAT_COLS = frozenset((
    "seq", "pattern_uid", "lattice", "canonical_hash", "footprint_kind", "shape", "rotation",
    "anchor_x", "anchor_y", "decomposition", "chain_kinds", "axis", "n_h", "n_v",
    "arithmetic", "exit_footprint", "parity", "vector_parity", "reflection", "twist", "twist_value",
))
# Derived finding-join columns (selected as output aliases; SQLite allows ORDER BY on an alias).
_JOIN_COLS = frozenset(("phys_foldable", "is_ground_truth", "pred_foldable", "agree"))

# The exact SELECT list shared by /api/patterns rows (kept beside the whitelist so they cannot drift).
_PATTERN_SELECT = """
  SELECT p.id, p.run_id, p.seq, p.pattern_uid, p.lattice, p.canonical_hash, p.norm_hash,
         p.footprint_kind, p.shape, p.rotation, p.anchor_x, p.anchor_y, p.decomposition,
         p.chain_kinds, p.axis, p.n_h, p.n_v, p.arithmetic, p.exit_footprint, p.parity,
         p.vector_parity, p.reflection, p.twist, p.twist_value, p.detail_json,
         f.foldable AS phys_foldable, f.is_ground_truth, f.provenance AS finding_provenance,
         json_extract(f.rec_json,'$.predicted.foldable') AS pred_foldable,
         CASE WHEN f.foldable IS NULL
                OR json_extract(f.rec_json,'$.predicted.foldable') IS NULL THEN NULL
              WHEN f.foldable = json_extract(f.rec_json,'$.predicted.foldable') THEN 1
              ELSE 0 END AS agree
"""


class BadRequest(Exception):
    """A malformed client request -> HTTP 400 (vs an unexpected server fault -> 500)."""


def _int(val, default):
    """Parse an integer query param, raising BadRequest (not ValueError->500) on garbage."""
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        raise BadRequest(f"expected an integer, got {val!r}")


def _coerce(val):
    """Map a raw query-string filter value to a SQL-bind value. 'true'/'false' -> 1/0,
    'null'/'none'/'' -> None (IS NULL), ASCII-digit -> int, else the literal string. (isascii guards
    against str.isdigit() Unicode digits like '²' that int() cannot parse.)"""
    low = val.strip().lower()
    if low in ("null", "none", ""):
        return None
    if low in ("true", "yes"):
        return 1
    if low in ("false", "no"):
        return 0
    stripped = low.lstrip("-")
    if stripped.isascii() and stripped.isdigit():
        return int(low)
    return val


def _add_filter(where, args, spec):
    """Append one filter to (where, args), whitelisted. Forms: `col:val` (pattern/finding column)
    and `tag:KEY:val` (EAV tag — KEY/val bind as parameters, never interpolated into SQL)."""
    parts = spec.split(":")
    if parts[0] == "tag" and len(parts) >= 3:
        key, v = parts[1], _coerce(parts[2])
        if v is None:
            where.append("NOT EXISTS(SELECT 1 FROM tag tf "
                         "WHERE tf.norm_hash=p.norm_hash AND tf.key=?)")
            args.append(key)
        else:
            where.append("EXISTS(SELECT 1 FROM tag tf "
                         "WHERE tf.norm_hash=p.norm_hash AND tf.key=? AND tf.val_bool=?)")
            args.extend([key, v])
        return
    col, _, raw = spec.partition(":")
    val = _coerce(raw)
    ref = ("p." + col if col in _PAT_COLS
           else "f.foldable" if col == "phys_foldable"
           else "f.is_ground_truth" if col == "is_ground_truth"
           else None)
    if ref is None:
        return                                  # unknown column -> silently ignored (closed whitelist)
    if val is None:
        where.append(f"{ref} IS NULL")
    else:
        where.append(f"{ref}=?")
        args.append(val)


def _order_clause(sort):
    """Resolve a sort key to (order_col_sql, join_sql, join_args), whitelisted. Unknown -> seq."""
    if sort and sort.startswith("tag:"):
        return "ts.val_bool", \
               " LEFT JOIN tag ts ON ts.norm_hash=p.norm_hash AND ts.key=? ", [sort[4:]]
    if sort in _PAT_COLS:
        return "p." + sort, "", []
    if sort in _JOIN_COLS:
        return sort, "", []                     # output alias (phys_foldable / agree / ...)
    return "p.seq", "", []


def _compare(conn, q):
    """GET /api/compare?a=&b= -> Store.diff_runs(a,b). Both run ids required + integer (else 400)."""
    one = lambda k: (q.get(k) or [None])[0]
    a, b = _int(one("a"), None), _int(one("b"), None)
    if a is None or b is None:
        raise BadRequest("compare requires integer run ids 'a' and 'b'")
    return Store.diff_runs(conn, a, b)


def list_runs(conn):
    """All runs with their pattern counts, newest grids first. I/O: (conn) -> list[dict]."""
    rows = conn.execute(
        "SELECT r.*, (SELECT COUNT(*) FROM patterns p WHERE p.run_id=r.id) AS n_patterns "
        "FROM runs r ORDER BY r.m, r.n, r.id").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["opts"] = json.loads(d.pop("opts_json") or "{}")
        d["counts"] = json.loads(d.pop("counts_json") or "{}")
        out.append(d)
    return out


def query_patterns(conn, q):
    """Paged, sorted, filtered patterns read. `q` is the parsed query dict (urlparse.parse_qs:
    values are lists). Returns {rows,total,tagKeys,limit,offset}. Every ORDER BY/WHERE fragment is
    whitelisted; values bind as parameters."""
    one = lambda k, d=None: (q.get(k) or [d])[0]
    where, args = [], []
    if one("run"):
        where.append("p.run_id=?"); args.append(_int(one("run"), None))
    if one("lattice"):
        where.append("p.lattice=?"); args.append(one("lattice"))
    for spec in q.get("filter", []):
        _add_filter(where, args, spec)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    total = conn.execute(
        "SELECT COUNT(*) FROM patterns p LEFT JOIN finding f ON f.norm_hash=p.norm_hash" + where_sql,
        args).fetchone()[0]

    order_col, join_sql, join_args = _order_clause(one("sort", "seq"))
    direction = "DESC" if (one("dir", "asc").lower() == "desc") else "ASC"
    tiebreak = "" if order_col == "p.seq" else ", p.seq ASC"
    limit = max(1, min(_int(one("limit", 200), 200), 2000))
    offset = max(0, _int(one("offset", 0), 0))

    rows_sql = (_PATTERN_SELECT
                + " FROM patterns p LEFT JOIN finding f ON f.norm_hash=p.norm_hash"
                + join_sql + where_sql
                + f" ORDER BY {order_col} {direction}{tiebreak} LIMIT ? OFFSET ?")
    raw = conn.execute(rows_sql, join_args + args + [limit, offset]).fetchall()

    # attach this page's EAV tags (one extra query, grouped by norm_hash)
    hashes = [r["norm_hash"] for r in raw]
    tag_map = {}
    if hashes:
        ph = ",".join("?" * len(hashes))
        for t in conn.execute(
                f"SELECT norm_hash,key,val_bool FROM tag WHERE norm_hash IN ({ph})", hashes):
            tag_map.setdefault(t["norm_hash"], {})[t["key"]] = t["val_bool"]

    rows = []
    for r in raw:
        d = dict(r)
        d["detail"] = json.loads(d.pop("detail_json"))      # the exact sol blob the viewer renders
        d["tags"] = tag_map.get(d["norm_hash"], {})
        rows.append(d)

    tag_keys = [k[0] for k in conn.execute("SELECT DISTINCT key FROM tag ORDER BY key").fetchall()]
    return {"rows": rows, "total": total, "tagKeys": tag_keys, "limit": limit, "offset": offset}


class FindingHandler(SimpleHTTPRequestHandler):
    """Static GET/HEAD (unchanged from stdlib); read API GET /api/runs + /api/patterns;
    POST /api/findings -> findings.submit_record()."""

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        parsed = urlparse.urlparse(self.path)
        route = parsed.path.rstrip("/")
        if route == "/api/runs":
            self._api_read(lambda conn: {"runs": list_runs(conn)})
        elif route == "/api/patterns":
            q = urlparse.parse_qs(parsed.query, keep_blank_values=True)
            self._api_read(lambda conn: query_patterns(conn, q))
        elif route == "/api/compare":
            q = urlparse.parse_qs(parsed.query, keep_blank_values=True)
            self._api_read(lambda conn: _compare(conn, q))
        else:
            super().do_GET()                            # static frontend byte-identical to stdlib

    def _api_read(self, fn) -> None:
        """Open a fresh read connection, run `fn(conn)`, emit JSON. Missing DB -> {dbMissing:true}
        (200) so the frontend cleanly falls back to the static results/*.json read path."""
        if not os.path.exists(Store.SQLITE_PATH):
            self._json(200, {"dbMissing": True, "rows": [], "runs": [], "total": 0, "tagKeys": []})
            return
        conn = Store.connect()
        try:
            self._json(200, fn(conn))
        except BadRequest as exc:                       # malformed query params -> 400, not 500
            self._json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:                        # noqa: BLE001 (report any query/IO failure)
            self._json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        finally:
            conn.close()

    def do_POST(self) -> None:  # noqa: N802 (stdlib naming)
        route = self.path.rstrip("/")
        if route not in (ENDPOINT, ENDPOINT_TAG):
            self.send_error(404, "no such endpoint (POST /api/findings or /api/tag)")
            return
        try:
            length = max(0, int(self.headers.get("Content-Length", 0)))   # negative CL -> read(-1) hangs
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"ok": False, "error": f"bad JSON body: {exc}"})
            return
        if route == ENDPOINT_TAG:
            self._post_tag(payload)
            return
        try:
            rec = F.submit_record(payload, db_path=FINDINGS_JSON, lab_log_path=LAB_LOG_PATH)  # validate FIRST -> upsert JSON -> LAB_LOG
        except ValidationError as exc:
            self._json(400, {"ok": False, "error": f"schema: {exc.message}"})
            return
        except json.JSONDecodeError as exc:             # canonicalHash present but not JSON -> client error, not 500
            self._json(400, {"ok": False, "error": f"canonicalHash must be a JSON string: {exc}"})
            return
        except Exception as exc:                        # noqa: BLE001 (report any engine/IO failure)
            self._json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            return
        self._mirror_finding(rec)                       # keep the SQLite finding row + v_compare live
        self._json(200, {"ok": True, "record": rec})

    def _mirror_finding(self, rec: dict) -> None:
        """Write a submitted finding into SQLite — the findings master (the JSON the submit pipeline
        also wrote is a regenerable export). Best-effort + logged: a mirror failure must not lose the
        already-persisted JSON record; the row can be rebuilt with migrate_to_sqlite."""
        try:
            conn = Store.connect()
            try:
                Store.init_schema(conn)
                Store.upsert_finding(conn, rec)
            finally:
                conn.close()
        except Exception as exc:                        # noqa: BLE001 (never fail the JSON write on a mirror error)
            sys.stderr.write(f"[serve] finding SQLite mirror failed: {exc}\n")

    def _post_tag(self, payload: dict) -> None:
        """Live single-row tag write-back: {canonicalHash, key, value(true|false|null), provenance?,
        by?, notes?} -> upsert/delete the EAV tag row. SQLite is the write-master for tags."""
        ch, key = payload.get("canonicalHash"), payload.get("key")
        if not ch or not key:
            self._json(400, {"ok": False, "error": "canonicalHash and key are required"})
            return
        try:
            json.loads(ch)                              # must be a JSON-encoded hash (the join key)
        except (ValueError, TypeError):
            self._json(400, {"ok": False, "error": "canonicalHash must be a JSON string"})
            return
        value = payload.get("value")
        if value not in (True, False, None):
            self._json(400, {"ok": False, "error": "value must be true, false, or null"})
            return
        try:
            conn = Store.connect()
            try:
                Store.init_schema(conn)
                nh = Store.upsert_tag(conn, ch, key, value,
                                      provenance=payload.get("provenance") or "handmath",
                                      by_who=payload.get("by"), notes=payload.get("notes"))
            finally:
                conn.close()
        except Exception as exc:                        # noqa: BLE001
            self._json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            return
        self._json(200, {"ok": True, "normHash": nh, "key": key, "value": value})

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:     # quieter than the stdlib default
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main(argv: list[str] | None = None) -> int:
    """Serve the frontend + findings POST route. I/O: (argv) -> exit code.
    `serve.py [port] [--db PATH | --test]` (port 8000, real write-master DB by default)."""
    import argparse
    p = argparse.ArgumentParser(description="3-stack frontend + findings/read API server")
    p.add_argument("port", nargs="?", type=int, default=8000)
    p.add_argument("--db", metavar="PATH", help="SQLite DB to read/write (default $FOLDDB_SQLITE)")
    p.add_argument("--test", action="store_true", help="serve the scratch DB results/folddb.test.sqlite3")
    ns = p.parse_args(sys.argv[1:] if argv is None else argv)
    port = ns.port
    global FINDINGS_JSON, LAB_LOG_PATH
    default_db = Store.resolve_db_path()                       # capture BEFORE overwriting SQLITE_PATH
    Store.SQLITE_PATH = Store.resolve_db_path(ns.db, ns.test)   # handler reads this module global
    FINDINGS_JSON, LAB_LOG_PATH = _findings_targets(Store.SQLITE_PATH, default_db)
    handler = functools.partial(FindingHandler, directory=ROOT)
    httpd = HTTPServer(("127.0.0.1", port), handler)
    print(f"serving {ROOT} at http://127.0.0.1:{port}/  "
          f"(GET /api/runs, /api/patterns -> {Store.SQLITE_PATH}; POST {ENDPOINT} -> {FINDINGS_JSON})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
