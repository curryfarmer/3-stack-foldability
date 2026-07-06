"""k_stress.py — exhaustive per-K stress census of 3-stack folds (TWIST-CENTRIC).

The START<->END seam gate is UNDER REVIEW (refuted 2026-07-05 by physical folds: 327ca6c4fc99, an
engine "all-mirror -> JAM", folds flat). So this harness classifies folds by the TWIST label + the
physical CLOSURE gate ONLY, and reports the seam chirality class as a raw ANNOTATION — never as a
jam. It answers the user's question directly: for each grid and decomposition, marching K, how many
closing folds exist, how many the twist calls foldable (Tw=0), and what their chirality distribution
is — plus a curated CALIBRATION BATCH of physical fold sheets (righttri-heavy, spanning K parity x
chirality class x decomp) whose folding will settle whether a "mirror" arrival jams or merely seats
with the printed seam flipped.

Reuses (no reinvention): find_example.gen_21 / gen_111 / gen_eq / render_case / KPLAN / verdict_text;
gen_testset._dedup_key / fold_uid / _fold_record; hunt_foldable.holes; seam_filter.tile_chirality.
No engine-math file is touched.

Output tree: report/tri/k-stress/
  <tiling>/<decomp>/summary.md + summary.json     per-family per-K counts + sampled example uids
  _calibration/foldsheet_<uid>.png + folds/<uid>.json + FOLD_LOG.md   sheets for the user to fold
  INDEX.md                                          aggregate of all 8 families

  python py/tri/k_stress.py [--kcap 20] [--hubs 8] [--budget 180] [--sample 3]
                            [--families righttri:2plus1 scalene:1plus1plus1 ...] [--no-batch]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_example as FE     # noqa: E402
import gen_testset as GT      # noqa: E402  _dedup_key / fold_uid / _fold_record
import hunt_foldable as HF    # noqa: E402
import seam_filter as SFILT   # noqa: E402  tile_chirality (ANNOTATION only — not applied as a gate)

TILINGS = ("equilateral", "righttri", "scalene", "hex")
DECOMPS = ("1plus1plus1", "2plus1")
KLASSES = ("all-proper", "all-mirror", "mixed", "off-cell", "uniform", "n/a")

KSTRESS = os.path.join(FE._REPORT_BASE, "k-stress")


def _gen(tiling, decomp, K, hubs):
    """(lat, iterator) for one (tiling, decomp, K). 2+1 sweeps `hubs` central hubs; 1+1+1 is
    single-hub by construction (flagged in the summary caveats)."""
    if decomp == "2plus1":
        return FE.gen_21(tiling, K, hubs=hubs)
    if tiling == "equilateral":
        return FE.gen_eq(decomp, K)
    return FE.gen_111(tiling, K, hub=None)


def _tw0(cand):
    """Twist label BEFORE any seam gate (as the generators emit it)."""
    return bool(cand["foldable"])


# equilateral 1+1+1 is the ONLY family with a hard solver parity constraint: SF.record_111 asserts
# Tw is a multiple of 360, which holds only at even K (KPLAN step 2). Every other family routes through
# gen_111/gen_21 (no such assert) and is marched by 1 to cover BOTH K parities.
def _k_step(tiling, decomp):
    return 2 if (tiling, decomp) == ("equilateral", "1plus1plus1") else 1


def census_family(tiling, decomp, kcap, hubs, budget, sample):
    """March K from the KPLAN start to kcap (step 1, except equilateral 1+1+1 which is even-K only)
    under `budget` seconds. Returns (per_k_rows, samples, caveats). Counts are DEDUPED within each K.
    Chirality is a read-only annotation via seam_filter.tile_chirality (klass in KLASSES)."""
    K0, _step, _pc = FE.KPLAN[(tiling, decomp)]
    step = _k_step(tiling, decomp)
    interior_deg = 6 if tiling == "hex" else 3
    rows, samples = [], []
    t0 = time.time()
    capped = False
    for K in range(K0, kcap + 1, step):
        if time.time() - t0 > budget:
            capped = True
            break
        lat, gen = _gen(tiling, decomp, K, hubs)
        seen = set()
        tally = {k: 0 for k in KLASSES}
        tw0_tally = {k: 0 for k in KLASSES}
        n_close = n_tw0 = 0
        k_samples = {"tw0": [], "twN": []}
        k_partial = False
        try:
            for cand in gen:
                key = GT._dedup_key(cand)
                if key in seen:
                    continue
                seen.add(key)
                n_close += 1
                tw0 = _tw0(cand)
                chir = SFILT.tile_chirality(lat, cand)
                klass = chir["klass"] if chir["klass"] in tally else "n/a"
                tally[klass] += 1
                if tw0:
                    n_tw0 += 1
                    tw0_tally[klass] += 1
                bucket = "tw0" if tw0 else "twN"
                if len(k_samples[bucket]) < sample:
                    cand["holes"] = len(HF.holes(lat, cand["region"], interior_deg))
                    uid = GT.fold_uid(tiling, decomp, cand)
                    k_samples[bucket].append(_sample_rec(uid, tiling, decomp, K, cand, chir))
                if time.time() - t0 > budget:
                    k_partial = capped = True
                    break
        except AssertionError as e:                 # solver rejected this K parity (eq 1+1+1) — skip it
            print("   skip %s %s K=%d: %s" % (tiling, decomp, K, e), flush=True)
            continue
        rows.append({
            "K": K, "closing": n_close, "tw0": n_tw0, "twN": n_close - n_tw0,
            "klass": tally, "tw0_klass": tw0_tally, "partial": k_partial,
        })
        samples.extend(k_samples["tw0"] + k_samples["twN"])
    caveats = []
    if decomp == "1plus1plus1":
        caveats.append("1+1+1 enumerates ONE central hub -> counts are exhaustive WITHIN that hub, "
                       "not over all hubs of the lattice.")
    else:
        caveats.append("2+1 sweeps the %d most-central hubs (--hubs)." % hubs)
    if capped:
        caveats.append("BUDGET CAP hit (%.0fs): the last K row (and any K above it) is PARTIAL — "
                       "counts are a lower bound." % budget)
    caveats.append("counts deduped within each K by canonical id-set; chirality is a read-only "
                   "annotation, NOT applied as a jam (seam gate under review).")
    return rows, samples, caveats


def _sample_rec(uid, tiling, decomp, K, cand, chir):
    """Compact per-example record (no cartesian geometry — the calibration batch stores the full
    render-source record; these are just pointers for the summary)."""
    tw = cand.get("tw")
    return {
        "uid": uid, "tiling": tiling, "decomp": decomp, "K": K,
        "tw0": _tw0(cand), "tw": tw, "tw_desc": cand.get("tw_desc"),
        "seam_klass": chir["klass"], "single_motion": chir["single_motion"],
        "symmetry": chir["symmetry"], "holes": cand.get("holes"),
    }


def _write_family(tiling, decomp, rows, samples, caveats):
    out = os.path.join(KSTRESS, tiling, decomp)
    os.makedirs(out, exist_ok=True)
    tot_close = sum(r["closing"] for r in rows)
    tot_tw0 = sum(r["tw0"] for r in rows)
    lead = next((s for s in samples if s["tw0"]), None)
    summ = {
        "tiling": tiling, "decomp": decomp,
        "K_range": [rows[0]["K"], rows[-1]["K"]] if rows else None,
        "total_closing": tot_close, "total_tw0": tot_tw0,
        "valid_pattern_found": tot_tw0 > 0,
        "lead_tw0_example": lead,
        "per_k": rows, "samples": samples, "caveats": caveats,
    }
    with open(os.path.join(out, "summary.json"), "w") as f:
        json.dump(summ, f, indent=1)

    L = ["# k-stress: %s / %s" % (tiling, decomp), "",
         "**Twist-centric** census (seam gate under review -> chirality is annotation only). Totals: "
         "**%d closing**, **%d Tw=0** (twist-foldable) over K=%s."
         % (tot_close, tot_tw0, "%d..%d" % (rows[0]["K"], rows[-1]["K"]) if rows else "-"), ""]
    if tot_tw0:
        L.append("Valid pattern (Tw=0 closing fold) EXISTS. Lead example: `%s` (K=%d, seam=%s)."
                 % (lead["uid"], lead["K"], lead["seam_klass"]))
    else:
        L.append("**No Tw=0 fold found** in this range — every closing fold twist-jams.")
    L += ["", "## Per-K counts", "",
          "| K | closing | Tw=0 | Tw!=0 | all-proper | all-mirror | mixed | off-cell | uniform | n/a | Tw=0 breakdown |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        kk = r["klass"]
        tw0b = ",".join("%s:%d" % (k, r["tw0_klass"][k]) for k in KLASSES if r["tw0_klass"][k])
        flag = " *(partial)*" if r["partial"] else ""
        L.append("| %d%s | %d | %d | %d | %d | %d | %d | %d | %d | %d | %s |" % (
            r["K"], flag, r["closing"], r["tw0"], r["twN"],
            kk["all-proper"], kk["all-mirror"], kk["mixed"], kk["off-cell"], kk["uniform"], kk["n/a"],
            tw0b or "-"))
    L += ["", "## Sampled example uids", "",
          "| uid | K | Tw=0 | seam class | single_motion | tw_desc |",
          "|---|---|---|---|---|---|"]
    for s in samples:
        L.append("| `%s` | %d | %s | %s | %s | %s |" % (
            s["uid"], s["K"], s["tw0"], s["seam_klass"], s["single_motion"], s["tw_desc"]))
    L += ["", "## Caveats", ""] + ["- %s" % c for c in caveats] + [""]
    with open(os.path.join(out, "summary.md"), "w") as f:
        f.write("\n".join(L))
    return summ


def _write_index(summaries):
    os.makedirs(KSTRESS, exist_ok=True)
    L = ["# 3-stack K-stress — exhaustive per-K census (all families)", "",
         "Twist-centric (the seam gate is under review; chirality is annotation only). Each cell links "
         "to `<tiling>/<decomp>/summary.md`.", "",
         "| family | K range | closing | Tw=0 | valid pattern? | lead Tw=0 uid |",
         "|---|---|---|---|---|---|"]
    for s in summaries:
        lead = s["lead_tw0_example"]
        L.append("| %s %s | %s | %d | %d | %s | %s |" % (
            s["tiling"], s["decomp"],
            "%d..%d" % tuple(s["K_range"]) if s["K_range"] else "-",
            s["total_closing"], s["total_tw0"],
            "**YES**" if s["valid_pattern_found"] else "no",
            ("`%s` (K=%d)" % (lead["uid"], lead["K"])) if lead else "-"))
    L += ["", "## The righttri question", "",
          "Tw=0 righttri folds are EVEN-K only (a twist fact, gate-independent). Every one is engine-"
          "labelled `all-mirror`, yet `327ca6c4fc99` (K=4) folds flat. The `_calibration/` batch folds "
          "several distinct even-K righttri Tw=0 sheets so physics can decide: does a mirror arrival "
          "JAM, or seat flat with the printed seam flipped? See `_calibration/FOLD_LOG.md`.", ""]
    with open(os.path.join(KSTRESS, "INDEX.md"), "w") as f:
        f.write("\n".join(L))


def build_calibration_batch(summaries, hubs, per_class=2, kspan=14):
    """Render a righttri/scalene batch of DISTINCT Tw=0 sheets for the user to physically fold. The
    selector is CHIRALITY-CLASS DIVERSE: up to `per_class` Tw=0 folds of EACH seam class (all-mirror
    AND all-proper) per (decomp), so the batch contrasts the two classes — the whole point of the
    calibration. all-proper Tw=0 folds live at ODD K (and only exist on scalene; righttri odd-K has no
    Tw=0), so the K window is widened to `kspan`. Each sheet is engine-labelled but the seam gate is
    NOT applied — the fold outcome is the experiment. Re-enumerates to recover full cand geometry."""
    cal = os.path.join(KSTRESS, "_calibration")
    folds_dir = os.path.join(cal, "folds")
    os.makedirs(folds_dir, exist_ok=True)
    FE.set_outdir(os.path.join("k-stress", "_calibration"))     # park renders here

    wanted = [("righttri", "2plus1"),       # CLEANEST test: 2+1 strand-twist is reliable (incl. 327ca/9c7a twins)
              ("righttri", "1plus1plus1"),  # confounded: Tw=0 label itself unreliable here (22924 physically twisted)
              ("scalene", "2plus1"),        # asymmetric tile — has BOTH classes (even-K mirror, odd-K proper)
              ("scalene", "1plus1plus1")]
    rows = []
    for tiling, decomp in wanted:
        K0, _s, _c = FE.KPLAN[(tiling, decomp)]
        got = {}                            # (decomp, klass) -> count
        stall = 0                           # consecutive scanned-K that added nothing new
        for K in range(K0, K0 + kspan):
            if all(got.get((decomp, kl), 0) >= per_class for kl in ("all-mirror", "all-proper")):
                break
            # A missing chirality class never materialises (parity law: all-mirror<->even K,
            # all-proper<->odd K; some families have only one). Bail after a stall so we don't
            # march the whole K-window rendering-scanning for a class that cannot appear.
            if stall >= 6:
                print("   .. %s/%s: stall (no new class in 6 K) -> stop at K=%d" % (
                    tiling, decomp, K), flush=True)
                break
            before = sum(got.values())
            lat, gen = _gen(tiling, decomp, K, hubs)
            seen = set()
            scanned = 0
            for cand in gen:
                if scanned >= 1200:
                    break
                key = GT._dedup_key(cand)
                if key in seen:
                    continue
                seen.add(key)
                scanned += 1
                if not _tw0(cand):
                    continue
                chir = SFILT.tile_chirality(lat, cand)
                klass = chir["klass"]
                if klass not in ("all-mirror", "all-proper"):
                    continue
                if got.get((decomp, klass), 0) >= per_class:
                    continue
                interior_deg = 6 if tiling == "hex" else 3
                cand["holes"] = len(HF.holes(lat, cand["region"], interior_deg))
                uid = GT.fold_uid(tiling, decomp, cand)
                verdict = FE.verdict_text(cand)                 # twist verdict (no seam demotion)
                try:
                    over, sheet, _v = FE.render_case(tiling, decomp, "allow", lat, K, cand,
                                                     name_stem=uid)
                except Exception as e:
                    print("   !! calib render failed %s %s K=%d: %s" % (tiling, uid, K, e), flush=True)
                    continue
                rec = GT._fold_record(uid, tiling, decomp, K, "calibration", cand, chir, verdict,
                                      over, sheet)
                rec["under_review"] = True
                with open(os.path.join(folds_dir, "%s.json" % uid), "w") as f:
                    json.dump(rec, f, indent=1)
                got[(decomp, klass)] = got.get((decomp, klass), 0) + 1
                rows.append({"uid": uid, "tiling": tiling, "decomp": decomp, "K": K,
                             "seam_klass": klass, "single_motion": chir["single_motion"],
                             "symmetry": chir["symmetry"], "tw_desc": cand.get("tw_desc"),
                             "foldsheet": os.path.basename(sheet)})
            stall = 0 if sum(got.values()) > before else stall + 1
    _write_fold_log(cal, rows)
    print("   calibration batch: %d sheets -> %s" % (len(rows), os.path.relpath(cal)), flush=True)
    return rows


def _write_fold_log(cal, rows):
    L = ["# K-stress calibration batch — physical fold log", "",
         "Each sheet is a **Tw=0** (twist-foldable) closing fold. The seam gate is NOT applied here —",
         "**folding these is the experiment** that settles whether a 'mirror' arrival JAMs or seats",
         "flat with the printed long/short seam flipped. Print `foldsheet_<uid>.png`, fold every marked",
         "crease, and record: does it seat flat as a 3-stack? do the printed START/END seams line up?", "",
         "**Cleanest test = the `righttri 2plus1` rows** (the 2+1 strand-twist is the reliable twist "
         "model; includes the `327ca6c4fc99`/`9c7a328f55fb` mirror TWINS — fold both, they must agree). "
         "If every `all-mirror` righttri-2+1 sheet folds flat like `327ca` did, then mirror != jam and "
         "the seam gate should become a cosmetic annotation.",
         "",
         "**Caveat on `righttri 1plus1plus1`:** the Tw=0 label itself is unreliable there — `22924cc0ef47` "
         "is engine-Tw=0 yet you saw it physically twist. A jam on those rows may be unmodeled twist, not "
         "seam, so treat them as secondary.",
         "",
         "**`all-proper` vs `all-mirror`:** all-proper Tw=0 folds exist only on **scalene at ODD K** "
         "(righttri odd-K has no Tw=0). Folding a scalene all-proper next to a scalene all-mirror is the "
         "direct class contrast.", "",
         "| uid | family | K | parity | engine seam class | single_motion | predicted (twist) | SEATS FLAT? | SEAMS MATCH? |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: (x["tiling"], x["decomp"], x["seam_klass"], x["K"])):
        parity = "even" if r["K"] % 2 == 0 else "odd"
        L.append("| `%s` | %s %s | %d | %s | %s | %s | FOLDABLE (Tw=0) |  |  |" % (
            r["uid"], r["tiling"], r["decomp"], r["K"], parity,
            r["seam_klass"], r["single_motion"]))
    L.append("")
    with open(os.path.join(cal, "FOLD_LOG.md"), "w") as f:
        f.write("\n".join(L))


def main():
    ap = argparse.ArgumentParser(description="exhaustive per-K stress census (twist-centric)")
    ap.add_argument("--kcap", type=int, default=20, help="march K up to this per family (default 20)")
    ap.add_argument("--hubs", type=int, default=8, help="2+1 central hubs to sweep (default 8)")
    ap.add_argument("--budget", type=float, default=180.0, help="per-family seconds (default 180)")
    ap.add_argument("--sample", type=int, default=3, help="example uids kept per (K, tw0/twN)")
    ap.add_argument("--families", nargs="+", default=None,
                    help="subset like righttri:2plus1 (default: all 8)")
    ap.add_argument("--no-batch", action="store_true", help="skip the calibration fold batch")
    ap.add_argument("--batch-only", action="store_true",
                    help="skip the census, just (re)build the calibration fold batch")
    args = ap.parse_args()

    if args.batch_only:
        print("=== calibration batch (batch-only) ===", flush=True)
        build_calibration_batch(None, args.hubs)
        print("\nK-stress -> %s" % os.path.relpath(KSTRESS), flush=True)
        return

    families = ([tuple(f.split(":")) for f in args.families] if args.families
                else [(t, d) for t in TILINGS for d in DECOMPS])
    summaries = []
    for tiling, decomp in families:
        print("=== %s / %s (K-stress, kcap=%d, budget=%.0fs) ===" % (tiling, decomp, args.kcap, args.budget),
              flush=True)
        t0 = time.time()
        rows, samples, caveats = census_family(tiling, decomp, args.kcap, args.hubs, args.budget, args.sample)
        summ = _write_family(tiling, decomp, rows, samples, caveats)
        summaries.append(summ)
        print("   closing=%d Tw=0=%d  valid=%s  (%.0fs)" % (
            summ["total_closing"], summ["total_tw0"], summ["valid_pattern_found"], time.time() - t0),
            flush=True)
    _write_index(summaries)
    if not args.no_batch:
        print("=== calibration batch ===", flush=True)
        build_calibration_batch(summaries, args.hubs)
    print("\nK-stress -> %s" % os.path.relpath(KSTRESS), flush=True)


if __name__ == "__main__":
    main()
