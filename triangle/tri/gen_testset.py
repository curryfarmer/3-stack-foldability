"""gen_testset.py — batch physical fold-check test set for all non-square 3-stack families.

For each of the 8 families (equilateral / righttri / scalene / hex) x (1+1+1 / 2+1), march K up
from the known first-closing K, enumerate CLOSING folds (every gen_* path already applies the
physical closure gate), dedup by tiling symmetry, and keep up to CAP_FOLD predicted-FOLDABLE +
CAP_JAM predicted-JAM distinct cases. Each kept case is rendered to a chain-overlay PNG + a printable
foldsheet PNG (reusing find_example.render_case), and logged with its engine PREDICTION so the user
can fold each sheet and confirm FOLD/JAM.

Dedup key (tile ids are canonical within the fixed ambient hub, so equal id-sets == same fold):
  1+1+1: (mid-chain ids, frozenset{armA ids, armC ids})  -> collapses the arm-swap twin enum emits
  2+1:   frozenset(region tile ids)

Output: report/tri/<outdir>/  (overlay_*/foldsheet_* PNGs + TEST_PLAN.md + testset.json).

  python py/tri/gen_testset.py [--outdir testset] [--cap-fold 6] [--cap-jam 6] [--budget 60]
"""
import argparse
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_example as FE    # noqa: E402  gen_111 / gen_21 / gen_eq / render_case / KPLAN
import hunt_foldable as HF   # noqa: E402  holes()
import seam_filter as SFILT  # noqa: E402  STRICT START<->END seam gate (demote mirror/off-cell FOLD->JAM)

TILINGS = ("equilateral", "righttri", "scalene", "hex")
DECOMPS = ("1plus1plus1", "2plus1")


def _trust(tiling, decomp):
    """How trustworthy the FOLD/JAM label is (drives 'fold to verify' emphasis). The physical
    CLOSURE gate is reliable everywhere; only the twist FOLD/JAM label varies. ALL 2+1 (incl.
    equilateral) is MODEL-tier — same strand-twist, and its end-domino seating is the open
    question the physical folds resolve. Only equilateral 1+1+1 has a validated solver."""
    if decomp == "2plus1":
        return "MODEL (2+1 strand-twist + seating - fold to verify)"
    if tiling == "equilateral":
        return "PROVEN (validated solver + physical closure)"
    if tiling == "hex":
        return "MODEL (hex path-sigma twist - fold to verify)"
    return "CLOSURE-PROVEN, twist label (fold to verify)"


def _chains(cand):
    """The 3 chains as tuple-tile lists, from a general cand ('chains') or an equilateral rec."""
    src = cand["chains"] if "chains" in cand else cand["rec"]["chains"]
    return [[tuple(t) for t in c] for c in src]


def _dedup_key(cand):
    if cand["decomp"] == "1plus1plus1":
        ch = _chains(cand)                                    # [armA, mid, armC]
        canon = lambda c: tuple(tuple(t) for t in c)         # noqa: E731
        return ("111", canon(ch[1]), frozenset({canon(ch[0]), canon(ch[2])}))
    return ("21", frozenset(tuple(t) for t in cand["region"]))


def _tk(t):
    """Stable, reversible JSON string key for a tile id (json.loads recovers the id list)."""
    return json.dumps(list(t), separators=(",", ":"))


def _canon_key(key):
    """Deterministic JSON string for a _dedup_key (stable across runs / set iteration order)."""
    if key[0] == "111":
        _, mid, arms = key
        mid_l = [list(t) for t in mid]                        # ordered path (direction is identity)
        arms_l = sorted([[list(t) for t in a] for a in arms])  # invariant to the arm A/C swap
        return json.dumps(["111", mid_l, arms_l], separators=(",", ":"))
    _, region = key
    return json.dumps(["21", sorted(list(t) for t in region)], separators=(",", ":"))


