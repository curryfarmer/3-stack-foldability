"""store.py — per-params JSON result files + a manifest index.

results/
  manifest.json          # index: list of {file, m, n, opts, count, generated}
  6x6_<hash8>.json       # {meta:{m,n,opts,generated,counts}, solutions:[...]}

The JSON shape matches the browser tool's own export (app.js exportJson) so the
'Load results' picker can consume either.
"""

import os
import json
import hashlib
import datetime
import sqlite3

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
MANIFEST = os.path.join(RESULTS_DIR, "manifest.json")
# SQLite source-of-truth (Phase-A store-all + non-destructive verdict/tag/finding columns). The JSON
# writer above becomes a one-way export. Override via env FOLDDB_SQLITE for tests / scratch DBs.
SQLITE_PATH = os.environ.get("FOLDDB_SQLITE") or os.path.join(RESULTS_DIR, "folddb.sqlite3")


def _canonical(opts):
    """Stable representation of the params that define a result set."""
    stacks = opts.get("stacks", 3)
    base = {
        "m": opts["m"], "n": opts["n"], "stacks": stacks,
        "dedup": bool(opts.get("dedup", True)),
    }
    if stacks == 3:
        base["shapes"] = {k: bool(v) for k, v in sorted(opts["shapes"].items())}
        base["decomps"] = {k: bool(v) for k, v in sorted(opts["decomps"].items())}
        base["allowNonCorner"] = bool(opts.get("allowNonCorner"))
        # store-all is a DIFFERENT result set (all covered candidates, not gate-survivors), so it
        # gets its own key/file. Added only when True so every existing legacy key is unchanged.
        if opts.get("storeAll"):
            base["storeAll"] = True
    return base


def params_key(opts):
    blob = json.dumps(_canonical(opts), sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(blob.encode()).hexdigest()[:8]


def result_path(opts):
    tag = "" if opts.get("stacks", 3) == 3 else f"{opts['stacks']}stack_"
    return os.path.join(RESULTS_DIR, f"{opts['m']}x{opts['n']}_{tag}{params_key(opts)}.json")


def load_manifest():
    if not os.path.exists(MANIFEST):
        return []
    with open(MANIFEST) as f:
        return json.load(f)


def save_manifest(entries):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(MANIFEST, "w") as f:
        json.dump(entries, f, indent=2)


def find_cached(opts):
    key = params_key(opts)
    for e in load_manifest():
        if e.get("key") == key:
            return e if os.path.exists(os.path.join(RESULTS_DIR, e["file"])) else None
    return None


def save_result(opts, solutions, ctx):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = result_path(opts)
    fname = os.path.basename(path)
    generated = datetime.datetime.now().isoformat(timespec="seconds")
    counts = {k: v for k, v in ctx.items() if isinstance(v, int) and not isinstance(v, bool)}
    payload = {
        "meta": {"m": opts["m"], "n": opts["n"], "stacks": opts.get("stacks", 3),
                 "opts": _canonical(opts), "generated": generated, "counts": counts},
        "solutions": solutions,
    }
    with open(path, "w") as f:
        json.dump(payload, f, separators=(",", ":"))

    entries = [e for e in load_manifest() if e.get("key") != params_key(opts)]
    entries.append({
        "key": params_key(opts), "file": fname,
        "m": opts["m"], "n": opts["n"], "opts": _canonical(opts),
        "count": len(solutions), "generated": generated,
    })
    entries.sort(key=lambda e: (e["m"], e["n"], e["key"]))
    save_manifest(entries)
    return path


# ============================================================================
# SQLite source-of-truth (Phase A store-all + Phase B non-destructive columns)
# ============================================================================
#
# patterns holds EVERY D4-deduped covered candidate; the foldability gates are merged in as
# nullable verdict columns (a new verdict is one ADD COLUMN). tag is an EAV side-table so a user
# can add/remove arbitrary columns with no migration. finding carries the physical ground-truth.
# v_compare derives the engine-vs-physical `agree` flag. The browser reads/writes this via serve.py
# (file:// keeps the JSON export as a read-only fallback). canonical_hash is the D4 dedup key;
# norm_hash (sorted-keys compact, == findings._norm_hash) is the cross-table join key.

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY,
  params_key TEXT UNIQUE,
  lattice TEXT, region TEXT,
  m INTEGER, n INTEGER, stacks INTEGER,
  opts_json TEXT, counts_json TEXT, generated TEXT
);

