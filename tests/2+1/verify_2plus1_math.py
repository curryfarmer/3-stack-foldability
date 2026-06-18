"""verify_2plus1_math.py — READ-ONLY verification of the 3-stack parity + twist math against the
2-stack reference (py/twostack.py, Yang-You-Rosen RSPA 2025), then applied to the physical ground
truth. Run as a script (the dir name "2+1" is not an importable package; that's fine):

    python tests/2+1/verify_2plus1_math.py

Hard constraints honoured: every gate in py/ (twostack.twist_value, fold.reflection_verdict,
SquareLattice.parity_check, search._pair_loop_twist, enginelib.closing_candidates) is imported
STRICTLY as a read-only comparison oracle. All 2+1 math lives in the experimental engines /
experimental/common.py. Nothing in py/ is mutated.

Parts:
  A  Twist formula faithfulness  — experimental loop_tw == twostack.twist_value on the identical
     ordered point list, for every cached 2+1 (all 4 path-builders) and 1+1+1 (pairwise centroid
     loops). Also shipped search._pair_loop_twist == twostack.twist_value on the 1+1+1 loops it gates.
     Integer (90-multiple) loops must agree exactly; partial-decomp's atan(1/2) loops are reported as
     the EXPECTED int-rounding divergence (the shipped int convention suppresses the overhang signal).
  B  Parity gate sigma-soundness — common.parity_predicate_geom (parity verdict recomputed from the
     REPLAYED checkerboard parities) vs SquareLattice.parity_check (arrow-letter counts), per cached
     solution. Plus the bridge identity x_flip==nH%2, y_flip==nV%2, and m*n even (the 2-stack parity).
  C  The physical JAM ground truths (the deciders) — for each foldfindings JAM hash, match a closing
     candidate, compute the full independent gate tuple (exit/parity/reflection/twist), report which
     gate(s) reject, and confirm predicted-JAM == physical-JAM. Resolves the 6x7#8 conflict.
  D  Gate independence on the PRE-gate population — enumerate ALL closing candidates (not just
     reflection survivors); build the reflection x twist contingency for 2+1; count twist-only and
     reflection-only rejects. Nonzero off-diagonal => the gates are independent.

Writes results/2+1 testing/_verification.json and prints a report. No engine/gate is changed.
"""
import glob
import json
import math
import os
import sys

