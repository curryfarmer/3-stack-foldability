#!/usr/bin/env python3
"""compute_twist_models.py — backfill the 2+1 twist-model ENGINE predictions across the DB.

The 2+1 "twist" gate is undecided in the shipped engine (search ships twist=NULL for 2+1). This
re-runnable layer recomputes every registered hypothesis (py/twist_models.MODELS — Model A/B/C, and
any added later) on each stored 2+1 solution and writes the verdict as a '<model>_pred' tag row
(provenance='engine'): pass in val_bool, raw twist (rounded) in val_int, the partial-decomp class in
val_text, and a 'v=<source-hash>' stamp in notes. Those sit beside the user's '<model>_actual'
observations so the viewer agree columns + the model_compare view surface engine-vs-reality mismatches.

It is idempotent (UPSERT on (norm_hash, key)) and registry-driven — ADD a hypothesis (edit
twist_models.MODELS) or CHANGE one (edit its fn) and re-run; rows + version stamps overwrite. --prune
drops '<model>_pred' rows for hypotheses no longer in the registry.

  python py/compute_twist_models.py                 # gate-valid 2+1 across every run (the default)
  python py/compute_twist_models.py --verbose        # also print tw/class per pattern
  python py/compute_twist_models.py --all-2plus1     # every 2+1, not just the gate-valid subset
  python py/compute_twist_models.py --run 12          # restrict to one run id
  python py/compute_twist_models.py --prune           # also drop preds for removed hypotheses
  python py/compute_twist_models.py --dry-run         # compute + report; write nothing
  python py/compute_twist_models.py --test            # operate on the scratch DB

"Gate-valid" = a 2+1 fold whose every DECIDED gate passes (arithmetic, exit_footprint, parity,
vector_parity, reflection) — so the only open question is the twist. --all-2plus1 drops that filter.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # py/ on path
import _bootstrap  # noqa: E402,F401  (puts every py/ subfolder + repo + tests on sys.path)

import store as Store        # noqa: E402
import twist_models          # noqa: E402

# The DECIDED gates a "gate-valid" 2+1 must all pass (twist is the only one left open).
_GATE_VALID = ("arithmetic", "exit_footprint", "parity", "vector_parity", "reflection")


def _scope_sql(run_id=None, all_2plus1=False):
    """Build the patterns SELECT + params for the chosen scope. I/O: (...) -> (sql, params)."""
    where = ["p.decomposition = '2+1'"]
    params = []
    if not all_2plus1:
        where += [f"p.{g} = 1" for g in _GATE_VALID]
    if run_id is not None:
        where.append("p.run_id = ?")
        params.append(run_id)
    sql = ("SELECT p.id, p.pattern_uid, p.norm_hash, p.detail_json, r.m, r.n "
           "FROM patterns p JOIN runs r ON r.id = p.run_id "
           "WHERE " + " AND ".join(where))
    return sql, params


def prune_stale(conn, *, dry=False):
    """Delete '<model>_pred' tag rows whose model is no longer in the registry. I/O: (conn, dry) -> dict
    {removed_keys: [...], rows: n}. Caller commits (no-op under dry)."""
    keep = {f"{k}_pred" for k in twist_models.MODELS}
    rows = conn.execute(
        "SELECT key, COUNT(*) AS n FROM tag WHERE substr(key, -5) = '_pred' GROUP BY key").fetchall()
    stale = {r["key"]: r["n"] for r in rows if r["key"] not in keep}
    if stale and not dry:
        conn.executemany("DELETE FROM tag WHERE key = ?", [(k,) for k in stale])
    return {"removed_keys": sorted(stale), "rows": sum(stale.values())}


def backfill(conn, *, run_id=None, all_2plus1=False, dry=False, verbose=False):
    """Recompute every registered model on each in-scope 2+1 pattern and UPSERT its '<model>_pred' tag.
    A pattern whose chains replay off-grid (or whose detail_json is corrupt) is skipped + counted, never
    silent. Batches all writes under one transaction (committed once, unless dry). I/O: (...) -> dict."""
    versions = {k: twist_models.model_version(k) for k in twist_models.MODELS}
    sql, params = _scope_sql(run_id, all_2plus1)
    patterns = conn.execute(sql, params).fetchall()

    computed = 0          # patterns successfully run
    written = 0           # pred tag rows upserted (computed * n_models, sans dry)
    skipped = []          # (pattern_uid, reason)
    for row in patterns:
        try:
            sol = json.loads(row["detail_json"])
            res = twist_models.compute_all(sol, row["m"], row["n"])
        except Exception as e:                                 # corrupt blob / off-grid replay / model bug
            skipped.append((row["pattern_uid"], f"{type(e).__name__}: {e}"))
            continue
        computed += 1
        if verbose:
            bits = " ".join(f"{k}={'P' if v['pass'] else 'F'}(tw={v['tw']}"
                            + (f",{v['class']}" if v["class"] else "") + ")"
                            for k, v in res.items())
            print(f"  {row['pattern_uid']} {row['m']}x{row['n']}  {bits}")
        if dry:
            continue
        for k, v in res.items():
            Store.upsert_engine_pred(conn, row["norm_hash"], f"{k}_pred", v["pass"],
                                     tw=v["tw"], cls=v["class"], version=versions[k], commit=False)
            written += 1
    if not dry:
        conn.commit()
    return {"scanned": len(patterns), "computed": computed, "written": written,
            "skipped": skipped, "versions": versions}


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Backfill 2+1 twist-model engine predictions (<model>_pred tags) across the DB.")
    p.add_argument("--db", metavar="PATH", help="DB path (default $FOLDDB_SQLITE or results/folddb.sqlite3)")
    p.add_argument("--test", action="store_true", help="operate on the scratch DB results/folddb.test.sqlite3")
    p.add_argument("--run", type=int, metavar="ID", help="restrict to one run id")
    p.add_argument("--all-2plus1", action="store_true",
                   help="every 2+1 pattern, not just the gate-valid subset")
    p.add_argument("--prune", action="store_true",
                   help="also drop <model>_pred rows for hypotheses no longer in the registry")
    p.add_argument("--dry-run", action="store_true", help="compute + report; write nothing")
    p.add_argument("--verbose", action="store_true", help="print each pattern's per-model verdict")
    ns = p.parse_args(sys.argv[1:] if argv is None else argv)

    path = Store.resolve_db_path(ns.db, ns.test)
    if not os.path.exists(path):
        print(f"no DB at {path} — generate patterns first (generate.py --store-all)", file=sys.stderr)
        return 1

    conn = Store.connect(path)
    try:
        Store.init_schema(conn)

        models = ", ".join(f"{k} (v{v})" for k, v in
                           ((k, twist_models.model_version(k)) for k in twist_models.MODELS))
        scope = "every 2+1" if ns.all_2plus1 else "gate-valid 2+1"
        if ns.run is not None:
            scope += f" in run {ns.run}"
        print(f"{'DRY RUN — ' if ns.dry_run else ''}backfill of {path}")
        print(f"  scope:  {scope}")
        print(f"  models: {models}")

        if ns.prune:
            pr = prune_stale(conn, dry=ns.dry_run)
            if not ns.dry_run:
                conn.commit()
            verb = "would prune" if ns.dry_run else "pruned"
            if pr["removed_keys"]:
                print(f"  {verb} {pr['rows']} stale pred row(s): {', '.join(pr['removed_keys'])}")
            else:
                print(f"  {verb} 0 stale pred rows (registry matches DB)")

        r = backfill(conn, run_id=ns.run, all_2plus1=ns.all_2plus1,
                     dry=ns.dry_run, verbose=ns.verbose)

        verb = "would write" if ns.dry_run else "wrote"
        print(f"  scanned {r['scanned']} pattern(s); computed {r['computed']}; "
              f"{verb} {r['computed'] * len(r['versions'])} pred tag(s)")
        if r["skipped"]:
            print(f"  skipped {len(r['skipped'])} (could not compute):")
            for uid, reason in r["skipped"][:10]:
                print(f"    {uid}: {reason}")
            if len(r["skipped"]) > 10:
                print(f"    ... and {len(r['skipped']) - 10} more")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
