"""status.py — summarize the physical-testing state: what's tested, per-grid agreement, and (if a
batch is named) how much of that batch is still pending a hand-fold.

This is a fast, read-only DB summary (it does NOT re-run the engine — that's `phystest check`)."""
import os
from collections import defaultdict

import records as R


def db_summary():
    findings = R.load_square_findings()
    tested = [r for r in findings if r.get("foldable") is not None]
    per_grid = defaultdict(lambda: {"tested": 0, "fold": 0, "jam": 0,
                                    "predAgree": 0, "predKnown": 0})
    for r in tested:
        g = per_grid[r.get("grid", "?")]
        g["tested"] += 1
        g["fold" if r["foldable"] else "jam"] += 1
        pred = (r.get("predicted") or {}).get("foldable")
        if pred is not None:
            g["predKnown"] += 1
            if bool(pred) == bool(r["foldable"]):
                g["predAgree"] += 1
    return {"totalTested": len(tested), "perGrid": dict(per_grid),
            "dbPresent": os.path.isfile(R.FOLDFINDINGS_PATH)}


def batch_summary(batch_dir):
    manifest = R.load_batch(batch_dir)
    items = manifest["items"]
    pending = [it for it in items if (it.get("actual") or {}).get("folded") is None]
    return {"grid": manifest.get("grid"), "policy": manifest.get("policy"),
            "queued": len(items), "pending": len(pending), "logged": len(items) - len(pending)}


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="phystest status",
                                 description="summarize physical-testing state")
    ap.add_argument("--batch", default=None, help="also summarize this batch directory")
    args = ap.parse_args(argv)

    s = db_summary()
    if not s["dbPresent"]:
        print("findings DB absent (results/foldfindings.json) -- nothing physically tested yet")
    else:
        print("physically tested: %d record(s)" % s["totalTested"])
        for grid in sorted(s["perGrid"]):
            g = s["perGrid"][grid]
            agree = ("%d/%d" % (g["predAgree"], g["predKnown"])) if g["predKnown"] else "n/a"
            print("  %-6s tested=%-3d  fold=%-3d jam=%-3d  engine-agreement=%s"
                  % (grid, g["tested"], g["fold"], g["jam"], agree))
    if args.batch:
        b = batch_summary(args.batch)
        print("batch %s  grid=%s policy=%s  queued=%d  logged=%d  PENDING=%d"
              % (args.batch, b["grid"], b["policy"], b["queued"], b["logged"], b["pending"]))
    return 0