CREATE TABLE IF NOT EXISTS patterns(
  id INTEGER PRIMARY KEY,
  run_id INTEGER REFERENCES runs(id) ON DELETE CASCADE,
  seq INTEGER,
  pattern_uid TEXT,                 -- stable DISTINCT-pattern id, shared across runs/opts
  lattice TEXT,
  canonical_hash TEXT, norm_hash TEXT,
  footprint_kind TEXT,              -- 'L'|'Rect'|'trapezoid' (lattice-generic)
  shape TEXT, rotation INTEGER, anchor_x INTEGER, anchor_y INTEGER,
  decomposition TEXT, chain_kinds TEXT, axis TEXT, n_h TEXT, n_v TEXT,
  -- non-destructive verdict columns (merged 1:1; a new verdict = one ADD COLUMN)
  arithmetic INTEGER, exit_footprint INTEGER, parity INTEGER, vector_parity INTEGER,
  reflection INTEGER, twist INTEGER, twist_value INTEGER,
  detail_json TEXT,                 -- exact sol blob -> viewer render path unchanged
  -- Identity = (run, per-run sequence). NOT canonical_hash: under --no-dedup distinct candidates can
  -- share a D4 canonical_hash, and Phase A must store ALL of them (canonical_hash is the JOIN key only).
  UNIQUE(run_id, seq)
);
CREATE INDEX IF NOT EXISTS ix_patterns_run ON patterns(run_id);
CREATE INDEX IF NOT EXISTS ix_patterns_normhash ON patterns(norm_hash);
CREATE INDEX IF NOT EXISTS ix_patterns_lattice ON patterns(lattice);
CREATE INDEX IF NOT EXISTS ix_patterns_uid ON patterns(pattern_uid);

CREATE TABLE IF NOT EXISTS tag(
  norm_hash TEXT, key TEXT,
  val_bool INTEGER, val_text TEXT, val_int INTEGER,
  provenance TEXT,                  -- 'engine'|'handmath'|'physical'
  by_who TEXT, date TEXT, notes TEXT,
  PRIMARY KEY(norm_hash, key)
);
CREATE INDEX IF NOT EXISTS ix_tag_key ON tag(key);

CREATE TABLE IF NOT EXISTS finding(
  norm_hash TEXT PRIMARY KEY,
  rec_json TEXT,
  foldable INTEGER,
  provenance TEXT,                  -- 'physical' (hand-folded) | 'handmath' (computed)
  is_ground_truth INTEGER,          -- 1 when physically folded+observed; outranks engine/handmath
  by_who TEXT, date TEXT
);

CREATE VIEW IF NOT EXISTS v_compare AS
  SELECT p.run_id, p.lattice, p.seq, p.pattern_uid, p.canonical_hash, p.norm_hash,
         p.reflection AS eng_refl, p.parity AS eng_parity, p.twist AS eng_twist,
         f.foldable AS phys_foldable, f.is_ground_truth,
         json_extract(f.rec_json,'$.predicted.foldable') AS pred_foldable,
         CASE WHEN f.foldable IS NULL
                OR json_extract(f.rec_json,'$.predicted.foldable') IS NULL THEN NULL
              WHEN f.foldable = json_extract(f.rec_json,'$.predicted.foldable') THEN 1
              ELSE 0 END AS agree
  FROM patterns p
  LEFT JOIN finding f ON f.norm_hash = p.norm_hash;
