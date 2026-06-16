"""findings.py — the FoldFinding pipeline: schema, validation, DB upsert, LAB_LOG append, submit.

A FoldFinding records a human paper-fold result for one enumerated 3-stack candidate, keyed by the
engine's `canonicalHash`. This module is the ONE findings schema + writer: it validates a finding
against a JSON schema, upserts it into the findings DB (results/foldfindings.json) keyed by the
normalized canonical hash, and appends a dated entry to docs/research/LAB_LOG.md.

Design notes:
  * The engine predicts JAM as a whole-candidate GATE VERDICT (which of parity/reflection/twist
    fails), never a per-fold index. So `jam.atFold` here is a USER-RECORDED physical observation
    (0-based index into `foldOrder`), and the engine side is `predicted.{foldable, failingGates}`.
  * Pure functions take/return data and never touch disk; the few I/O helpers are thin and explicit
    so `submit()` can be driven from a CLI, a stdlib HTTP POST route (serve.py), or a test.
"""
from __future__ import annotations

import json
import os

import jsonschema

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
# Default write targets; override via env (FOLDFINDINGS_DB / FOLDFINDINGS_LABLOG) to capture into a
# scratch DB/log — e.g. a serve.py smoke run or an experiment — without touching the committed files.
DB_PATH = os.environ.get("FOLDFINDINGS_DB") or os.path.join(RESULTS_DIR, "foldfindings.json")
LAB_LOG_PATH = os.environ.get("FOLDFINDINGS_LABLOG") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "research", "LAB_LOG.md")

# Physical jam vocabulary the user may report (superset of the engine's gate names).
REASON_ENUM = ["parity", "reflection", "twist", "exit_footprint", "overlap", "offgrid", "other"]
# Engine gate names (== closing_candidates "fails"); kept separate from the physical reasons.
GATE_ENUM = ["parity", "refl", "twist"]

# FoldFinding JSON schema (Draft 2020-12). Required keys carry identity + physical verdict +
# provenance; everything else is optional so migrated twoplus1_labels records map in losslessly.
SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["grid", "id", "canonicalHash", "foldable", "by", "date"],
    "properties": {
        "grid": {"type": "string"},
        "id": {"type": "integer"},
        "canonicalHash": {"type": "string"},
        "foldable": {"type": ["boolean", "null"]},
        "jam": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "atFold": {"type": ["integer", "null"]},
                "crease": {
                    "type": ["array", "null"],
                    "minItems": 2,
                    "maxItems": 2,
                    "items": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                },
                "reason": {"enum": REASON_ENUM + [None]},
            },
        },
        "foldOrder": {"type": "array", "items": {"enum": ["L", "R", "U", "D"]}},
        "predicted": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "foldable": {"type": "boolean"},
                "failingGates": {"type": "array", "items": {"enum": GATE_ENUM}},
                "matched": {"type": "boolean"},
            },
        },
        "observed": {"type": "object"},
        "by": {"type": "string"},
        "date": {"type": "string"},
        "notes": {"type": "string"},
        # Free-form user tags: arbitrary string keys -> tri-state bool (true/false/null=untested).
        # Used to record, per finding, which candidate decomposition idea holds (e.g. {"modelA": true}).
        "tags": {
            "type": "object",
            "additionalProperties": {"type": ["boolean", "null"]},
        },
    },
}


def load_schema() -> dict:
    """Return the FoldFinding JSON schema (so callers/tests use it without disk I/O). I/O: () -> dict."""
    return SCHEMA


def validate_finding(rec: dict) -> None:
    """Validate a FoldFinding dict against SCHEMA; raise jsonschema.ValidationError if malformed.
    I/O: (rec) -> None (raises on any bad/missing/extra field)."""
    jsonschema.validate(rec, SCHEMA)


def _norm_hash(canonical_hash: str) -> str:
    """Normalize a canonical-hash JSON string (sorted keys, compact) for stable keying/compare.
    Same algorithm as tests/enginelib.norm_hash. I/O: (json str) -> normalized json str."""
    return json.dumps(json.loads(canonical_hash), sort_keys=True, separators=(",", ":"))


def norm_finding(rec: dict) -> dict:
    """Return a shallow copy of rec with canonicalHash normalized (sorted keys, compact).
    I/O: (rec) -> rec (the normalized hash is the DB key); does not mutate the input."""
    out = dict(rec)
    out["canonicalHash"] = _norm_hash(rec["canonicalHash"])
    return out


# ---------- findings DB (a JSON list keyed by normalized canonicalHash) ----------

