"""partial_decomp engine — the lead's variable-width reduction. Thin to a 1-unit (kept-strand cell
center) by default, but keep a residual 2-UNIT (domino centroid) at placements incident to a
short-side fold, preserving the fold count K. The 1-unit<->2-unit seam steps a half-cell off the
sublattice, so its Tw can carry a (1,2)-slope atan(1/2) residual.

That residual is NOT treated as failure: it is the OVERHANG signature -- the fold closes but lands
offset, so one end sticks out past the target footprint. The engine returns a 3-way `class`:
  flat     Tw ~= 0                       -> flat-folds onto the same footprint
  overhang Tw = nonzero multiple of Q    -> closes with a protruding strip (the lead's promising case)
  twisted  Tw = nonzero multiple of 360  -> genuine twist / jam
  mixed    neither                       -> twist+overhang combo / off-quantum (flagged, pass=False)
`pass` (promising) = flat OR overhang.

Extra signals for curation / physical reading:
  tw_hub1, class_hub1   same model but with the two hub placements forced to clean 1-unit joins
  hub_removable         True if the overhang vanishes (class_hub1==flat) when hubs are forced 1-unit
                        -> the stick-out is a fixable HUB seam, not an intrinsic interior overhang
  sign                  +1 / -1 / 0 direction of the residual
  n2units               how many residual 2-units the partial decomp kept (rigidity it couldn't thin)
  frac                  number of fractional (non-90) turns in the loop (the seam kinks)
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # experimental/
import common  # noqa: E402

NAME = "partial decomp"


def twist_2plus1(two, one, m, n, ctx=None):
    ctx = ctx or common.prepare(two, one, m, n)
    pls2, idx, path1 = ctx["pls2"], ctx["idx"], ctx["path1"]

    body, kinds = common.model_a_path(pls2, idx, force_hub_1unit=False)
    tw = common.loop_tw(body, path1)
    cls = common.classify_partial(tw)

    body1, _ = common.model_a_path(pls2, idx, force_hub_1unit=True)
    tw1 = common.loop_tw(body1, path1)
    cls1 = common.classify_partial(tw1)

    return {
        "pass": cls in ("flat", "overhang"),
        "tw": tw,
        "class": cls,
        "tw_hub1": tw1,
        "class_hub1": cls1,
        "hub_removable": (cls != "flat") and (cls1 == "flat"),
        "sign": 0 if cls == "flat" else (1 if tw > 0 else -1),
        "n2units": kinds.count("2"),
        "frac": common.frac_turns(common.loop_terms(body + list(reversed(path1)))),
    }
