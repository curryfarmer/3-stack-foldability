"""hunt_foldable.py — search for a FOLDABLE (all pairwise loops Tw=0) closing 1+1+1 triangle
fold whose region has NO HOLES (simply connected).

Constraints, in order of cost:
  - closing: 3 vertex-disjoint K-node chains from the canonical trapezoid hub, ends form a trapezoid;
  - even K only (odd K hits the -240 degenerate-seam artifact on the arm-arm loop, non-physical);
  - hole-free: flood-fill the complement from the ambient boundary; any unreached empty triangle is
    an enclosed hole -> reject;
  - foldable: all three pairwise-loop twists == 0.

Run:  .\.venv\Scripts\python.exe py/tri/hunt_foldable.py [K] [budget]
Prints + renders any hit to report/tri/foldable_K<K>_<n>.png.
"""
import os
import sys
from collections import deque, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trilattice as TL   # noqa: E402
import tritwist as TW      # noqa: E402
import trisearch as TS     # noqa: E402
import trirender as TR     # noqa: E402
import prove_obstruction as PO  # noqa: E402


def holes(lat, region, interior_deg=3):
    """Return the set of enclosed empty tiles (holes) of `region` within ambient `lat`.

    `interior_deg` = the dual-degree of a fully-surrounded tile (3 for any triangle tiling, 6 for
    honeycomb hexagons); a tile with fewer neighbours sits on the ambient outer boundary and seeds
    the complement flood-fill. Empty tiles the flood never reaches are enclosed holes.
    """
    region = set(region)
    boundary = [t for t in lat.tris if t not in region and len(lat.adj[t]) < interior_deg]
    seen = set(boundary)
    q = deque(boundary)
    while q:
        x = q.popleft()
        for y in lat.adj[x]:
            if y not in region and y not in seen:
                seen.add(y)
                q.append(y)
    return [t for t in lat.tris if t not in region and t not in seen]


def hunt(K, budget):
    assert K % 2 == 0, "use even K (odd K has the -240 seam artifact)"
    lat, S, back = PO.build_ambient(K)
    arm1, m, arm2 = S
    midpaths = [p for p in PO.grow(lat, m, K, {arm1, arm2}) if p[1] == back]
    cnt = 0
    closing = 0
    holefree = 0
    twhist = Counter()
    hits = []
    for pm in midpaths:
        um = set(pm)
        for pa in PO.grow(lat, arm1, K, um | {arm2}):
            ua = um | set(pa)
            for pc in PO.grow(lat, arm2, K, ua):
                cnt += 1
                if cnt > budget:
                    print("budget hit at %d" % cnt, flush=True)
                    return hits, closing, holefree, twhist, cnt
                if not PO.is_trapezoid(lat, [pa[-1], pm[-1], pc[-1]]):
                    continue
                closing += 1
                region = set(pa) | set(pm) | set(pc)
                if holes(lat, region):
                    continue
                holefree += 1
                L = TS.pairwise_twists(lat, [list(pa), list(pm), list(pc)])
                key = tuple(round(L[k]["Tw"]) for k in ("AB", "BC", "AC"))
                twhist[key] += 1
                if all(abs(L[k]["Tw"]) < 1e-6 for k in L):
                    hits.append((pa, pm, pc, L))
                    print("  HIT: foldable + hole-free at K=%d  ends=%s" %
                          (K, [pa[-1], pm[-1], pc[-1]]), flush=True)
                    if len(hits) >= 5:
                        return hits, closing, holefree, twhist, cnt
    return hits, closing, holefree, twhist, cnt


def render_hits(K, hits):
    out = []
    for i, (pa, pm, pc, L) in enumerate(hits, 1):
        region = sorted(set(pa) | set(pm) | set(pc))
        sub = TL.TriLattice(cells=region)
        note = ("1+1+1 triangle fold (K=%d, %d tris)\nAB=%+.0f BC=%+.0f AC=%+.0f\n"
                "FOLDABLE (Tw=0) + NO HOLES" % (K, len(region), L["AB"]["Tw"],
                                                L["BC"]["Tw"], L["AC"]["Tw"]))
        p = TR.render_tiling(sub, [list(pa), list(pm), list(pc)],
                             "1+1+1 triangle fold (K=%d) — FOLDABLE, hole-free" % K,
                             "foldable_K%d_%d.png" % (K, i), twist_note=note,
                             footprint=[pa[0], pm[0], pc[0]])
        out.append(p)
    return out


def main(K, budget):
    print("Hunting: closing + even-K + hole-free + Tw=0, K=%d budget=%d" % (K, budget), flush=True)
    hits, closing, holefree, twhist, cnt = hunt(K, budget)
    print("\nK=%d: iters=%d  closing=%d  hole-free=%d" % (K, cnt, closing, holefree), flush=True)
    print("twist patterns among hole-free closing folds:", dict(twhist), flush=True)
    print("FOLDABLE + hole-free hits:", len(hits), flush=True)
    if hits:
        for p in render_hits(K, hits):
            print("  rendered", os.path.relpath(p), flush=True)


if __name__ == "__main__":
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 40000000
    main(K, budget)