def fold_uid(tiling, decomp, cand):
    """Stable 12-hex content id for a fold = sha1 over (tiling, decomp, canonical dedup identity).
    Same physical fold -> same id across runs. Reuses store.pattern_uid's sha1[:12] convention (a
    local helper, no py/tri -> py/storage coupling). Each id ties 1:1 to a folds/<uid>.json."""
    payload = "tri|%s|%s|%s" % (tiling, decomp, _canon_key(_dedup_key(cand)))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _fold_record(uid, tiling, decomp, K, quad, cand, tc, verdict, over, sheet):
    """Self-contained per-fold JSON: identity + topology (tile ids) + CARTESIAN geometry + seam
    analysis, numerically complete so a consumer needs no engine to read the fold. render_fold.py
    reconstructs the exact sheet from this file (it is the render source of truth)."""
    chains = _chains(cand)                                     # handles the eq-1+1+1 rec shape too
    if "footprint" in cand:
        footprint = [tuple(t) for t in cand["footprint"]]
        end_fp = [tuple(t) for t in cand["end_footprint"]]
    else:                                                     # equilateral 1+1+1 solver-rec shape
        r = cand["rec"]
        footprint = [tuple(t) for t in r["footprint"]]
        end_fp = [tuple(t) for t in r["end_footprint"]]
    region = sorted(tuple(t) for t in cand["region"])
    partners = [tuple(t) for t in cand["partners"]] if "partners" in cand else None
    two_tris = [tuple(t) for t in cand["two_tris"]] if "two_tris" in cand else None

    tile_cart = FE.GEN[tiling]["tile_cart"]                   # tile id -> [cart pts]; pure (no lat)
    geom_tiles = set(region) | set(footprint) | set(end_fp)
    for c in chains:
        geom_tiles |= {tuple(t) for t in c}
    for extra in (partners, two_tris):
        if extra:
            geom_tiles |= set(extra)
    geometry = {}
    for t in sorted(geom_tiles):
        try:
            geometry[_tk(t)] = [[float(x), float(y)] for (x, y) in tile_cart(t)]
        except Exception:                                    # a stray id with no geometry must not kill the dump
            pass

    rec = {
        "schema": "tri-fold/1", "uid": uid,
        "tiling": tiling, "decomp": decomp, "K": K,
        "quadrant": quad, "quad_label": QUAD_LABEL.get(quad, quad),
        "label": "%s %s %s" % (tiling, decomp, quad),
        "suspect": tiling == "righttri",                     # user flags 45-45-90 as physically suspect
        "holes_mode": "allow",
        "chains": [[list(t) for t in c] for c in chains],
        "footprint": [list(t) for t in footprint],
        "end_footprint": [list(t) for t in end_fp],
        "region": [list(t) for t in region],
        "tw": cand.get("tw"), "tw_desc": cand.get("tw_desc"),
        "foldable": bool(cand["foldable"]),
        "seam_ok": cand.get("seam_ok"), "seam_detail": cand.get("seam_detail"),
        "seam_note": cand.get("seam_note"),
        "seam_class": tc.get("klass"), "single_motion": tc.get("single_motion"),
        "chirality": tc,                                     # full per-tile orientation read-out
        "holes": cand.get("holes"),
        "verdict": verdict,
        "geometry": geometry,
        "overlay": os.path.basename(over), "foldsheet": os.path.basename(sheet),
    }
    if partners is not None:
        rec["partners"] = [list(t) for t in partners]
    if two_tris is not None:
        rec["two_tris"] = [list(t) for t in two_tris]
    return rec


def _gen_for(tiling, decomp, K):
    if decomp == "2plus1":
        # a single central hub yields only ~1 distinct foldable 2+1 REGION, so sweep several hubs to
        # surface a 2nd example (equilateral 2+1 also routes here, unified onto the domino model).
        return FE.gen_21(tiling, K, hubs=8)
    if tiling == "equilateral":
        return FE.gen_eq(decomp, K)
    return FE.gen_111(tiling, K, hub=None)


