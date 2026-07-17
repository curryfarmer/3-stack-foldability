"""migrate_canonical_hash.py — rewrite stored canonicalHash strings through the S3 fix.

S3 changed SquareLattice.canonical_hash to minimize over the sheet's AUTOMORPHISM subgroup
instead of all 8 of D4 (see square/lattice/square.py). On a non-square sheet the old minimum
could be attained at a transposing element, so the stored representative describes the fold on
the TRANSPOSED n x m sheet and can even sit off-grid. The dedup CLASSES are unchanged (a
sheet-covering fold's transposed image covers n x m and is never a legal m x n candidate, so for
m != n the two groups induce the same partition) -- only the representative moves. The map is
therefore a BIJECTION and this migration cannot lose or merge a record.

No search is needed. A stored hash IS the fold, serialized (fp cells + per-chain base + arrows),
so each record is migrated from its own string:

  1. Parse the hash back into a footprint + chains.
  2. Over-generate its D4 orbit. The ambient sheet of the stored representative is unknown (that
     is the bug), so images are generated under BOTH (m, n) and (n, m); wrong-ambient images are
     garbage that step 3 discards.
  3. Keep the images that are LEGAL on m x n: every chain replays through Fold.make_fold without
     leaving the grid (it returns None when a fold would), and the chains together cover the sheet
     exactly -- which is precisely the engine's own admission rule (search.search_chains only
     emits a candidate when len(reserved) == m * n).
  4. new = canonical_hash(any legal image) -- valid because every legal image is in one Aut-orbit.

Every step is checked and any violation is a STOP, never a skip:
  * at least one legal image exists (else the stored hash is not a fold on its own grid);
  * _hash_over(ALL8, legal image) == the stored hash (round-trips the reconstruction);
  * every legal image yields the SAME new hash (confirms the single-Aut-orbit claim per record);
  * no two records collide on (grid, norm_hash) afterwards -- records.append_square_finding dedups
    on that key, and its meaning shifts for non-square grids;
  * square grids (Aut == D4) come back byte-identical -- a built-in control group.

Usage:
  python scripts/migrate_canonical_hash.py            # dry-run: report the map, write nothing
  python scripts/migrate_canonical_hash.py --apply    # rewrite in place (back up first)
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "square"))
import _bootstrap  # noqa: E402,F401

import fold as Fold  # noqa: E402
from generate import make_uid  # noqa: E402
from lattice.square import SquareLattice as SL  # noqa: E402

FINDINGS = os.path.join(_ROOT, "results", "foldfindings.json")
TO_TEST = os.path.join(_ROOT, "results", "to_test_folds.json")
SNAPSHOT = os.path.join(_ROOT, "square", "tests", "fixtures", "foldfindings_snapshot.json")
# gen_golden.probe_deciders matches these hashes against the vet goldens' hashes; regenerating the
# goldens without migrating this leaves every non-square decider silently "not in any vet golden set".
LABELS = os.path.join(_ROOT, "square", "tests", "fixtures", "twoplus1_labels.json")
UID_MAP_OUT = os.path.join(_ROOT, "results", "s3_uid_map.json")

# NOT migrated, deliberately: square/tests/fixtures/{6x4_bbc04a7f,6x5_c25f38f8}.json. They are
# frozen bundles from earlier, separately-dated engine runs, and test_manifest_counts anchors on
# their solution COUNTS (which this change does not move) and never reads their hashes. Rewriting
# them with today's engine would erode the independence that makes them a cross-check.

ALL8 = tuple({"rot": r, "flip": f} for r in range(4) for f in range(2))


class Stop(Exception):
    """A migration invariant was violated. Never routed around."""


# ---------- hash <-> config ----------

def norm_hash(s: str) -> str:
    """Key-order-independent normal form. Identical to records.norm_hash / validate_square._norm_hash."""
    return json.dumps(json.loads(s), sort_keys=True, separators=(",", ":"))


def parse(h: str):
    """Serialized canonical form -> (footprint, chains) in the engine's internal shape."""
    d = json.loads(h)
    fp = {"cells": [tuple(c) for c in d["fp"]]}
    chains = [{"kind": c["kind"],
               "baseCells": [tuple(b) for b in c["base"]],
               "foldArrows": list(c["arrows"])} for c in d["chains"]]
    return fp, chains


