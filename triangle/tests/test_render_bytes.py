"""test_render_bytes.py — the triangle overlay + twist renderers are byte-deterministic.

Rendering the same input twice, in one interpreter, must produce identical PNG bytes. This is the
triangle half of the S10 "regenerate ≡ generate" contract. SELF-REFERENTIAL — no committed baseline is
read — so the dpi unification (150/160/170 -> 150) can never silently invalidate a golden.

Two renderers are pinned:
  * render_general.render — the chain overlay, driven by a tiny self-contained fake lattice
    (tile_cart / centroid / sigma), so it exercises the shared tristyle path (palette, arrows,
    footprints, save) without pulling in any engine lattice module.
  * render_twist.render_twist — the twist-enumeration diagram, driven by an in-memory tri-fold/1
    record (chains + geometry only). render_twist reads NO lattice, so a fake record fully drives
    the loop-index-sigma / gamma / Tw=0-FOLD-vs-Tw!=0-JAM label code -- exactly the "label/sigma
    could regress" surface. Both the 1+1+1 shape (3 theta-graph loops) and the 2+1 shape (1 reduced
    loop = strand + reversed(1-chain)) are covered. render_reflection is NOT here: it rebuilds a live
    engine lattice (find_example.build_lat) from real tile ids, so it cannot run in this fake style.

OUT / REPORT_BASE are redirected to tmp_path (mutable module attrs by design). No committed golden:
each record is rendered twice in-process and the two PNGs are diffed.
"""
import json

import render_general
import render_twist


class _FakeLat:
    """Unit square per integer tile id (x, y); sigma is checkerboard parity."""
    def tile_cart(self, t):
        x, y = t
        return [(x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1)]

    def centroid(self, t):
        x, y = t
        return (x + 0.5, y + 0.5)

    def sigma(self, t):
        x, y = t
        return 1 if (x + y) % 2 == 0 else -1


CHAINS = [[(0, 0), (1, 0), (2, 0)]]
FOOTPRINT = [(0, 0)]


def test_render_general_is_byte_deterministic(tmp_path, monkeypatch):
    monkeypatch.setattr(render_general, "OUT", str(tmp_path))
    lat = _FakeLat()
    render_general.render(lat, CHAINS, FOOTPRINT, "t", "a.png")
    render_general.render(lat, CHAINS, FOOTPRINT, "t", "b.png")
    a = (tmp_path / "a.png").read_bytes()
    b = (tmp_path / "b.png").read_bytes()
    assert a == b, "triangle overlay render is not byte-deterministic"


# ------------------------------------------------------------------ render_twist -----
def _sq_geom(tiles):
    """Unit-square polygon per (x, y) tile, keyed exactly as gen_testset._tk (json list, tight sep)
    so render_twist._centroid_map / _tk resolve every loop tile. I/O: (iterable[(x,y)]) -> geom dict."""
    g = {}
    for (x, y) in tiles:
        g[json.dumps([x, y], separators=(",", ":"))] = [[x, y], [x + 1, y], [x + 1, y + 1], [x, y + 1]]
    return g


# Fake tri-fold/1 records. render_twist consumes ONLY chains + geometry (no lattice), so the tiling is
# irrelevant to byte-determinism; what is pinned is the label/sigma code path on each decomposition.
_REC_111 = {
    "uid": "det111aaaaaa", "tiling": "equilateral", "decomp": "1plus1plus1", "K": 3,
    "chains": [[[0, 0], [1, 0], [2, 0]],
               [[0, 1], [1, 1], [2, 1]],
               [[0, 2], [1, 2], [2, 2]]],
    "geometry": _sq_geom([(x, y) for y in range(3) for x in range(3)]),
}
_REC_21 = {
    "uid": "det21bbbbbbb", "tiling": "equilateral", "decomp": "2plus1", "K": 4,
    "chains": [[[0, 0], [1, 0], [2, 0], [3, 0]],
               [[0, 1], [3, 1]]],
    "geometry": _sq_geom([(0, 0), (1, 0), (2, 0), (3, 0), (0, 1), (3, 1)]),
}


def _render_twist_twice(tmp_path, monkeypatch, rec):
    """Write rec to tmp_path, render its twist figure twice (distinct out_subs), return both PNGs' bytes."""
    monkeypatch.setattr(render_twist, "REPORT_BASE", str(tmp_path))
    jp = tmp_path / ("%s.json" % rec["uid"])
    jp.write_text(json.dumps(rec))
    pa, _ = render_twist.render_twist(str(jp), out_sub="a")
    pb, _ = render_twist.render_twist(str(jp), out_sub="b")
    with open(pa, "rb") as f:
        a = f.read()
    with open(pb, "rb") as f:
        b = f.read()
    return a, b


def test_render_twist_111_is_byte_deterministic(tmp_path, monkeypatch):
    """1+1+1: three theta-graph twist loops (AB/BC/AC), loop-index sigma -> per-vertex sig*gamma."""
    a, b = _render_twist_twice(tmp_path, monkeypatch, _REC_111)
    assert a == b, "render_twist 1+1+1 is not byte-deterministic"


def test_render_twist_21_is_byte_deterministic(tmp_path, monkeypatch):
    """2+1: one reduced loop (strand + reversed(1-chain)), same loop-index sigma / Tw label path."""
    a, b = _render_twist_twice(tmp_path, monkeypatch, _REC_21)
    assert a == b, "render_twist 2+1 is not byte-deterministic"
