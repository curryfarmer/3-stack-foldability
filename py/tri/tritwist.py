"""tritwist.py — closed-loop twist on the triangle lattice.

Same machinery as the square engine (py/search.py _pair_loop_twist, py/twostack.py twist_value):
walk a closed centroid loop, take the doubled signed turn gamma = 2*turn at each vertex, and form
the sigma-weighted sum Tw = sum sigma(v) * gamma(v). Foldable <=> Tw = 0.

Two things make the square framework port verbatim:
  - sigma is the bipartite up/down 2-coloring (UP=+1, DOWN=-1); every dual step flips it, so
    sigma-parity == index-parity along any walk (same as the square checkerboard along a unit walk).
  - turns are multiples of 60 deg, so gamma is a multiple of 120 and a closed loop's Tw is a
    multiple of 360 (the triangle analog of "no 936 pathology").
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trilattice as TL  # noqa: E402


def signed_turn_deg(p1, p2, p3):
    v1 = (p2[0] - p1[0], p2[1] - p1[1])
    v2 = (p3[0] - p2[0], p3[1] - p2[1])
    if math.hypot(*v1) < 1e-9 or math.hypot(*v2) < 1e-9:
        return 0.0
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    cross = v1[0] * v2[1] - v1[1] * v2[0]
    return math.degrees(math.atan2(cross, dot))


def loop_twist(loop_tids, cent=None, sigma=None):
    """Closed loop of tile ids -> dict with sigma-weighted twist (deg) + diagnostics.

    `cent`/`sigma` are callables tid->centroid / tid->+-1; default to the equilateral-triangle
    lattice, so any other reflection tiling (e.g. righttri) just passes its own.

    Tw_sigma   = sum_k sigma(tri_k) * gamma_k          (the physical twist)
    Tw_index   = sum_k (-1)^k * gamma_k                 (index-parity bucketing; == +/-Tw_sigma
                                                          iff sigma strictly alternates round loop)
    gamma_k    = 2 * signed_turn at vertex k (cyclic)
    """
    cent = cent or TL.centroid
    sigma = sigma or TL.sigma
    n = len(loop_tids)
    cents = [cent(t) for t in loop_tids]
    gammas, sigs = [], []
    tw_sigma = tw_index = 0.0
    for k in range(n):
        p1, p2, p3 = cents[(k - 1) % n], cents[k], cents[(k + 1) % n]
        g = 2.0 * signed_turn_deg(p1, p2, p3)
        s = sigma(loop_tids[k])
        gammas.append(round(g, 3))
        sigs.append(s)
        tw_sigma += s * g
        tw_index += (1 if k % 2 == 0 else -1) * g
    alternates = all(sigma(loop_tids[k]) != sigma(loop_tids[(k + 1) % n]) for k in range(n))
    return {
        "Tw": round(tw_sigma, 3),
        "Tw_index": round(tw_index, 3),
        "gammas": gammas,
        "sigmas": sigs,
        "alternates": alternates,
        "n": n,
    }


def fractional(deg, base=360.0, tol=1e-6):
    """True if deg is NOT a multiple of `base` (a geometry-bug flag)."""
    r = abs(deg) % base
    return min(r, base - r) > tol


def _hex_ring_around(lat, a, b):
    """The 6 triangles around interior vertex (a, b), ordered cyclically by angle."""
    ring = [(a, b, "U"), (a - 1, b, "U"), (a, b - 1, "U"),
            (a - 1, b, "D"), (a - 1, b - 1, "D"), (a, b - 1, "D")]
    ring = [t for t in ring if t in lat.adj]
    vx, vy = TL.vcart((a, b))
    ring.sort(key=lambda t: math.atan2(TL.centroid(t)[1] - vy, TL.centroid(t)[0] - vx))
    return ring


def _selfcheck():
    lat = TL.TriLattice(2, 3)
    ring = _hex_ring_around(lat, 1, 1)
    print("hex ring around vertex (1,1):", ring)
    print("  consecutive adjacency (closed):",
          all(ring[(k + 1) % 6] in lat.adj[ring[k]] for k in range(6)))
    res = loop_twist(ring)
    print("  gammas:", res["gammas"])
    print("  sigma alternates round loop:", res["alternates"])
    print("  Tw_sigma = %.3f deg | Tw_index = %.3f deg" % (res["Tw"], res["Tw_index"]))
    print("  Tw multiple of 360 (clean):", not fractional(res["Tw"]),
          "| gammas all multiple of 120:", all(not fractional(g, 120.0) for g in res["gammas"]))


if __name__ == "__main__":
    _selfcheck()