"""

# Column order for the patterns INSERT (kept beside SCHEMA_SQL so they cannot drift).
_PATTERN_COLS = (
    "run_id", "seq", "pattern_uid", "lattice", "canonical_hash", "norm_hash",
    "footprint_kind", "shape", "rotation", "anchor_x", "anchor_y",
    "decomposition", "chain_kinds", "axis", "n_h", "n_v",
    "arithmetic", "exit_footprint", "parity", "vector_parity",
    "reflection", "twist", "twist_value", "detail_json",
)


def _norm_hash(canonical_hash):
    """Normalized canonical-hash key (sorted keys, compact) — mirrors findings._norm_hash so
    patterns.norm_hash joins tag/finding rows byte-for-byte. I/O: (json str) -> json str."""
    return json.dumps(json.loads(canonical_hash), sort_keys=True, separators=(",", ":"))


def pattern_uid(lattice, m, n, canonical_hash):
    """Stable DISTINCT-pattern id: the SAME D4-canonical pattern maps to the SAME uid across every
    run/opts combination (and across re-imports). 12 hex chars. I/O: (...) -> str."""
    blob = f"{lattice}|{m}x{n}|{canonical_hash}"
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


def _b(x):
    """SQLite-friendly bool: True/False -> 1/0, None -> None (NULL). I/O: (bool|None) -> int|None."""
    return None if x is None else int(bool(x))


def _legacy_vector_parity(chains):
    """Recompute the legacy nH-even/nV-odd vector parity from a sol's chains — used when seeding
    pre-storeAll JSON whose verdict block predates the vectorParity column. I/O: (chains) -> bool."""
    for c in chains:
        arrows = c.get("foldArrows", [])
        nH = sum(1 for a in arrows if a in ("L", "R"))
        if nH % 2 != 0 or (len(arrows) - nH) % 2 != 1:
            return False
    return True


def connect(path=None):
    """Open the folddb SQLite connection (WAL, FK cascade on, Row factory). I/O: (path?) -> conn."""
    conn = sqlite3.connect(path or SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn):
    """Create tables/indexes/view if absent (idempotent). I/O: (conn) -> None."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def _pattern_row(run_id, sol, lattice, m, n):
    """Flatten one solution dict into a patterns row tuple (order == _PATTERN_COLS)."""
    ch = sol["chains"]
    v = sol.get("verdict", {})
    fp = sol["footprint"]
    vp = v["vectorParity"] if "vectorParity" in v else _legacy_vector_parity(ch)
    twist = v.get("twist")
    twist_value = (None if twist is None
                   else sum(1 for p in sol.get("twistPairs", []) if p.get("tw", 0) != 0))
    ch_hash = sol["canonicalHash"]
    return (
        run_id, sol.get("id"), pattern_uid(lattice, m, n, ch_hash), lattice,
        ch_hash, _norm_hash(ch_hash),
        fp["shape"], fp["shape"], fp.get("rotation"),
        fp["anchor"]["x"], fp["anchor"]["y"],
        sol["decomposition"], "+".join(c["kind"] for c in ch), None,
        ",".join(str(c.get("nH", "")) for c in ch),
        ",".join(str(c.get("nV", "")) for c in ch),
        _b(v.get("arithmetic")), _b(v.get("exitFootprint")), _b(v.get("parity")), _b(vp),
        _b(v.get("reflection")), _b(twist), twist_value,
        json.dumps(sol, separators=(",", ":")),
    )


def upsert_run(conn, opts, ctx, lattice, region):
    """Replace the run row for these params (cascade-clearing its old patterns) and return run_id."""
    pk = params_key(opts)
    counts = {k: v for k, v in ctx.items() if isinstance(v, int) and not isinstance(v, bool)}
    generated = datetime.datetime.now().isoformat(timespec="seconds")
    conn.execute("DELETE FROM runs WHERE params_key=?", (pk,))     # ON DELETE CASCADE clears patterns
    cur = conn.execute(
        "INSERT INTO runs(params_key,lattice,region,m,n,stacks,opts_json,counts_json,generated) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (pk, lattice, region, opts["m"], opts["n"], opts.get("stacks", 3),
         json.dumps(_canonical(opts), separators=(",", ":")),
         json.dumps(counts, separators=(",", ":")), generated))
    return cur.lastrowid


