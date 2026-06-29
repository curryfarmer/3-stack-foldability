"""fold_class.py — derive a grid-agnostic symmetry-equivalence label for fold patterns.

`canonical_hash` already dedups the D4 grid symmetries WITHIN a fixed m x n grid, but two patterns
that are the SAME physical fold can still land in different rows when they differ by:
  * transpose         (x<->y; a 6x8 pattern and its 8x6 image are stored under different grids/uids;
                       canonical_hash's internal transforms do not reliably reach this when m != n), or
  * time-reversal     (fold the strip the other way: reverse each chain's fold sequence and swap the
                       start/end footprint — same creases, opposite traversal; flips the twist sign).

`fold_class` collapses those: it is sha1(min over the orbit { fwd, time-reversed } x { id, transpose }
of the canonical_hash)[:12]. Equal fold_class  <=>  same fold up to D4 x transpose x time-reversal.

It is a NON-DESTRUCTIVE label: written as an EAV `fold_class` tag (val_text), it touches no pattern
row, uid, finding, or canonical_hash. The viewer uses it only to optionally collapse symmetry twins.

CLI:  python py/fold_class.py [--db PATH] [--all] [--decomp 2+1] [--run N] [--dry-run]
  Default scope is every distinct norm_hash with a stored detail blob (the tag PK is norm_hash, so one
  compute per distinct pattern suffices). --decomp / --run narrow it; --dry-run computes + reports
  without writing.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # py/ on path
import _bootstrap  # noqa: E402,F401  (puts every py/ subfolder + repo + tests on sys.path)

import fold as Fold                              # noqa: E402
import search as Search                          # noqa: E402
import store as Store                            # noqa: E402
from lattice.square import SquareLattice as SL   # noqa: E402

# The single diagonal reflection (x,y) -> (y,x); the other diagonal is this composed with rot180,
# which canonical_hash DOES reach internally, so one explicit transpose orientation suffices.
_TRANSPOSE = {"rot": 1, "flip": 1}


def _cells_set(cells):
    return sorted((c[0], c[1]) for c in cells)


def _replay(base, arrows, m, n):
    """Base placement + one per fold. base/arrows from a stored chain. Raises if it leaves the grid."""
    pl = Fold.initial_placement([(b[0], b[1]) for b in base])
    placements = [pl]
    for d in arrows:
        pl = Fold.make_fold(pl, d, m, n)
        if pl is None:
            raise ValueError("fold left grid")
        placements.append(pl)
    return placements


def _reverse_chain(base, arrows, m, n):
    """Time-reverse one chain: new base = its final placement, new arrows = the fold directions that
    walk the placements backwards. Found by replay (always valid on a real stored chain), so we never
    replay a transformed/relabelled chain (transform_arrow is not replay-equivariant). Raises if a
    reverse direction cannot be found. I/O: (base, arrows, m, n) -> (new_base_cells, new_arrows)."""
    placements = _replay(base, arrows, m, n)
    rev = []
    for k in range(len(placements) - 1, 0, -1):
        cur = placements[k]
        want = _cells_set(placements[k - 1]["cells"])
        found = None
        for d in "LRUD":
            nxt = Fold.make_fold(cur, d, m, n)
            if nxt is not None and _cells_set(nxt["cells"]) == want:
                found = d
                break
        if found is None:
            raise ValueError("no reverse direction at step %d" % k)
        rev.append(found)
    return list(placements[-1]["cells"]), rev


def _canon(fp_cells, chains, m, n):
    """Normalized canonical_hash string (D4-min within the grid) for a (footprint, chains) pair."""
    raw = Search.canonical_hash({"cells": fp_cells}, chains, m, n)
    return json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":"))


def _time_reverse(fp_cells, chains, m, n):
    """Whole-pattern time reversal (per-chain reverse; footprint = union of the new base cells)."""
    new_chains, new_fp = [], []
    for c in chains:
        nb, na = _reverse_chain(c["baseCells"], c["foldArrows"], m, n)
        new_chains.append({"kind": c["kind"], "baseCells": nb, "foldArrows": na})
        new_fp += list(nb)
    return new_fp, new_chains


def _transpose(fp_cells, chains, m, n):
    """Relabel a pattern under the diagonal reflection (no replay). Result lives in the (n, m) grid."""
    tf = [SL.apply_transform(_TRANSPOSE, x, y, m, n) for (x, y) in fp_cells]
    tc = [{"kind": c["kind"],
           "baseCells": [SL.apply_transform(_TRANSPOSE, b[0], b[1], m, n) for b in c["baseCells"]],
           "foldArrows": [SL.transform_arrow(_TRANSPOSE, a) for a in c["foldArrows"]]}
          for c in chains]
    return tf, tc


def fold_class_key(fp_cells, chains, m, n):
    """The 12-hex symmetry-equivalence id. fp_cells: list of (x,y); chains: dicts with tuple baseCells
    + foldArrows. min over { fwd, time-reversed } x { id, transpose }; transpose applied AFTER reversal
    (relabel only) so no transformed chain is ever replayed. Falls back to {fwd, transpose(fwd)} if the
    time-reversal cannot be computed. I/O: (fp_cells, chains, m, n) -> 12-hex str."""
    variants = [_canon(fp_cells, chains, m, n)]
    tf, tc = _transpose(fp_cells, chains, m, n)
    variants.append(_canon(tf, tc, n, m))
    try:
        rf, rc = _time_reverse(fp_cells, chains, m, n)
        variants.append(_canon(rf, rc, m, n))
        trf, trc = _transpose(rf, rc, m, n)
        variants.append(_canon(trf, trc, n, m))
    except ValueError:
        pass                                       # reversal unavailable -> D4 x transpose only
    return hashlib.sha1(min(variants).encode()).hexdigest()[:12]


def fold_class_of_sol(sol, m, n):
    """fold_class for a stored solution blob (footprint.cells + chains with {x,y} baseCells)."""
    fp = [(c["x"], c["y"]) for c in sol["footprint"]["cells"]]
    chains = [{"kind": c["kind"],
               "baseCells": [(b["x"], b["y"]) for b in c["baseCells"]],
               "foldArrows": list(c["foldArrows"])}
              for c in sol["chains"]]
    return fold_class_key(fp, chains, m, n)


def _upsert(conn, norm_hash, fc, date):
    conn.execute(
        "INSERT INTO tag(norm_hash,key,val_text,provenance,by_who,date) VALUES(?,?,?,?,?,?) "
        "ON CONFLICT(norm_hash,key) DO UPDATE SET val_text=excluded.val_text,"
        "provenance=excluded.provenance,by_who=excluded.by_who,date=excluded.date",
        (norm_hash, "fold_class", fc, "derived", "fold_class.py", date))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Backfill the fold_class symmetry-equivalence tag.")
    ap.add_argument("--db", default=None, help="SQLite path (default: the real folddb.sqlite3)")
    ap.add_argument("--all", action="store_true", help="(default behaviour) every distinct pattern")
    ap.add_argument("--decomp", default=None, help="restrict to a decomposition, e.g. 2+1")
    ap.add_argument("--run", type=int, default=None, help="restrict to one run_id")
    ap.add_argument("--dry-run", action="store_true", help="compute + report, write nothing")
    args = ap.parse_args(argv)

    conn = Store.connect(args.db)
    try:
        where = ["p.detail_json IS NOT NULL", "p.detail_json != ''"]
        params = []
        if args.decomp:
            where.append("p.decomposition=?"); params.append(args.decomp)
        if args.run is not None:
            where.append("p.run_id=?"); params.append(args.run)
        # one representative row per distinct norm_hash (the tag PK) — MIN(id) is deterministic.
        sql = ("SELECT p.norm_hash, p.detail_json, r.m AS m, r.n AS n "
               "FROM patterns p JOIN runs r ON r.id=p.run_id "
               "WHERE " + " AND ".join(where) +
               " GROUP BY p.norm_hash HAVING p.id=MIN(p.id)")
        rows = conn.execute(sql, params).fetchall()

        date = datetime.datetime.now().isoformat(timespec="seconds")
        n_ok = n_err = 0
        classes = set()
        for r in rows:
            try:
                sol = json.loads(r["detail_json"])
                fc = fold_class_of_sol(sol, r["m"], r["n"])
            except Exception as e:                 # noqa: BLE001 — skip a bad blob, keep going
                n_err += 1
                continue
            classes.add(fc)
            n_ok += 1
            if not args.dry_run:
                _upsert(conn, r["norm_hash"], fc, date)
        if not args.dry_run:
            conn.commit()

        verb = "would tag" if args.dry_run else "tagged"
        print(f"fold_class: {verb} {n_ok} distinct patterns into {len(classes)} classes "
              f"({n_err} skipped).")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
