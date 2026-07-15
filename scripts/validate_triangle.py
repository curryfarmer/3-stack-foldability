"""scripts/validate_triangle.py — regression proof for the triangle engine.

Re-derives a FRESH FOLD/JAM verdict for every physically-tested triangle ground-truth record
straight from its stored geometry, using the CURRENT (post-cleanup) `triangle/tri/*.py` code, and
confirms it still agrees with the physical outcome John recorded (`actual.folded`). This is a
regression proof, not a search: nothing here re-derives geometry the record doesn't already carry
(except for the 2plus1 case, see `_recompute_21` below, where the pure re-search fallback is only
used if the direct recompute cannot be wired).

GROUND TRUTH SOURCE. Every `tri-fold/1` record under `report/tri/**/folds/*.json` whose
`actual.folded` is not None was physically folded by John (`actual` block == ground truth; the
`foldable` field on the record itself is just the stored verdict at write time — never trusted
directly, only used to build the CLI announcement of expected count). We glob recursively rather
than pinning to the two directories a first-pass investigation named (`mvp_matrix/` and
`k-stress/_calibration/`) because a third batch directory (`report/tri/righttri_k16/folds/`) also
holds a physically-tested record (`004e88bd6c9e`, the K>=14 45-45-90 confirmation) that is required
to reach the ground-truth doc's stated "22 fold-events" count — pinning to two directories yields
21, not 22 (see docs/research/GROUND_TRUTH_folds.md). Filtering on `actual.folded is not None`
(mirroring the square-side `foldable is not None` filter) is the correct, directory-independent
predicate; a raw glob of the two named directories also contains 5 stale untested placeholder
records (`actual.folded is None`) that must be excluded. With this predicate the recursive glob
yields exactly 22 records: 20 distinct uids + 2 uids folded once each in both the MVP matrix and
K-stress calibration batches (`22924cc0ef47`, `327ca6c4fc99`) — matching the doc exactly.

RECOMPUTE PIPELINE (per record; nothing here mutates any file on disk):
  1. lat = find_example.build_lat(tiling, decomp, K)   — rebuilds the exact ambient lattice (cheap,
     zero search cost: it takes [0] of a generator without ever calling next() on it).
  2. CLOSURE sanity check (must still be True for every real ground-truth record; a False here is a
     genuine regression signal, not merely a verdict disagreement, so it is reported as its own
     mismatch kind):
       - 1plus1plus1 : foldclose.reflection_closes_111(lat, chains)
       - 2plus1      : foldsim.valid_21(lat, strand, partners, one_chain, footprint, end_footprint)
         NOT foldclose.reflection_closes_21 — confirmed DEAD CODE by inspection: domino21.py's own
         docstring says foldsim.valid_21 "Replaces the old reflection_closes_21, which over-folded
         the rigid domino edge and admitted non-seating folds", and a repo-wide grep confirms
         reflection_closes_21 has zero live callers anywhere in triangle/. find_example.gen_21 (the
         actual 2plus1 candidate generator) never calls it either — the physical closure check for
         2plus1 lives inside domino21.enum_domino_21 via foldsim.valid_21. Using the dead function
         here was tried first and DOES fail on real closing folds (confirmed by hand on
         1ed623ab65ae): it is not merely unused, it is actively wrong post-refactor.
  3. TWIST verdict:
       - 1plus1plus1 : find_example.pairwise(chains, cent, "path") -> Tw==0 (rounded) on AB/BC/AC.
       - 2plus1      : tritwist.loop_twist(strand + list(reversed(one_chain)), cent=cent,
         sigma=tritwist.path_sigma(n)) -> |Tw| < 1e-6. This is the exact pure-math call
         domino21.enum_domino_21 itself makes on its `loop` (see domino21.py L80-81) — no full
         re-search needed, it is a pure function of the stored strand/one_chain geometry alone.
  4. seam_filter.apply(lat, cand) — demotes a twist-predicted FOLD to JAM on an off-cell arrival
     (the only non-cosmetic seam failure per the 2026-07-06 finding; mirror/proper chirality is
     cosmetic and never demotes).
  5. fresh verdict = cand["foldable"] after step 4; compared against `actual.folded`.

Run standalone from anywhere:  python scripts/validate_triangle.py
"""
import glob
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TRIANGLE_DIR = os.path.join(_REPO_ROOT, "triangle")
if _TRIANGLE_DIR not in sys.path:
    sys.path.insert(0, _TRIANGLE_DIR)
import _bootstrap  # noqa: E402  puts triangle/ (for `import lattice`) + triangle/tri on sys.path

FOLDS_GLOB = os.path.join(_REPO_ROOT, "report", "tri", "**", "folds", "*.json")


def _totuple(x):
    """Recursively turn JSON-decoded lists (tile ids, vertex coords) back into tuples, since the
    lattice code uses tile ids as dict keys / set members."""
    if isinstance(x, list):
        return tuple(_totuple(e) for e in x)
    return x


def _load_ground_truth():
    """Every physically-tested tri-fold/1 record, recursively, regardless of which batch directory
    it lives under. Returns (records, dirs_present) where dirs_present is False only when there is
    no report/tri/ directory at all (the graceful-skip signal for a fresh clone)."""
    report_tri = os.path.join(_REPO_ROOT, "report", "tri")
    if not os.path.isdir(report_tri):
        return [], False
    files = sorted(glob.glob(FOLDS_GLOB, recursive=True))
    records = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            rec = json.load(fh)
        rec["_file"] = os.path.relpath(f, _REPO_ROOT)
        records.append(rec)
    valid = [r for r in records if r.get("actual", {}).get("folded") is not None]
    return valid, True


