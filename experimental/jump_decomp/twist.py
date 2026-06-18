"""jump_decomp engine — reduce the 2-chain to ONE kept strand (one cell per placement, K points =
K folds). The twin cells are treated as holes, so a short-side / along-axis fold appears as an
axis-aligned 3-jump; turns stay 90-multiples -> integer Tw in {0, +-720}. Canonical strand = the one
whose two hub seams are non-diagonal. This is Model B, the validated reduction. Binary verdict."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # experimental/
import common  # noqa: E402

NAME = "jump decomp"


def twist_2plus1(two, one, m, n, ctx=None):
    ctx = ctx or common.prepare(two, one, m, n)
    body = common.strand_path(ctx["pls2"], ctx["idx"])
    tw = common.loop_tw(body, ctx["path1"])
    return {"pass": common.is0(tw), "tw": tw}
