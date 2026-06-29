"""analyze_twist_2plus1_compare.py — Phase-1 read-only 2+1 twist-model comparison.

Compares two ways to stand a rigid 2-chain (domino ribbon) in for a 1-chain so the closed-loop
twist applies, then DIFFS their Tw==0 verdicts over every cached 2+1 solution. No engine state is
changed; this only reads results/*.json.

  Model B  (validated jump-strand)  one kept-strand cell center per placement (K points = K folds).
            3-jumps (short-side / along-axis folds) are left as long axis-aligned steps -> turns
            stay 90-mult -> integer Tw in {0, +-720}. Canonical strand = the one whose two hub
            seams are non-diagonal (edge-adjacent to the 1-chain base).

  Model A  (lead's partial decomp)  also one point per placement (fold count K preserved), but THIN
            to a 1-unit (kept-strand cell center, half-int/half-int) by default and keep a residual
            2-UNIT (domino centroid, int/half-int) only at placements incident to a short-side fold,
            so that step moves by 2 instead of the strand's 3-jump.
              A_nat   centroid at every short-incident placement (incl. hubs if a hub fold is short)
              A_hub1  same, but force the two hub placements to 1-unit (clean unit join to 1-chain)

  filled   (cross-check only)  insert the two collinear midpoints on each 3-jump (gamma=0); the
            hypothesis-doc lemma says filled == jump. Asserted here as an internal sanity check;
            filled crosses the domino's RIGID internal edge as if a crease, so it never ships.

The decision question: do A and B agree on the Tw==0 verdict for every cached 2+1? And does Model A
inject a fractional (atan-1/2) seam artifact at the 1-unit<->2-unit transitions (the 936/+-212
pathology relocated from the hub to the seam)? Float turn math is used so any artifact is visible.

Usage:  python tests/analyze_twist_2plus1_compare.py [resultfile ...]   (default: all 3-stack json)
"""
import json
import sys
import glob
import os
from math import atan2, degrees, hypot
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "py"))
import _bootstrap  # noqa: E402,F401  (py/ subfolders + repo + tests on sys.path)
import fold  # noqa: E402


# ---------- replay + path builders ----------

def replay(base_cells, fold_arrows, m, n):
    base = [(c["x"], c["y"]) for c in base_cells]
    pl = fold.initial_placement(base)
    pls = [pl]
    for d in fold_arrows:
        pl = fold.make_fold(pl, d, m, n)
        if pl is None:
            raise ValueError("fold %s left grid" % d)
        pls.append(pl)
    return pls


def cc(cell):
    return (cell[0] + 0.5, cell[1] + 0.5)


def centroid(cells):
    k = len(cells)
    return (sum(c[0] + 0.5 for c in cells) / k, sum(c[1] + 0.5 for c in cells) / k)


def strand_path(pls, idx):
    return [cc(p["cells"][idx]) for p in pls]


def full_centroid_path(pls):
    return [centroid(p["cells"]) for p in pls]


def short_incident(pls, idx):
    """Placements that are an endpoint of a length-3 strand step (a short-side / along-axis fold)."""
    cells = [p["cells"][idx] for p in pls]
    s = set()
    for k in range(len(cells) - 1):
        a, b = cells[k], cells[k + 1]
        if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 3:
            s.add(k)
            s.add(k + 1)
    return s


def model_a_path(pls, idx, force_hub_1unit=False):
    """One point per placement: 1-unit (strand cell) by default, 2-unit (centroid) at short-incident
    placements. Returns (points, kinds) with kinds[k] in {'1','2'}."""
    short = short_incident(pls, idx)
    K = len(pls)
    pts, kinds = [], []
    for k, p in enumerate(pls):
        is2 = k in short and not (force_hub_1unit and k in (0, K - 1))
        if is2:
            pts.append(centroid(p["cells"]))
            kinds.append('2')
        else:
            pts.append(cc(p["cells"][idx]))
            kinds.append('1')
    return pts, kinds


