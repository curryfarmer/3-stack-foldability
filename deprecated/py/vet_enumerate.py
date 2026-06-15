"""vet_enumerate.py — render the COMPLETE set of distinct closing 3-stack fold candidates for a
grid, INCLUDING the ones the theory predicts JAM (the rejects the results/*.json files throw away).

Purpose: ground-truth the foldability predictor by exact match. The search keeps only candidates
that pass every gate; here we keep every candidate that *closes* (folds back to a footprint-shaped
3-stack = exit_footprint_check) and tag it by the gates it then passes/fails:

    predicted FOLD  iff  parity ∧ reflection ∧ (twist passes, or twist undecided [2+1])
    predicted JAM   otherwise  (filename records which gate failed: parity / refl / twist)

Dedup is the search's full D4 canonical hash (4 rot × 2 flip), applied across the whole closing
set — so no two sheets are rotations/reflections of each other, rejects included. Fold them all:
the physically-foldable subset should equal the FOLD-tagged subset exactly.

Usage:
  python vet_enumerate.py count            # just print counts for 6x4, 6x5
  python vet_enumerate.py                  # render 6x4, 6x5 -> report/foldsheets/vet/
  python vet_enumerate.py 8x6 9x4          # render the given grids
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "explainer"))
import search as S            # noqa: E402
import foldpattern as fp      # noqa: E402
import render_foldpath as rfp  # noqa: E402

OPTS = {"shapes": {"L": True, "Rect": True},
        "decomps": {"1+1+1": True, "2+1": True},
        "allowNonCorner": False, "dedup": True}
OUT_DIR = os.path.join(HERE, "..", "report", "foldsheets", "vet")


def enumerate_grid(m, n):
    """All distinct (D4-deduped) closing fold candidates, each tagged foldable + failing gates."""
    K = m * n // 3
    seen = {}
    results = []
    for footprint in S.enumerate_footprints(m, n, OPTS):
        for decomp in S.enumerate_decompositions(footprint, OPTS):
            ctx = {"nodeCount": 0, "candidateCount": 0, "coveredCount": 0, "cancelled": False}

            def on_candidate(chains, _fp=footprint, _dc=decomp):
                if not S.exit_footprint_check(chains, _fp["shape"]):
                    return                       # not a closing fold — outside the universe
                par = S.parity_check(chains)
                ref = S.reflection_check(chains)
                tw = S.twist_check(chains)       # decided only for all-1chain (1+1+1)
                h = S.canonical_hash(_fp, chains, m, n)
                if h in seen:
                    return
                seen[h] = True
                fails = []
                if not par:
                    fails.append("parity")
                if not ref:
                    fails.append("refl")
                if tw["decided"] and not tw["pass"]:
                    fails.append("twist")
                results.append({
                    "chains": [{"kind": c["kind"],
                                "baseCells": [{"x": b[0], "y": b[1]} for b in c["baseCells"]],
                                "foldArrows": list(c["foldArrows"])} for c in chains],
                    "shape": _fp["shape"], "decomp": _dc["decomp"], "hash": h,
                    "foldable": (par and ref and (not tw["decided"] or tw["pass"])),
                    "fails": fails,
                })

            S.search_decomposition(m, n, K, decomp, on_candidate, ctx)
    # FOLD first, then by shape/decomp/hash for stable ordering
    results.sort(key=lambda r: (not r["foldable"], r["shape"], r["decomp"], r["hash"]))
    return results, K


def render_grid_full(m, n, out_dir):
    res, K = enumerate_grid(m, n)
    grid = f"{m}x{n}"
    nfold = sum(r["foldable"] for r in res)
    os.makedirs(out_dir, exist_ok=True)
    for i, r in enumerate(res, 1):
        try:
            pat = fp.classify(r["chains"], m, n)
        except AssertionError as e:
            print(f"   skip {grid} cand {i}: {e}")
            continue
        verd = "FOLD" if r["foldable"] else "JAM-" + "+".join(r["fails"])
        pat["meta"] = {"m": m, "n": n, "id": i, "shape": r["shape"], "decomp": r["decomp"],
                       "canonicalHash": r["hash"], "K": K, "pred": verd}
        out = os.path.join(out_dir, f"{grid}_{i:02d}_{verd}_{r['shape']}_{r['decomp']}.png")
        rfp.render(pat, out)
        print(f"   {os.path.relpath(out)}")
    print(f"{grid}: {len(res)} distinct closing candidates  "
          f"({nfold} predicted FOLD, {len(res) - nfold} predicted JAM)")
    return res


def count_only(grids):
    for (m, n) in grids:
        res, K = enumerate_grid(m, n)
        nfold = sum(r["foldable"] for r in res)
        from collections import Counter
        jam = Counter("+".join(r["fails"]) for r in res if not r["foldable"])
        print(f"{m}x{n} K={K}: {len(res)} closing candidates  "
              f"FOLD={nfold}  JAM={len(res) - nfold}  jam-reasons={dict(jam)}")


def parse_grid(s):
    a, b = s.lower().split("x")
    return (int(a), int(b))


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "count":
        grids = [parse_grid(a) for a in args[1:]] or [(6, 4), (6, 5)]
        count_only(grids)
    else:
        grids = [parse_grid(a) for a in args] or [(6, 4), (6, 5)]
        for (m, n) in grids:
            render_grid_full(m, n, OUT_DIR)
        print(f"\ncomplete vet set -> {os.path.relpath(OUT_DIR)}/")
