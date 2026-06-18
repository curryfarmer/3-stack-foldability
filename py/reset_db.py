#!/usr/bin/env python3
"""reset_db.py — wipe the SQLite pattern DB back to its ground-truth findings (or fully).

The physical-verification reset: clears every run (cascading its patterns), every custom tag, and
every finding that is NOT ground truth, then VACUUMs — leaving only the physically-folded-with-verdict
findings (finding.is_ground_truth=1) to rebuild from. The pattern set is regenerable any time via
`generate.py --store-all`; the ground-truth findings are the irreplaceable record, so they survive by
default. Always prints a before->after row-count summary; --dry-run reports without writing.

  python py/reset_db.py --dry-run                 # preview the reset (writes nothing)
  python py/reset_db.py                            # reset the real DB, keep ground truths
  python py/reset_db.py --test                     # reset the scratch DB instead
  python py/reset_db.py --all                      # also delete findings (fully empty DB)
  python py/reset_db.py --export-findings [PATH]   # first dump findings -> JSON (a regenerable backup)

Tip: rehearse on the scratch DB first (`--test`), and back up the real DB by copying the .sqlite3 file.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import store as Store  # noqa: E402

_TABLES = ("runs", "patterns", "tag", "finding")


def counts(conn):
    """Row counts per table + the ground-truth subset. I/O: (conn) -> dict."""
    out = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in _TABLES}
    out["ground_truth"] = conn.execute(
        "SELECT COUNT(*) FROM finding WHERE COALESCE(is_ground_truth,0)=1").fetchone()[0]
    return out


def reset(conn, *, keep_ground_truth=True):
    """Delete runs (ON DELETE CASCADE clears patterns) + tags + (unless keep_ground_truth) findings.
    Keeps finding.is_ground_truth=1 rows when keep_ground_truth. Caller commits + VACUUMs.
    I/O: (conn, keep_ground_truth) -> None."""
    conn.execute("DELETE FROM runs")                       # CASCADE clears patterns
    conn.execute("DELETE FROM tag")
    if keep_ground_truth:
        conn.execute("DELETE FROM finding WHERE COALESCE(is_ground_truth,0)!=1")
    else:
        conn.execute("DELETE FROM finding")


def _summary(before, after_or_plan, *, dry, keep_gt):
    kept_findings = before["ground_truth"] if keep_gt else 0
    verb = "would delete" if dry else "deleted"
    lines = [
        f"  runs:     {before['runs']} -> {after_or_plan['runs']}  ({verb} {before['runs'] - after_or_plan['runs']})",
        f"  patterns: {before['patterns']} -> {after_or_plan['patterns']}  ({verb} {before['patterns'] - after_or_plan['patterns']})",
        f"  tags:     {before['tag']} -> {after_or_plan['tag']}  ({verb} {before['tag'] - after_or_plan['tag']})",
        f"  findings: {before['finding']} -> {after_or_plan['finding']}  "
        f"(kept {kept_findings} ground-truth, {verb} {before['finding'] - after_or_plan['finding']})",
    ]
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Reset the SQLite pattern DB to its ground-truth findings (or fully).")
    p.add_argument("--db", metavar="PATH", help="DB path (default $FOLDDB_SQLITE or results/folddb.sqlite3)")
    p.add_argument("--test", action="store_true", help="reset the scratch DB results/folddb.test.sqlite3")
    p.add_argument("--dry-run", action="store_true", help="report what would change; write nothing")
    p.add_argument("--all", action="store_true",
                   help="also delete findings (default keeps ground-truth findings)")
    p.add_argument("--export-findings", metavar="PATH", nargs="?", const="",
                   help="dump findings to a JSON backup before resetting (default results/foldfindings.json)")
    ns = p.parse_args(sys.argv[1:] if argv is None else argv)

    path = Store.resolve_db_path(ns.db, ns.test)
    if not os.path.exists(path):
        print(f"no DB at {path} — nothing to reset", file=sys.stderr)
        return 1

    conn = Store.connect(path)
    try:
        Store.init_schema(conn)
        before = counts(conn)
        keep_gt = not ns.all

        if ns.export_findings is not None:                 # flag present (with or without a PATH)
            if ns.dry_run:                                 # dry-run writes NOTHING — not even the backup
                print("(--export-findings skipped under --dry-run; re-run without --dry-run to export)")
            else:
                outp = Store.export_findings(conn, ns.export_findings or None)
                print(f"exported {before['finding']} finding(s) -> {outp}")

        if ns.dry_run:
            plan = {"runs": 0, "patterns": 0, "tag": 0,
                    "finding": before["ground_truth"] if keep_gt else 0,
                    "ground_truth": before["ground_truth"] if keep_gt else 0}
            print(f"DRY RUN — reset of {path} (keep_ground_truth={keep_gt}):")
            print(_summary(before, plan, dry=True, keep_gt=keep_gt))
            return 0

        reset(conn, keep_ground_truth=keep_gt)
        conn.commit()
        conn.execute("VACUUM")                             # reclaim space (outside any transaction)
        after = counts(conn)
        print(f"reset {path} (keep_ground_truth={keep_gt}):")
        print(_summary(before, after, dry=False, keep_gt=keep_gt))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