def filled_path(pls, idx):
    cells = [p["cells"][idx] for p in pls]
    out = [cc(cells[0])]
    for k in range(len(cells) - 1):
        a, b = cells[k], cells[k + 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        if abs(dx) + abs(dy) == 3:                    # collinear midpoints on the 3-jump
            sx = (dx > 0) - (dx < 0)
            sy = (dy > 0) - (dy < 0)
            out.append(cc((a[0] + sx, a[1] + sy)))
            out.append(cc((a[0] + 2 * sx, a[1] + 2 * sy)))
        out.append(cc(b))
    return out


# ---------- turn / twist (float, artifact-visible) ----------

def loop_terms(pts):
    n = len(pts)
    terms = []
    for i in range(n):
        p1, p2, p3 = pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        v1 = (p2[0] - p1[0], p2[1] - p1[1])
        v2 = (p3[0] - p2[0], p3[1] - p2[1])
        ang = 0.0
        if hypot(*v1) > 1e-9 and hypot(*v2) > 1e-9:
            dot = v1[0] * v2[0] + v1[1] * v2[1]
            cross = v1[0] * v2[1] - v1[1] * v2[0]
            ang = degrees(atan2(cross, dot))
        terms.append(2 * ang)                          # doubled turn angle
    return terms


def tw_of(terms, sflip=False, gflip=False):
    t = 0.0
    for i, x in enumerate(terms):
        s = 1 if i % 2 else -1                          # odd -> +, even -> -  (== odd - even)
        if sflip:
            s = -s
        t += s * (-x if gflip else x)
    return round(t, 6)


def loop_tw(body, path1):
    return tw_of(loop_terms(body + list(reversed(path1))))


def frac_turns(terms):
    return sum(1 for t in terms if abs(t % 90) > 1e-6)


def is0(x):
    return abs(x) < 1e-6


def classify_step(p, q):
    dx, dy = abs(q[0] - p[0]), abs(q[1] - p[1])
    if dx + dy == 1:
        return "unit"
    if dx == 1 and dy == 1:
        return "DIAG"
    if (dx == 0 and dy == 2) or (dx == 2 and dy == 0):
        return "2JMP"
    return "far(%g,%g)" % (dx, dy)


def pick_canon_idx(pls2, path1):
    """Canonical jump-strand = the strand whose two hub seams are non-diagonal."""
    seams = {}
    for idx in (0, 1):
        sp = strand_path(pls2, idx)
        K = len(sp)
        loop = sp + list(reversed(path1))
        seams[idx] = (classify_step(loop[K - 1], loop[K]),
                      classify_step(loop[2 * K - 1], loop[0]))
    cands = [idx for idx in (0, 1) if "DIAG" not in seams[idx]]
    return (cands[0] if cands else 0), seams


# ---------- per-solution ----------

def analyze_2plus1(sols, m, n):
    rows = []
    for s in sols:
        two = next(c for c in s["chains"] if len(c["baseCells"]) == 2)
        one = next(c for c in s["chains"] if len(c["baseCells"]) == 1)
        pls2 = replay(two["baseCells"], two["foldArrows"], m, n)
        pls1 = replay(one["baseCells"], one["foldArrows"], m, n)
        path1 = strand_path(pls1, 0)
        idx, seams = pick_canon_idx(pls2, path1)

        b_path = strand_path(pls2, idx)
        f_path = filled_path(pls2, idx)
        a_nat, kinds_nat = model_a_path(pls2, idx, force_hub_1unit=False)
        a_h1, _ = model_a_path(pls2, idx, force_hub_1unit=True)
        cen = full_centroid_path(pls2)

        tw_b = loop_tw(b_path, path1)
        tw_f = loop_tw(f_path, path1)
        tw_a = loop_tw(a_nat, path1)
        tw_a1 = loop_tw(a_h1, path1)
        tw_c = loop_tw(cen, path1)

        rows.append({
            "id": s["id"], "shape": s["footprint"]["shape"],
            "twB": tw_b, "twF": tw_f, "twA": tw_a, "twA1": tw_a1, "twC": tw_c,
            "n2units": kinds_nat.count('2'),
            "fracA": frac_turns(loop_terms(a_nat + list(reversed(path1)))),
            "fracA1": frac_turns(loop_terms(a_h1 + list(reversed(path1)))),
            "fracB": frac_turns(loop_terms(b_path + list(reversed(path1)))),
            "fracC": frac_turns(loop_terms(cen + list(reversed(path1)))),
            "filled_eq_jump": is0(tw_f - tw_b),
        })
    return rows


def oracle_111(sols, m, n):
    """1+1+1 trivial reduction (strand = the chain) must reproduce stored pairwise twists."""
    ok = tot = 0
    for s in sols:
        paths = [strand_path(replay(c["baseCells"], c["foldArrows"], m, n), 0) for c in s["chains"]]
        for p in s.get("twistPairs", []):
            tot += 1
            ok += is0(loop_tw(paths[p["i"]], paths[p["j"]]) - p["tw"])
    return ok, tot


def conv_ok(body, path1):
    terms = loop_terms(body + list(reversed(path1)))
    base = tw_of(terms)
    variants = [tw_of(terms, sflip=True), tw_of(terms, gflip=True),
                tw_of(terms, sflip=True, gflip=True),
                tw_of(loop_terms(path1 + list(reversed(body))))]
    return all(abs(v) == abs(base) for v in variants)


# ---------- driver ----------

def analyze_file(f):
    data = json.load(open(f))
    if not isinstance(data, dict) or "meta" not in data or data["meta"].get("stacks") == 2:
        return None
    m, n = data["meta"]["m"], data["meta"]["n"]
    sols21 = [s for s in data["solutions"] if s["decomposition"] == "2+1"]
    sols111 = [s for s in data["solutions"] if s["decomposition"] == "1+1+1"]
    if not sols21:
        return None
    grid = "%dx%d" % (m, n)
    om, ot = oracle_111(sols111, m, n)
    rows = analyze_2plus1(sols21, m, n)
    print("\n=== %s  %s  2+1:%d  1+1+1:%d ===" % (os.path.basename(f), grid, len(sols21), len(sols111)))
    if ot:
        print("  oracle 1+1+1 trivial-reduction reproduces stored tw: %d/%d %s"
              % (om, ot, "PASS" if om == ot else "FAIL"))
    for r in rows:
        agree = is0(r["twA"]) == is0(r["twB"])
        print("  #%-3s %-4s B:%-7g A_nat:%-9g A_hub1:%-9g 2u=%-2d fracA=%-2d %s%s"
              % (r["id"], r["shape"], r["twB"], r["twA"], r["twA1"], r["n2units"], r["fracA"],
                 "" if agree else "  <-- A/B DISAGREE",
                 "" if r["filled_eq_jump"] else "  <-- filled!=jump"))
    for r in rows:
        r["grid"] = grid
    return {"rows": rows, "oracle": (om, ot), "grid": grid}


def main(files):
    print("==== 2+1 twist model comparison: Model A (partial decomp) vs Model B (jump strand) ====")
    allrows, om, ot = [], 0, 0
    for f in sorted(files):
        r = analyze_file(f)
        if r:
            allrows += r["rows"]
            om += r["oracle"][0]
            ot += r["oracle"][1]
    if not allrows:
        print("\n(no 2+1 solutions found)")
        return
    n = len(allrows)
    # contingency (A_nat vs B), using Tw==0 verdicts
    cont = Counter()
    disagree = []
    for r in allrows:
        a0, b0 = is0(r["twA"]), is0(r["twB"])
        cont[(b0, a0)] += 1
        if a0 != b0:
            disagree.append(r)
    fe = sum(1 for r in allrows if not r["filled_eq_jump"])
    fa = sum(r["fracA"] for r in allrows)
    fa1 = sum(r["fracA1"] for r in allrows)
    fb = sum(r["fracB"] for r in allrows)
    print("\n==== TOTAL (%d cached 2+1 solutions) ====" % n)
    print("oracle 1+1+1 trivial reduction      : %d/%d %s" % (om, ot, "PASS" if om == ot else "FAIL"))
    print("filled != jump (lemma violations)   : %d  (expect 0)" % fe)
    print("contingency  (Tw==0)  B \\ A_nat :")
    print("                 A:PASS   A:FAIL")
    print("  B:PASS        %5d   %5d" % (cont[(True, True)], cont[(True, False)]))
    print("  B:FAIL        %5d   %5d" % (cont[(False, True)], cont[(False, False)]))
    print("A/B verdict disagreements           : %d" % len(disagree))
    for r in disagree:
        print("    %s #%s %s : B=%g(%s)  A_nat=%g(%s)" %
              (r["grid"], r["id"], r["shape"], r["twB"], "0" if is0(r["twB"]) else "x",
               r["twA"], "0" if is0(r["twA"]) else "x"))
    print("fractional turns  B / A_nat / A_hub1: %d / %d / %d   (B must be 0; A>0 => seam artifact)"
          % (fb, fa, fa1))
    print("flagged-twisted (B, current gate) by grid:")
    grids = sorted(set(r["grid"] for r in allrows))
    for g in grids:
        gr = [r for r in allrows if r["grid"] == g]
        nb = sum(1 for r in gr if not is0(r["twB"]))
        na = sum(1 for r in gr if not is0(r["twA"]))
        print("    %-6s  B:%d/%d  A_nat:%d/%d" % (g, nb, len(gr), na, len(gr)))


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        args = sorted(glob.glob(os.path.join(ROOT, "results", "*.json")))
    main(args)