def collect_family(tiling, decomp, cap_fold, cap_jam, budget):
    """March K; return (folds, jams) each a list of (lat, K, cand), deduped, capped."""
    K0, step, kcap = FE.KPLAN[(tiling, decomp)]
    interior_deg = 6 if tiling == "hex" else 3
    seen, folds, jams = set(), [], []
    t0 = time.time()
    for K in range(K0, kcap + 1, step):
        lat, gen = _gen_for(tiling, decomp, K)
        for cand in gen:
            key = _dedup_key(cand)
            if key in seen:
                continue
            seen.add(key)
            SFILT.apply(lat, cand)          # STRICT seam gate: a mirror/off-cell FOLD becomes a JAM here
            cand["holes"] = len(HF.holes(lat, cand["region"], interior_deg))
            bucket, cap = (folds, cap_fold) if cand["foldable"] else (jams, cap_jam)
            if len(bucket) < cap:
                bucket.append((lat, K, cand))
            if (len(folds) >= cap_fold and len(jams) >= cap_jam) or time.time() - t0 > budget:
                break
        if (len(folds) >= cap_fold and len(jams) >= cap_jam) or time.time() - t0 > budget:
            break
    return folds, jams


def collect_family_compare(tiling, decomp, cap_pass, cap_fail, budget):
    """Seam-flag COMPARISON collector. March K; among candidates the TWIST already calls FOLD
    (Tw=0, i.e. cand['foldable'] BEFORE the seam filter), split by the new flag:
        pass <- Tw=0 AND seam_ok        (predicted FOLD, expect flat)
        fail <- Tw=0 AND NOT seam_ok    (seam-demoted, predicted JAM; SAME twist label)
    Tw!=0 candidates are dropped -- both columns share Tw=0 so only the flag differs. The `fail`
    bucket is non-empty only on unequal-sided tiles (righttri/scalene); everywhere else it stays
    empty, which is exactly the flag's fingerprint. Returns (passes, fails)."""
    K0, step, kcap = FE.KPLAN[(tiling, decomp)]
    interior_deg = 6 if tiling == "hex" else 3
    seen, passes, fails = set(), [], []
    t0 = time.time()
    for K in range(K0, kcap + 1, step):
        lat, gen = _gen_for(tiling, decomp, K)
        for cand in gen:
            key = _dedup_key(cand)
            if key in seen:
                continue
            seen.add(key)
            tw_fold = bool(cand["foldable"])            # the twist label, BEFORE the seam filter
            SFILT.apply(lat, cand)                      # stamps seam_ok/seam_detail, may demote foldable
            if not tw_fold:                             # Tw!=0 is not part of this comparison
                if time.time() - t0 > budget:
                    break
                continue
            cand["holes"] = len(HF.holes(lat, cand["region"], interior_deg))
            bucket, cap = (passes, cap_pass) if cand.get("seam_ok") else (fails, cap_fail)
            if len(bucket) < cap:
                bucket.append((lat, K, cand))
            if (len(passes) >= cap_pass and len(fails) >= cap_fail) or time.time() - t0 > budget:
                break
        if (len(passes) >= cap_pass and len(fails) >= cap_fail) or time.time() - t0 > budget:
            break
    return passes, fails


# ------------------------------------------------------------------ 4-quadrant MVP matrix (twist x seam)
# The user's minimum-viable stress set: per (grid, decomp) one example of each combination of the TWO
# independent fold obstructions — the strand TWIST (Tw=0 vs Tw!=0) and the START<->END SEAM gate
# (rotational-equivalent vs mirror/off-cell). The four cells:
#   tw0_seamok  : Tw=0 AND seam-aligned  -> the IDEAL clean FOLD (prefer K>=6 to stress the engine)
#   twN_seamok  : Tw!=0 AND seam-aligned -> twist says JAM, seam agrees it returns proper (over-rotation)
#   tw0_seambad : Tw=0 AND seam-misaligned-> the mirror/off-cell JAM the twist ALONE mislabels FOLD
#   twN_seambad : Tw!=0 AND seam-misaligned-> both obstructions fire (twist over-rotates AND mirrors)
# seambad cells populate ONLY on unequal-sided tiles (righttri/scalene); uniform families (eq/hex) and
# scalene (no mirror axis) leave them empty by construction — that emptiness is reported, not hidden.
QUADS = ("tw0_seamok", "twN_seamok", "tw0_seambad", "twN_seambad")
QUAD_LABEL = {
    "tw0_seamok":  "Tw=0, seam-aligned (IDEAL FOLD)",
    "twN_seamok":  "Tw!=0, seam-aligned (twist-JAM only)",
    "tw0_seambad": "Tw=0, seam-misaligned (seam-JAM only; twist mislabels FOLD)",
    "twN_seambad": "Tw!=0, seam-misaligned (both obstructions)",
}


