"""trisearch.py — brute-force 3-stack enumerator on the small triangle grid.

The region is tiny (12 triangles) so we enumerate exhaustively, mirroring py/search.py:
  - 1+1+1: three 1-chains (triangle walks, K=4 each) from the 3 trapezoid-footprint triangles,
    disjoint, covering all 12, ending in a congruent trapezoid (exit-footprint).
  - 2+1: a rigid rhombus-ribbon 2-chain (walk on the M x N rhombus/cell grid, K=4 rhombi = 8
    triangles) from the footprint rhombus + a 1-chain (triangle walk, K=4) from the third
    footprint triangle, disjoint, covering all 12, exit trapezoid. Twist via the half-tile
    (canonical-strand) reduction: collapse each 2-chain rhombus to one representative triangle.

No parity gate is imposed (the triangle parity rule is itself unknown / under test); we enumerate
all geometric solutions and annotate each with twist. Foldable <=> Tw = 0 is the hypothesis tested.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trilattice as TL   # noqa: E402
import tritwist as TW      # noqa: E402

K = 4  # chain length on the 2x3 grid (12 triangles / 3)


# ---------- generic triangle walk ----------
def grow_walks(lat, start, length, free):
    """All simple triangle walks of `length` cells from `start`, staying inside `free`."""
    out = []

    def dfs(walk, used):
        if len(walk) == length:
            out.append(list(walk))
            return
        for nb in lat.adj[walk[-1]]:
            if nb in free and nb not in used:
                used.add(nb)
                walk.append(nb)
                dfs(walk, used)
                walk.pop()
                used.discard(nb)

    if start in free:
        dfs([start], {start})
    return out


def exit_ok(lat, finals):
    """The 3 chain-end triangles must form a trapezoid (a path: degrees 1,2,1 among themselves)."""
    if len(set(finals)) != 3:
        return False
    deg = []
    for t in finals:
        deg.append(sum(1 for u in finals if u != t and u in lat.adj[t]))
    return sorted(deg) == [1, 1, 2]


def pairwise_twists(lat, chains):
    """The three theta-graph pairwise-loop twists for a 1+1+1 solution."""
    names = ["AB", "BC", "AC"]
    pairs = [(0, 1), (1, 2), (0, 2)]
    res = {}
    for nm, (i, j) in zip(names, pairs):
        loop = chains[i] + list(reversed(chains[j]))
        res[nm] = TW.loop_twist(loop)
    return res


# ---------- 1+1+1 ----------
def search_111(lat, K=None, require_exit=True):
    Kc = K if K is not None else len(lat.tris) // 3
    sols, seen = [], set()
    allset = set(lat.tris)
    for fp in lat.all_trapezoids():
        A, B, C = fp
        for wa in grow_walks(lat, A, Kc, allset):
            freeb = allset - set(wa)
            for wb in grow_walks(lat, B, Kc, freeb):
                freec = freeb - set(wb)
                for wc in grow_walks(lat, C, Kc, freec):
                    if set(wc) != freec:
                        continue
                    closes = exit_ok(lat, [wa[-1], wb[-1], wc[-1]])
                    if require_exit and not closes:
                        continue
                    key = (tuple(wa), tuple(wb), tuple(wc))
                    if key in seen:
                        continue
                    seen.add(key)
                    loops = pairwise_twists(lat, [wa, wb, wc])
                    foldable = closes and all(abs(loops[k]["Tw"]) < 1e-6 for k in loops)
                    sols.append({"decomp": "1+1+1", "footprint": fp,
                                 "chains": [wa, wb, wc], "loops": loops, "closes": closes,
                                 "foldable": foldable,
                                 "frac": any(TW.fractional(loops[k]["Tw"]) for k in loops)})
    return sols


# ---------- 2+1 ----------
def _rhombus_grid_adj(M, N):
    adj = {}
    for j in range(N):
        for i in range(M):
            nb = []
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if 0 <= i + di < M and 0 <= j + dj < N:
                    nb.append((i + di, j + dj))
            adj[(i, j)] = nb
    return adj


def grow_rhombus_walks(radj, start, length, free):
    out = []

    def dfs(walk, used):
        if len(walk) == length:
            out.append(list(walk))
            return
        for nb in radj[walk[-1]]:
            if nb in free and nb not in used:
                used.add(nb); walk.append(nb)
                dfs(walk, used)
                walk.pop(); used.discard(nb)

    if start in free:
        dfs([start], {start})
    return out


def search_21(lat):
    """2+1: rigid rhombus-ribbon 2-chain + 1-chain; twist via canonical-strand reduction."""
    sols, seen = [], set()
    M, N = lat.M, lat.N
    radj = _rhombus_grid_adj(M, N)
    allcells = {(i, j) for j in range(N) for i in range(M)}
    alltris = set(lat.tris)
    for fp in lat.all_trapezoids():
        # trapezoid (i0,j0): 2-chain base rhombus = (i0,j0); 1-chain base = UP(i0+1,j0)
        i0, j0, _ = fp[0]
        one_base = fp[2]                         # UP(i0+1, j0)
        for rib in grow_rhombus_walks(radj, (i0, j0), K, allcells):
            ribset = set(rib)
            two_tris = set()
            for (ci, cj) in rib:
                two_tris.add((ci, cj, "U")); two_tris.add((ci, cj, "D"))
            if one_base in two_tris:             # 1-chain start must be free
                continue
            free1 = alltris - two_tris
            for w1 in grow_walks(lat, one_base, K, free1):
                if set(w1) != free1:
                    continue
                # exit: 2-chain end rhombus contributes its strand triangle + 1-chain end
                strand = [(ci, cj, "U") for (ci, cj) in rib]   # canonical strand = UP per rhombus
                finals = [strand[-1], w1[-1]]
                # the third "exit cell" is the other strand-adjacent end triangle of last rhombus
                last_rh = rib[-1]
                third = (last_rh[0], last_rh[1], "D")
                if not exit_ok(lat, [strand[-1], third, w1[-1]]):
                    continue
                loop = strand + list(reversed(w1))
                res = TW.loop_twist(loop)
                key = (tuple(rib), tuple(w1))
                if key in seen:
                    continue
                seen.add(key)
                sols.append({"decomp": "2+1", "footprint": fp,
                             "ribbon": rib, "two_tris": sorted(two_tris),
                             "chains": [strand, w1], "one_chain": w1,
                             "loop": res, "foldable": abs(res["Tw"]) < 1e-6,
                             "frac": TW.fractional(res["Tw"])})
    return sols


def _summary(sols, kind):
    n = len(sols)
    fold = sum(1 for s in sols if s["foldable"])
    frac = sum(1 for s in sols if s["frac"])
    print("%-6s solutions: %3d | predicted foldable (Tw=0): %3d | fractional-twist (BUG): %d"
          % (kind, n, fold, frac))


if __name__ == "__main__":
    lat = TL.TriLattice(2, 3)
    s111 = search_111(lat)
    s21 = search_21(lat)
    _summary(s111, "1+1+1")
    _summary(s21, "2+1")
    # show a few twist values
    print("\nsample 1+1+1 loop twists (AB,BC,AC):")
    for s in s111[:6]:
        print("  fp=%s  AB=%g BC=%g AC=%g  foldable=%s"
              % (s["footprint"][1], s["loops"]["AB"]["Tw"], s["loops"]["BC"]["Tw"],
                 s["loops"]["AC"]["Tw"], s["foldable"]))
    print("\nsample 2+1 reduced-loop twists:")
    for s in s21[:6]:
        print("  fp=%s  ribbon=%s  Tw=%g  foldable=%s"
              % (s["footprint"][1], s["ribbon"], s["loop"]["Tw"], s["foldable"]))
