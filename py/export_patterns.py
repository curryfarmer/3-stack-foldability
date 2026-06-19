#!/usr/bin/env python3
"""export_patterns.py — query patterns by verdict flags and export each as a fold-pattern image.

Pulls a sorted/filtered set of patterns out of the SQLite DB (reusing serve.query_patterns, so the
sort/filter vocabulary is IDENTICAL to GET /api/patterns) and renders each to a PNG in an output
folder — the physical to-test batch. Writes an index.csv beside the images (pattern_uid, hashes,
verdict columns, image file) so a folded result can be cross-referenced back to its candidate.

  python py/export_patterns.py --out batch_a --filter parity:true --sort reflection
  python py/export_patterns.py --out batch_b --run 7 --filter twist:null --limit 50
  python py/export_patterns.py --out batch_c --filter exit_footprint:true --filter is_ground_truth:null --test
  python py/export_patterns.py --out batch_d --uid a1b2c3d4e5f6 --uid 0f1e2d3c4b5a   # pull by pattern_uid directly
  python py/export_patterns.py --out batch_e --uid "a1b2c3d4e5f6 0f1e2d3c4b5a ..."   # or paste a whole batch into one --uid
  python py/export_patterns.py --out batch_f --uids-file uids.txt                     # ... or one uid per line ('-' = stdin)

Sort/filter keys == the API whitelist (serve._PAT_COLS + finding joins): parity, reflection, twist,
vector_parity, exit_footprint, arithmetic, phys_foldable, is_ground_truth, decomposition, shape, …
Filter forms: `col:true|false|null|<int>` and `tag:KEY:true|false|null`.
"""
import argparse
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for d in (HERE, ROOT):                       # py/ for store/render, ROOT for serve
    if d not in sys.path:
        sys.path.insert(0, d)

import store as Store          # noqa: E402
import serve                   # noqa: E402  (reuse query_patterns + its whitelist)
import render_square           # noqa: E402

_PAGE = 2000                                 # query_patterns hard-caps a page at 2000 rows

# index.csv columns (the cross-ref sheet for recording physical results later)
_CSV_COLS = ["image", "pattern_uid", "canonical_hash", "norm_hash", "run_id", "decomposition",
             "arithmetic", "exit_footprint", "parity", "vector_parity", "reflection", "twist",
             "phys_foldable", "is_ground_truth"]


def _collect_uids(uid_args, uids_file):
    """Flatten --uid values (each may be a newline/space/comma-separated batch) + a --uids-file (or
    stdin when '-') into an order-preserving, de-duplicated pattern_uid list. I/O: (list, path|None)
    -> list[str]."""
    raw = []
    for chunk in uid_args:
        raw.extend(re.split(r"[\s,]+", chunk.strip()))
    if uids_file:
        text = sys.stdin.read() if uids_file == "-" else open(uids_file, encoding="utf-8").read()
        raw.extend(re.split(r"[\s,]+", text.strip()))
    seen, out = set(), []
    for u in raw:
        if u and u not in seen:
            seen.add(u); out.append(u)
    return out


def _fetch(conn, q, hard_limit):
    """Page through query_patterns until exhausted (or hard_limit rows). Returns (rows, total)."""
    rows, offset = [], 0
    total = None
    while True:
        page = dict(q)
        page["limit"] = [str(_PAGE)]
        page["offset"] = [str(offset)]
        res = serve.query_patterns(conn, page)
        total = res["total"]
        rows.extend(res["rows"])
        offset += len(res["rows"])
        if not res["rows"] or offset >= total or (hard_limit and len(rows) >= hard_limit):
            break
    if hard_limit:
        rows = rows[:hard_limit]
    return rows, total