def collect_family_quadrants(tiling, decomp, budget, kmin_ideal=6):
    """March K; fill one candidate per QUADRANT (twist x seam). tw0_seamok prefers K>=kmin_ideal
    (falls back to any-K if none big enough within budget). Returns {quad: (lat,K,cand) or None}."""
    K0, step, kcap = FE.KPLAN[(tiling, decomp)]
    interior_deg = 6 if tiling == "hex" else 3
    seen, buckets = set(), {q: None for q in QUADS}
    ideal_fallback = None
    t0 = time.time()

    def _hard_quads_done():                 # the 3 non-ideal cells + a K>=kmin ideal all found
        return (buckets["tw0_seamok"] is not None and buckets["twN_seamok"] is not None
                and buckets["tw0_seambad"] is not None and buckets["twN_seambad"] is not None)

    for K in range(K0, kcap + 1, step):
        lat, gen = _gen_for(tiling, decomp, K)
        for cand in gen:
            key = _dedup_key(cand)
            if key in seen:
                continue
            seen.add(key)
            tw_fold = bool(cand["foldable"])            # twist label BEFORE the seam gate
            SFILT.apply(lat, cand)                      # stamps seam_ok; demotes a mirror/off-cell FOLD
            seam_ok = bool(cand.get("seam_ok"))
            cand["holes"] = len(HF.holes(lat, cand["region"], interior_deg))
            if tw_fold and seam_ok:
                if K >= kmin_ideal and buckets["tw0_seamok"] is None:
                    buckets["tw0_seamok"] = (lat, K, cand)
                elif ideal_fallback is None:
                    ideal_fallback = (lat, K, cand)
            elif (not tw_fold) and seam_ok and buckets["twN_seamok"] is None:
                buckets["twN_seamok"] = (lat, K, cand)
            elif tw_fold and (not seam_ok) and buckets["tw0_seambad"] is None:
                buckets["tw0_seambad"] = (lat, K, cand)
            elif (not tw_fold) and (not seam_ok) and buckets["twN_seambad"] is None:
                buckets["twN_seambad"] = (lat, K, cand)
            if _hard_quads_done() or time.time() - t0 > budget:
                break
        if _hard_quads_done() or time.time() - t0 > budget:
            break
    if buckets["tw0_seamok"] is None:               # never found a big one -> accept any-K ideal
        buckets["tw0_seamok"] = ideal_fallback
    return buckets


