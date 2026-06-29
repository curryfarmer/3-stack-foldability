#!/usr/bin/env python3
"""reconcile_2plus1.py — read-only agreement report: physical ground truth vs the engine theory.

Answers three questions for 2+1, straight off the SQLite write-master:

  1. SURVIVOR CENSUS — per grid, how many 2+1 candidates survive the search's gates
     (exit+parity+reflection), and how the leading twist model (Model B) splits them (Tw=0 vs Tw!=0).
     The survivor count is exactly the set the web-app search shows.

  2. GROUND-TRUTH AGREEMENT — for every physically-folded pattern (finding.is_ground_truth=1),
     line up the PHYSICAL verdict against the THEORY: the three-gate verdict (is it a survivor?) and
     each twist model's prediction. Flags the two failure modes that matter:
       * gate-SURVIVOR that physically JAMS  -> the gates OVER-ACCEPT (a further gate is needed)
       * gate-FAILURE  that physically FOLDS -> a gate is TOO STRICT (over-rejects)

  3. CRITERION SCORECARD — score candidate predicates against all current ground truth:
       three-gate            = exit & parity & reflection
       three-gate + Model B  = exit & parity & reflection & (Model B Tw=0)
     Report TP/TN/FP/FN and every mismatch (by pattern_uid) so a predicate can be falsified.

  python py/reconcile_2plus1.py            # the live DB
  python py/reconcile_2plus1.py --test     # the scratch DB
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # py/ on path
import _bootstrap  # noqa: E402,F401  (puts every py/ subfolder + repo + tests on sys.path)

import store as Store            # noqa: E402

_W = {1: "FOLD", 0: "JAM", None: "untested"}


def _census(conn):
    """Per-grid 2+1 survivor census from the nc-2+1 runs (one row per distinct pattern_uid)."""
    return conn.execute("""
        SELECT r.m, r.n,
          COUNT(DISTINCT p.pattern_uid) AS total,
          COUNT(DISTINCT CASE WHEN p.exit_footprint=1 AND p.parity=1 AND p.reflection=1
                              THEN p.pattern_uid END) AS surv,
          COUNT(DISTINCT CASE WHEN p.exit_footprint=1 AND p.parity=1 AND p.reflection=1
                              AND tb.val_bool=1 THEN p.pattern_uid END) AS surv_tw0,
          COUNT(DISTINCT CASE WHEN p.exit_footprint=1 AND p.parity=1 AND p.reflection=1
                              AND tb.val_bool=0 THEN p.pattern_uid END) AS surv_twN
        FROM patterns p JOIN runs r ON r.id=p.run_id
        LEFT JOIN tag tb ON tb.norm_hash=p.norm_hash AND tb.key='modelB_pred'
        WHERE p.decomposition='2+1' AND r.label='nc-2+1'
        GROUP BY r.m, r.n ORDER BY r.m, r.n
    """).fetchall()


def _ground_truth(conn):
    """One row per physically-folded 2+1 pattern_uid: physical verdict + gate verdict + twist preds.
    Dedup across runs by pattern_uid (gate verdicts are anchor-independent, so MAX is exact)."""
    return conn.execute("""
        SELECT r.m, r.n, p.pattern_uid,
          f.foldable AS phys,
          MAX(p.exit_footprint) AS exit_fp, MAX(p.parity) AS parity, MAX(p.reflection) AS refl,
          MAX(CASE WHEN ta.key='modelA_pred' THEN ta.val_bool END) AS twA,
          MAX(CASE WHEN ta.key='modelB_pred' THEN ta.val_bool END) AS twB,
          MAX(CASE WHEN ta.key='modelC_pred' THEN ta.val_bool END) AS twC
        FROM finding f
        JOIN patterns p ON p.norm_hash = f.norm_hash
        JOIN runs r ON r.id = p.run_id
        LEFT JOIN tag ta ON ta.norm_hash = p.norm_hash AND ta.key IN
              ('modelA_pred','modelB_pred','modelC_pred')
        WHERE f.is_ground_truth=1 AND p.decomposition='2+1'
        GROUP BY p.pattern_uid
        ORDER BY r.m, r.n, p.pattern_uid
    """).fetchall()


def _score(rows, predicate):
    """TP/TN/FP/FN of a predicate(row)->bool|None against physical foldable. None pred = skipped.
    I/O: (rows, fn) -> (tp, tn, fp, fn, [mismatch rows])."""
    tp = tn = fpos = fneg = 0
    mism = []
    for r in rows:
        pred = predicate(r)
        if pred is None:
            continue
        phys = bool(r["phys"])
        if pred and phys:
            tp += 1
        elif not pred and not phys:
            tn += 1
        elif pred and not phys:
            fpos += 1; mism.append((r, "FP: predicate=FOLD, physical=JAM"))
        else:
            fneg += 1; mism.append((r, "FN: predicate=JAM, physical=FOLD"))
    return tp, tn, fpos, fneg, mism


def main(argv=None):
    p = argparse.ArgumentParser(description="2+1 physical-vs-theory agreement report (read-only).")
    p.add_argument("--db", metavar="PATH", help="DB path (default $FOLDDB_SQLITE or results/folddb.sqlite3)")
    p.add_argument("--test", action="store_true", help="read the scratch DB results/folddb.test.sqlite3")
    ns = p.parse_args(sys.argv[1:] if argv is None else argv)

    path = Store.resolve_db_path(ns.db, ns.test)
    conn = Store.connect(path)
    try:
        Store.init_schema(conn)

        print("=" * 72)
        print("1. SURVIVOR CENSUS  (2+1, non-corner; survivors = exit & parity & reflection)")
        print("=" * 72)
        print(f"  {'grid':>6} {'total':>6} {'surv':>6} {'surv·Tw=0':>10} {'surv·Tw≠0':>10}")
        for r in _census(conn):
            print(f"  {r['m']}x{r['n']:<4} {r['total']:>6} {r['surv']:>6} "
                  f"{r['surv_tw0']:>10} {r['surv_twN']:>10}")

        rows = _ground_truth(conn)
        print()
        print("=" * 72)
        print(f"2. GROUND-TRUTH AGREEMENT  ({len(rows)} physically-folded 2+1 pattern(s))")
        print("=" * 72)
        if not rows:
            print("  (no ground truth yet — ingest physical findings first)")
        else:
            print(f"  {'grid':>5} {'pattern_uid':>13} {'phys':>5} {'gate':>5} {'survivor?':>9} "
                  f"{'twA':>4} {'twB':>4} {'twC':>4}")
            over_accept, over_reject = [], []
            for r in rows:
                survivor = bool(r["exit_fp"] and r["parity"] and r["refl"])
                gate = "FOLD" if survivor else "JAM"
                phys = bool(r["phys"])
                tag = ""
                if survivor and not phys:
                    over_accept.append(r); tag = "  <- SURVIVOR JAMS (over-accept)"
                if (not survivor) and phys:
                    over_reject.append(r); tag = "  <- FAILURE FOLDS (over-reject)"
                tw = lambda v: {1: "0", 0: "≠0", None: "·"}[v]   # noqa: E731 (Model pass=Tw=0)
                print(f"  {r['m']}x{r['n']:<3} {r['pattern_uid']:>13} {_W[r['phys']]:>5} "
                      f"{gate:>5} {str(survivor):>9} {tw(r['twA']):>4} {tw(r['twB']):>4} "
                      f"{tw(r['twC']):>4}{tag}")
            print(f"\n  over-accept (survivor jams): {len(over_accept)}    "
                  f"over-reject (failure folds): {len(over_reject)}")

            print()
            print("=" * 72)
            print("3. CRITERION SCORECARD  (vs all current ground truth)")
            print("=" * 72)
            preds = {
                "three-gate (exit&parity&refl)":
                    lambda r: bool(r["exit_fp"] and r["parity"] and r["refl"]),
                "three-gate & Model B (Tw=0)":
                    lambda r: (None if r["twB"] is None
                               else bool(r["exit_fp"] and r["parity"] and r["refl"] and r["twB"])),
            }
            for name, fn in preds.items():
                tp, tn, fpos, fneg, mism = _score(rows, fn)
                ok = "PERFECT" if (fpos == 0 and fneg == 0) else f"{fpos+fneg} MISMATCH"
                print(f"\n  [{name}]  TP={tp} TN={tn} FP={fpos} FN={fneg}  -> {ok}")
                for r, why in mism:
                    print(f"      {r['m']}x{r['n']} {r['pattern_uid']}  {why}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