def main(argv=None):
    p = argparse.ArgumentParser(description="Export sorted/filtered patterns as fold-pattern images.")
    p.add_argument("--out", required=True, metavar="DIR", help="output folder for the image batch")
    p.add_argument("--sort", default="seq", help="sort key (e.g. reflection, parity, twist, seq)")
    p.add_argument("--dir", default="asc", choices=("asc", "desc"))
    p.add_argument("--filter", action="append", default=[], metavar="COL:VAL",
                   help="repeatable; col:true|false|null|<int> or tag:KEY:val")
    p.add_argument("--run", type=int, help="restrict to one run id")
    p.add_argument("--lattice", help="restrict to one lattice (e.g. square)")
    p.add_argument("--uid", action="append", default=[], metavar="UID",
                   help="repeatable; export these pattern_uid(s). One value may be a whole batch "
                        "(split on newlines/spaces/commas) so you can paste many at once.")
    p.add_argument("--uids-file", metavar="PATH",
                   help="read pattern_uids from a file, one per line ('-' = stdin)")
    p.add_argument("--limit", type=int, help="cap the number of images (default: all matching)")
    p.add_argument("--dpi", type=int, default=150)
    p.add_argument("--format", default="png", choices=("png", "pdf"))
    p.add_argument("--db", metavar="PATH", help="DB path (default $FOLDDB_SQLITE or results/folddb.sqlite3)")
    p.add_argument("--test", action="store_true", help="read the scratch DB results/folddb.test.sqlite3")
    ns = p.parse_args(sys.argv[1:] if argv is None else argv)

    path = Store.resolve_db_path(ns.db, ns.test)
    if not os.path.exists(path):
        print(f"no DB at {path} — generate one first (generate.py --store-all)", file=sys.stderr)
        return 1

    uids = _collect_uids(ns.uid, ns.uids_file)

    q = {"sort": [ns.sort], "dir": [ns.dir], "filter": ns.filter}
    if ns.run is not None:
        q["run"] = [str(ns.run)]
    if ns.lattice:
        q["lattice"] = [ns.lattice]
    if uids:
        q["uid"] = uids

    conn = Store.connect(path)
    try:
        rows, total = _fetch(conn, q, ns.limit)
        run_mn = {r["id"]: (r["m"], r["n"])
                  for r in conn.execute("SELECT id, m, n FROM runs").fetchall()}
    finally:
        conn.close()

    if not rows:
        print(f"no patterns matched (total={total}) — nothing exported")
        return 0

    os.makedirs(ns.out, exist_ok=True)
    written, failed, used = [], 0, set()
    for r in rows:
        m, n = run_mn.get(r["run_id"], (None, None))
        if m is None:                                    # run row vanished mid-export — skip, don't crash
            print(f"  ! run {r['run_id']} missing m/n; skipping {r['pattern_uid']}", file=sys.stderr)
            failed += 1
            continue
        base = f"{m}x{n}_{r['pattern_uid']}"
        fname = f"{base}.{ns.format}"
        if fname in used:                                # same uid across runs / --no-dedup dup: keep both
            fname = f"{base}_r{r['run_id']}s{r['seq']}.{ns.format}"
        used.add(fname)
        img = os.path.join(ns.out, fname)
        try:                                             # one malformed detail blob must not abort the batch
            render_square.render(r["detail"], m, n, img,
                                 title=f"{m}x{n}  {r['pattern_uid']}", dpi=ns.dpi)
        except Exception as exc:                         # noqa: BLE001 (render any row we can; report the rest)
            print(f"  ! render failed for {r['pattern_uid']}: {type(exc).__name__}: {exc}", file=sys.stderr)
            failed += 1
            continue
        written.append((fname, r))

    index = os.path.join(ns.out, "index.csv")
    with open(index, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(_CSV_COLS)
        for fname, r in written:
            w.writerow([fname, r["pattern_uid"], r["canonical_hash"], r["norm_hash"], r["run_id"],
                        r["decomposition"], r["arithmetic"], r["exit_footprint"], r["parity"],
                        r["vector_parity"], r["reflection"], r["twist"],
                        r["phys_foldable"], r["is_ground_truth"]])

    print(f"exported {len(written)} image(s) -> {ns.out}  (index: {index})")
    if uids:                                             # never silently swallow a requested uid that hit nothing
        got = {r["pattern_uid"] for r in rows}
        missing = [u for u in uids if u not in got]
        if missing:
            print(f"  note: {len(missing)} requested uid(s) matched no pattern: {', '.join(missing)}")
    if failed:                                           # never silently drop rows
        print(f"  note: {failed} pattern(s) skipped (missing run m/n or render error; see stderr above)")
    if ns.limit and total > ns.limit:                    # never silently truncate
        print(f"  note: --limit {ns.limit} kept the first {ns.limit} of {total} matching patterns "
              f"({total - ns.limit} not exported)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