def _run_quadrants(families, args, out_report):
    """Emit the twist x seam MVP matrix: one sheet per populated quadrant per (grid, decomp), each
    with a stable uid + a self-contained folds/<uid>.json (the render source of truth)."""
    rows, matrix = [], []
    folds_dir = os.path.join(out_report, "folds")
    os.makedirs(folds_dir, exist_ok=True)
    for tiling, decomp in families:
        print("=== %s / %s (quadrants) ===" % (tiling, decomp), flush=True)
        buckets = collect_family_quadrants(tiling, decomp, args.budget, kmin_ideal=args.kmin_ideal)
        got = {q: (buckets[q] is not None) for q in QUADS}
        print("   " + "  ".join("%s=%s" % (q, "Y" if got[q] else "-") for q in QUADS), flush=True)
        matrix.append({"tiling": tiling, "decomp": decomp, **{q: got[q] for q in QUADS}})
        for q in QUADS:
            if buckets[q] is None:
                continue
            lat, K, cand = buckets[q]
            uid = fold_uid(tiling, decomp, cand)
            try:
                over, sheet, verdict = FE.render_case(tiling, decomp, "allow", lat, K, cand,
                                                      name_stem=uid)
            except Exception as e:
                print("   !! render failed %s %s: %s" % (tiling, uid, e), flush=True)
                continue
            tc = SFILT.tile_chirality(lat, cand)
            data_path = os.path.join(folds_dir, "%s.json" % uid)
            with open(data_path, "w") as f:
                json.dump(_fold_record(uid, tiling, decomp, K, q, cand, tc, verdict, over, sheet),
                          f, indent=1)
            rows.append({
                "uid": uid, "suspect": tiling == "righttri",
                "tiling": tiling, "decomp": decomp, "K": K, "quad": q,
                "quad_label": QUAD_LABEL[q],
                "tw": cand.get("tw"),
                "tw_zero": all(v == 0 for v in cand["tw"]) if isinstance(cand.get("tw"), (list, tuple))
                           else (abs(cand["tw"]) < 1e-6 if isinstance(cand.get("tw"), (int, float)) else None),
                "seam_ok": cand.get("seam_ok"), "seam_class": tc["klass"],
                "single_motion": tc["single_motion"], "seam_detail": cand.get("seam_detail"),
                "holes": cand["holes"], "predicted": "FOLDABLE" if cand["foldable"] else "JAM",
                "verdict": verdict,
                "data": os.path.relpath(data_path),
                "overlay": os.path.relpath(over), "foldsheet": os.path.relpath(sheet),
            })
    os.makedirs(out_report, exist_ok=True)
    with open(os.path.join(out_report, "testset.json"), "w") as f:
        json.dump(rows, f, indent=1)
    _write_quadrant_plan(os.path.join(out_report, "TEST_PLAN.md"), rows, matrix)
    print("\n%d quadrant sheets (+per-fold json in folds/) -> %s"
          % (len(rows), os.path.relpath(out_report)), flush=True)


