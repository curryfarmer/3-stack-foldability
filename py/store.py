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
# Conventional scratch/test DB (the `--test` flag): a throwaway peer of the write-master so a reset or
# experiment can be rehearsed without touching real data. Gitignored, regenerable.
TEST_SQLITE_PATH = os.path.join(RESULTS_DIR, "folddb.test.sqlite3")


def resolve_db_path(arg=None, test=False):
    """Pick the SQLite path a CLI should use. Precedence: explicit --db PATH > --test (scratch DB) >
    SQLITE_PATH (which already honors $FOLDDB_SQLITE, else the default). I/O: (arg?, test?) -> path."""
    if arg:
        return arg
    if test:
        return TEST_SQLITE_PATH
    return SQLITE_PATH


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


def load_manifest(path=None):
    path = path or MANIFEST
    if not os.path.exists(path):
        return []
    with open(path) as f:
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
  opts_json TEXT, counts_json TEXT, generated TEXT,
  label TEXT,                       -- short user name for the run (e.g. 'twist-fix v2')
  notes TEXT,                       -- free-text annotation (hand-edit in a DB browser); survives re-runs
  frozen INTEGER DEFAULT 0          -- 1 = a preserved snapshot; a re-run never replaces it (see freeze_run)
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

-- patterns_grid denormalizes the run's grid (m, n) + label onto each pattern row so a DB-browser
-- Browse-Data filter can pin a grid size directly (patterns itself only carries run_id). Read-only.
CREATE VIEW IF NOT EXISTS patterns_grid AS
  SELECT r.m, r.n, r.label AS run_label, p.*
  FROM patterns p
  JOIN runs r ON r.id = p.run_id;

