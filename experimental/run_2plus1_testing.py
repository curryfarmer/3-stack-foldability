"""run_2plus1_testing.py — run the 4 candidate 2+1 twist engines over EVERY cached 3-stack grid's
2+1 solutions, tag each with all 4 engine verdicts, and curate a minimal covering set that spans the
full 4-engine verdict space (not just partial's overhang axis).

Input : all results/*.json 3-stack caches with 2+1 solutions. These are exit+parity+reflection
        passers (twist is non-filtering). The 6x6 set is non-corner (corner 6x6 has 0 2+1).
Output: results/2+1 testing/
          all_2plus1.json       every tested solution (grid#id) + a `twistEngines` tag block
          <grid>_<id>.json      one representative per distinct 4-engine verdict-bucket
          _summary.json         per-grid + per-bucket counts, normal==jump, the reject(s)

Run:  python experimental/run_2plus1_testing.py
"""
import json
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))            # .../experimental
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import common  # noqa: E402
from no_decomp import twist as e_no            # noqa: E402
from jump_decomp import twist as e_jump        # noqa: E402
from normal_decomp import twist as e_normal    # noqa: E402
from partial_decomp import twist as e_partial  # noqa: E402

ENGINES = [e_no, e_jump, e_normal, e_partial]
OUTDIR = os.path.join(ROOT, "results", "2+1 testing")


def scan_caches():
    """Every 3-stack cache that has 2+1 solutions -> (grid, noncorner, m, n, sols)."""
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "results", "*.json"))):
        try:
            data = json.load(open(f))
        except Exception:
            continue
        if not isinstance(data, dict) or "meta" not in data:
            continue
        meta = data["meta"]
        if meta.get("stacks") != 3:
            continue
        m, n = meta.get("m"), meta.get("n")
        sols = [s for s in data.get("solutions", []) if s.get("decomposition") == "2+1"]
        if not sols:
            continue
        out.append(("%dx%d" % (m, n), bool(meta.get("opts", {}).get("allowNonCorner")), m, n, sols))
    if not out:
        raise SystemExit("no 3-stack cache with 2+1 solutions found")
    return out


def tag_solution(sol, m, n):
    two, one = common.split_chains(sol)
    ctx = common.prepare(two, one, m, n)          # shared by all 4 engines
    return {mod.NAME: mod.twist_2plus1(two, one, m, n, ctx=ctx) for mod in ENGINES}


def bucket_key(rec):
    """Full 4-engine qualitative signature. n2units is NOT a splitter (recorded as a range)."""
    t = rec["twistEngines"]
    p = t["partial decomp"]
    return (
        rec["grid_shape"],
        t["no decomp"]["pass"], t["jump decomp"]["pass"], t["normal decomp"]["pass"],
        p["class"], p["hub_removable"], p["sign"],
    )


def describe_bucket(k):
    shape, no, jump, normal, pcls, hubrm, sign = k
    sound = ("no/jump/normal=FOLD" if (no and jump and normal) else
             "no/jump/normal=%s/%s/%s" % tuple("FOLD" if x else "TWIST" for x in (no, jump, normal)))
    if pcls == "flat":
        ptxt = "partial=flat"
    elif pcls == "overhang":
        ptxt = "partial=overhang%+d %s" % (sign, "(hub-removable)" if hubrm else "(intrinsic)")
    else:
        ptxt = "partial=%s" % pcls
    return "%-4s %s  %s" % (shape, sound, ptxt)


