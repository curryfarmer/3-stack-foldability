"""logresult.py — record a physical FOLD/JAM outcome for a curated batch item.

Marks the item in the batch manifest AND appends the outcome to the square findings DB
(results/foldfindings.json) in the exact schema scripts/validate_square.py reads — so the very next
`phystest check` re-derives a fresh engine verdict for it and confirms the prediction held.
"""
import datetime
import os

import records as R


def _find_item(manifest, uid):
    for it in manifest["items"]:
        if it.get("uid") == uid:
            return it
    return None


def log_square(batch_dir, uid, folded, by, date=None, notes=""):
    """Record outcome for one item. Returns (record, created, matched_prediction)."""
    if date is None:
        date = datetime.date.today().isoformat()
    manifest = R.load_batch(batch_dir)
    if manifest.get("engine") != "square":
        raise ValueError("this batch is engine=%s; only square logging is wired today"
                         % manifest.get("engine"))
    item = _find_item(manifest, uid)
    if item is None:
        raise KeyError("uid %s not in batch %s" % (uid, batch_dir))

    predicted = item.get("predicted", {})
    rec, created = R.append_square_finding(
        grid=item["grid"], canonical_hash=item["canonicalHash"], folded=folded,
        by=by, date=date, notes=notes, predicted=predicted)

    # stamp the manifest item too, so the batch is a self-contained record of what was tested
    item["actual"] = {"folded": bool(folded), "by": by, "date": date, "notes": notes}
    R.save_batch(batch_dir, manifest)

    pred_foldable = predicted.get("foldable")
    matched = None if pred_foldable is None else (bool(pred_foldable) == bool(folded))
    return rec, created, matched


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="phystest log",
                                 description="record a physical fold outcome for a batch item")
    ap.add_argument("--batch", required=True, help="batch directory (holding batch.json)")
    ap.add_argument("--uid", required=True, help="the candidate uid from the batch manifest")
    ap.add_argument("--folded", required=True, choices=["yes", "no"],
                    help="did it physically fold flat? yes=FOLD, no=JAM")
    ap.add_argument("--by", required=True, help="who folded it (e.g. john)")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    ap.add_argument("--notes", default="")
    args = ap.parse_args(argv)

    folded = args.folded == "yes"
    rec, created, matched = log_square(args.batch, args.uid, folded, args.by,
                                       date=args.date, notes=args.notes)
    outcome = "FOLD" if folded else "JAM"
    if not created:
        print("already recorded for grid=%s uid=%s (not overwritten)" % (rec["grid"], args.uid))
        return 0
    tail = "" if matched is None else ("  prediction %s" % ("MATCHED" if matched else "**MISSED**"))
    print("logged %s  grid=%s  uid=%s  by=%s  date=%s%s"
          % (outcome, rec["grid"], args.uid, rec["by"], rec["date"], tail))
    if matched is False:
        print("  !! engine predicted foldable=%s but physical outcome was %s -- run `phystest check`"
              % (rec.get("predicted", {}).get("foldable"), outcome))
    return 0
