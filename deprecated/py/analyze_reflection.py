#!/usr/bin/env python3
"""analyze_reflection.py — Q4 vector-reflection analysis (read-only, engine untouched).

Evaluates the two "vectors stay aligned" verdicts INDEPENDENTLY for every full-coverage
candidate, so we can see where they disagree:
  - parity_check  (search.py): orientation-aware fold-count parity.
  - reflection_check (search.py): all chains' projected final {edge, sign} must agree.

The engine applies parity THEN reflection (short-circuit), so disagreements are normally
invisible. Here we compute both on the same candidate population (exit-footprint passers) and
build a parity x reflection contingency table, split by decomp and shape.

Answers:
  Q4a  does reflection ever reject what parity admits? (parity=T, refl=F count)
  Q4b  what is the actual 1+1+1 final-vector pattern? (dump accepted 1+1+1 vectors)
  Q4c  is the mismatch about edge or only sign? (edge vs sign-only tally)

Reuses search.py / fold.py primitives directly — no engine changes.
"""
import fold as Fold
import search as Search


GRIDS = [(6, 4), (6, 5), (6, 6), (5, 6), (3, 4), (4, 3), (3, 2)]


def final_vectors(chains):
    """Project each chain's canonical base vector through its fold chain -> [(edge, sign)]."""
    out = []
    for c in chains:
        base = c["baseCells"][0]
        v0 = {"x": base[0], "y": base[1], "edge": "T", "sign": 1}
        vf = Fold.project_vector(v0, c["placements"][-1]["transformChain"])
        out.append((vf["edge"], vf["sign"]))
    return out


def reflection_verdict(fvs):
    """All final vectors agree? plus mismatch classification when they don't."""
    edges = {e for (e, s) in fvs}
    signs = {s for (e, s) in fvs}
    if len(edges) == 1 and len(signs) == 1:
        return True, None
    if len(edges) == 1 and len(signs) > 1:
        return False, "sign-only"
    return False, "edge"


def analyze_grid(m, n):
    K = (m * n) // 3
    opts = {"shapes": {"L": True, "Rect": True},
            "decomps": {"2+1": True, "1+1+1": True},
            "allowNonCorner": False}
    rows = []                 # raw exit-passing candidates
    accepted_hashes = set()   # exit & parity & refl  -> dedup (engine-equivalent set)
    ctx = {k: 0 for k in ("nodeCount", "candidateCount", "coveredCount")}
    ctx["cancelled"] = False

    for fp in Search.enumerate_footprints(m, n, opts):
        for decomp in Search.enumerate_decompositions(fp, opts):

            def on_candidate(chains, _fp=fp, _decomp=decomp):
                if not Search.exit_footprint_check(chains, _fp["shape"]):
                    return
                parity = Search.parity_check(chains)          # may return early
                fvs = final_vectors(chains)
                refl, mismatch = reflection_verdict(fvs)
                nHV = []
                for c in chains:
                    nH = sum(1 for a in c["foldArrows"] if a in ("L", "R"))
                    nHV.append((nH, len(c["foldArrows"]) - nH))
                rows.append({
                    "shape": _fp["shape"], "decomp": _decomp["decomp"],
                    "parity": parity, "refl": refl, "mismatch": mismatch,
                    "fvs": fvs, "nHV": nHV,
                })
                if parity and refl:
                    accepted_hashes.add(Search.canonical_hash(_fp, chains, m, n))

            Search.search_decomposition(m, n, K, decomp, on_candidate, ctx)

    return rows, len(accepted_hashes)


def contingency(rows):
    """Return dict (parity,refl)->count."""
    c = {(True, True): 0, (True, False): 0, (False, True): 0, (False, False): 0}
    for r in rows:
        c[(r["parity"], r["refl"])] += 1
    return c


def fmt_cont(c, label):
    return (f"{label:<22} | P✓R✓ {c[(True,True)]:>5}  P✓R✗ {c[(True,False)]:>5}  "
            f"P✗R✓ {c[(False,True)]:>5}  P✗R✗ {c[(False,False)]:>5}")