def _write_quadrant_plan(path, rows, matrix):
    lines = [
        "# 3-stack MVP stress matrix — twist x seam (one example per quadrant per family)",
        "",
        "Two INDEPENDENT fold obstructions, crossed. **Twist** = strand over-rotation (Tw=0 vs Tw!=0).",
        "**Seam** = does the END footprint return onto the START footprint as a *single rigid motion*",
        "(rotational-equivalent, A->A B->B C->C proper) or come back mirrored / off-cell. A real flat",
        "fold needs BOTH clear: Tw=0 AND seam-aligned.",
        "",
        "| quadrant | Tw | seam | physical meaning | engine verdict |",
        "|---|---|---|---|---|",
        "| tw0_seamok  | 0    | aligned      | ideal clean fold (prefer K>=6)             | FOLD |",
        "| twN_seamok  | !=0  | aligned      | over-rotation only (seam returns proper)    | JAM (twist) |",
        "| tw0_seambad | 0    | mirror/off   | twist mislabels FOLD; seam catches the mirror| JAM (seam) |",
        "| twN_seambad | !=0  | mirror/off   | both obstructions fire                       | JAM (both) |",
        "",
        "Mirror enforcement applies only to the ISOSCELES-not-uniform tile (45-45-90 righttri), where a",
        "mirror arrival swaps the equal labelled legs on the same cell. K-PARITY LAW (2026-07-02): an",
        "on-cell arrival is a mirror at EVEN K and a proper rotation at ODD K (chains alternate sigma),",
        "so righttri seam-ALIGNED cells require odd K and every even-K righttri fold is a seam JAM.",
        "30-60-90 scalene mirrors seat the mirror-partner cell with all edge roles matched = exempt;",
        "equilateral/hex are edge-uniform so a mirror is invisible = exempt. Empty cells below are",
        "structural absence, not a search miss.",
        "",
        "## Coverage (which quadrants exist per family)",
        "",
        "| family | tw0_seamok | twN_seamok | tw0_seambad | twN_seambad |",
        "|---|---|---|---|---|",
    ]
    for m in matrix:
        lines.append("| %s %s | %s | %s | %s | %s |" % (
            m["tiling"], m["decomp"],
            *["Y" if m[q] else "-" for q in QUADS]))
    lines += [
        "",
        "Each fold has a stable **uid**; its numerically-complete data is `folds/<uid>.json` (identity +",
        "tile ids + cartesian polygons + per-tile seam analysis). Re-render any fold from that file with",
        "`python py/tri/render_fold.py --uid <uid>`. Rows marked **suspect** are 45-45-90 righttri, which",
        "the user flags as physically suspect (kept for the seam-bad column; filter by the `suspect` field",
        "in testset.json).",
        "",
        "## Sheets to fold",
        "",
        "| uid | family | quadrant | K | Tw | seam | class | single_motion | predicted | ACTUAL |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        fam = "%s %s%s" % (r["tiling"], r["decomp"], " (suspect)" if r.get("suspect") else "")
        lines.append("| `%s` | %s | %s | %d | %s | %s | %s | %s | **%s** |  |" % (
            r["uid"], fam, r["quad"], r["K"], _fmt_tw(r["tw"]),
            "ok" if r["seam_ok"] else "BAD", r["seam_class"], r["single_motion"], r["predicted"]))
    lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description="batch fold-check test set for all non-square families")
    ap.add_argument("--outdir", default="testset", help="under report/tri/ and results/ (default: testset)")
    ap.add_argument("--cap-fold", type=int, default=2, help="max distinct FOLDABLE cases per family")
    ap.add_argument("--cap-jam", type=int, default=2, help="max distinct JAM cases per family")
    ap.add_argument("--budget", type=float, default=60.0, help="per-family wall-clock budget (s)")
    ap.add_argument("--families", nargs="+", default=None,
                    help="subset like 'scalene:1plus1plus1' (default: all 8)")
    ap.add_argument("--compare", action="store_true",
                    help="seam-flag comparison matrix: per family emit Tw=0 seam-PASS vs Tw=0 seam-FAIL "
                         "sheets (same twist label, opposite flag) across all grids x both decomps")
    ap.add_argument("--quadrants", action="store_true",
                    help="MVP stress matrix: per family emit one sheet per twist x seam quadrant "
                         "(tw0_seamok / twN_seamok / tw0_seambad / twN_seambad)")
    ap.add_argument("--kmin-ideal", type=int, default=6, dest="kmin_ideal",
                    help="prefer K>=this for the tw0_seamok ideal-fold cell (default 6)")
    args = ap.parse_args()

    FE.set_outdir(args.outdir)                               # park all renders in report/tri/<outdir>
    out_report = FE.REPORT

    families = ([tuple(f.split(":")) for f in args.families] if args.families
                else [(t, d) for t in TILINGS for d in DECOMPS])

    if args.quadrants:
        return _run_quadrants(families, args, out_report)
    if args.compare:
        return _run_compare(families, args, out_report)

    rows = []
    for tiling, decomp in families:
        print("=== %s / %s ===" % (tiling, decomp), flush=True)
        folds, jams = collect_family(tiling, decomp, args.cap_fold, args.cap_jam, args.budget)
        print("   kept %d foldable, %d jam" % (len(folds), len(jams)), flush=True)
        for verdict_class, cases in (("fold", folds), ("jam", jams)):
            for idx, (lat, K, cand) in enumerate(cases, 1):
                suffix = "_%s%d" % (verdict_class, idx)
                try:
                    over, sheet, verdict = FE.render_case(tiling, decomp, "allow", lat, K, cand, suffix)
                except Exception as e:                       # one bad render must not kill the batch
                    print("   !! render failed %s%s: %s" % (tiling, suffix, e), flush=True)
                    continue
                rows.append({
                    "tiling": tiling, "decomp": decomp, "K": K,
                    "case": verdict_class + str(idx),
                    "predicted": "FOLDABLE" if cand["foldable"] else "JAM",
                    "tw": cand.get("tw"), "holes": cand["holes"],
                    "trust": _trust(tiling, decomp), "verdict": verdict,
                    "overlay": os.path.relpath(over), "foldsheet": os.path.relpath(sheet),
                })

    # manifest + human-readable test plan
    os.makedirs(out_report, exist_ok=True)
    with open(os.path.join(out_report, "testset.json"), "w") as f:
        json.dump(rows, f, indent=1)
    _write_test_plan(os.path.join(out_report, "TEST_PLAN.md"), rows)
    n_fold = sum(1 for r in rows if r["predicted"] == "FOLDABLE")
    print("\n%d cases total (%d predicted FOLDABLE, %d predicted JAM) -> %s"
          % (len(rows), n_fold, len(rows) - n_fold, os.path.relpath(out_report)), flush=True)


