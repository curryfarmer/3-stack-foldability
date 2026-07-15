"""records.py — physical-test record schema + findings-DB read/write.

The unified in-memory record is `physical-test/1` (see docs/schema/physical-test-1.md). On disk the
SQUARE ground truth lives in results/foldfindings.json in its own historical shape, which
scripts/validate_square.py reads directly — so this module maps to/from that shape rather than
inventing a parallel store the checker would ignore. Triangle ground truth lives as `tri-fold/1`
records under report/tri/**/folds/ and is read (never written here) by scripts/validate_triangle.py.
"""
import json
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FOLDFINDINGS_PATH = os.path.join(_REPO_ROOT, "results", "foldfindings.json")


def repo_root():
    return _REPO_ROOT


def norm_hash(canonical_hash_str):
    """Key-order-independent normal form of a canonicalHash JSON string. Identical to the
    normalization scripts/validate_square.py uses, so a hash curated here matches the checker's."""
    return json.dumps(json.loads(canonical_hash_str), sort_keys=True, separators=(",", ":"))


# ---------- square findings DB (results/foldfindings.json) ----------

def load_square_findings():
    """The raw foldfindings.json list (its native schema), or [] if the gitignored file is absent."""
    if not os.path.isfile(FOLDFINDINGS_PATH):
        return []
    with open(FOLDFINDINGS_PATH, encoding="utf-8") as f:
        return json.load(f)


def tested_square_index():
    """{normalized-canonicalHash: record} for every square finding that carries a PHYSICAL outcome
    (foldable is not None). Used by curate to skip already-folded candidates and by status."""
    out = {}
    for r in load_square_findings():
        if r.get("foldable") is None or "canonicalHash" not in r:
            continue
        try:
            out[norm_hash(r["canonicalHash"])] = r
        except (ValueError, KeyError):
            continue
    return out


def append_square_finding(*, grid, canonical_hash, folded, by, date, notes="",
                          predicted=None, provenance="physical"):
    """Append one physically-observed square outcome to foldfindings.json in its native schema
    (the schema scripts/validate_square.py reads). Refuses to double-log the same (grid, hash);
    returns (record, created: bool). Creates results/ + the file if missing."""
    findings = load_square_findings()
    key = norm_hash(canonical_hash)
    for r in findings:
        if r.get("grid") == grid and "canonicalHash" in r and norm_hash(r["canonicalHash"]) == key:
            return r, False  # already recorded — never silently overwrite a physical outcome
    next_id = 1 + max((r.get("id", 0) for r in findings), default=0)
    rec = {
        "grid": grid,
        "id": next_id,
        "canonicalHash": canonical_hash,
        "foldable": bool(folded),
        "by": by,
        "date": date,
        "provenance": provenance,
        "notes": notes,
    }
    if predicted is not None:
        rec["predicted"] = predicted
    findings.append(rec)
    os.makedirs(os.path.dirname(FOLDFINDINGS_PATH), exist_ok=True)
    with open(FOLDFINDINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(findings, f, indent=1)
    return rec, True


# ---------- physical-test/1 records + batch manifest ----------

def physical_record_from_bundle(bundle, foldsheet_rel):
    """Build a blank physical-test/1 record (actual.folded = None) from an engine <uid>.json bundle.
    Carries the engine's PREDICTION so log/status/check can compare it to the eventual outcome."""
    verdict = bundle.get("verdict", {})
    predicted_foldable = verdict.get("twist")  # True / False / None(undecided) for the square engine
    failing = [g for g in ("arithmetic", "exitFootprint", "parity", "reflection")
               if verdict.get(g) is False]
    return {
        "schema": "physical-test/1",
        "tiling": bundle.get("lattice", bundle.get("tiling", "square")),
        "grid": "%sx%s" % (bundle.get("m"), bundle.get("n")) if bundle.get("m") else bundle.get("grid"),
        "gridFile": None,  # reserved for arbitrary-sheet fold-grid/1 inputs
        "uid": bundle.get("uid"),
        "canonicalHash": bundle.get("canonicalHash"),
        "decomp": bundle.get("decomposition", bundle.get("decomp")),
        "stacks": bundle.get("stacks"),
        "predicted": {"foldable": predicted_foldable, "failingGates": failing, "source": "engine"},
        "actual": {"folded": None, "by": None, "date": None, "notes": ""},
        "foldsheet": foldsheet_rel,
    }


def load_batch(batch_dir):
    path = os.path.join(batch_dir, "batch.json")
    if not os.path.isfile(path):
        raise FileNotFoundError("no batch.json in %s" % batch_dir)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_batch(batch_dir, manifest):
    os.makedirs(batch_dir, exist_ok=True)
    with open(os.path.join(batch_dir, "batch.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