def _recompute_111(FE, FC, rec):
    """Fresh (closure_ok, fresh_foldable) for a 1plus1plus1 record."""
    lat = FE.build_lat(rec["tiling"], rec["decomp"], rec["K"])
    chains = [[_totuple(t) for t in w] for w in rec["chains"]]
    footprint = [_totuple(t) for t in rec["footprint"]]
    end_footprint = [_totuple(t) for t in rec["end_footprint"]]

    closure_ok = FC.reflection_closes_111(lat, chains)

    cent = FE.GEN[rec["tiling"]]["cent"]
    loops = FE.pairwise(chains, cent, "path")
    tw = [round(loops[nm]["Tw"]) for nm in ("AB", "BC", "AC")]
    twist_ok = all(v == 0 for v in tw)

    cand = {"decomp": rec["decomp"], "chains": chains, "footprint": footprint,
            "end_footprint": end_footprint, "foldable": twist_ok}
    return lat, cand, closure_ok, tw


def _recompute_21(FE, FSIM, TW, rec):
    """Fresh (closure_ok, fresh_foldable) for a 2plus1 record."""
    lat = FE.build_lat(rec["tiling"], rec["decomp"], rec["K"])
    chains = [[_totuple(t) for t in w] for w in rec["chains"]]
    footprint = [_totuple(t) for t in rec["footprint"]]
    end_footprint = [_totuple(t) for t in rec["end_footprint"]]
    partners = [_totuple(t) for t in rec["partners"]]
    strand, one_chain = chains

    closure_ok, _diag = FSIM.valid_21(lat, strand, partners, one_chain, footprint, end_footprint)

    cent = FE.GEN[rec["tiling"]]["cent"]
    loop = list(strand) + list(reversed(one_chain))
    res = TW.loop_twist(loop, cent=cent, sigma=TW.path_sigma(len(loop)))
    twist_ok = abs(res["Tw"]) < 1e-6

    cand = {"decomp": rec["decomp"], "chains": chains, "footprint": footprint,
            "end_footprint": end_footprint, "partners": partners, "foldable": twist_ok}
    return lat, cand, closure_ok, res["Tw"]


def run():
    """Returns (n_agree, n_total, mismatches). n_total is None (skip signal) when no ground-truth
    data is present at all. `mismatches` is a list of dicts, each either a verdict disagreement
    (kind="verdict_disagree") or a closure-gate regression (kind="closure_gate_failed")."""
    records, dirs_present = _load_ground_truth()
    if not dirs_present or not records:
        return None, None, None

    import find_example as FE       # noqa: E402  lazy: keeps this module import-safe/side-effect-light
    import foldclose as FC          # noqa: E402
    import foldsim as FSIM          # noqa: E402
    import seam_filter as SFILT     # noqa: E402
    import tritwist as TW           # noqa: E402

    n_agree = 0
    mismatches = []
    for rec in records:
        uid = rec["uid"]
        tiling, decomp, K = rec["tiling"], rec["decomp"], rec["K"]
        actual = bool(rec["actual"]["folded"])
        try:
            if decomp == "1plus1plus1":
                lat, cand, closure_ok, detail = _recompute_111(FE, FC, rec)
            elif decomp == "2plus1":
                lat, cand, closure_ok, detail = _recompute_21(FE, FSIM, TW, rec)
            else:
                mismatches.append({"uid": uid, "file": rec["_file"], "kind": "unknown_decomp",
                                    "detail": decomp})
                continue
        except Exception as exc:  # noqa: BLE001 — surface as a mismatch, never crash the whole run
            mismatches.append({"uid": uid, "file": rec["_file"], "tiling": tiling, "decomp": decomp,
                                "K": K, "kind": "exception", "detail": repr(exc)})
            continue

        if not closure_ok:
            mismatches.append({"uid": uid, "file": rec["_file"], "tiling": tiling, "decomp": decomp,
                                "K": K, "kind": "closure_gate_failed",
                                "detail": "stored chains no longer close under the current gate"})

        SFILT.apply(lat, cand)
        fresh = bool(cand["foldable"])

        if fresh == actual:
            n_agree += 1
        else:
            mismatches.append({"uid": uid, "file": rec["_file"], "tiling": tiling, "decomp": decomp,
                                "K": K, "kind": "verdict_disagree", "fresh": fresh, "actual": actual,
                                "twist_detail": detail, "seam_detail": cand.get("seam_detail")})

    return n_agree, len(records), mismatches


if __name__ == "__main__":
    _json = "--json" in sys.argv[1:]
    n_agree, n_total, mismatches = run()
    if _json:
        # Machine-readable form consumed by scripts/phystest (the physical-testing suite). Exit
        # code matches the human form: 0 on PASS or SKIP, 1 only on a real mismatch.
        print(json.dumps({"engine": "triangle", "skipped": n_total is None,
                          "nAgree": n_agree, "nTotal": n_total,
                          "mismatches": mismatches or []}))
        sys.exit(1 if mismatches else 0)
    if n_total is None:
        print("triangle: SKIPPED (no ground-truth data present)")
        sys.exit(0)
    print("triangle: %d/%d agree (mismatches: %s)" % (n_agree, n_total, mismatches))
    sys.exit(0 if not mismatches else 1)