def main():
    caches = scan_caches()
    tagged = []
    for grid, nc, m, n, sols in caches:
        for s in sols:
            try:
                tags = tag_solution(s, m, n)
            except Exception as ex:
                print("  skip %s #%s: %s" % (grid, s.get("id"), ex))
                continue
            rec = dict(s)
            rec["grid"] = grid
            rec["grid_shape"] = s["footprint"]["shape"]
            rec["twistEngines"] = tags
            tagged.append(rec)
    print("tagged %d 2+1 across %d grids: %s"
          % (len(tagged), len(caches), ", ".join("%s%s" % (g, "*" if nc else "")
                                                  for g, nc, *_ in caches)))

    # --- physical check: normal == jump everywhere ---
    nj_ok = sum(1 for r in tagged
                if common.is0(r["twistEngines"]["normal decomp"]["tw"]
                              - r["twistEngines"]["jump decomp"]["tw"]))

    # --- bucket into the minimal covering set across the full 4-engine space ---
    buckets = {}
    for r in tagged:
        buckets.setdefault(bucket_key(r), []).append(r)
    repkey = lambda r: (r["grid"], r["id"])
    curated = sorted((min(v, key=repkey) for v in buckets.values()), key=repkey)

    # --- write outputs ---
    os.makedirs(OUTDIR, exist_ok=True)
    for stale in glob.glob(os.path.join(OUTDIR, "*.json")):       # clear prior run
        os.remove(stale)
    with open(os.path.join(OUTDIR, "all_2plus1.json"), "w") as fh:
        json.dump({"twistEngineModels": MODEL_DOC,
                   "solutions": [{"grid": r["grid"], **{k: v for k, v in r.items()
                                                        if k not in ("grid", "grid_shape")}}
                                 for r in tagged]}, fh, indent=2)
    for r in curated:
        out = {k: v for k, v in r.items() if k != "grid_shape"}
        with open(os.path.join(OUTDIR, "%s_%d.json" % (r["grid"], r["id"])), "w") as fh:
            json.dump(out, fh, indent=2)

    # --- summary ---
    from collections import Counter
    per_grid = {}
    for g, nc, *_ in caches:
        gr = [r for r in tagged if r["grid"] == g]
        per_grid[g + ("*" if nc else "")] = {
            "n": len(gr),
            "sound_fold": sum(1 for r in gr if all(r["twistEngines"][e]["pass"]
                                                   for e in ("no decomp", "jump decomp", "normal decomp"))),
            "partial": dict(Counter(r["twistEngines"]["partial decomp"]["class"] for r in gr)),
        }
    rejects = [{"grid": r["grid"], "id": r["id"],
                "tw": {e: r["twistEngines"][e]["tw"] for e in
                       ("no decomp", "jump decomp", "normal decomp", "partial decomp")}}
               for r in tagged
               if not all(r["twistEngines"][e]["pass"]
                          for e in ("no decomp", "jump decomp", "normal decomp"))]
    bucket_report = [{"key": describe_bucket(k), "count": len(v),
                      "rep": "%s#%d" % (min(v, key=repkey)["grid"], min(v, key=repkey)["id"]),
                      "n2units": sorted(set(r["twistEngines"]["partial decomp"]["n2units"] for r in v)),
                      "members": ["%s#%d" % (r["grid"], r["id"]) for r in sorted(v, key=repkey)]}
                     for k, v in sorted(buckets.items(), key=lambda kv: -len(kv[1]))]
    summary = {
        "tested": len(tagged),
        "normal_eq_jump": "%d/%d" % (nj_ok, len(tagged)),
        "sound_engines_reject": len(rejects),
        "rejects": rejects,
        "per_grid": per_grid,
        "distinct_buckets": len(buckets),
        "curated": ["%s_%d" % (r["grid"], r["id"]) for r in curated],
        "buckets": bucket_report,
    }
    with open(os.path.join(OUTDIR, "_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)

    # --- console ---
    print("\nnormal == jump tw : %d/%d  %s"
          % (nj_ok, len(tagged), "PASS (filled == jump everywhere)" if nj_ok == len(tagged) else "FAIL"))
    print("no/jump/normal REJECT (Tw!=0): %d / %d" % (len(rejects), len(tagged)))
    for rj in rejects:
        print("    %s#%d  tw=%s" % (rj["grid"], rj["id"], rj["tw"]))
    print("\nper grid (*=non-corner):")
    for g, d in per_grid.items():
        print("  %-7s n=%-3d sound-FOLD=%-3d partial=%s" % (g, d["n"], d["sound_fold"], d["partial"]))
    print("\ndistinct 4-engine buckets: %d  -> curated %d files" % (len(buckets), len(curated)))
    for b in bucket_report:
        print("  %-9s x%-3d  %-50s 2u=%s" % (b["rep"], b["count"], b["key"], b["n2units"]))
    print("\nwrote -> %s" % os.path.relpath(OUTDIR, ROOT))


MODEL_DOC = {
    "no decomp": "whole-domino centroid per placement (un-reduced; the 936 artifact). pass = Tw==0.",
    "jump decomp": "one kept strand, twin cells as holes, short-side folds = 3-jumps (Model B). pass = Tw==0.",
    "normal decomp": "filled: kept strand with 3-jumps filled by collinear midpoints (== jump). pass = Tw==0.",
    "partial decomp": ("lead's variable-width: 1-unit by default, 2-unit centroid at short-side folds. "
                       "3-way class flat/overhang/twisted/mixed; pass = flat or overhang "
                       "(overhang = atan(1/2) residual = one end sticks out but the fold closes)."),
}


if __name__ == "__main__":
    main()
