"""test_tri_sigma.py — guards the systemic bipartite->path_sigma twist convention.

trisearch.pairwise_twists (and solve_foldable.record_111 built on it) must score each spliced
pairwise loop chainA + reversed(chainB) with the loop-INDEX sigma (tritwist.path_sigma) — the YYR
authority — NOT the bipartite tile-coloring, which fails to alternate round a spliced loop and reads
a spurious Tw=0. This pins the equilateral 1+1+1 K=10 case (2 closing folds) so a silent revert to the
bipartite convention trips here instead of surfacing as a wrong foldability/JAM diagnosis downstream.

Run: python -m pytest triangle/tests/test_tri_sigma.py   (sys.path via conftest.py)
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # triangle/ for _bootstrap
import _bootstrap  # noqa: E402,F401  (triangle/_bootstrap: triangle/ + tri/ on sys.path; conftest also sets this)

import tritwist as TW           # noqa: E402
import trisearch as TS          # noqa: E402
import prove_obstruction as PO  # noqa: E402
import solve_foldable as SF     # noqa: E402


def _enum_k10():
    """Enumerate every closing equilateral 1+1+1 fold at K=10 (fast: 2 folds). I/O: () -> (lat, list)."""
    lat, S, back = PO.build_ambient(10)
    return lat, list(SF.enum_111(lat, S, back, 10))


def _loops(chains, sig):
    """AB/BC/AC pairwise-loop Tw (int deg) for a given sigma. sig="path" uses path_sigma; else the
    bipartite default. I/O: (chains[3], sig) -> {AB,BC,AC: int}."""
    out = {}
    for nm, (i, j) in zip(("AB", "BC", "AC"), ((0, 1), (1, 2), (0, 2))):
        loop = list(chains[i]) + list(reversed(chains[j]))
        s = TW.path_sigma(len(loop)) if sig == "path" else None
        out[nm] = int(round(TW.loop_twist(loop, sigma=s)["Tw"]))
    return out


def test_pairwise_twists_uses_path_sigma():
    """TS.pairwise_twists matches the path_sigma authority and diverges from bipartite (revert guard)."""
    lat, folds = _enum_k10()
    assert folds, "expected closing equilateral 1+1+1 folds at K=10"
    saw_divergence = False
    for (pa, pm, pc) in folds:
        ch = [list(pa), list(pm), list(pc)]
        L = TS.pairwise_twists(lat, ch)
        got = {nm: int(round(L[nm]["Tw"])) for nm in ("AB", "BC", "AC")}
        assert got == _loops(ch, "path"), "pairwise_twists diverged from path_sigma: %s" % got
        if got != _loops(ch, "bip"):
            saw_divergence = True
    assert saw_divergence, "path and bipartite agree everywhere -> this test cannot detect a revert"


def test_record_111_tw_matches_path_spectrum():
    """solve_foldable.record_111 twist == the path_sigma K=10 spectrum {+-(720,720,480)}."""
    lat, folds = _enum_k10()
    spec = {tuple(SF.record_111(lat, pa, pm, pc, 10)["tw"]) for (pa, pm, pc) in folds}
    assert spec == {(720, 720, 480), (-720, -720, -480)}, spec


def test_oracle_111_k10_self_consistent():
    """ORACLE_111[10] equals the freshly-recomputed path spectrum (guards a stale/bipartite oracle)."""
    lat, folds = _enum_k10()
    spec = Counter()
    for (pa, pm, pc) in folds:
        L = TS.pairwise_twists(lat, [list(pa), list(pm), list(pc)])
        spec[tuple(int(round(L[nm]["Tw"])) for nm in ("AB", "BC", "AC"))] += 1
    exp = SF.ORACLE_111[10]
    assert len(folds) == exp["closing"], "closing count %d != %d" % (len(folds), exp["closing"])
    assert dict(spec) == exp["spectrum"], dict(spec)


if __name__ == "__main__":
    test_pairwise_twists_uses_path_sigma()
    test_record_111_tw_matches_path_spectrum()
    test_oracle_111_k10_self_consistent()
    print("PASS  path_sigma convention pinned (eq 1+1+1 K=10)")
