"""domino21.py — generalized 2+1 decomposition (rigid 2-chain + 1-chain) for ANY reflection
tiling, the tiling-agnostic analog of solve_foldable.enum_21 (which is rhombus-specific to the
equilateral lattice). Used for righttri / scalene / hexagon; equilateral keeps the validated
rhombus enum_21.

Model (research-grade — find an example, may jam; twist is a prediction, not a proof):
  - A DOMINO = an adjacent pair of tiles (the rigid 2-stack unit). The 2-chain is a strip of K
    dominoes built by "fattening" a canonical STRAND (a simple K-walk of representative tiles):
    domino_k = {strand_k, partner_k} with partner_k an unused neighbor of strand_k.
  - The 1-chain is a disjoint simple K-walk.
  - START footprint = the trapezoid S=[strand_0, partner_0, one_0] (so partner_0 is forced = S's
    middle). CLOSING <=> the END triple [strand_-1, partner_-1, one_-1] is again a trapezoid.
  - TWIST via the canonical-strand reduced loop = strand + reversed(1-chain), scored with the
    PATH-FOLLOWING sigma (tritwist.path_sigma): +-1 by loop index. On a non-bipartite tiling
    (honeycomb) that is the only well-defined sigma; on the bipartite ones the strand is not
    sigma-alternating anyway, so path-following is the consistent choice. Tw == Tw_index here.

Reuses trisearch.grow_walks / exit_ok (lat.adj only) so it runs on every Lattice subclass.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trisearch as TS   # noqa: E402  grow_walks, exit_ok
import tritwist as TW     # noqa: E402  loop_twist, path_sigma, fractional
import foldsim as FSIM    # noqa: E402  valid_21 (printed-sheet flat-fold closure gate)


def _gen_partners(lat, strand, first, reserved):
    """Lazily yield injective partner assignments: one neighbor per strand tile, all distinct,
    none in the strand or `reserved`, with partner[0] forced to `first` (the start domino's other
    tile = the start trapezoid's middle)."""
    sset = set(strand)
    n = len(strand)
    partners = [None] * n

    def dfs(k, used):
        if k == n:
            yield list(partners)
            return
        cands = (first,) if k == 0 else lat.adj[strand[k]]
        for p in cands:
            if p in sset or p in used or p in reserved:
                continue
            partners[k] = p
            yield from dfs(k + 1, used | {p})
        partners[k] = None

    yield from dfs(0, set())


def enum_domino_21(lat, S, K, cent=None, time_budget=None, t0=None, stats=None):
    """Yield closing 2+1 solutions from start trapezoid S=[a, mid, b] (a = strand base, mid =
    partner base, b = 1-chain base). Each dict carries strand/partners/one_chain, the 2-chain tile
    set, start/end footprints, and the path-following reduced-loop twist (`loop`).

    `stats`, if given, is a dict this mutates in place with pure counters (no effect on which
    candidates are yielded or their order): "strands" (K-walks of the domino spine), "partner_sets"
    (injective partner rows offered for those strands), "partner_clean" (partner rows that did not
    collide with the strand -- i.e. actually form K disjoint dominoes), "tried" (raw one_chain
    candidates considered), "topology_pass" (passed the dual-graph exit_ok check), "closure_pass"
    (passed the physical closure/foldsim gate -- same count as what's yielded).

    The first three matter for the 2+1-vs-1+1+1 rarity question: they are mortality the 1+1+1 ladder
    has no analogue for, and they are paid BEFORE a single one_chain is generated."""
    a, mid, b = S
    all_tiles = set(lat.tris)
    t0 = t0 if t0 is not None else time.time()
    for strand in TS.grow_walks(lat, a, K, all_tiles - {mid, b}):
        sset = set(strand)
        if stats is not None:
            stats["strands"] = stats.get("strands", 0) + 1
        for partners in _gen_partners(lat, strand, mid, reserved={b}):
            if stats is not None:
                stats["partner_sets"] = stats.get("partner_sets", 0) + 1
            two = sset | set(partners)
            if len(two) != 2 * K:                # partners collided with strand -> not a clean 2-chain
                continue
            if stats is not None:
                stats["partner_clean"] = stats.get("partner_clean", 0) + 1
            free1 = all_tiles - two
            for one_chain in TS.grow_walks(lat, b, K, free1):
                if stats is not None:
                    stats["tried"] += 1
                if not TS.exit_ok(lat, [strand[-1], partners[-1], one_chain[-1]]):
                    continue
                if stats is not None:
                    stats["topology_pass"] += 1
                # PHYSICAL CLOSURE GATE (foldsim): exit_ok is only dual-graph topology. Simulate
                # folding the PRINTED sheet (rigid dominoes + folding ribbon hinges + 1-chain) and
                # require it to seat as a flat 3-stack onto the START trapezoid (all tiles land on
                # {a,mid,b}, uniform K layers, single-valued). Replaces the old reflection_closes_21,
                # which over-folded the rigid domino edge and admitted non-seating folds.
                end_fp = [strand[-1], partners[-1], one_chain[-1]]
                closes, diag = FSIM.valid_21(lat, list(strand), list(partners), list(one_chain),
                                             [a, mid, b], end_fp)
                if not closes:
                    continue
                if stats is not None:
                    stats["closure_pass"] += 1
                loop = list(strand) + list(reversed(one_chain))
                res = TW.loop_twist(loop, cent=cent, sigma=TW.path_sigma(len(loop)))
                yield {
                    "strand": list(strand), "partners": list(partners),
                    "one_chain": list(one_chain), "two_tris": sorted(two),
                    "footprint": [a, mid, b],
                    "end_footprint": end_fp,
                    "loop": res, "sim": diag,
                }
            if time_budget and (time.time() - t0) > time_budget:
                return


def crease_set_21(lat, strand, partners, one_chain, sig=None):
    """Physically-faithful FOLD-edge set for the generic 2+1 sheet: each ribbon hinge between
    consecutive dominoes, and each 1-chain crease. The domino's internal edge (strand_k<->partner_k)
    is deliberately NOT here — a domino is one RIGID 2-tile unit (see rigid_set_21). Values are a
    +-1 used only to 2-color mountain/valley (sig callable; default all-valley)."""
    sig = sig or (lambda t: 1)
    cr = {}

    def add(t1, t2):
        if t2 in lat.adj.get(t1, ()):
            cr[lat.shared[(t1, t2)]] = sig(t1)

    dom = [(strand[k], partners[k]) for k in range(len(strand))]
    for k in range(len(dom) - 1):
        for u in dom[k]:
            for v in dom[k + 1]:
                add(u, v)                                    # ribbon hinge between dominoes
    for k in range(len(one_chain) - 1):
        add(one_chain[k], one_chain[k + 1])                  # 1-chain crease
    return cr


def rigid_set_21(lat, strand, partners):
    """The RIGID (keep-attached, flat) interior edges internal to the 2-chain: each domino's own
    strand_k<->partner_k edge. Rendered grey (not a fold). Returns a set of shared-edge (vertex) keys."""
    rig = set()
    for k in range(len(strand)):
        if partners[k] in lat.adj.get(strand[k], ()):
            rig.add(lat.shared[(strand[k], partners[k])])
    return rig


def _selfcheck():
    """Smoke test on a small right-isosceles patch: find one closing 2+1 example."""
    import righttri as RT
    lat = RT.RightTriLattice(6, 6)
    # a central trapezoid hub
    mids = [t for t in lat.tris if len(lat.adj[t]) == 3]
    cx = sum(c[0] for c in lat.cent.values()) / len(lat.cent)
    cy = sum(c[1] for c in lat.cent.values()) / len(lat.cent)
    mid = min(mids, key=lambda t: (lat.cent[t][0] - cx) ** 2 + (lat.cent[t][1] - cy) ** 2)
    fp = next(f for f in lat.all_trapezoids() if f[1] == mid)
    print("righttri start trapezoid:", fp)
    n = 0
    for sol in enum_domino_21(lat, fp, K=3, cent=RT.centroid, time_budget=20.0):
        n += 1
        if n == 1:
            r = sol["loop"]
            print("  first 2+1 closing fold: strand=%s" % sol["strand"])
            print("    end_footprint=%s  Tw(path)=%.0f  clean=%s"
                  % (sol["end_footprint"], r["Tw"], not TW.fractional(r["Tw"])))
        if n >= 3:
            break
    print("  closing 2+1 examples found (capped at 3):", n)


if __name__ == "__main__":
    _selfcheck()