def _ensure_parent(path: str) -> None:
    """Make a path's parent dir if it has one (no-op for a bare filename in cwd). I/O: (path) -> None."""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def load_db(path: str = DB_PATH) -> list[dict]:
    """Load the findings DB (a JSON list); return [] if the file is absent. I/O: (path) -> list[dict]."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_db(recs: list[dict], path: str = DB_PATH) -> None:
    """Write the findings DB list as pretty JSON, atomically (temp file + replace).
    I/O: (recs, path) -> None."""
    _ensure_parent(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(recs, f, indent=2)
    os.replace(tmp, path)


def upsert(recs: list[dict], rec: dict) -> list[dict]:
    """Return a NEW list with rec inserted, or replacing the record sharing its normalized hash.
    Keyed by normalized canonicalHash so a re-submit overwrites rather than duplicates. Pure: does
    not mutate `recs` or `rec`. I/O: (recs, rec) -> new list[dict]."""
    key = _norm_hash(rec["canonicalHash"])
    out = [r for r in recs if _norm_hash(r["canonicalHash"]) != key]
    out.append(rec)
    return out


# ---------- LAB_LOG append (newest-first, idempotent) ----------

def _foldable_word(v) -> str:
    """Human label for a foldable bit: None->untested, True->FOLD, False->JAM. I/O: (bool|None)->str."""
    return "untested" if v is None else ("FOLD" if v else "JAM")


def _lab_marker(rec: dict) -> str:
    """Stable idempotency marker for a finding's LAB_LOG entry. I/O: (rec) -> html-comment str."""
    return f"<!-- finding:{_norm_hash(rec['canonicalHash'])}|{rec['date']}|{rec.get('by', '?')} -->"


def lab_log_line(rec: dict) -> str:
    """Build the dated LAB_LOG markdown block for a finding (incl. its idempotency marker).
    I/O: (rec) -> markdown str ending in a newline."""
    verdict = _foldable_word(rec.get("foldable"))
    pred = rec.get("predicted") or {}
    pred_word = _foldable_word(pred["foldable"]) if "foldable" in pred else "n/a"
    fails = ",".join(pred.get("failingGates", [])) or "-"
    jam = rec.get("jam") or {}
    lines = [
        f"## {rec['date']} — physical finding: {rec['grid']}#{rec['id']} ({verdict})",
        _lab_marker(rec),
        "",
        f"- grid {rec['grid']} #{rec['id']}, by {rec.get('by', '?')}",
        f"- physical: {verdict}; engine predicted: {pred_word} "
        f"(fails: {fails}; matched: {pred.get('matched', '?')})",
        f"- canonicalHash: `{_norm_hash(rec['canonicalHash'])}`",
    ]
    if jam:
        lines.append(f"- jam: atFold {jam.get('atFold')}, reason {jam.get('reason')}, "
                     f"crease {jam.get('crease')}")
    if rec.get("notes"):
        lines.append(f"- notes: {rec['notes']}")
    return "\n".join(lines) + "\n"


def append_lab_log(rec: dict, path: str = LAB_LOG_PATH) -> bool:
    """Insert a finding's dated entry at the top of LAB_LOG (newest-first), idempotently.
    Skips (returns False) if an entry with the same (hash,date,by) marker is already present.
    I/O: (rec, path) -> bool (True iff written)."""
    content = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            content = f.read()
    if _lab_marker(rec) in content:
        return False
    block = lab_log_line(rec) + "\n"
    idx = content.find("\n## ")                    # insert just before the newest existing entry
    if idx == -1:
        new = (content.rstrip("\n") + "\n\n" + block) if content.strip() else block
    else:
        new = content[:idx + 1] + block + content[idx + 1:]
    _ensure_parent(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new)
    os.replace(tmp, path)
    return True


# ---------- engine prediction (gate-verdict, projected from closing_candidates) ----------

def _parse_grid(grid: str) -> tuple[int, int]:
    """Parse a 'MxN' grid string into (m, n) ints. I/O: ('6x5') -> (6, 5)."""
    m, n = grid.lower().split("x")
    return int(m), int(n)


def _predicted_trace_for(rec: dict, *, allow_non_corner: bool = False):
    """Look up the engine trace for a finding by enumerating closing candidates and matching on the
    normalized canonicalHash. Lazily imports tests/enginelib so the runtime module has NO test-only
    top-level dependency (the import fires only when engine prediction is actually requested) and so a
    bare `python py/findings.py submit` works without conftest's sys.path setup.
    I/O: (rec) -> {'foldable','failingGates','chains','matched'} | None (no candidate has that hash)."""
    import sys
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for d in (os.path.join(repo, "tests"), os.path.join(repo, "py")):   # enginelib, then search/twostack
        if d not in sys.path:
            sys.path.insert(0, d)
    from enginelib import predicted_trace  # lazy, test-helper
    m, n = _parse_grid(rec["grid"])
    return predicted_trace(m, n, rec["canonicalHash"], allow_non_corner=allow_non_corner)


