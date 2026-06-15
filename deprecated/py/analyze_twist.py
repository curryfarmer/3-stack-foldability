"""analyze_twist.py — validate the 1+1+1 twist criterion against the results cache.

What this checks (read-only post-processing over results/*.json, no engine change):

  ORACLE   the validated turn-angle primitive on the 2-stack cases (O1 2x4 => Tw=0,
           O2 3x3-hole => Tw=+1), via twostack.twist_value.

  CORRECT  the pairwise-loop criterion (== search.py twist_check, the shipped code):
               for the theta graph (2 fused hubs + 3 one-chains), each unordered pair {i,j}
               closes a 2-stack-style loop L_ij = chain_i forward + chain_j reversed; its
               closed-loop twist is Tw(i,j) = _pair_loop_twist(path_i, path_j).
               foldable(1+1+1)  <=>  Tw(i,j) = 0 for ALL THREE pairs.
           Rebuilt here from scratch (replay folds -> centroids -> _pair_loop_twist) and
           compared to the stored verdict.twist; expected 100% match.

  C1-TEST  the EXPLAINER s2.5 PROPOSAL  T_i = sum_{interior corners} sigma(v) gamma(v),
           sigma=(-1)^(x+y),  foldable <=> T_A = T_B = T_C.
           This DISAGREES with ground truth, and the disagreement is structural, not a bug:
           if Tw(i,j) = T_i - T_j held, the three pairwise twists would be a COBOUNDARY and
           must satisfy the cocycle  Tw(0,1) - Tw(0,2) + Tw(1,2) = 0.  On twisted solutions
           the pairwise pattern is e.g. {01:0, 02:0, 12:720} => cocycle = 720 != 0.  No
           per-chain T can reproduce that, so T_A=T_B=T_C is provably NOT the criterion.
           (Twist is a closed-loop invariant, not a homology class: although the theta graph
           has cycle rank 2, twist is not additive over cycle sums, so all THREE pairwise
           loops must be tested, not just an independent two.)

Usage:  python3 analyze_twist.py [resultsfile ...]   (default: all 3-stack results/*.json)
"""
import json
import sys
import glob
import os
from math import atan2, degrees

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fold        # noqa: E402
import search      # noqa: E402  (reuse _pair_loop_twist — the shipped pairwise primitive)
import twostack    # noqa: E402  (reuse twist_value — the validated closed-loop primitive)


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


def signed_turn_deg(p1, p2, p3):
    v1 = (p2[0] - p1[0], p2[1] - p1[1])
    v2 = (p3[0] - p2[0], p3[1] - p2[1])
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    cross = v1[0] * v2[1] - v1[1] * v2[0]
    return round(degrees(atan2(cross, dot)))


def chain_twist_global_sigma(placements):
    """EXPLAINER s2.5 proposal: per-chain interior-corner sum with global sigma."""
    pts = center_path(placements)
    T = 0
    for k in range(1, len(pts) - 1):
        gamma = 2 * signed_turn_deg(pts[k - 1], pts[k], pts[k + 1])
        if gamma == 0:
            continue
        cell = placements[k]["cells"][0]
        sigma = 1 if (cell[0] + cell[1]) % 2 == 0 else -1
        T += sigma * gamma
    return T


def oracle_twostack():
    tw_2x4 = [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (2, 1), (1, 1), (0, 1)]
    ring_3x3 = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2), (1, 2), (0, 2), (0, 1)]
    v1 = twostack.twist_value(tw_2x4)
    v2 = twostack.twist_value(ring_3x3)
    ok = (v1 == 0) and (abs(v2) == 720)
    print("ORACLE  O1 2x4=%s (exp 0)   O2 3x3-hole=%s (exp +/-720)   %s"
          % (v1, v2, "PASS" if ok else "FAIL"))
    return ok


def analyze_file(f):
    data = json.load(open(f))
    if not isinstance(data, dict) or "meta" not in data:
        return None
    meta = data["meta"]
    if meta.get("stacks") == 2:
        return None
    m, n = meta["m"], meta["n"]
    sols = [s for s in data["solutions"] if s["decomposition"] == "1+1+1"]
    if not sols:
        return None
    print("\n=== %s  %dx%d  1+1+1: %d ===" % (os.path.basename(f), m, n, len(sols)))
    n_correct = n_c1 = n_cocycle_hold = 0
    for s in sols:
        chains = s["chains"]
        placements = [replay_placements(c["baseCells"], c["foldArrows"], m, n) for c in chains]
        paths = [center_path(pl) for pl in placements]

        # CORRECT criterion: all three pairwise loops zero (rebuilt from scratch)
        pw = {}
        for i in range(len(chains)):
            for j in range(i + 1, len(chains)):
                pw[(i, j)] = search._pair_loop_twist(paths[i], paths[j])
        correct_pass = all(v == 0 for v in pw.values())

        # C1 proposal: per-chain agreement
        Ts = [chain_twist_global_sigma(pl) for pl in placements]
        c1_pass = all(t == Ts[0] for t in Ts)

        # cocycle obstruction (would-be coboundary check on the pairwise values)
        cocycle = pw[(0, 1)] - pw[(0, 2)] + pw[(1, 2)]
        cocycle_holds = (cocycle == 0)

        stored = bool(s["verdict"]["twist"])
        n_correct += (correct_pass == stored)
        n_c1 += (c1_pass == stored)
        n_cocycle_hold += cocycle_holds

        flag = "ok " if (correct_pass == stored and c1_pass == stored) else "** "
        print("  %s#%-3s %-4s pw=%-26s correct=%-5s | C1 T=%-18s C1pass=%-5s | cocycle=%-4s | stored=%s"
              % (flag, s["id"], s["footprint"]["shape"],
                 str({"%d%d" % k: v for k, v in pw.items()}), correct_pass,
                 str(Ts), c1_pass, cocycle, stored))
    N = len(sols)
    print("  -- CORRECT(all-pairs-0) == stored: %d/%d | C1(T_A=T_B=T_C) == stored: %d/%d | cocycle holds: %d/%d"
          % (n_correct, N, n_c1, N, n_cocycle_hold, N))
    return (n_correct, n_c1, n_cocycle_hold, N)


def main(files):
    print("==== 1+1+1 twist criterion validation ====")
    oracle_ok = oracle_twostack()
    tc = tcc = tco = tot = 0
    for f in files:
        r = analyze_file(f)
        if r:
            tc += r[0]; tcc += r[1]; tco += r[2]; tot += r[3]
    print("\n==== TOTAL (%d 1+1+1 solutions) ====" % tot)
    print("oracle O1/O2                        : %s" % ("PASS" if oracle_ok else "FAIL"))
    print("CORRECT (all 3 pairwise loops = 0)  : %d/%d  %s" % (tc, tot, "PASS" if tc == tot else "FAIL"))
    print("C1  (T_A=T_B=T_C, EXPLAINER s2.5)   : %d/%d  %s" % (tcc, tot, "matches" if tcc == tot else "DISPROVEN"))
    print("cocycle Tw01-Tw02+Tw12==0 holds     : %d/%d  (fails => no per-chain T exists => C1 impossible)" % (tco, tot))


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        here = os.path.dirname(os.path.abspath(__file__))
        args = sorted(glob.glob(os.path.join(here, "..", "results", "*.json")))
    main(args)
