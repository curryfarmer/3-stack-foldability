"""prove_obstruction.py — proof-by-exhaustion that no closing 3-stack fold exists on the
equilateral-triangle lattice for chain length K up to a bound.

Reductions that make this a finite, rigorous check:
  (R1) Symmetry. The triangular lattice symmetry group (p6m) is transitive on trapezoids
       (a trapezoid = a mid triangle + an unordered pair of its 3 neighbors; the group is
       transitive on triangles and rotates the 3 neighbor-pairs into each other). So fixing ONE
       canonical start hub S is without loss of generality for the EXISTENCE question.
  (R2) Forced mid-chain. The mid cell m of S has exactly 3 neighbors: the two arms (= the other
       two chains' start cells) and one "back" neighbor x. The mid-chain cannot revisit and cannot
       step onto another chain's start, so its first step is forced m->x. (Verified below.)

A "closing 3-stack fold of length K" = three vertex-disjoint simple paths of K nodes each, from the
three cells of S, whose three end cells form a trapezoid (any trapezoid; all are congruent, so this
IS exit-footprint congruence). We enumerate all of them from the canonical S inside a disk large
enough to contain every reachable path, and count. Zero ⇒ no closing fold for that K (any hub).

Run: .\.venv\Scripts\python.exe -m triangle.tri.prove_obstruction [Kmax]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trilattice as TL  # noqa: E402


def build_ambient(reach):
    """A triangle region big enough that a radius-`reach` walk from the centre stays inside."""
    s = 2 * reach + 6
    lat = TL.TriLattice(cells=TL.triangle_cells(s))
    # canonical hub: a central DOWN triangle as mid + two of its neighbors as arms
    import statistics
    cx = statistics.mean(TL.centroid(t)[0] for t in lat.tris)
    cy = statistics.mean(TL.centroid(t)[1] for t in lat.tris)
    mids = [t for t in lat.tris if t[2] == "D" and len(lat.adj[t]) == 3]
    mid = min(mids, key=lambda t: (TL.centroid(t)[0] - cx) ** 2 + (TL.centroid(t)[1] - cy) ** 2)
    arms = lat.adj[mid]                       # 3 neighbors (all UP)
    arm1, arm2, back = arms[0], arms[1], arms[2]
    S = [arm1, mid, arm2]                     # trapezoid: arms + mid; `back` is the forced exit
    return lat, S, back


def is_trapezoid(lat, cells):
    if len(set(cells)) != 3:
        return False
    deg = [sum(1 for u in cells if u != t and u in lat.adj[t]) for t in cells]
    return sorted(deg) == [1, 1, 2]


def grow(lat, start, K, blocked):
    """All simple K-node paths from `start` avoiding `blocked` (a set).

    LAZY, and with a mutable used-set. The old version accumulated every path into a list AND
    allocated a fresh tuple + frozenset at each node of the walk; on the honeycomb (degree 6, no
    parity/reachability prune) that is what OOMed the census. Same DFS order, so every caller -- all
    of which merely iterate -- sees an identical sequence."""
    if start in blocked:
        return

    def dfs(last, path, used):
        if len(path) == K:
            yield tuple(path)
            return
        for nb in lat.adj[last]:
            if nb not in used and nb not in blocked:
                used.add(nb)
                path.append(nb)
                yield from dfs(nb, path, used)
                path.pop()
                used.discard(nb)

    yield from dfs(start, [start], {start})


def count_closing(lat, S, back, K, cap=None):
    arm1, mid, arm2 = S
    # (R2) mid-chain forced first step m->x = back; enumerate mid-chains from that
    closing = 0
    examples = []
    base_block = {arm1, arm2}
    # mid-chain: starts mid, second node = back
    midpaths = [p for p in grow(lat, mid, K, base_block) if K == 1 or p[1] == back]
    for pm in midpaths:
        um = set(pm)
        for pa in grow(lat, arm1, K, um | {arm2}):
            ua = um | set(pa)
            for pc in grow(lat, arm2, K, ua):
                if is_trapezoid(lat, [pa[-1], pm[-1], pc[-1]]):
                    closing += 1
                    if len(examples) < 2:
                        examples.append((pa, pm, pc))
                    if cap and closing >= cap:
                        return closing, examples, midpaths
    return closing, examples, midpaths


def main(Kmax):
    print("Proof-by-exhaustion: closing 3-stack folds on the triangular lattice")
    print("(canonical hub WLOG by p6m-transitivity on trapezoids; mid-chain forced)\n")
    print(" K | mid-chains | closing folds")
    print("---+------------+--------------")
    all_zero_through = None      # highest K proven fold-free so far (None until the first clean K)
    counterexample_K = None
    for K in range(2, Kmax + 1):
        lat, S, back = build_ambient(K)
        # verify R2: mid's only non-arm neighbor is `back`
        assert set(lat.adj[S[1]]) == {S[0], S[2], back}, "mid-chain not forced (R2 fails)"
        closing, examples, midpaths = count_closing(lat, S, back, K)
        print(" %2d | %10d | %d %s" % (K, len(midpaths), closing,
              "" if closing == 0 else "  <-- COUNTEREXAMPLE: %s" % (examples[0],)))
        if closing == 0:
            all_zero_through = K
        else:
            counterexample_K = K
            break
    # Guard the verdict so it can never emit a null/empty range: a counterexample at the very first K
    # leaves all_zero_through == None, which would otherwise print a self-contradictory "2 <= K <= 0".
    if counterexample_K is not None:
        print("\nResult: a closing 3-stack fold EXISTS at K = %d (COUNTEREXAMPLE above); the "
              "obstruction does NOT hold." % counterexample_K)
    elif all_zero_through is not None:
        print("\nResult: NO closing 3-stack fold exists for 2 <= K <= %d  (exhaustive, hub WLOG)."
              % all_zero_through)
    else:
        print("\nResult: no K tested (need Kmax >= 2).")
    print("R2 (forced mid-chain) verified at every K.")


if __name__ == "__main__":
    Kmax = int(sys.argv[1]) if len(sys.argv) > 1 else 9
    main(Kmax)
