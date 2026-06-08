"""analyze_loop_seams.py — validate the 1+1+1 pairwise-loop math (read-only).

Probes the two structural worries about the theta-graph pairwise twist:

  SEAM     each pairwise loop L_ij = path_i (S->E) + reversed path_j (E->S) closes
           through the two fused hubs with 2 seam steps:
             exit seam:  end(i)   -> end(j)     (index K-1 -> K)
             start seam: start(j) -> start(i)   (index 2K-1 -> 0, the wrap)
           For an L footprint one base pair is DIAGONAL ((0,1)~(1,0)); for Rect the
           far pair is a colinear 2-JUMP ((0,0)~(0,2)). Both break the unit-step
           checkerboard alternation. This script classifies every seam, dumps the
           doubled-turn terms at the 4 seam-flanking vertices, and checks whether
           the loop twist still lands on a multiple of 360 (i.e. the +-90/+-270
           artifacts cancel in the odd-even difference).

  RANK2    the theta graph has cycle rank 2 (L_BC = L_AB xor L_AC as edge sets), so
           "only 2 loops are independent" IF twist were additive over cycles. Checks:
             (a) cocycle  Tw01 - Tw02 + Tw12 == 0 ?  (holds iff additive)
             (b) per-chain contribution of the SHARED chain across its two loops
                 (additivity needs them equal; reversal needs them negated)
             (c) classifier accuracy when testing only 2 of the 3 loops vs stored
                 ground truth — does any 2-subset suffice?

Usage:  python analyze_loop_seams.py [resultsfile ...]   (default: all 3-stack results)
"""
import json
import sys
import glob
import os
from math import atan2, degrees, hypot

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fold        # noqa: E402
import search      # noqa: E402


def replay_placements(base_cells, fold_arrows, m, n):
    base = [(c["x"], c["y"]) for c in base_cells]
    pl = fold.initial_placement(base)
    placements = [pl]
    active = pl
    for d in fold_arrows:
        active = fold.make_fold(active, d, m, n)
        if active is None:
            raise ValueError(f"fold {d} left grid")
        placements.append(active)
    return placements


def center_path(placements):
    pts = []
    for p in placements:
        cs = p["cells"]
        k = len(cs) or 1
        pts.append((sum(c[0] + 0.5 for c in cs) / k, sum(c[1] + 0.5 for c in cs) / k))
    return pts


def classify_step(p, q):
    dx, dy = abs(q[0] - p[0]), abs(q[1] - p[1])
    if dx + dy == 1:
        return "unit"
    if dx == 1 and dy == 1:
        return "DIAG"
    if (dx == 0 and dy == 2) or (dx == 2 and dy == 0):
        return "2JMP"
    return "other(%g,%g)" % (dx, dy)


def loop_terms(path_a, path_b):
    """Replicate search._pair_loop_twist but return per-iteration doubled turns.
    Iteration i computes the turn AT vertex pts[(i+1)%n]; bucket = i%2 (even/odd)."""
    pts = path_a + list(reversed(path_b))
    n = len(pts)
    terms = []
    for i in range(n):
        p1, p2, p3 = pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        v1 = (p2[0] - p1[0], p2[1] - p1[1])
        v2 = (p3[0] - p2[0], p3[1] - p2[1])
        ang = 0
        if hypot(*v1) > 1e-9 and hypot(*v2) > 1e-9:
            dot = v1[0] * v2[0] + v1[1] * v2[1]
            cross = v1[0] * v2[1] - v1[1] * v2[0]
            ang = round(degrees(atan2(cross, dot)))
        terms.append(2 * ang)
    return pts, terms


def bucket_diff(terms, idxs=None):
    """odd-bucket sum minus even-bucket sum over the given iteration indices."""
    idxs = range(len(terms)) if idxs is None else idxs
    return sum(terms[i] if i % 2 else -terms[i] for i in idxs)