def _image(t, fp, chains, a, b):
    """Apply one D4 element under ambient (a, b). Wrong ambient -> garbage, filtered by _is_legal."""
    return (
        {"cells": [SL.apply_transform(t, c[0], c[1], a, b) for c in fp["cells"]]},
        [{"kind": c["kind"],
          "baseCells": [SL.apply_transform(t, x, y, a, b) for (x, y) in c["baseCells"]],
          "foldArrows": [SL.transform_arrow(t, d) for d in c["foldArrows"]]} for c in chains],
    )


def _is_legal(fp, chains, m, n) -> bool:
    """Is this configuration a real fold on the m x n sheet?

    Replays each chain the way the search built it and demands the same admission rule the engine
    uses: no fold leaves the grid, and the chains tile the sheet exactly."""
    if not all(0 <= x < m and 0 <= y < n for (x, y) in fp["cells"]):
        return False
    covered = []
    for c in chains:
        if not all(0 <= x < m and 0 <= y < n for (x, y) in c["baseCells"]):
            return False
        p = Fold.initial_placement(c["baseCells"])
        covered.extend(p["cells"])
        for d in c["foldArrows"]:
            p = Fold.make_fold(p, d, m, n)
            if p is None:                       # the fold left the grid
                return False
            covered.extend(p["cells"])
    if len(covered) != m * n:                   # overlap => short of m*n distinct cells
        return False
    return set(covered) == {(x, y) for x in range(m) for y in range(n)}


def migrate_hash(h: str, m: int, n: int) -> str:
    """Stored (all-of-D4) hash -> the automorphism-subgroup hash of the same fold. STOPs on doubt."""
    fp, chains = parse(h)
    legal = []
    seen = set()
    ambients = {(m, n), (n, m)}
    for (a, b) in ambients:
        for t in ALL8:
            f2, c2 = _image(t, fp, chains, a, b)
            key = SL._hash_over([{"rot": 0, "flip": 0}], f2, c2, m, n)  # identity sig = config id
            if key in seen:
                continue
            seen.add(key)
            if _is_legal(f2, c2, m, n):
                legal.append((f2, c2))

    if not legal:
        raise Stop(f"{m}x{n}: no image of the stored hash is a legal fold on its own grid: {h[:90]}")

    news = {SL.canonical_hash(f2, c2, m, n) for (f2, c2) in legal}
    if len(news) != 1:
        raise Stop(f"{m}x{n}: legal images span {len(news)} Aut-orbits (expected 1): {h[:90]}")

    # The stored string must be one of the recovered fold's own D4 images -- i.e. the parse and the
    # arrow/coord transforms round-trip. Compared through norm_hash because 61 of the 70 stored
    # strings serialize "chains" before "fp": an artifact of an older serializer, not a content
    # difference (scripts/validate_square.py:20-28). The passing oracle already proves the two key
    # orders select the SAME orbit member, so this is a content check, not a byte check.
    f0, c0 = legal[0]
    orbit = {norm_hash(SL._hash_over([t], f0, c0, m, n)) for t in ALL8}
    if norm_hash(h) not in orbit:
        raise Stop(f"{m}x{n}: reconstruction does not round-trip to the stored hash: {h[:90]}")

    new = news.pop()
    # Rewrite ONLY what actually changed. make_uid hashes this exact string, so re-serializing a
    # content-identical hash would churn its uid for nothing (and would silently drag every square
    # grid along, destroying the control group).
    return h if norm_hash(new) == norm_hash(h) else new


