"""test_render_bundle.py — render_bundle.render_record dispatch + 2+1 twist-loop geometry.

render_record is the shared "stamped record -> on-disk bundle" step used by BOTH generate.py and
render_cli.py; render_twist_2plus1.build_loop is the 2+1 jump-strand loop builder. Both had zero
coverage. Two contracts are pinned here:

  * byte-determinism — rendering the same record twice, in one interpreter, yields identical PNG
    bytes, for a 2-stack, a 2+1 and a 1+1+1 record — BOTH images (schematic + twist) each time, since
    every record now yields the standardised two-image bundle. This is test_render_bytes.py's single-
    figure guarantee lifted to the whole bundle (the S10 "regenerate == generate" contract). SELF-
    REFERENTIAL: no committed golden, so a dpi/style change can never silently invalidate one.
  * guards — render_record rejects a record missing uid / m,n / a known schema with ValueError, and
    build_loop rejects a non-2+1 record (its unguarded next() would otherwise raise a bare
    StopIteration on the missing domino chain).

The three records are frozen literals harvested once from the engine (6x4 3-stack, 4x4 2-stack), so
this suite imports only the render modules — never search/lattice — and needs no engine run.
"""
import copy

import pytest

import render_bundle as RB
from render_twist_2plus1 import build_loop

# A real 2+1 FOLD on 6x4: one domino chain (7 fold arrows -> 8 placements) + one monomino chain.
REC_2P1 = {
    "decomposition": "2+1",
    "footprint": {"cells": [{"x": 1, "y": 0}, {"x": 0, "y": 0}, {"x": 1, "y": 1}]},
    "chains": [
        {"kind": "2chain", "baseCells": [{"x": 1, "y": 0}, {"x": 1, "y": 1}],
         "foldArrows": ["R", "R", "R", "R", "D", "L", "L"]},
        {"kind": "1chain", "baseCells": [{"x": 0, "y": 0}],
         "foldArrows": ["D", "D", "D", "R", "U", "R", "D"]},
    ],
    "verdict": {"arithmetic": True, "exitFootprint": True, "parity": True,
                "reflection": True, "twist": True},
}

# A real 1+1+1 FOLD on 6x4: three monomino chains (no domino -> not a 2+1).
REC_111 = {
    "decomposition": "1+1+1",
    "footprint": {"cells": [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 2, "y": 0}]},
    "chains": [
        {"kind": "1chain", "baseCells": [{"x": 0, "y": 0}],
         "foldArrows": ["D", "D", "D", "R", "U", "R", "D"]},
        {"kind": "1chain", "baseCells": [{"x": 1, "y": 0}],
         "foldArrows": ["D", "R", "R", "R", "D", "L", "D"]},
        {"kind": "1chain", "baseCells": [{"x": 2, "y": 0}],
         "foldArrows": ["R", "R", "R", "D", "D", "D", "L"]},
    ],
    "verdict": {"arithmetic": True, "exitFootprint": True, "parity": True,
                "reflection": True, "twist": True},
}

# A real 2-stack FOLD on 4x4: a Hamiltonian circuit + the crease it cuts to open the loop.
REC_2STACK = {
    "circuit": [[0, 0], [1, 0], [2, 0], [3, 0], [3, 1], [2, 1], [1, 1], [1, 2],
                [2, 2], [3, 2], [3, 3], [2, 3], [1, 3], [0, 3], [0, 2], [0, 1]],
    "cutEdge": [[1, 0], [1, 1]],
    "verdict": {"reflection": True, "twist": True, "foldable": True},
}


def _stamped(rec, uid, m, n):
    """Deep-copy rec and stamp the uid/m/n render_record requires. I/O: (rec, str, int, int) -> rec."""
    r = copy.deepcopy(rec)
    r["uid"], r["m"], r["n"] = uid, m, n
    return r


def _bytes(path):
    with open(path, "rb") as f:
        return f.read()


# ------------------------------------------------------------- byte-determinism ----

@pytest.mark.parametrize("rec, uid, m, n, label", [
    (REC_2STACK, "det2stk", 4, 4, "2-stack"),
    (REC_2P1, "det2p1", 6, 4, "2+1"),
    (REC_111, "det111", 6, 4, "1+1+1"),
])
def test_render_record_is_byte_deterministic(tmp_path, rec, uid, m, n, label):
    """render_record on the same record, twice, into two dirs -> identical PNG bytes per figure.
    Every record yields BOTH images (schematic + twist) -- the standardised two-image bundle."""
    a = RB.render_record(_stamped(rec, uid, m, n), str(tmp_path / "a"))
    b = RB.render_record(_stamped(rec, uid, m, n), str(tmp_path / "b"))
    assert _bytes(a["schematic"]) == _bytes(b["schematic"]), f"{label} schematic not byte-deterministic"
    assert _bytes(a["twist"]) == _bytes(b["twist"]), f"{label} twist not byte-deterministic"


# ------------------------------------------------------------------------ guards ----

def test_render_record_rejects_missing_uid(tmp_path):
    rec = copy.deepcopy(REC_2P1)
    rec["m"], rec["n"] = 6, 4                         # no uid
    with pytest.raises(ValueError, match="missing 'uid'"):
        RB.render_record(rec, str(tmp_path))


def test_render_record_rejects_missing_mn(tmp_path):
    rec = copy.deepcopy(REC_2P1)
    rec["uid"] = "nomn"                               # no m/n
    with pytest.raises(ValueError, match="missing 'm'"):
        RB.render_record(rec, str(tmp_path))


def test_render_record_rejects_unknown_schema(tmp_path):
    rec = {"uid": "bogus", "m": 6, "n": 4}            # neither chains+footprint nor circuit
    with pytest.raises(ValueError, match="unknown schema"):
        RB.render_record(rec, str(tmp_path))


# --------------------------------------------------------------- build_loop geom ----

def test_build_loop_length_is_2K_for_2plus1():
    """The jump-strand loop = body + reversed(path1), each of K points, so len(loop) == 2*K. The
    6x4 2+1 domino has 7 fold arrows -> 8 placements -> K = 8."""
    info = build_loop(REC_2P1, 6, 4)
    assert info["K"] == 8, f"expected K=8 (7 arrows -> 8 placements), got {info['K']}"
    assert len(info["loop"]) == 2 * info["K"] == 16


def test_build_loop_rejects_non_2plus1():
    """A 1+1+1 record has no 2-cell domino chain; build_loop must raise, not leak a StopIteration."""
    with pytest.raises(ValueError, match=r"2\+1"):
        build_loop(REC_111, 6, 4)