def predict_finding(rec: dict, *, allow_non_corner: bool = False) -> dict:
    """Build the engine `predicted` block for a finding (gate-verdict, never a fold index).
    Returns {'foldable','failingGates','matched':True} when a candidate matches the hash, else
    {'matched': False} (valid schema but the hash exists in no enumerated candidate).
    I/O: (rec) -> predicted block dict."""
    trace = _predicted_trace_for(rec, allow_non_corner=allow_non_corner)
    if trace is None:
        return {"matched": False}
    return {"foldable": trace["foldable"], "failingGates": trace["failingGates"], "matched": True}


# ---------- submit (validate FIRST, then persist) ----------

def submit_record(rec: dict, *, db_path: str = DB_PATH, lab_log_path: str = LAB_LOG_PATH,
                  engine_predict: bool = True) -> dict:
    """Validate an in-memory FoldFinding, then upsert it into the DB and append a LAB_LOG entry.
    Validation runs FIRST: a malformed payload raises ValidationError and writes NOTHING. The stored
    record keys on the normalized canonicalHash (re-submit overwrites, never duplicates). With
    engine_predict=True the engine `predicted` block is filled (lazy enginelib enumeration). This is
    the one write path that the file/CLI submit() and the serve.py POST route both wrap.
    I/O: (rec, ...) -> the persisted (normalized) finding dict."""
    validate_finding(rec)                          # raise BEFORE any write
    rec = norm_finding(rec)                         # DB key = normalized canonical hash
    if engine_predict:
        rec["predicted"] = predict_finding(rec)
    save_db(upsert(load_db(db_path), rec), db_path)
    append_lab_log(rec, lab_log_path)
    return rec


def submit(path: str, *, db_path: str = DB_PATH, lab_log_path: str = LAB_LOG_PATH,
           engine_predict: bool = True) -> dict:
    """Read a FoldFinding JSON file and submit it (validate FIRST, then persist). Thin file wrapper
    over submit_record. I/O: (path, ...) -> the persisted (normalized) finding dict."""
    with open(path, encoding="utf-8") as f:
        rec = json.load(f)
    return submit_record(rec, db_path=db_path, lab_log_path=lab_log_path, engine_predict=engine_predict)


# ---------- migration (twoplus1_labels.json -> FoldFinding DB, lossless) ----------

def migrate_record(old: dict, *, date: str, by: str = "(migrated)") -> dict:
    """Map one legacy twoplus1_labels record to a FoldFinding (lossless).
    Identity + verdict + notes are PRESERVED verbatim; the legacy shape/orient/K land in `observed`;
    canonicalHash is kept byte-identical (lookups normalize on read). I/O: (old, date, by) -> FoldFinding."""
    return {
        "grid": old["grid"],
        "id": old["id"],
        "canonicalHash": old["canonicalHash"],         # byte-identical, not normalized (lossless)
        "foldable": old.get("foldable"),
        "observed": {k: old[k] for k in ("shape", "orient", "K") if k in old},
        "by": by,
        "date": date,
        "notes": old.get("notes", ""),
    }


def migrate(old_list: list[dict], *, date: str, by: str = "(migrated)") -> list[dict]:
    """Migrate a list of legacy records to validated FoldFindings (raises if any result is malformed).
    I/O: (old_list, date, by) -> list[FoldFinding]."""
    out = [migrate_record(o, date=date, by=by) for o in old_list]
    for rec in out:
        validate_finding(rec)
    return out


# ---------- CLI ----------

def main(argv: list[str] | None = None) -> int:
    """CLI: `submit <file>` (validate+persist a finding) / `migrate <in.json> <out.json>` (lossless).
    I/O: (argv) -> exit code (0 ok)."""
    import datetime
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: findings.py submit <file> | migrate <in.json> <out.json>", file=sys.stderr)
        return 2
    cmd, rest = args[0], args[1:]
    if cmd == "submit" and len(rest) == 1:
        rec = submit(rest[0])
        print(f"submitted {rec['grid']}#{rec['id']} -> {DB_PATH} (predicted: {rec.get('predicted')})")
        return 0
    if cmd == "migrate" and len(rest) == 2:
        src, dst = rest
        with open(src, encoding="utf-8") as f:
            old = json.load(f)
        recs = migrate(old, date=datetime.date.today().isoformat())
        save_db(recs, dst)
        print(f"migrated {len(recs)} record(s): {src} -> {dst}")
        return 0
    print(f"bad args: {args}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