-- model_compare puts each 2+1 fold's ENGINE prediction next to the user's PHYSICAL observation, per
-- twist hypothesis, with an agree flag. Long format (one row per pattern×model) so it stays dynamic
-- as hypotheses are added: each '<model>_pred' tag (engine) is matched to its '<model>_actual' tag
-- (you). Filter by model_key / agree=0 in a DB browser to find engine-vs-reality mismatches.
CREATE VIEW IF NOT EXISTS model_compare AS
  SELECT r.m, r.n, p.pattern_uid, p.norm_hash, p.decomposition,
         substr(tp.key, 1, length(tp.key) - 5) AS model_key,
         tp.val_bool AS eng_pass, tp.val_int AS eng_tw, tp.val_text AS eng_class,
         ta.val_bool AS phys_pass,
         (tp.val_bool = ta.val_bool) AS agree
  FROM patterns p
  JOIN runs r ON r.id = p.run_id
  JOIN tag tp ON tp.norm_hash = p.norm_hash AND substr(tp.key, -5) = '_pred'
  LEFT JOIN tag ta ON ta.norm_hash = p.norm_hash
       AND ta.key = substr(tp.key, 1, length(tp.key) - 5) || '_actual'
  WHERE p.decomposition = '2+1';
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
    """Open the folddb SQLite connection (WAL, FK cascade on, Row factory). busy_timeout lets a write
    wait out a transient lock (a dying process, a WAL checkpoint) instead of failing instantly; a GUI
    holding the DB open (DB Browser) will still block — close it first. I/O: (path?) -> conn."""
    conn = sqlite3.connect(path or SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_schema(conn):
    """Create tables/indexes/view if absent (idempotent), and back-fill the run-annotation columns on
    DBs created before they existed (ALTER ADD COLUMN preserves all data). I/O: (conn) -> None."""
    conn.executescript(SCHEMA_SQL)
    have = {r["name"] for r in conn.execute("PRAGMA table_info(runs)").fetchall()}
    for col, ddl in (("label", "label TEXT"), ("notes", "notes TEXT"),
                     ("frozen", "frozen INTEGER DEFAULT 0")):
        if col not in have:
            conn.execute(f"ALTER TABLE runs ADD COLUMN {ddl}")
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


def upsert_run(conn, opts, ctx, lattice, region, *, label=None, note=None):
    """Replace the LIVE run row for these params (cascade-clearing its old patterns) and return run_id.
    Frozen snapshots (frozen=1) are never touched. A hand-edited label/notes on the previous live run
    is carried forward unless a new value is passed, so DB-browser annotations survive a plain re-run."""
    pk = params_key(opts)
    counts = {k: v for k, v in ctx.items() if isinstance(v, int) and not isinstance(v, bool)}
    generated = datetime.datetime.now().isoformat(timespec="seconds")
    prev = conn.execute(                                           # preserve annotation across re-run
        "SELECT label, notes FROM runs WHERE params_key=? AND COALESCE(frozen,0)=0", (pk,)).fetchone()
    keep_label = label if label is not None else (prev["label"] if prev else None)
    keep_notes = note if note is not None else (prev["notes"] if prev else None)
    conn.execute("DELETE FROM runs WHERE params_key=? AND COALESCE(frozen,0)=0", (pk,))  # CASCADE clears patterns
    cur = conn.execute(
        "INSERT INTO runs(params_key,lattice,region,m,n,stacks,opts_json,counts_json,generated,"
        "label,notes,frozen) VALUES(?,?,?,?,?,?,?,?,?,?,?,0)",
        (pk, lattice, region, opts["m"], opts["n"], opts.get("stacks", 3),
         json.dumps(_canonical(opts), separators=(",", ":")),
         json.dumps(counts, separators=(",", ":")), generated, keep_label, keep_notes))
    return cur.lastrowid


def freeze_run(conn, params_key_str, label):
    """Preserve the current LIVE run for a params_key as a snapshot: rename its params_key (so the next
    generate writes a fresh live run beside it instead of replacing it), set frozen=1 + label. Patterns
    reference run_id (not params_key), so they ride along untouched. Commits.
    I/O: (conn, params_key, label) -> frozen run_id | None (None if no live run for that key)."""
    row = conn.execute(
        "SELECT id, params_key FROM runs WHERE params_key=? AND COALESCE(frozen,0)=0",
        (params_key_str,)).fetchone()
    if row is None:
        return None
    base = f"{row['params_key']}#{label or 'snapshot'}"           # keep params_key UNIQUE
    new_pk, i = base, 2
    while conn.execute("SELECT 1 FROM runs WHERE params_key=?", (new_pk,)).fetchone():
        new_pk, i = f"{base}-{i}", i + 1
    conn.execute("UPDATE runs SET frozen=1, label=?, params_key=? WHERE id=?",
                 (label, new_pk, row["id"]))
    conn.commit()
    return row["id"]


# Verdict columns compared by diff_runs (the non-destructive gate annotations only — not geometry).
_VERDICT_COLS = ("arithmetic", "exit_footprint", "parity", "vector_parity",
                 "reflection", "twist", "twist_value")


def diff_runs(conn, run_a, run_b):
    """Compare two runs pattern-by-pattern, joined on the stable pattern_uid. Reports verdict-column
    FLIPS plus patterns present in only one run. (pattern_uid is unique per run for dedup'd sets; under
    --no-dedup a uid can repeat within a run and only the last row is compared.)
    I/O: -> {a, b, changed:[{pattern_uid, deltas:{col:[a_val,b_val]}}], onlyA:[uid], onlyB:[uid]}."""
    def by_uid(rid):
        return {r["pattern_uid"]: r for r in conn.execute(
            f"SELECT pattern_uid,{','.join(_VERDICT_COLS)} FROM patterns WHERE run_id=?", (rid,))}
    A, B = by_uid(run_a), by_uid(run_b)
    changed = []
    for uid in A.keys() & B.keys():
        deltas = {c: [A[uid][c], B[uid][c]] for c in _VERDICT_COLS if A[uid][c] != B[uid][c]}
        if deltas:
            changed.append({"pattern_uid": uid, "deltas": deltas})
    changed.sort(key=lambda d: d["pattern_uid"])
    return {"a": run_a, "b": run_b, "changed": changed,
            "onlyA": sorted(A.keys() - B.keys()), "onlyB": sorted(B.keys() - A.keys())}


def insert_patterns(conn, run_id, solutions, lattice, m, n):
    """Batch-insert solutions as patterns rows (INSERT OR IGNORE on UNIQUE(run_id,seq) — only ignores a
    genuine re-insert of the same seq, never a distinct candidate). Returns the count actually inserted."""
    rows = [_pattern_row(run_id, s, lattice, m, n) for s in solutions]
    ph = ",".join("?" * len(_PATTERN_COLS))
    cur = conn.executemany(
        f"INSERT OR IGNORE INTO patterns({','.join(_PATTERN_COLS)}) VALUES({ph})", rows)
    return cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else len(rows)


def save_sqlite(opts, solutions, ctx, *, lattice="square", region="rect", path=None,
                label=None, note=None):
    """High-level: open+init the DB, replace the live run, insert its patterns, commit. I/O: -> run_id."""
    conn = connect(path)
    try:
        init_schema(conn)
        run_id = upsert_run(conn, opts, ctx, lattice, region, label=label, note=note)
        insert_patterns(conn, run_id, solutions, lattice, opts["m"], opts["n"])
        conn.commit()
        return run_id
    finally:
        conn.close()


def snapshot_and_save(opts, solutions, ctx, *, snapshot, label=None, note=None,
                      lattice="square", region="rect", path=None):
    """Freeze the current live run for these params under `snapshot` (preserving it), then write the new
    live run, and diff old-vs-new by pattern_uid. The engine-vs-old-engine compare path. I/O:
    -> {run_id, frozen_id, diff}  (frozen_id/diff are None when there was no prior live run)."""
    conn = connect(path)
    try:
        init_schema(conn)
        frozen_id = freeze_run(conn, params_key(opts), snapshot)
        run_id = upsert_run(conn, opts, ctx, lattice, region, label=label, note=note)
        insert_patterns(conn, run_id, solutions, lattice, opts["m"], opts["n"])
        conn.commit()
        diff = diff_runs(conn, frozen_id, run_id) if frozen_id is not None else None
        return {"run_id": run_id, "frozen_id": frozen_id, "diff": diff}
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


def upsert_engine_pred(conn, norm_hash, key, passval, tw=None, cls=None, version=None, *, commit=True):
    """Write one ENGINE model prediction as a tag row (provenance='engine'), keyed (norm_hash, key) —
    by convention key is '<model>_pred', the twin of the user's '<model>_actual' tag. Carries pass in
    val_bool (the viewer ✓/✗ + the model_compare agree flag), the rounded twist in val_int and the
    partial-decomp class in val_text (both SQL / DB-browser visible), and a 'tw=<raw>; v=<version>'
    stamp in notes so a re-run after a hypothesis changes is detectable. Idempotent upsert on the PK;
    pass commit=False to batch many writes under one transaction. I/O: (...) -> norm_hash."""
    date = datetime.datetime.now().isoformat(timespec="seconds")
    notes = f"tw={tw}; v={version}" if version is not None else f"tw={tw}"
    conn.execute(
        "INSERT INTO tag(norm_hash,key,val_bool,val_int,val_text,provenance,by_who,date,notes) "
        "VALUES(?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(norm_hash,key) DO UPDATE SET val_bool=excluded.val_bool,val_int=excluded.val_int,"
        "val_text=excluded.val_text,provenance=excluded.provenance,by_who=excluded.by_who,"
        "date=excluded.date,notes=excluded.notes",
        (norm_hash, key, _b(passval), None if tw is None else round(tw),
         cls, "engine", "engine", date, notes))
    if commit:
        conn.commit()
    return norm_hash


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


def export_json(conn, run_id, out_dir=None):
    """One-way snapshot: regenerate the legacy <grid>_<hash>.json for a run from the DB (file:// / git
    archival). Writes into `out_dir` (default the real RESULTS_DIR) — pass a dir to export beside a
    scratch DB instead of polluting results/. SQLite stays the only write master. I/O: -> path."""
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
    out_dir = out_dir or RESULTS_DIR
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, os.path.basename(result_path(opts)))
    with open(path, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    return path


def export_findings(conn, path=None):
    """One-way export: write every `finding` row back out as a foldfindings.json list (the stored
    rec_json blobs). Reverse of migrate_to_sqlite.migrate_findings — makes the JSON a regenerable
    artifact so it can be safely wiped while SQLite stays the findings master. I/O: (conn, path?) -> path."""
    import findings as F                               # lazy: reuse the atomic writer + default path
    path = path or F.DB_PATH
    rows = conn.execute("SELECT rec_json FROM finding ORDER BY norm_hash").fetchall()
    recs = [json.loads(r["rec_json"]) for r in rows]
    F.save_db(recs, path)
    return path
