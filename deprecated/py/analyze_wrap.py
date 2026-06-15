"""analyze_wrap.py — perimeter-wrap hypothesis test.

Hypothesis (Q2): in every L-shaped solution, 2 of the 3 "chains" minimally WRAP the
outermost perimeter ring of the m x n grid; only the remaining chain solves the interior.

Method: replay each chain's folds (fold.py) -> its cell coverage. Compute the boundary
ring. For every solution report, per chain, how many cells sit on the ring, and test the
clean form of the hypothesis: does the interior chain touch the ring at all (0 = clean),
and do 2 chains alone cover the entire ring.

Usage:  python3 analyze_wrap.py [resultsfile ...]
        (default: all results/*.json that are 3-stack, i.e. no meta.stacks==2)
"""
import json
import sys
import glob
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fold  # noqa: E402


def chain_cells(base_cells, fold_arrows, m, n):
    """Union of all placement cells for one chain (base + each fold image)."""
    base = [(c["x"], c["y"]) for c in base_cells]
    pl = fold.initial_placement(base)
    cells = set(pl["cells"])
    active = pl
    for d in fold_arrows:
        active = fold.make_fold(active, d, m, n)
        if active is None:  # should not happen on a valid stored solution
            raise ValueError(f"fold {d} left grid")
        cells.update(active["cells"])
    return cells


def ring_cells(m, n):
    return {(x, y) for x in range(m) for y in range(n)
            if x == 0 or x == m - 1 or y == 0 or y == n - 1}


def analyze_solution(sol, m, n):
    ring = ring_cells(m, n)
    chains = []
    for ch in sol["chains"]:
        cs = chain_cells(ch["baseCells"], ch["foldArrows"], m, n)
        chains.append({
            "kind": ch["kind"],
            "cells": cs,
            "size": len(cs),
            "on_ring": len(cs & ring),
            "frac_ring": len(cs & ring) / len(cs),
        })
    # which 2 chains best cover the ring; is the third (interior) ring-free?
    nC = len(chains)
    best = None
    for skip in range(nC):
        union2 = set()
        for i in range(nC):
            if i != skip:
                union2 |= chains[i]["cells"]
        covers_ring = ring.issubset(union2)
        interior_ring_touch = chains[skip]["on_ring"]
        cand = {
            "interior_idx": skip,
            "interior_kind": chains[skip]["kind"],
            "two_cover_ring": covers_ring,
            "interior_ring_cells": interior_ring_touch,
            "interior_size": chains[skip]["size"],
        }
        # prefer: interior chain touches ring least, and the 2 cover the ring
        keyv = (not covers_ring, interior_ring_touch)
        if best is None or keyv < best[0]:
            best = (keyv, cand)
    return {
        "id": sol["id"],
        "shape": sol["footprint"]["shape"],
        "decomp": sol["decomposition"],
        "ring_size": len(ring),
        "chains": [{k: c[k] for k in ("kind", "size", "on_ring", "frac_ring")} for c in chains],
        "best_split": best[1],
        "clean_wrap": best[1]["two_cover_ring"] and best[1]["interior_ring_cells"] == 0,
    }


def main(files):
    for f in files:
        data = json.load(open(f))
        if not isinstance(data, dict) or "meta" not in data:
            continue  # skip manifest.json etc.
        meta = data["meta"]
        if meta.get("stacks") == 2:
            continue
        m, n = meta["m"], meta["n"]
        sols = [s for s in data["solutions"] if s["footprint"]["shape"] == "L"]
        ring = 2 * m + 2 * n - 4
        K = m * n // 3
        # min interior cells forced into the 2 wrap chains: 2K - ring (if positive)
        min_spill = max(0, 2 * K - ring)
        print(f"\n=== {os.path.basename(f)}  {m}x{n}  L-shaped solutions: {len(sols)} "
              f"(ring={ring} cells, K={K}, 2 wrap-chains=2K={2*K}, forced interior spill>={min_spill}) ===")
        if not sols:
            print("  (no L solutions)")
            continue
        by_decomp = {}
        for s in sols:
            r = analyze_solution(s, m, n)
            by_decomp.setdefault(r["decomp"], []).append(r)
            chain_desc = "  ".join(
                f"{c['kind']}:{c['on_ring']}/{c['size']}({c['frac_ring']*100:.0f}%ring)"
                for c in r["chains"])
            bs = r["best_split"]
            flag = "CLEAN-WRAP" if r["clean_wrap"] else (
                "2cover,interior-touches" if bs["two_cover_ring"] else "NO-2-cover")
            print(f"  #{r['id']:>2} {r['decomp']:<5} | {chain_desc:<60} | "
                  f"interior={bs['interior_kind']}(ring_touch={bs['interior_ring_cells']}) | {flag}")
        # summary
        for dec, rs in sorted(by_decomp.items()):
            clean = sum(1 for r in rs if r["clean_wrap"])
            cover = sum(1 for r in rs if r["best_split"]["two_cover_ring"])
            print(f"  -- {dec}: {len(rs)} sols | 2-chains-cover-ring: {cover}/{len(rs)} | "
                  f"clean-wrap (interior ring-free): {clean}/{len(rs)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        here = os.path.dirname(os.path.abspath(__file__))
        args = sorted(glob.glob(os.path.join(here, "..", "results", "*.json")))
    main(args)
