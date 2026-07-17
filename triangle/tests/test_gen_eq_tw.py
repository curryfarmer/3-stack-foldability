"""test_gen_eq_tw.py — regression pin for the equilateral gen_eq top-level `tw` (TR-2).

gen_eq's 1+1+1 branch used to yield a candidate carrying `rec`/`tw_desc` but NO top-level `tw`,
so the record writer in run_case (`"tw": cand.get("tw")`) stored tw:null for every equilateral
candidate even though the twist was computed. This pins that the yielded candidate exposes a
non-null 3-tuple `tw` at the top level, matching gen_111/gen_21.

Run: python -m pytest triangle/tests/test_gen_eq_tw.py   (sys.path via conftest.py)
"""
import time

import find_example as FE  # noqa: E402


def _first_eq_candidate(K=10, budget=30.0):
    """First closing equilateral 1+1+1 candidate at K (K=10 is the documented first-closing K).
    I/O: (int, float) -> candidate dict. Budgeted so a non-yielding run can't hang the suite."""
    t0 = time.time()
    _lat, it = FE.gen_eq("1plus1plus1", K, budget=budget, t0=t0)
    return next(it)


def test_gen_eq_candidate_has_nonnull_tw():
    """A gen_eq equilateral candidate exposes a non-null top-level `tw` (list of 3 ints)."""
    cand = _first_eq_candidate()
    tw = cand.get("tw")                       # exactly what the record writer reads (run_case ~:415)
    assert tw is not None, "gen_eq candidate must carry a top-level 'tw' (was None => stored tw:null)"
    assert isinstance(tw, list) and len(tw) == 3
    assert all(isinstance(v, int) for v in tw)
    # tw agrees with the human-readable description and the carried record.
    assert cand["tw_desc"] == "Tw AB=%+d BC=%+d AC=%+d" % tuple(tw)
    assert list(cand["rec"]["tw"]) == tw


if __name__ == "__main__":
    test_gen_eq_candidate_has_nonnull_tw()
    print("PASS  gen_eq candidate carries non-null top-level tw")
