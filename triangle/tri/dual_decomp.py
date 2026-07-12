"""Dual-decomposability: which sheets fold BOTH as 2+1 (rigid domino ribbon) and as 1+1+1?

The two decompositions are not as far apart as their separate code paths suggest. Both start from the
same trapezoid S = [a, mid, b] and both end on a triple [.,.,.] that must again be a trapezoid:

    2+1     strand  from a     partners from mid    one_chain from b
    1+1+1   chain A from a     chain B  from mid    chain C   from b

So a 2+1 solution and a 1+1+1 solution over the SAME tiles are the same three tile-sequences, read
under different rigidity assumptions. Exactly two things differ:

  * CHAIN-NESS. 1+1+1 needs `partners` to be a connected simple path (it is a fold chain). The 2+1
    enumerator (domino21._gen_partners) only requires each partner to be an unused NEIGHBOUR of its
    strand tile, injectively -- the partner row need not be a walk at all. So a 2+1 splits into a
    1+1+1 only when its partner row happens to be a path.
  * RIGIDITY. In 2+1 the strand-partner crease is never folded (domino21.rigid_set_21); the domino is
    one rigid 2-stack unit. In 1+1+1 that crease does not exist -- the two rows fold independently.

Hence the two directions, and the two gates each must clear:

    split_21_to_111   is `partners` a path?          -> re-score with reflection_closes_111 + 3 theta twists
    merge_111_to_21   is a chain pair in lockstep?   -> re-score with foldsim.valid_21 + reduced-loop twist

A sheet that clears BOTH is *dual*: the same parallel run of tiles can be read either as one rigid
domino or as two independent monomino chains, and it folds flat either way. That is the structural
statement of why 2+1 is the rarer decomposition -- 2+1 is 1+1+1 plus a rigidity constraint, so the
2+1 solutions can only ever be a subset of the dual-readable ones.

Usage:
    python -m triangle.tri.dual_decomp                      # scan the whole census
    python -m triangle.tri.dual_decomp --tiling righttri
"""
import argparse
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_example as FE      # noqa: E402  build_lat, pairwise, GEN
import foldclose as FC         # noqa: E402  reflection_closes_111
import foldsim as FSIM         # noqa: E402  valid_21
import tritwist as TW          # noqa: E402  loop_twist, path_sigma

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CENSUS = os.path.join(REPO, "results", "census")

TILINGS = ["equilateral", "righttri", "scalene", "hex"]


def _t(x):
    """JSON list -> lattice tile id (tuple)."""
    return tuple(x)


def _longest_run(flags):
    """Longest run of consecutive True in a bool list."""
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def is_path(lat, chain):
    """Is this tile sequence a connected simple walk? (1+1+1 chains must be; 2+1 partner rows need not.)"""
    if len(set(chain)) != len(chain):
        return False
    return all(chain[i + 1] in lat.adj[chain[i]] for i in range(len(chain) - 1))


def path_run(lat, chain):
    """Longest stretch of the sequence that IS a walk, in tiles. == len(chain) iff is_path."""
    if len(chain) < 2:
        return len(chain)
    steps = [chain[i + 1] in lat.adj[chain[i]] for i in range(len(chain) - 1)]
    return _longest_run(steps) + 1


def in_lockstep(lat, c1, c2):
    """Is every tile of c2 adjacent to its opposite number in c1? (the domino/twin condition)"""
    return len(c1) == len(c2) and all(b in lat.adj[a] for a, b in zip(c1, c2))


def lockstep_run(lat, c1, c2):
    """Longest stretch over which two chains run PARALLEL — i.e. c2[k] adjacent to c1[k] for a run of
    consecutive k. This is the *partial* version of the domino condition: over such a stretch the two
    rows are a domino ribbon (readable as one rigid 2-stack unit), and outside it they are not. A run
    of len(c1) is full dominoability; a run of 1 is none. This is the statistic that says how close a
    1+1+1 sheet comes to being 2+1, and it is what a plain fold/no-fold count cannot see."""
    return _longest_run([b in lat.adj[a] for a, b in zip(c1, c2)])


def score_111(lat, tiling, chains):
    """Re-score a chain triple through the 1+1+1 gates. -> (closes, tw, foldable)"""
    chains = [list(c) for c in chains]
    if not FC.reflection_closes_111(lat, chains):
        return False, None, False
    L = FE.pairwise(chains, FE.GEN[tiling]["cent"], "path")
    tw = [int(round(L[nm]["Tw"])) for nm in ("AB", "BC", "AC")]
    return True, tw, all(v == 0 for v in tw)


def score_21(lat, tiling, strand, partners, one_chain):
    """Re-score a (strand, partners, one_chain) triple through the 2+1 gates. -> (closes, tw, foldable)"""
    fp = [strand[0], partners[0], one_chain[0]]
    end_fp = [strand[-1], partners[-1], one_chain[-1]]
    closes, _ = FSIM.valid_21(lat, list(strand), list(partners), list(one_chain), fp, end_fp)
    if not closes:
        return False, None, False
    loop = list(strand) + list(reversed(one_chain))
    res = TW.loop_twist(loop, cent=FE.GEN[tiling]["cent"], sigma=TW.path_sigma(len(loop)))
    tw = round(res["Tw"], 3)
    return True, tw, abs(res["Tw"]) < 1e-6