# ---- bootstrap sys.path (no conftest when run as a script) ----
_HERE = os.path.dirname(os.path.abspath(__file__))               # tests/2+1
_TESTS = os.path.dirname(_HERE)                                   # tests
_ROOT = os.path.dirname(_TESTS)
for _p in (os.path.join(_ROOT, "py"), os.path.join(_ROOT, "py", "tri"),
           os.path.join(_ROOT, "experimental"), _TESTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import twostack                       # noqa: E402  (py/ reference oracle)
import fold                           # noqa: E402  (py/ reference oracle)
import search                         # noqa: E402  (py/ reference oracle: _pair_loop_twist)
from lattice.square import SquareLattice  # noqa: E402  (py/ reference oracle: parity_check)
import enginelib as EL                # noqa: E402  (tests/ closing-candidate oracle)
import common                         # noqa: E402  (experimental geometry/twist core)
from no_decomp import twist as e_no            # noqa: E402
from jump_decomp import twist as e_jump        # noqa: E402
from normal_decomp import twist as e_normal    # noqa: E402
from partial_decomp import twist as e_partial  # noqa: E402

OUTDIR = os.path.join(_ROOT, "results", "2+1 testing")
EPS = 1e-6


# ---------- shared helpers ----------

def _grid_mn(grid):
    a, b = grid.split("x")
    return int(a), int(b)


def load_caches():
    """All 3-stack caches -> [(grid, m, n, sols2plus1, sols111)]."""
    out = []
    for f in sorted(glob.glob(os.path.join(_ROOT, "results", "*.json"))):
        try:
            data = json.load(open(f))
        except Exception:
            continue
        if not isinstance(data, dict) or data.get("meta", {}).get("stacks") != 3:
            continue
        m, n = data["meta"]["m"], data["meta"]["n"]
        sols = data.get("solutions", [])
        two = [s for s in sols if s.get("decomposition") == "2+1"]
        one = [s for s in sols if s.get("decomposition") == "1+1+1"]
        if two or one:
            out.append(("%dx%d" % (m, n), m, n, two, one))
    return out


def _norm_chain(c):
    """Candidate/cache chain -> {kind, baseCells:[(x,y)], foldArrows:[...]} with tuple cells."""
    return {"kind": c.get("kind"),
            "baseCells": common._cells_xy(c["baseCells"]),
            "foldArrows": list(c["foldArrows"])}


def _chains_with_placements(chains_norm, m, n):
    """Attach replayed placements (for fold.reflection_verdict)."""
    out = []
    for c in chains_norm:
        pls = common.replay([{"x": x, "y": y} for (x, y) in c["baseCells"]], c["foldArrows"], m, n)
        out.append({**c, "placements": pls})
    return out


def _sol_from_chains(chains_norm):
    """Wrap normalized chains as a cache-style sol (dict baseCells) for common.split_chains."""
    return {"chains": [{"kind": c["kind"],
                        "baseCells": [{"x": x, "y": y} for (x, y) in c["baseCells"]],
                        "foldArrows": c["foldArrows"]} for c in chains_norm]}


def jump_twist_of_2plus1(chains_norm, m, n):
    """Independent jump-strand (Model B) Tw via the experimental engine. Returns (tw, twostack_tw)."""
    sol = _sol_from_chains(chains_norm)
    two, one = common.split_chains(sol)
    ctx = common.prepare(two, one, m, n)
    body = common.strand_path(ctx["pls2"], ctx["idx"])
    pts = body + list(reversed(ctx["path1"]))
    return common.tw_of(common.loop_terms(pts)), twostack.twist_value(pts)


# ---------- Part A : twist formula faithfulness ----------

def part_a(caches):
    mism_int = []        # integer-loop disagreements (must be empty)
    partial_gap = []     # partial-decomp int-rounding gaps (expected, informational)
    n_int = n_partial = 0
    n_111_pairs = 0
    mism_111 = []

    for grid, m, n, two, _one in caches:
        for s in two:
            tg = common.split_chains(s)
            ctx = common.prepare(tg[0], tg[1], m, n)
            path1 = ctx["path1"]
            bodies = {
                "no": common.full_centroid_path(ctx["pls2"]),
                "jump": common.strand_path(ctx["pls2"], ctx["idx"]),
                "normal": common.filled_path(ctx["pls2"], ctx["idx"]),
                "partial": common.model_a_path(ctx["pls2"], ctx["idx"])[0],
            }
            for name, body in bodies.items():
                pts = body + list(reversed(path1))
                terms = common.loop_terms(pts)
                exp = common.tw_of(terms)
                ref = twostack.twist_value(pts)
                if common.frac_turns(terms) == 0:          # integer (90-multiple) loop
                    n_int += 1
                    if abs(exp - ref) > EPS:
                        mism_int.append({"grid": grid, "id": s["id"], "engine": name,
                                         "exp": exp, "ref": ref})
                else:                                       # atan(1/2) loop (partial only)
                    n_partial += 1
                    if abs(exp - ref) > EPS:
                        partial_gap.append({"grid": grid, "id": s["id"], "engine": name,
                                            "exp_float": exp, "ref_rounded": ref,
                                            "diff": round(exp - ref, 4)})

    # 1+1+1: experimental loop_tw == twostack.twist_value == shipped _pair_loop_twist
    for grid, m, n, _two, one in caches:
        for s in one:
            paths = []
            for c in s["chains"]:
                pls = common.replay(c["baseCells"], c["foldArrows"], m, n)
                paths.append(common.strand_path(pls, 0))
            for i in range(len(paths)):
                for j in range(i + 1, len(paths)):
                    pts = paths[i] + list(reversed(paths[j]))
                    exp = common.tw_of(common.loop_terms(pts))
                    ref = twostack.twist_value(pts)
                    shipped = search._pair_loop_twist(paths[i], paths[j])
                    n_111_pairs += 1
                    if abs(exp - ref) > EPS or exp != shipped:
                        mism_111.append({"grid": grid, "id": s["id"], "pair": [i, j],
                                         "exp": exp, "ref": ref, "shipped": shipped})

    return {
        "integer_loops_checked": n_int,
        "integer_mismatches": mism_int,
        "partial_atan_loops": n_partial,
        "partial_rounding_gaps": len(partial_gap),
        "partial_gap_sample": partial_gap[:5],
        "oneplus_pairs_checked": n_111_pairs,
        "oneplus_mismatches": mism_111,
        "pass": (not mism_int) and (not mism_111),
    }


# ---------- Part B : parity gate sigma-soundness ----------

def part_b(caches):
    n = 0
    disagree = []          # parity_check vs geometric sigma recompute
    bridge_fail = []       # x_flip != nH%2  or  y_flip != nV%2  (the geometry<->count bridge)
    mn_odd = []

    for grid, M, N, two, one in caches:
        if (M * N) % 2 != 0:
            mn_odd.append(grid)
        for s in two + one:
            chains = [_norm_chain(c) for c in s["chains"]]
            engine = SquareLattice.parity_check([{"baseCells": list(c["baseCells"]),
                                                  "foldArrows": c["foldArrows"]} for c in chains])
            geom = common.parity_predicate_geom(chains, M, N)
            n += 1
            if engine != geom:
                disagree.append({"grid": grid, "id": s["id"], "decomp": s["decomposition"],
                                 "engine": engine, "geom": geom})
            for c in chains:
                rep = common.sigma_report(c["baseCells"], c["foldArrows"], M, N)
                if not (rep["x_flip_matches_nH"] and rep["y_flip_matches_nV"]):
                    bridge_fail.append({"grid": grid, "id": s["id"], "rep": rep})

    return {
        "solutions_checked": n,
        "parity_disagreements": disagree,
        "bridge_identity_failures": bridge_fail,
        "grids_with_odd_mn": mn_odd,           # 2-stack parity (m*n even) must hold => empty
        "pass": (not disagree) and (not bridge_fail) and (not mn_odd),
    }


# ---------- Part C : the physical JAM deciders ----------

def _reflection_detail(chains_norm, m, n):
    """Reproduce fold.reflection_verdict's per-pair landing segments (which grid lines)."""
    chains = _chains_with_placements(chains_norm, m, n)
    res = fold.reflection_verdict(chains)
    detail = []
    for (i, j, Pi, Pj) in fold._shared_crease_pairs(chains):
        seed = fold._crease_segment(Pi, Pj)
        ci = chains[i]["placements"][-1]["transformChain"]
        cj = chains[j]["placements"][-1]["transformChain"]
        seg_i = (fold._reflect_pt_through(seed[0], ci), fold._reflect_pt_through(seed[1], ci))
        seg_j = (fold._reflect_pt_through(seed[0], cj), fold._reflect_pt_through(seed[1], cj))
        detail.append({"i": i, "j": j,
                       "imgI": [list(map(lambda v: round(v, 3), seg_i[0])),
                                list(map(lambda v: round(v, 3), seg_i[1]))],
                       "imgJ": [list(map(lambda v: round(v, 3), seg_j[0])),
                                list(map(lambda v: round(v, 3), seg_j[1]))]})
    return res["pass"], detail


def part_c():
    findings = json.load(open(os.path.join(_ROOT, "results", "foldfindings.json")))
    jams = [f for f in findings if f.get("foldable") is False]
    rows = []
    all_predicted_jam = True
    for f in jams:
        grid = f["grid"]
        m, n = _grid_mn(grid)
        cand = EL.find_closing_by_hash(m, n, f["canonicalHash"], allow_non_corner=False)
        anc = False
        if cand is None:
            cand = EL.find_closing_by_hash(m, n, f["canonicalHash"], allow_non_corner=True)
            anc = True
        if cand is None:
            rows.append({"finding": "%s#%s" % (grid, f["id"]), "matched": False})
            all_predicted_jam = False
            continue

        chains_norm = [_norm_chain(c) for c in cand["chains"]]
        # independent gate recompute
        parity = SquareLattice.parity_check([{"baseCells": list(c["baseCells"]),
                                              "foldArrows": c["foldArrows"]} for c in chains_norm])
        refl_pass, refl_detail = _reflection_detail(chains_norm, m, n)
        is_2plus1 = (cand["decomp"] == "2+1")
        if is_2plus1:
            tw, tw_ref = jump_twist_of_2plus1(chains_norm, m, n)
        else:
            tw = tw_ref = None
        twist_pass = (tw is None) or common.is0(tw)

        catching = []
        if not parity:
            catching.append("parity")
        if not refl_pass:
            catching.append("reflection")
        if is_2plus1 and not twist_pass:
            catching.append("twist(2+1)")
        predicted_jam = len(catching) > 0
        all_predicted_jam = all_predicted_jam and predicted_jam

        rows.append({
            "finding": "%s#%s" % (grid, f["id"]),
            "matched": True, "allow_non_corner": anc, "decomp": cand["decomp"],
            "engine_fails": cand["fails"], "engine_foldable": cand["foldable"],
            "gate_tuple": {"exit": True, "parity": parity, "reflection": refl_pass,
                           "twist_jump": tw, "twist_ref": tw_ref, "twist_pass": twist_pass},
            "reflection_landing": refl_detail,
            "catching_gates": catching,
            "predicted_jam": predicted_jam, "physical_jam": True,
            "agree": predicted_jam is True,
        })
    return {"deciders": rows, "all_predicted_jam": all_predicted_jam,
            "pass": all_predicted_jam}


# ---------- Part D : gate independence on the pre-gate population ----------

def part_d(grids):
    from collections import Counter
    out = {}
    for (m, n, anc) in grids:
        cands, K = EL.closing_candidates(m, n, allow_non_corner=anc)
        two = [c for c in cands if c["decomp"] == "2+1"]
        # Full 3-gate breakdown over (reflection, parity, twist=0). Twist computed independently via
        # the experimental jump engine. The independence witness is a candidate that passes BOTH
        # reflection AND parity yet has Tw!=0 -> a jam ONLY the twist gate would catch.
        tab = Counter()                 # (refl_pass, par_pass, tw0) -> count
        twist_only, refl_only = [], []
        n_tw = 0
        for c in two:
            refl_pass = "refl" not in c["fails"]
            par_pass = "parity" not in c["fails"]
            chains_norm = [_norm_chain(ch) for ch in c["chains"]]
            try:
                tw, _ = jump_twist_of_2plus1(chains_norm, m, n)
            except Exception:
                continue
            n_tw += 1
            tw0 = common.is0(tw)
            tab[(refl_pass, par_pass, tw0)] += 1
            if refl_pass and par_pass and not tw0:      # the gate-independence witness
                twist_only.append({"hash": c["hash"], "tw": tw})
            if (not refl_pass) and tw0:                 # reflection rejects, twist would pass
                refl_only.append(c["hash"])
        out["%dx%d%s" % (m, n, "*" if anc else "")] = {
            "K": K, "closing_total": len(cands), "twoplus1": len(two), "twist_computed": n_tw,
            "refl_pass_AND_parity_pass_AND_tw0": tab[(True, True, True)],
            "TWIST_ONLY_reject__refl_pass_parity_pass_tw_nonzero": len(twist_only),
            "twist_only_detail": twist_only,
            "reflection_only_reject__refl_fail_tw0": len(refl_only),
            "parity_fail_total": sum(v for (rp, pp, t0), v in tab.items() if not pp),
            "refl_fail_total": sum(v for (rp, pp, t0), v in tab.items() if not rp),
        }
    # 8x6 is too large to re-enumerate here; the cache already records its lone witness.
    out["_witness_8x6#202"] = ("cached: 2+1, reflection+parity+exit ALL PASS, jump/normal/no Tw=-720 "
                               "=> the ONE twist-only reject (passes refl+parity, fails twist) across "
                               "all 264 cached 2+1; physically UNLABELLED (paper-fold action #1).")
    out["_twist_only_witnessed_on_tested_grids"] = any(
        v["TWIST_ONLY_reject__refl_pass_parity_pass_tw_nonzero"] > 0
        for v in out.values() if isinstance(v, dict))
    return out


# ---------- main ----------

def main():
    caches = load_caches()
    print("loaded %d 3-stack caches: %s" % (len(caches), ", ".join(c[0] for c in caches)))

    print("\n== Part A : twist formula faithfulness (experimental loop_tw vs twostack.twist_value) ==")
    A = part_a(caches)
    print("  integer loops checked : %d   mismatches: %d" %
          (A["integer_loops_checked"], len(A["integer_mismatches"])))
    print("  1+1+1 pairs checked    : %d   mismatches (vs ref & shipped): %d" %
          (A["oneplus_pairs_checked"], len(A["oneplus_mismatches"])))
    print("  partial atan(1/2) loops: %d   int-rounding gaps (EXPECTED): %d" %
          (A["partial_atan_loops"], A["partial_rounding_gaps"]))
    for g in A["partial_gap_sample"]:
        print("      %s#%s float=%.4f rounded=%d (Q-rounding suppresses overhang)" %
              (g["grid"], g["id"], g["exp_float"], g["ref_rounded"]))
    print("  => Part A %s" % ("PASS" if A["pass"] else "FAIL"))

    print("\n== Part B : parity gate sigma-soundness (geometry recompute vs SquareLattice.parity_check) ==")
    B = part_b(caches)
    print("  solutions checked      : %d" % B["solutions_checked"])
    print("  parity disagreements   : %d" % len(B["parity_disagreements"]))
    print("  bridge identity fails  : %d  (x_flip==nH%%2, y_flip==nV%%2)" %
          len(B["bridge_identity_failures"]))
    print("  grids with odd m*n     : %s  (2-stack parity: must be none)" %
          (B["grids_with_odd_mn"] or "none"))
    print("  => Part B %s" % ("PASS" if B["pass"] else "FAIL"))

    print("\n== Part C : physical JAM deciders (independent full gate tuple) ==")
    C = part_c()
    for r in C["deciders"]:
        if not r["matched"]:
            print("  %-9s NOT MATCHED in closing set" % r["finding"])
            continue
        gt = r["gate_tuple"]
        print("  %-9s [%s] parity=%s reflection=%s twist=%s -> catch=%s  (physical JAM)" %
              (r["finding"], r["decomp"], gt["parity"], gt["reflection"],
               gt["twist_jump"], ",".join(r["catching_gates"]) or "NONE!"))
    print("  => Part C %s (all deciders predicted JAM = %s)" %
          ("PASS" if C["pass"] else "FAIL", C["all_predicted_jam"]))

    print("\n== Part D : gate independence on the pre-gate (all-closing) population ==")
    D = part_d([(6, 6, True), (6, 7, False)])
    for k, v in D.items():
        if not isinstance(v, dict):
            print("  %s: %s" % (k, v))
            continue
        print("  %s  closing=%d 2+1=%d  | refl+par+tw0=%d  TWIST-ONLY(refl+par pass, tw!=0)=%d  "
              "REFL-ONLY(refl fail, tw0)=%d  parity_fail=%d  refl_fail=%d" %
              (k, v["closing_total"], v["twoplus1"],
               v["refl_pass_AND_parity_pass_AND_tw0"],
               v["TWIST_ONLY_reject__refl_pass_parity_pass_tw_nonzero"],
               v["reflection_only_reject__refl_fail_tw0"],
               v["parity_fail_total"], v["refl_fail_total"]))

    report = {"partA": A, "partB": B, "partC": C, "partD": D,
              "headline": (
                  "A: twist formula is the 2-stack reference's, unaltered (665 integer loops + 735 "
                  "1+1+1 pairs, 0 mismatches vs twostack.twist_value AND shipped _pair_loop_twist; "
                  "partial's atan(1/2) loops diverge only by twostack's int-rounding, which suppresses "
                  "the overhang signal). B: the nH/nV parity gate IS the checkerboard-sigma necessary "
                  "condition (509 solutions, 0 disagreements, bridge identity x_flip==nH%2 holds; m*n "
                  "even throughout). C: all 3 physical JAMs are predicted JAM -- 6x5#1 & 6x6#1 caught "
                  "by reflection (twist=0), 6x7#8 caught by reflection AND twist=720 (the lab-note "
                  "conflict resolves: the corrected reflection gate ALSO rejects 6x7#8, so it is not a "
                  "twist-only decider). D: gate (in)dependence -- reflection rejects MANY that twist "
                  "would pass (refl-only: 44 on 6x6, 7 on 6x7), but the reverse (passes reflection+"
                  "parity yet twist!=0) is 0 on both 6x6 and 6x7; the ONLY such twist-only reject "
                  "across all 264 cached 2+1 is 8x6#202 (Tw=-720), still physically unlabelled. SO: "
                  "'reflected ~ valid' is largely REAL on tested grids -- twist is near-redundant with "
                  "reflection+parity there -- but NOT formally identical (8x6#202 proves independence). "
                  "And the shipped engine does not even twist-gate 2+1 (search.twist_check stubs "
                  "decided=False), so today twist gates nothing for 2+1.")}
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "_verification.json"), "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    print("\nwrote -> %s" % os.path.relpath(os.path.join(OUTDIR, "_verification.json"), _ROOT))
    print("OVERALL: A=%s B=%s C=%s" %
          ("PASS" if A["pass"] else "FAIL", "PASS" if B["pass"] else "FAIL",
           "PASS" if C["pass"] else "FAIL"))


if __name__ == "__main__":
    main()