def analyze_file(f, dump_budget):
    data = json.load(open(f))
    if not isinstance(data, dict) or "meta" not in data or data["meta"].get("stacks") == 2:
        return None
    m, n = data["meta"]["m"], data["meta"]["n"]
    sols = [s for s in data["solutions"] if s["decomposition"] == "1+1+1"]
    if not sols:
        return None
    print("\n=== %s  %dx%d  1+1+1: %d ===" % (os.path.basename(f), m, n, len(sols)))
    stats = {"pairs": 0, "non360": 0, "cocycle_fail": 0, "n": 0,
             "seam_kinds": {}, "subset_wrong": [0, 0, 0], "stored_true": 0}
    for s in sols:
        chains = s["chains"]
        placements = [replay_placements(c["baseCells"], c["foldArrows"], m, n) for c in chains]
        paths = [center_path(pl) for pl in placements]
        K = len(paths[0])
        pw, seams = {}, {}
        for i in range(3):
            for j in range(i + 1, 3):
                pts, terms = loop_terms(paths[i], paths[j])
                tw = bucket_diff(terms)
                assert tw == search._pair_loop_twist(paths[i], paths[j])  # exact replica
                pw[(i, j)] = tw
                exit_k = classify_step(pts[K - 1], pts[K])
                start_k = classify_step(pts[2 * K - 1], pts[0])
                seams[(i, j)] = (exit_k, start_k)
                for kind in (exit_k, start_k):
                    stats["seam_kinds"][kind] = stats["seam_kinds"].get(kind, 0) + 1
                stats["pairs"] += 1
                if tw % 360 != 0:
                    stats["non360"] += 1
                # focused dump of seam-flanking terms for the first few interesting loops
                if dump_budget[0] > 0 and ("DIAG" in (exit_k, start_k)):
                    dump_budget[0] -= 1
                    # vertices at loop indices K-1,K (exit) and 2K-1,0 (start);
                    # vertex idx v is computed at iteration i = v-1 (mod n)
                    n2 = 2 * K
                    flank = [(v - 1) % n2 for v in (K - 1, K, 2 * K - 1, 0)]
                    seam_part = bucket_diff(terms, flank)
                    body_part = bucket_diff(terms, [i for i in range(n2) if i not in flank])
                    print("  DUMP %s #%-3s pair %d%d seams(exit=%s,start=%s) tw=%d" %
                          (s["footprint"]["shape"], s["id"], i, j, exit_k, start_k, tw))
                    print("       seam-flank doubled-turns %s -> odd-even seam part = %+d ; body part = %+d"
                          % ([terms[i2] for i2 in flank], seam_part, body_part))
        cocycle = pw[(0, 1)] - pw[(0, 2)] + pw[(1, 2)]
        if cocycle != 0:
            stats["cocycle_fail"] += 1
        stored = bool(s["verdict"]["twist"])
        stats["stored_true"] += stored
        stats["n"] += 1
        # (b) shared-chain contribution across its two loops (chain 0 in L01 vs L02)
        # (c) does any 2-loop subset reproduce the stored verdict?
        keys = [(0, 1), (0, 2), (1, 2)]
        for d, drop in enumerate(keys):
            verdict2 = all(pw[k] == 0 for k in keys if k != drop)
            if verdict2 != stored:
                stats["subset_wrong"][d] += 1
        if cocycle != 0:
            print("  RANK2 %s #%-3s pw=%s cocycle=%+d  (additivity violated; twisted pair varies)"
                  % (s["footprint"]["shape"], s["id"],
                     {"%d%d" % k: v for k, v in pw.items()}, cocycle))
    print("  -- %d sols, %d loops | non-360 twists: %d | cocycle fails: %d/%d | seams: %s"
          % (stats["n"], stats["pairs"], stats["non360"], stats["cocycle_fail"],
             stats["n"], stats["seam_kinds"]))
    print("  -- 2-loop-subset misclassifications (drop 01/02/12): %s  vs stored (true=%d/%d)"
          % (stats["subset_wrong"], stats["stored_true"], stats["n"]))
    return stats


def main(files):
    print("==== 1+1+1 pairwise-loop math: seam + rank-2 validation ====")
    dump_budget = [6]
    tot = {"pairs": 0, "non360": 0, "cocycle_fail": 0, "n": 0,
           "seam_kinds": {}, "subset_wrong": [0, 0, 0]}
    for f in files:
        r = analyze_file(f, dump_budget)
        if not r:
            continue
        for k in ("pairs", "non360", "cocycle_fail", "n"):
            tot[k] += r[k]
        for k, v in r["seam_kinds"].items():
            tot["seam_kinds"][k] = tot["seam_kinds"].get(k, 0) + v
        tot["subset_wrong"] = [a + b for a, b in zip(tot["subset_wrong"], r["subset_wrong"])]
    print("\n==== TOTAL (%d solutions, %d pairwise loops) ====" % (tot["n"], tot["pairs"]))
    print("seam step census                  : %s" % tot["seam_kinds"])
    print("loops with tw NOT mult of 360     : %d   (0 => seam artifacts cancel in odd-even)" % tot["non360"])
    print("cocycle Tw01-Tw02+Tw12 != 0       : %d   (>0 => twist NOT additive over cycle space)" % tot["cocycle_fail"])
    print("2-loop subsets misclassify        : drop01=%d drop02=%d drop12=%d  (all >0 => need all 3)"
          % tuple(tot["subset_wrong"]))


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        here = os.path.dirname(os.path.abspath(__file__))
        args = sorted(glob.glob(os.path.join(here, "..", "results", "*.json")))
    main(args)