def split_21_to_111(lat, tiling, rec):
    """A 2+1 record -> its 1+1+1 reading, if it has one. Returns a dict or None (partner row not a path)."""
    strand = [_t(x) for x in rec["strand"]]
    partners = [_t(x) for x in rec["partners"]]
    one_chain = [_t(x) for x in rec["one_chain"]]
    if not is_path(lat, partners):
        return None                       # the domino's partner row is not a chain -> no 1+1+1 reading
    closes, tw, foldable = score_111(lat, tiling, [strand, partners, one_chain])
    return {"partners_is_path": True, "closes_111": closes, "tw_111": tw, "foldable_111": foldable}


def merge_111_to_21(lat, tiling, rec):
    """A 1+1+1 record -> its 2+1 reading(s), if any. The domino must pair an ARM chain with the MID
    chain (in a trapezoid the two arms touch the mid but not each other), so there are exactly two
    candidate pairings: (A,B) with C free, and (C,B) with A free."""
    A, B, C = ([_t(x) for x in c] for c in rec["chains"])
    out = []
    for strand, one_chain, tag in ((A, C, "AB|C"), (C, A, "CB|A")):
        if not in_lockstep(lat, strand, B):
            continue                      # not a twin pair -> cannot be read as a rigid domino
        closes, tw, foldable = score_21(lat, tiling, strand, B, one_chain)
        out.append({"pairing": tag, "closes_21": closes, "tw_21": tw, "foldable_21": foldable})
    return out


def scan(tilings, census=CENSUS, verbose=False):
    rows = []
    for path in sorted(os.listdir(census)):
        if not path.endswith(".jsonl.gz"):
            continue
        stem = path[:-len(".jsonl.gz")]
        tiling, decomp, ktag = stem.rsplit("_", 2)
        if tiling not in tilings:
            continue
        K = int(ktag[1:])
        lat = FE.build_lat(tiling, decomp, K)

        # STREAM. The biggest cell holds 2,000,000 records; materialising them (and a per-record run
        # list) is hundreds of MB to GBs for no reason. Accumulate scalars + a run histogram instead.
        n = fold = convertible = dual = 0
        run_sum = run_max = run_max_fold = run_half = 0
        with gzip.open(os.path.join(census, path), "rt") as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                n += 1
                foldable = r["foldable"]
                fold += bool(foldable)

                if decomp == "2plus1":
                    run = path_run(lat, [_t(x) for x in r["partners"]])
                    s = split_21_to_111(lat, tiling, r)
                    ok = s is not None and foldable and s["foldable_111"]
                    convertible += s is not None
                else:
                    A, B, C = ([_t(x) for x in c] for c in r["chains"])
                    run = max(lockstep_run(lat, A, B), lockstep_run(lat, C, B))
                    ms = merge_111_to_21(lat, tiling, r)
                    ok = bool(ms) and foldable and any(m["foldable_21"] for m in ms)
                    convertible += bool(ms)
                dual += bool(ok)

                run_sum += run
                run_max = max(run_max, run)
                if foldable:
                    run_max_fold = max(run_max_fold, run)
                if run * 2 >= K:
                    run_half += 1
        if not n:
            continue

        rows.append(dict(
            tiling=tiling, decomp=decomp, K=K, n=n, fold=fold,
            convertible=convertible, dual=dual,
            run_max=run_max,
            run_mean=round(run_sum / n, 2),
            run_max_fold=run_max_fold,
            run_half=run_half,          # parallel over >= half the chain
        ))
        if verbose:
            print("  %-12s %-12s K=%-2d n=%-6d fold=%-5d conv=%-5d dual=%-4d "
                  "run(max/mean)=%d/%.1f  >=K/2: %d"
                  % (tiling, decomp, K, n, fold, convertible, dual,
                     rows[-1]["run_max"], rows[-1]["run_mean"], rows[-1]["run_half"]),
                  flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser(description="dual-decomposability scan over the census")
    ap.add_argument("--tiling", action="append", choices=TILINGS)
    ap.add_argument("--census", default=CENSUS)
    ap.add_argument("--out")
    args = ap.parse_args()
    tilings = args.tiling or TILINGS
    out = args.out or os.path.join(args.census, "dual_decomp.json")

    rows = scan(tilings, census=args.census, verbose=True)
    with open(out, "w") as fh:
        json.dump(rows, fh, indent=2)

    print("\n### Dual-decomposable patterns\n")
    print("| tiling | decomp | K | closing | flat | convertible | dual | longest parallel run "
          "(max / mean) | run ≥ K/2 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: (r["decomp"], r["tiling"], r["K"])):
        print("| %s | %s | %d | %d | %d | %d | %d | %d / %.1f of %d | %d |"
              % (r["tiling"], r["decomp"], r["K"], r["n"], r["fold"],
                 r["convertible"], r["dual"], r["run_max"], r["run_mean"], r["K"],
                 r["run_half"]))
    print("\n`convertible` = admits the other decomposition's reading in FULL "
          "(2+1: the partner row is a path; 1+1+1: a chain pair is in lockstep the whole way).")
    print("`dual` = folds flat under BOTH readings.")
    print("`longest parallel run` = the PARTIAL statistic — the longest stretch, in tiles, over "
          "which the two rows run parallel (2+1: the partner row is a walk; 1+1+1: a chain pair is "
          "adjacent index-by-index). A run of K is full convertibility; a run of 1 is none. This is "
          "how close a sheet comes to admitting the other decomposition.")
    print("\n-> %s" % os.path.relpath(out, REPO))


if __name__ == "__main__":
    main()