# ---------- file migration ----------

def _load(path):
    with open(path) as f:
        return json.load(f)


def _detect_newline(path):
    """Sniff a file's line-ending style from its raw bytes. I/O: (path) -> '\\r\\n' or '\\n'."""
    with open(path, "rb") as f:
        return "\r\n" if b"\r\n" in f.read() else "\n"


def _dump(path, obj):
    """Write in the file's existing on-disk format: indent=2, no trailing newline, and the file's
    OWN line endings preserved (platform default for a not-yet-existing output file, matching the
    old text-mode behaviour). _assert_format_fidelity proves this reproduces each target
    byte-for-byte before we touch it, so the only diff this migration produces is the hashes it
    actually changed. I/O: (path, obj) -> None."""
    newline = _detect_newline(path) if os.path.exists(path) else os.linesep
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(obj, indent=2).replace("\n", newline))


def _assert_format_fidelity(path):
    """Load->dump must be a byte-identical no-op before we trust _dump with the ground truth.
    Checks against the file's ACTUAL line endings (never an assumed CRLF), so an LF checkout is
    validated instead of being permanently refused. I/O: (path) -> None (raises Stop on any reformat)."""
    with open(path, "rb") as f:
        original = f.read()
    newline = "\r\n" if b"\r\n" in original else "\n"
    reserialized = json.dumps(json.loads(original.decode("utf-8")), indent=2).replace("\n", newline)
    if reserialized.encode("utf-8") != original:
        raise Stop(f"{os.path.relpath(path, _ROOT)}: re-serializing would reformat the file; "
                   f"refusing to rewrite it")


def migrate_findings(path, apply_it, report):
    """results/foldfindings.json — 70 records, canonicalHash only, no geometry."""
    recs = _load(path)
    seen_keys = {}
    for r in recs:
        grid, h = r.get("grid"), r.get("canonicalHash")
        if not grid or not h:
            raise Stop(f"record id={r.get('id')} has no grid/canonicalHash")
        m, n = (int(v) for v in grid.split("x"))
        new = migrate_hash(h, m, n)
        if m == n and new != h:
            raise Stop(f"{grid} id={r.get('id')}: square grid must be byte-identical (Aut == D4 "
                       f"there, so the control group must not move)")
        key = (grid, norm_hash(new))
        if key in seen_keys:
            raise Stop(f"{grid}: records id={seen_keys[key]} and id={r.get('id')} collide "
                       f"on (grid, norm_hash) after migration")
        seen_keys[key] = r.get("id")
        report.note(grid, h, new, r.get("id"), m, n)
        r["canonicalHash"] = new
    if apply_it:
        _dump(path, recs)
    return len(recs)


def migrate_to_test(path, apply_it, report):
    """results/to_test_folds.json — 13 folds; carries footprint+chains, so it cross-checks itself."""
    doc = _load(path)
    folds = doc["folds"]
    for r in folds:
        grid, h = r["grid"], r["canonicalHash"]
        m, n = int(r["m"]), int(r["n"])
        if f"{m}x{n}" != grid:
            raise Stop(f"to_test: grid {grid} disagrees with m={m} n={n}")
        new = migrate_hash(h, m, n)

        # This file stores the fold's OWN geometry. Hash it directly and demand the hash-only path
        # agreed -- an independent witness that the reconstruction in migrate_hash is right.
        # This file stores cells as plain [x, y] pairs (not search._xy's {"x":,"y":} dicts).
        fp = {"cells": [tuple(c) for c in r["footprint"]["cells"]]}
        chains = [{"kind": c["kind"],
                   "baseCells": [tuple(b) for b in c["baseCells"]],
                   "foldArrows": list(c["foldArrows"])} for c in r["chains"]]
        # Compared through norm_hash throughout: migrate_hash deliberately returns the STORED bytes
        # when the content is unchanged, and the legacy key order makes raw == meaningless here.
        direct = SL.canonical_hash(fp, chains, m, n)
        if norm_hash(direct) != norm_hash(new):
            raise Stop(f"to_test {grid} id={r.get('id')}: hash-only migration disagrees with the "
                       f"stored geometry")
        # The stored hash must be SOME D4 image of the stored geometry -- the historic D4 minimum
        # before this migration runs, the Aut minimum after. Accepting the whole orbit keeps the
        # script idempotent (re-running it is a no-op) while still catching a genuine mismatch
        # between the hash and the geometry sitting next to it.
        orbit = {norm_hash(SL._hash_over([t], fp, chains, m, n)) for t in ALL8}
        if norm_hash(h) not in orbit:
            raise Stop(f"to_test {grid} id={r.get('id')}: stored canonicalHash is not any D4 image "
                       f"of the geometry stored alongside it")
        report.note(grid, h, new, r.get("id"), m, n, source="to_test")
        r["canonicalHash"] = new
        r["canonicalHashNorm"] = norm_hash(new)
    if apply_it:
        _dump(path, doc)
    return len(folds)


