"""normal_decomp engine — fully decompose: traverse the kept strand but FILL each 3-jump with its
two collinear midpoints (the cells the jump skipped), so the path is unit-step and hole-free. The
inserted points have gamma=0 and shift the checkerboard phase evenly, so Tw is unchanged: filled ==
jump (theorem; verified 0 violations). This crosses the domino's rigid internal edge as if a crease,
so it is a cross-check, not a shippable physical model. Binary verdict."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # experimental/
import common  # noqa: E402

NAME = "normal decomp"


def twist_2plus1(two, one, m, n, ctx=None):
    ctx = ctx or common.prepare(two, one, m, n)
    body = common.filled_path(ctx["pls2"], ctx["idx"])
    tw = common.loop_tw(body, ctx["path1"])
    return {"pass": common.is0(tw), "tw": tw}