def _run_compare(families, args, out_report):
    """Minimum-viable seam-flag matrix: for every (grid, decomp) emit up to --cap-fold Tw=0 seam-PASS
    and up to --cap-jam Tw=0 seam-FAIL sheets, then write a comparison manifest + TEST_PLAN. Only the
    unequal-sided families (righttri / scalene) are expected to populate the FAIL column; an empty FAIL
    everywhere else is the control that proves the flag bites only non-uniform tiles."""
    rows, matrix = [], []
    for tiling, decomp in families:
        print("=== %s / %s (compare) ===" % (tiling, decomp), flush=True)
        passes, fails = collect_family_compare(tiling, decomp, args.cap_fold, args.cap_jam, args.budget)
        print("   Tw=0: %d seam-PASS, %d seam-FAIL" % (len(passes), len(fails)), flush=True)
        matrix.append({"tiling": tiling, "decomp": decomp,
                       "n_pass": len(passes), "n_fail": len(fails)})
        for cls, cases in (("pass", passes), ("fail", fails)):
            for idx, (lat, K, cand) in enumerate(cases, 1):
                suffix = "_%s%d" % (cls, idx)
                try:
                    over, sheet, verdict = FE.render_case(tiling, decomp, "allow", lat, K, cand, suffix)
                except Exception as e:                       # one bad render must not kill the batch
                    print("   !! render failed %s%s: %s" % (tiling, suffix, e), flush=True)
                    continue
                rows.append({
                    "tiling": tiling, "decomp": decomp, "K": K,
                    "case": cls + str(idx),
                    "seam_flag": "PASS" if cls == "pass" else "FAIL",
                    "predicted": "FOLDABLE" if cls == "pass" else "JAM",
                    "expected": "FOLD" if cls == "pass" else "JAM",
                    "tw": cand.get("tw"), "seam_ok": cand.get("seam_ok"),
                    "seam_detail": cand.get("seam_detail"), "holes": cand["holes"],
                    "verdict": verdict,
                    "overlay": os.path.relpath(over), "foldsheet": os.path.relpath(sheet),
                })

    os.makedirs(out_report, exist_ok=True)
    with open(os.path.join(out_report, "testset.json"), "w") as f:
        json.dump(rows, f, indent=1)
    _write_compare_plan(os.path.join(out_report, "TEST_PLAN.md"), rows, matrix)
    n_pass = sum(1 for r in rows if r["seam_flag"] == "PASS")
    print("\n%d compare sheets (%d seam-PASS, %d seam-FAIL) -> %s"
          % (len(rows), n_pass, len(rows) - n_pass, os.path.relpath(out_report)), flush=True)


def _write_compare_plan(path, rows, matrix):
    """Comparison TEST_PLAN: a matrix (which family the flag bites) + per-family PASS/FAIL sheet rows.
    Both columns share Tw=0 by construction -- the ONLY difference is the new seam flag, so folding a
    matched PASS/FAIL pair isolates exactly what the flag adds over the twist."""
    lines = [
        "# 3-stack seam-flag comparison test set (Tw=0 seam-PASS vs Tw=0 seam-FAIL)",
        "",
        "Every sheet here has **Tw=0** (the twist calls it foldable). They are split ONLY by the new",
        "seam flag — a real FOLD must return the END footprint onto the START footprint as a *rotational",
        "equivalent* (A->A, B->B, C->C, proper rotation, no mirror). The flag is enforced only on tiles",
        "with UNEQUAL sides (45-45-90 righttri, 30-60-90 scalene); equilateral + hex are edge-uniform so a",
        "mirror is invisible and exempt (both decomps).",
        "",
        "- **seam-PASS** -> predicted **FOLD**: fold it, expect it to seat flat as a 3-stack.",
        "- **seam-FAIL** -> predicted **JAM** (same Tw=0!): the END comes back mirrored/off-cell (short",
        "  seam onto long, or a tile flipped); fold it, expect it to jam. This is the case the twist",
        "  ALONE mislabels FOLD and the flag catches.",
        "",
        "Fold a matched PASS/FAIL pair in the same family to confirm the flag adds real signal.",
        "",
        "## Flag fingerprint (where the seam flag bites)",
        "",
        "| family | decomp | Tw=0 seam-PASS | Tw=0 seam-FAIL | flag bites? |",
        "|---|---|---|---|---|",
    ]
    for m in matrix:
        bites = "**YES**" if m["n_fail"] > 0 else ("no" if m["n_pass"] else "n/a (no Tw=0 fold)")
        lines.append("| %s | %s | %d | %d | %s |" % (
            m["tiling"], m["decomp"], m["n_pass"], m["n_fail"], bites))
    lines += [
        "",
        "Expected: the FAIL column is populated only on righttri/scalene 2+1 (unequal-sided tiles); every",
        "uniform family and all 1+1+1 show FAIL=0 (flag never bites). equilateral 1+1+1 is a proven",
        "obstruction, so it has no Tw=0 fold at all.",
        "",
        "## Sheets to fold",
        "",
        "| family | case | K | Tw | seam flag | predicted | expected | seam detail | ACTUAL |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append("| %s %s | %s | %d | %s | **%s** | %s | %s | %s |  |" % (
            r["tiling"], r["decomp"], r["case"], r["K"], _fmt_tw(r["tw"]),
            r["seam_flag"], r["predicted"], r["expected"], r["seam_detail"] or "-"))
    lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines))


