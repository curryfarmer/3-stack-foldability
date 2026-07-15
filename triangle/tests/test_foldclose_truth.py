"""test_foldclose_truth.py — regression anchors for the non-square physical closure gate.

Pins engine == physical reality on the confirmed ground truth so later hardening can't silently
drift it:

  POSITIVE  the large scalene 1+1+1 (K=16, fixtures/example_scalene_1plus1_allow.json):
            physically foldable; the gate must say reflection_closes_111 == True and every pairwise
            loop twist == 0 (=> foldable).

  NEGATIVE  the equilateral 1+1+1 obstruction at K=12: all 94 closing folds physically close
            (reflection_closes_111 True) but NONE is flat-foldable (some pairwise twist != 0). This
            pins both the JAM-labelling path and the known equilateral obstruction.

Run: python -m pytest triangle/tests/test_foldclose_truth.py   (sys.path via conftest.py)
"""
import json
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))            # repo root

import foldclose as FC          # noqa: E402
import tritwist as TW           # noqa: E402
import scalene as SC            # noqa: E402
import trilattice as TL         # noqa: E402
import prove_obstruction as PO  # noqa: E402
import solve_foldable as SF     # noqa: E402

# TRACKED anchor: promoted out of gitignored results/30-6-2026/ so it travels with the corpus and a
# fresh clone RUNS this assertion instead of erroring on the unguarded read it used to do.
ANCHOR = os.path.join(_HERE, "fixtures", "example_scalene_1plus1_allow.json")


def _anchor_or_skip():
    """Load the tracked scalene anchor. Backstop guard: the file is tracked, so absence means a
    broken checkout rather than a fresh clone. I/O: () -> anchor dict."""
    if not os.path.exists(ANCHOR):
        pytest.skip(f"anchor missing: {ANCHOR}")
    with open(ANCHOR) as f:
        return json.load(f)


def _pairwise_tw(chains, cent, sigma):
    """The three theta-graph pairwise-loop twists (AB, BC, AC), rounded to int degrees."""
    out = []
    for (i, j) in ((0, 1), (1, 2), (0, 2)):
        loop = list(chains[i]) + list(reversed(chains[j]))
        out.append(int(round(TW.loop_twist(loop, cent=cent, sigma=sigma)["Tw"])))
    return out


def test_scalene_anchor_foldable():
    """The large scalene 1+1+1 (K=16) is physically foldable; the engine must agree."""
    d = _anchor_or_skip()
    assert d["tiling"] == "scalene" and d["decomp"] == "1plus1plus1" and d["K"] == 16
    chains = [[tuple(t) for t in c] for c in d["chains"]]
    region = sorted({t for c in chains for t in c})
    lat = SC.ScaleneLattice(cells=region)
    assert FC.reflection_closes_111(lat, chains), "anchor must physically close"
    tw = _pairwise_tw(chains, SC.centroid, SC.sigma)
    assert tw == [0, 0, 0], "anchor twist must be zero (foldable), got %s" % tw


def test_equilateral_K12_obstruction():
    """All equilateral 1+1+1 closing folds at K=12 close but none is flat-foldable (JAM)."""
    lat, S, back = PO.build_ambient(12)
    closing = foldable = 0
    for (pa, pm, pc) in SF.enum_111(lat, S, back, 12):
        ch = [list(pa), list(pm), list(pc)]
        if not FC.reflection_closes_111(lat, ch):
            continue                                   # not a physical closure -> not counted
        closing += 1
        if _pairwise_tw(ch, TL.centroid, TL.sigma) == [0, 0, 0]:
            foldable += 1
    assert closing == 94, "expected 94 closing folds at eq K=12, got %d" % closing
    assert foldable == 0, "equilateral 1+1+1 is obstructed at K=12; found %d foldable" % foldable


if __name__ == "__main__":
    test_scalene_anchor_foldable()
    print("PASS  scalene anchor (K=16) folds: reflection_closes_111 + Tw=[0,0,0]")
    test_equilateral_K12_obstruction()
    print("PASS  equilateral K=12 obstruction: 94 close, 0 foldable")
    print("ALL GROUND-TRUTH ANCHORS GREEN")
