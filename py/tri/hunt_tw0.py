"""hunt_tw0.py — does a FOLDABLE (Tw=0) closing 1+1+1 triangle fold exist at a given even K,
allowing holes? Exhaustively enumerates closing folds from the canonical hub, records the full
pairwise-twist histogram, collects every Tw=0 (all three loops zero) example with its hole status,
and renders up to 3.

Run:  .\.venv\Scripts\python.exe py/tri/hunt_tw0.py [K]
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trilattice as TL   # noqa: E402
import tritwist as TW      # noqa: E402
import trisearch as TS     # noqa: E402
import trirender as TR     # noqa: E402
import prove_obstruction as PO   # noqa: E402
from hunt_foldable import holes  # noqa: E402


def main(K):
    assert K % 2 == 0
    lat, S, back = PO.build_ambient(K)
    arm1, m, arm2 = S
    midpaths = [p for p in PO.grow(lat, m, K, {arm1, arm2}) if p[1] == back]
    print("K=%d  mid-chains=%d  enumerating closing folds..." % (K, len(midpaths)), flush=True)
    cnt = closing = 0
    hist = Counter()
    tw0 = []          # (pa,pm,pc,L,has_holes)
    for pm in midpaths:
        um = set(pm)
        for pa in PO.grow(lat, arm1, K, um | {arm2}):
            ua = um | set(pa)
            for pc in PO.grow(lat, arm2, K, ua):
                cnt += 1
                if not PO.is_trapezoid(lat, [pa[-1], pm[-1], pc[-1]]):
                    continue
                closing += 1
                L = TS.pairwise_twists(lat, [list(pa), list(pm), list(pc)])
                key = tuple(round(L[k]["Tw"]) for k in ("AB", "BC", "AC"))
                hist[key] += 1
                if all(abs(L[k]["Tw"]) < 1e-6 for k in L):
                    hh = bool(holes(lat, set(pa) | set(pm) | set(pc)))
                    tw0.append((pa, pm, pc, L, hh))
    print("iters=%d  closing=%d" % (cnt, closing), flush=True)
    print("twist (AB,BC,AC) histogram over ALL closing folds:", flush=True)
    for k, v in sorted(hist.items(), key=lambda kv: -kv[1]):
        frac = any(TW.fractional(x) for x in k)
        print("   %-22s x %-4d %s" % (str(k), v, "(fractional/non-physical)" if frac else ""), flush=True)
    print("FOLDABLE (Tw=0 on all 3 loops): %d   [hole-free of those: %d]"
          % (len(tw0), sum(1 for t in tw0 if not t[4])), flush=True)
    for i, (pa, pm, pc, L, hh) in enumerate(tw0[:3], 1):
        region = sorted(set(pa) | set(pm) | set(pc))
        sub = TL.TriLattice(cells=region)
        note = ("1+1+1 triangle fold (K=%d, %d tris)\nAB=0 BC=0 AC=0  -> FOLDABLE\n%s"
                % (K, len(region), "has holes" if hh else "hole-free"))
        p = TR.render_tiling(sub, [list(pa), list(pm), list(pc)],
                             "1+1+1 triangle fold (K=%d) — FOLDABLE (Tw=0)%s"
                             % (K, "" if not hh else ", holey"),
                             "tw0_K%d_%d.png" % (K, i), twist_note=note,
                             footprint=[pa[0], pm[0], pc[0]])
        print("  rendered", os.path.relpath(p), "holes=%s" % hh, flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 12)