class Report:
    def __init__(self):
        self.rows = []      # (grid, old, new, id, m, n, source)

    def note(self, grid, old, new, rid, m, n, source="findings"):
        self.rows.append((grid, old, new, rid, m, n, source))

    def summarize(self):
        grids = {}
        for (grid, old, new, rid, m, n, src) in self.rows:
            g = grids.setdefault(grid, {"n": 0, "changed": 0, "square": m == n,
                                        "offgridOld": 0, "offgridNew": 0})
            g["n"] += 1
            if old != new:
                g["changed"] += 1
            for tag, h in (("offgridOld", old), ("offgridNew", new)):
                fp = json.loads(h)["fp"]
                if any(not (0 <= x < m and 0 <= y < n) for x, y in fp):
                    g[tag] += 1
        print("\n  grid   sq  records  reHashed  off-grid(old->new)")
        for grid in sorted(grids):
            g = grids[grid]
            print("  %-5s  %-3s %7d  %8d  %6d -> %d"
                  % (grid, "yes" if g["square"] else "no", g["n"], g["changed"],
                     g["offgridOld"], g["offgridNew"]))
        return grids

    def uid_map(self):
        out = {}
        for (grid, old, new, rid, m, n, src) in self.rows:
            if old == new:
                continue
            o, w = make_uid("square", m, n, old), make_uid("square", m, n, new)
            if o != w:
                out[o] = {"newUid": w, "grid": grid, "id": rid, "source": src}
        return out


def main():
    apply_it = "--apply" in sys.argv[1:]
    report = Report()

    print("S3 canonical-hash migration —", "APPLY (rewriting in place)" if apply_it else "DRY RUN")
    for path, fn in ((FINDINGS, migrate_findings), (LABELS, migrate_findings),
                     (TO_TEST, migrate_to_test)):
        if not os.path.exists(path):
            raise Stop(f"missing: {path}")
        _assert_format_fidelity(path)
        n = fn(path, apply_it, report)
        print(f"  {os.path.relpath(path, _ROOT)}: {n} records OK")

    report.summarize()
    uids = report.uid_map()
    print(f"\n  non-square uids changed: {len(uids)}")
    if apply_it:
        _dump(UID_MAP_OUT, uids)
        print(f"  wrote {os.path.relpath(UID_MAP_OUT, _ROOT)}")

        import shutil
        shutil.copyfile(FINDINGS, SNAPSHOT)
        print(f"  refreshed {os.path.relpath(SNAPSHOT, _ROOT)} (drift-guard)")
    else:
        print("\n  (dry run — nothing written; re-run with --apply)")


if __name__ == "__main__":
    try:
        main()
    except Stop as e:
        print(f"\nSTOP: {e}", file=sys.stderr)
        sys.exit(2)
