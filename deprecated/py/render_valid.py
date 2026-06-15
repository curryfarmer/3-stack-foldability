"""render_valid.py — path fold-sheets for every predicted-FOLD pattern of a grid.

Enumerates all closing candidates with allowNonCorner=True, keeps those that pass the FULL fold
gate (parity + corrected reflection + twist), and renders each as a path sheet via
render_foldpath.render. Footprint anchor (corner / edge / interior) is encoded in the filename.

  python render_valid.py 6x4 6x5        # all predicted-FOLD sheets for each grid
  python render_valid.py 6x6 --2plus1 1 # ONE valid 2+1 sheet for 6x6 (prefers non-corner)

Names: <m>x<n>_fold_<NN>_<decomp>_<anchor>.png   (e.g. 6x4_fold_03_2p1_edge.png)
Prints every written path (one per line) so the caller knows the keep-set.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "explainer"))
import search as S          # noqa: E402
import foldpattern as fp    # noqa: E402
import render_foldpath as rfp  # noqa: E402

OUT = os.path.join(HERE, "..", "report", "foldsheets")
_OPTS = {"shapes": {"L": True, "Rect": True}, "decomps": {"1+1+1": True, "2+1": True},
         "allowNonCorner": True, "dedup": True}


def _anchor(cells, m, n):
    corners = {(0, 0), (m - 1, 0), (0, n - 1), (m - 1, n - 1)}
    onbound = lambda c: c[0] in (0, m - 1) or c[1] in (0, n - 1)
    if any(c in corners for c in cells):
        return "corner"
    if any(onbound(c) for c in cells):
        return "edge"
    return "interior"


def valid_candidates(m, n):
    """All distinct predicted-FOLD candidates for (m,n): (decomp, anchor, shape, chains-dicts)."""
    K = m * n // 3
    seen = {}
    out = []
    for footprint in S.enumerate_footprints(m, n, _OPTS):
        for decomp in S.enumerate_decompositions(footprint, _OPTS):
            ctx = {"nodeCount": 0, "candidateCount": 0, "coveredCount": 0, "cancelled": False}

            def on_candidate(chains, _fp=footprint):
                if not S.exit_footprint_check(chains, _fp["shape"]):
                    return
                h = S.canonical_hash(_fp, chains, m, n)
                if h in seen:
                    return
                seen[h] = True
                par = S.parity_check(chains)
                ref = S.reflection_check(chains)
                tw = S.twist_check(chains)
                fold = par and ref and (not tw["decided"] or tw["pass"])
                if not fold:
                    return
                sizes = sorted((len(c["baseCells"]) for c in chains), reverse=True)
                dec = "2+1" if sizes == [2, 1] else "1+1+1"
                anc = _anchor([tuple(c) for c in _fp["cells"]], m, n)
                cd = [{"kind": c["kind"],
                       "baseCells": [{"x": b[0], "y": b[1]} for b in c["baseCells"]],
                       "foldArrows": list(c["foldArrows"])} for c in chains]
                out.append((dec, anc, _fp["shape"], cd))

            S.search_decomposition(m, n, K, decomp, on_candidate, ctx)
    return out


def render_one(m, n, dec, anc, shape, chains, idx):
    pat = fp.classify(chains, m, n)
    pat["meta"] = {"m": m, "n": n, "id": f"{idx:02d}", "shape": shape, "decomp": dec,
                   "K": m * n // 3, "physical": "predicted FOLD (untested)"}
    name = f"{m}x{n}_fold_{idx:02d}_{dec.replace('+', 'p')}_{anc}.png"
    path = os.path.join(OUT, name)
    rfp.render(pat, path)
    return path


def render_grid(m, n):
    cands = valid_candidates(m, n)
    paths = []
    for i, (dec, anc, shape, chains) in enumerate(cands, 1):
        paths.append(render_one(m, n, dec, anc, shape, chains, i))
    return paths


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--2plus1" in args:
        gi = args.index("--2plus1")
        grid = args[gi - 1]
        m, n = (int(v) for v in grid.split("x"))
        cands = [c for c in valid_candidates(m, n) if c[0] == "2+1"]
        if not cands:
            print(f"NO valid 2+1 for {grid}")
            sys.exit(0)
        pick = next((c for c in cands if c[1] != "corner"), cands[0])
        print("wrote", render_one(m, n, pick[0], pick[1], pick[2], pick[3], 1))
    else:
        for grid in args:
            m, n = (int(v) for v in grid.split("x"))
            for p in render_grid(m, n):
                print("wrote", p)