def insert_patterns(conn, run_id, solutions, lattice, m, n):
    """Batch-insert solutions as patterns rows (INSERT OR IGNORE on UNIQUE(run_id,seq) — only ignores a
    genuine re-insert of the same seq, never a distinct candidate). Returns the count actually inserted."""
    rows = [_pattern_row(run_id, s, lattice, m, n) for s in solutions]
    ph = ",".join("?" * len(_PATTERN_COLS))
    cur = conn.executemany(
        f"INSERT OR IGNORE INTO patterns({','.join(_PATTERN_COLS)}) VALUES({ph})", rows)
    return cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else len(rows)


def save_sqlite(opts, solutions, ctx, *, lattice="square", region="rect", path=None):
    """High-level: open+init the DB, replace the run, insert its patterns, commit. I/O: -> run_id."""
    conn = connect(path)
    try:
        init_schema(conn)
        run_id = upsert_run(conn, opts, ctx, lattice, region)
        insert_patterns(conn, run_id, solutions, lattice, opts["m"], opts["n"])
        conn.commit()
        return run_id
    finally:
        conn.close()


def upsert_tag(conn, canonical_hash, key, value, *, provenance="handmath", by_who=None, notes=None):
    """Live single-row tag write-back (the in-viewer custom-column tagging). value None DELETES the row
    (un-toggle); else upserts val_bool on PK(norm_hash,key). Commits. I/O: (...) -> norm_hash."""
    nh = _norm_hash(canonical_hash)
    if value is None:
        conn.execute("DELETE FROM tag WHERE norm_hash=? AND key=?", (nh, key))
    else:
        date = datetime.datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO tag(norm_hash,key,val_bool,provenance,by_who,date,notes) "
            "VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(norm_hash,key) DO UPDATE SET val_bool=excluded.val_bool,"
            "provenance=excluded.provenance,by_who=excluded.by_who,date=excluded.date,notes=excluded.notes",
            (nh, key, _b(value), provenance, by_who, date, notes))
    conn.commit()
    return nh


def upsert_finding(conn, rec, *, provenance=None):
    """Mirror a submitted FoldFinding into the SQLite finding table so v_compare stays live. Provenance
    comes from the record ('physical' default); only a PHYSICAL result with a known foldable is ground
    truth (handmath/engine are recorded but not GT). Commits. I/O: (conn, rec) -> norm_hash."""
    nh = _norm_hash(rec["canonicalHash"])
    foldable = rec.get("foldable")
    prov = provenance or rec.get("provenance") or "physical"
    is_gt = 1 if (prov == "physical" and foldable is not None) else 0
    conn.execute(
        "INSERT INTO finding(norm_hash,rec_json,foldable,provenance,is_ground_truth,by_who,date) "
        "VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(norm_hash) DO UPDATE SET rec_json=excluded.rec_json,foldable=excluded.foldable,"
        "provenance=excluded.provenance,is_ground_truth=excluded.is_ground_truth,"
        "by_who=excluded.by_who,date=excluded.date",
        (nh, json.dumps(rec, separators=(",", ":")), _b(foldable), prov, is_gt,
         rec.get("by"), rec.get("date")))
    conn.commit()
    return nh


def export_json(conn, run_id):
    """One-way snapshot: regenerate the legacy results/<grid>_<hash>.json + manifest entry for a run
    from the DB (file:// / git archival). SQLite stays the only write master. I/O: -> path."""
    run = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if run is None:
        raise KeyError(f"no run id {run_id}")
    opts = json.loads(run["opts_json"])               # already the _canonical form
    counts = json.loads(run["counts_json"])
    rows = conn.execute(
        "SELECT detail_json FROM patterns WHERE run_id=? ORDER BY seq", (run_id,)).fetchall()
    solutions = [json.loads(r["detail_json"]) for r in rows]
    payload = {
        "meta": {"m": run["m"], "n": run["n"], "stacks": run["stacks"],
                 "opts": opts, "generated": run["generated"], "counts": counts},
        "solutions": solutions,
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = result_path(opts)
    with open(path, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    return path
