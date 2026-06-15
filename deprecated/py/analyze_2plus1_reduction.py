"""analyze_2plus1_reduction.py — validate the 2+1 twist math (read-only).

Tests the two proposed 2+1 formulations against every cached 2+1 solution:

  A (domino-bipartite)  the 2-chain treated as one rigid unit per placement: centroid path
                        + index-parity sigma (index parity IS the domino-level bipartite).
                        Loop = centroid path + reversed 1-chain path, shipped
                        _pair_loop_twist. Expectation from the probe: body turns are 90
                        multiples (centroid steps are axis-aligned, lengths 2/1) but the
                        hub seams are off-lattice (domino centroid x.0 vs cell x.5) ->
                        fractional turn artifacts. Measured here.

  B (strand reduction)  hypothesis_2plus1_reduction.md: delete one strand of the rigid
                        domino; the survivor (cells[0] = strand P, cells[1] = strand Q —
                        reflect_cells preserves list order so each tracks one material
                        half) is an honest lattice walk on a holey grid. Loop = strand
                        path + reversed 1-chain path, same machinery as 1+1+1.
                        SELF-CHECKS the doc's claims: axis-aligned steps (TRUE, but
                        lengths {1,3} — the doc's "unit moves" is FALSE), checkerboard
                        alternation (TRUE: odd-length steps), grid partition (TRUE).
                        Open point 5.1: does the P/Q strand choice change the verdict?

  CONVENTIONS           Tw = sum sigma(v)*gamma(v) is globally linear in both sign
                        choices, so verdict (Tw==0) must be invariant under: sigma phase
                        flip (swap odd/even buckets), gamma sign flip (mirror plane),
                        both, and loop orientation. Verified numerically on every loop.

  ORACLE                trivial reduction on 1+1+1 (strand = the chain itself) must
                        reproduce the stored pairwise twists exactly.

Ground-truth caveat: results/twoplus1_labels.json is all-null (no physical fold verdicts
yet), so this establishes well-definedness + physicality + internal consistency +
discrimination structure, NOT correctness against reality. See FOLDING.md.

Usage:  python analyze_2plus1_reduction.py [resultsfile ...]   (default: all 3-stack results)
"""
import json
import sys
import glob
import os
from math import atan2, degrees, hypot
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fold        # noqa: E402
import search      # noqa: E402


# --- replay + paths (same primitives as analyze_twist / analyze_loop_seams) ---

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


def strand_path(placements, idx):
    return [(p["cells"][idx][0] + 0.5, p["cells"][idx][1] + 0.5) for p in placements]


def centroid_path(placements):
    pts = []
    for p in placements:
        cs = p["cells"]
        k = len(cs)
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
    return "far(%g,%g)" % (dx, dy)


def loop_turns(pts):
    """Per-iteration doubled turn angles (float deg, NOT rounded — so fractional
    seam artifacts are visible). Iteration i = turn at vertex pts[(i+1)%n]."""
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
        terms.append(2 * ang)
    return terms


def tw_from_terms(terms, sigma_flip=False, gamma_flip=False):
    tw = 0.0
    for i, t in enumerate(terms):
        s = 1 if i % 2 else -1
        if sigma_flip:
            s = -s
        tw += s * (-t if gamma_flip else t)
    return round(tw, 6)


def pair_tw(path_a, path_b):
    return tw_from_terms(loop_turns(path_a + list(reversed(path_b))))


# --- per-solution analysis ---