def main():
    all_rows = []
    print("=== per-grid: candidate population (raw, pre-dedup) + engine cross-check ===\n")
    for (m, n) in GRIDS:
        rows, accepted = analyze_grid(m, n)
        for r in rows:
            r["grid"] = f"{m}x{n}"
        all_rows.extend(rows)
        c = contingency(rows)
        print(fmt_cont(c, f"{m}x{n} (raw {len(rows)})"))
        print(f"{'':22} | accepted(dedup, =engine) = {accepted}")
    print()

    # ---- Q4a: does reflection add constraint beyond parity? ----
    overall = contingency(all_rows)
    print("=== Q4a: overall contingency (all grids, raw candidates) ===")
    print(fmt_cont(overall, "ALL"))
    pr = overall[(True, False)]
    rp = overall[(False, True)]
    print(f"\nparity✓ & reflection✗  = {pr}  -> reflection "
          f"{'ADDS constraint (NOT redundant)' if pr else 'is REDUNDANT given parity'}")
    print(f"parity✗ & reflection✓  = {rp}  -> parity "
          f"{'ADDS constraint beyond reflection' if rp else 'adds nothing reflection misses'}")

    # split by decomp + shape
    print("\n--- split by decomp ---")
    for d in ("2+1", "1+1+1"):
        print(fmt_cont(contingency([r for r in all_rows if r["decomp"] == d]), d))
    print("--- split by shape ---")
    for s in ("L", "Rect"):
        print(fmt_cont(contingency([r for r in all_rows if r["shape"] == s]), s))
    print("--- split by shape x decomp ---")
    for s in ("L", "Rect"):
        for d in ("2+1", "1+1+1"):
            print(fmt_cont(contingency([r for r in all_rows
                                        if r["shape"] == s and r["decomp"] == d]),
                           f"{s} {d}"))

    # ---- Q4c: edge vs sign-only mismatch among reflection failures ----
    fails = [r for r in all_rows if not r["refl"]]
    edge = sum(1 for r in fails if r["mismatch"] == "edge")
    sign = sum(1 for r in fails if r["mismatch"] == "sign-only")
    print(f"\n=== Q4c: reflection failures = {len(fails)}  "
          f"(edge-mismatch {edge}, sign-only {sign}) ===")
    print("  sign-only failures (parity may admit, edges agree but sides differ):")
    shown = 0
    for r in fails:
        if r["mismatch"] == "sign-only" and r["parity"]:
            print(f"    {r['grid']} {r['shape']} {r['decomp']} nHV={r['nHV']} fvs={r['fvs']}")
            shown += 1
            if shown >= 12:
                print("    ...")
                break

    # ---- the crux rows: parity✓ refl✗ (reflection rejecting parity-admitted) ----
    crux = [r for r in all_rows if r["parity"] and not r["refl"]]
    print(f"\n=== crux: parity✓ & reflection✗  ({len(crux)} rows) ===")
    for r in crux[:20]:
        print(f"    {r['grid']} {r['shape']} {r['decomp']} mismatch={r['mismatch']} "
              f"nHV={r['nHV']} fvs={r['fvs']}")
    if len(crux) > 20:
        print(f"    ... (+{len(crux)-20} more)")

    # ---- Q4b: accepted 1+1+1 final-vector patterns ----
    print("\n=== Q4b: accepted (P✓R✓) 1+1+1 final-vector patterns ===")
    seen = {}
    for r in all_rows:
        if r["decomp"] == "1+1+1" and r["parity"] and r["refl"]:
            key = (r["shape"], tuple(sorted(r["fvs"])), tuple(sorted(r["nHV"])))
            seen.setdefault(key, [0, r["grid"]])
            seen[key][0] += 1
    if not seen:
        print("  (none accepted)")
    for (shape, fvs, nhv), (cnt, grid) in sorted(seen.items()):
        print(f"  {shape:<4} fvs={list(fvs)}  nHV={list(nhv)}  (x{cnt}, e.g. {grid})")


if __name__ == "__main__":
    main()