def _fmt_tw(tw):
    """Compact twist label for the table (list for 1+1+1, scalar for 2+1)."""
    if isinstance(tw, (list, tuple)):
        return "0/0/0" if all(v == 0 for v in tw) else ",".join(str(v) for v in tw)
    return "%g" % tw if isinstance(tw, (int, float)) else str(tw)


def _write_test_plan(path, rows):
    n_fold = sum(1 for r in rows if r["predicted"] == "FOLDABLE")
    lines = [
        "# 3-stack foldability physical test set",
        "",
        "Print each foldsheet, cut the outer boundary, fold every marked crease (red=mountain,",
        "blue=valley), and check whether it seats flat as a 3-stack. Record the actual result in the",
        "last column and compare to the engine PREDICTION.",
        "",
        "## How to read the PREDICTION (from the 2026-07-01 gate audit)",
        "",
        "Every sheet here already passes the **physical closure gate** — 1+1+1 via `reflection_closes_111`,",
        "and 2+1 via the printed-sheet flat-fold simulator (`foldsim`: rigid dominoes + START hub, fold",
        "each crease, require all tiles to seat on {a,mid,b} with uniform K layers). The drawn sheet's",
        "cut/fold/rigid edges are exactly what that gate validates (sheet rigid == gate rigid: the END",
        "trapezoid is cut, not glued). That gate is the *authority*. The FOLD-vs-JAM *label* comes from",
        "the twist (Tw==0 => foldable), whose reliability varies — that is what your folding validates:",
        "",
        "- **PROVEN** — equilateral 1+1+1: validated solver, twist is XVAL-locked. Expect agreement.",
        "- **CLOSURE-PROVEN** — scalene / righttri 1+1+1: bipartite global-sigma, twist reliable but",
        "  not yet physically validated except the scalene K=16 anchor (ground truth = foldable).",
        "- **MODEL** — hex 1+1+1 and ALL 2+1: twist is DECORATIVE here (non-bipartite path-sigma /",
        "  2+1 strand-reduction). The audit measured ~99% twist false-JAM on hex 1+1+1 and both-way",
        "  disagreement on 2+1. Treat the FOLD/JAM here as a guess; the fold is the real answer. The",
        "  open question 'does triangle 2+1 seat as the model predicts' is resolved by THESE rows.",
        "",
        "%d cases: %d predicted FOLDABLE, %d predicted JAM." % (len(rows), n_fold, len(rows) - n_fold),
        "",
        "| family | case | K | predicted | trust | holes | foldsheet | ACTUAL (fold / jam) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append("| %s %s | %s | %d | **%s** | %s | %d | %s |  |" % (
            r["tiling"], r["decomp"], r["case"], r["K"], r["predicted"],
            r["trust"].split(" ")[0], r["holes"], os.path.basename(r["foldsheet"])))
    lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
