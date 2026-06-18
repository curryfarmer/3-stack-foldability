"""no_decomp engine — do NOT decompose the 2-chain. Each placement contributes one point: the whole
domino's centroid. This is the original un-reduced approach; the rigid ribbon's half-cell-offset
centroids inject the classic 936-degree artifact, so it almost never reads Tw==0. Binary verdict."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # experimental/
import common  # noqa: E402

NAME = "no decomp"


def twist_2plus1(two, one, m, n, ctx=None):
    ctx = ctx or common.prepare(two, one, m, n)
    body = common.full_centroid_path(ctx["pls2"])
    tw = common.loop_tw(body, ctx["path1"])
    return {"pass": common.is0(tw), "tw": tw}