def check_strand_invariants(pls2, pls1, m, n):
    """Stage 1 self-checks; returns list of violation strings (empty = pass)."""
    bad = []
    cover = set(p["cells"][0] for p in pls1)
    for idx in (0, 1):
        cells = [p["cells"][idx] for p in pls2]
        cover |= set(cells)
        for a, b in zip(cells, cells[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            if dx != 0 and dy != 0:
                bad.append(f"strand{idx} non-axis step {a}->{b}")
            if abs(dx) + abs(dy) not in (1, 3):
                bad.append(f"strand{idx} step len {abs(dx)+abs(dy)} {a}->{b}")
            if (a[0] + a[1]) % 2 == (b[0] + b[1]) % 2:
                bad.append(f"strand{idx} checkerboard break {a}->{b}")
    if len(cover) != m * n:
        bad.append(f"partition {len(cover)} != {m*n}")
    return bad


def analyze_2plus1(sols, m, n):
    rows = []
    for s in sols:
        two = next(c for c in s["chains"] if len(c["baseCells"]) == 2)
        one = next(c for c in s["chains"] if len(c["baseCells"]) == 1)
        pls2 = replay_placements(two["baseCells"], two["foldArrows"], m, n)
        pls1 = replay_placements(one["baseCells"], one["foldArrows"], m, n)
        bad = check_strand_invariants(pls2, pls1, m, n)
        path1 = strand_path(pls1, 0)
        row = {"id": s["id"], "shape": s["footprint"]["shape"], "bad": bad}
        for label, pts in (("P", strand_path(pls2, 0)),
                           ("Q", strand_path(pls2, 1)),
                           ("C", centroid_path(pls2))):
            K = len(pts)
            loop = pts + list(reversed(path1))
            terms = loop_turns(loop)
            tw = tw_from_terms(terms)
            seams = (classify_step(loop[K - 1], loop[K]),
                     classify_step(loop[2 * K - 1], loop[0]))
            row[label] = {"tw": tw, "seams": seams,
                          "integerTw": (tw % 720 == 0),
                          "flips": conventions_ok(terms, tw, pts, path1)}
            row[label]["frac_turns"] = sum(1 for t in terms if abs(t % 90) > 1e-6)
        # canonical strand (hypothesis 5.1 fallback rule): the strand whose loop closes
        # WITHOUT diagonal seams (= the strand edge-adjacent to the 1-chain base).
        # DIAG-seam strand loops carry a quantized +-360 (half-twist) seam artifact.
        cands = [k for k in ("P", "Q") if "DIAG" not in row[k]["seams"]]
        row["canon"] = cands[0] if cands else None
        rows.append(row)
    return rows


def conventions_ok(terms, tw, path_a, path_b):
    """Stage 4: verdict invariance under sigma flip / gamma flip / both / orientation."""
    twists = [tw_from_terms(terms, sigma_flip=True),          # sigma phase
              tw_from_terms(terms, gamma_flip=True),          # gamma sign
              tw_from_terms(terms, sigma_flip=True, gamma_flip=True),
              pair_tw(path_b, path_a)]                        # loop orientation
    return all(abs(t) == abs(tw) for t in twists)


def oracle_111(sols, m, n):
    """Trivial reduction on 1+1+1: strand=chain — must reproduce stored pairwise twists."""
    n_match = n_tot = 0
    for s in sols:
        pls = [replay_placements(c["baseCells"], c["foldArrows"], m, n) for c in s["chains"]]
        paths = [strand_path(p, 0) for p in pls]
        stored = {(p["i"], p["j"]): p["tw"] for p in s.get("twistPairs", [])}
        for (i, j), v in stored.items():
            n_tot += 1
            n_match += (pair_tw(paths[i], paths[j]) == v)
    return n_match, n_tot


# --- driver ---

def analyze_file(f):
    data = json.load(open(f))
    if not isinstance(data, dict) or "meta" not in data or data["meta"].get("stacks") == 2:
        return None
    m, n = data["meta"]["m"], data["meta"]["n"]
    sols21 = [s for s in data["solutions"] if s["decomposition"] == "2+1"]
    sols111 = [s for s in data["solutions"] if s["decomposition"] == "1+1+1"]
    if not sols21 and not sols111:
        return None
    print("\n=== %s  %dx%d  2+1: %d   1+1+1: %d ===" %
          (os.path.basename(f), m, n, len(sols21), len(sols111)))
    om, ot = oracle_111(sols111, m, n)
    if ot:
        print("  ORACLE 1+1+1 trivial-reduction reproduces stored pairwise tw: %d/%d %s"
              % (om, ot, "PASS" if om == ot else "FAIL"))
    rows = analyze_2plus1(sols21, m, n)
    agree = flagged = 0
    for r in rows:
        P, Q, C = r["P"], r["Q"], r["C"]
        canon = r[r["canon"]] if r["canon"] else None
        pq_agree = (P["tw"] == 0) == (Q["tw"] == 0)
        agree += pq_agree
        flagged += (canon is not None and canon["tw"] != 0)
        marks = []
        if r["bad"]:
            marks.append("SELFCHK:" + ";".join(r["bad"][:2]))
        if canon is None:
            marks.append("NO-CANON")
        elif not canon["integerTw"]:
            marks.append("CANON-HALFTW")
        if not (P["flips"] and Q["flips"] and C["flips"]):
            marks.append("CONV-FAIL")
        print("  #%-3s %-4s P: tw=%-6g seams=%-12s | Q: tw=%-6g seams=%-12s | canon=%s tw=%-6s | "
              "centroid: tw=%-8g fracTurns=%d %s"
              % (r["id"], r["shape"], P["tw"], "/".join(P["seams"]),
                 Q["tw"], "/".join(Q["seams"]), r["canon"],
                 "%g" % canon["tw"] if canon else "-",
                 C["tw"], C["frac_turns"], " ".join(marks)))
    if rows:
        print("  -- %d sols | P/Q verdicts agree: %d/%d | canonical-strand flagged twisted: %d/%d"
              % (len(rows), agree, len(rows), flagged, len(rows)))
    return {"rows": rows, "oracle": (om, ot), "grid": "%dx%d" % (m, n)}


def main(files):
    print("==== 2+1 twist validation: strand reduction (B) vs domino-bipartite (A) ====")
    all_rows, om, ot = [], 0, 0
    for f in files:
        r = analyze_file(f)
        if r:
            for row in r["rows"]:
                row["grid"] = r["grid"]
            all_rows += r["rows"]
            om += r["oracle"][0]
            ot += r["oracle"][1]
    n = len(all_rows)
    selfchk = sum(1 for r in all_rows if r["bad"])
    no_canon = sum(1 for r in all_rows if not r["canon"])
    canon_rows = [r for r in all_rows if r["canon"]]
    canon_halftw = sum(1 for r in canon_rows if not r[r["canon"]]["integerTw"])
    conv = sum(1 for r in all_rows if not (r["P"]["flips"] and r["Q"]["flips"] and r["C"]["flips"]))
    pq = sum(1 for r in all_rows if (r["P"]["tw"] == 0) == (r["Q"]["tw"] == 0))
    # the DIAG-strand offset: Q-P (or P-Q) where exactly one strand loop is DIAG-seamed
    offsets = Counter()
    for r in all_rows:
        diag = [k for k in ("P", "Q") if "DIAG" in r[k]["seams"]]
        if len(diag) == 1 and r["canon"]:
            offsets[r[diag[0]]["tw"] - r[r["canon"]]["tw"]] += 1
    cent_match = sum(1 for r in canon_rows if r["C"]["tw"] == r[r["canon"]]["tw"])
    cent_frac = sum(1 for r in all_rows if r["C"]["frac_turns"])
    print("\n==== TOTAL (%d 2+1 solutions) ====" % n)
    print("oracle (1+1+1 trivial reduction)     : %d/%d  %s" % (om, ot, "PASS" if om == ot else "FAIL"))
    print("stage-1 self-check violations        : %d   (axis/steplen/checkerboard/partition)" % selfchk)
    print("solutions with no non-DIAG strand    : %d   (canonical rule total when 0)" % no_canon)
    print("canonical strand non-integer Tw      : %d   (0 => canonical reduction is physical)" % canon_halftw)
    print("convention-flip verdict changes      : %d   (0 => conventions don't matter)" % conv)
    print("P/Q strand verdicts agree            : %d/%d  (5.1 conjecture: disagreements = DIAG artifact)" % (pq, n))
    print("DIAG-strand offset (tw_DIAG - tw_canon): %s   (expect subset of {0,+-360})" % dict(offsets))
    print("centroid (A) tw == canonical tw      : %d/%d ; centroid loops w/ fractional turns: %d" % (cent_match, len(canon_rows), cent_frac))
    print("canonical tw histogram               : %s" % dict(Counter(r[r["canon"]]["tw"] for r in canon_rows)))
    print("canonical flagged-twisted by grid    : %s" %
          {g: "%d/%d" % (sum(1 for r in canon_rows if r["grid"] == g and r[r["canon"]]["tw"] != 0),
                         sum(1 for r in all_rows if r["grid"] == g))
           for g in sorted(set(r["grid"] for r in all_rows))})


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        here = os.path.dirname(os.path.abspath(__file__))
        args = sorted(glob.glob(os.path.join(here, "..", "results", "*.json")))
    main(args)
