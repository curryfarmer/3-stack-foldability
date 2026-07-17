"""test_render_bytes.py — the square foldsheet renderer is byte-deterministic.

Rendering the same record twice, in one interpreter, must produce identical PNG bytes. This is the
square half of the S10 "regenerate ≡ generate" contract. It is SELF-REFERENTIAL — it reads no
committed baseline — so a dpi/style change can never silently invalidate a golden (there is none).

matplotlib's Agg PNG embeds a `Software` chunk (its version) but no timestamp, so two saves in the same
environment are byte-identical; if that ever changes, pass metadata={"Software": None} in figstyle.save.
"""
import figstyle as fs  # noqa: F401  (import triggers apply_style; also proves the module imports)
import render_square

# Minimal valid 3-stack detail: no chains -> an empty footprint on a bare grid. render() still exercises
# new_grid_axes + draw_grid_cells + the empty-footprint/reflection paths + save.
DETAIL = {"footprint": {"cells": []}, "chains": [], "decomposition": "1+1+1", "verdict": {}}


def test_render_square_is_byte_deterministic(tmp_path):
    p1 = tmp_path / "a.png"
    p2 = tmp_path / "b.png"
    render_square.render(DETAIL, 3, 3, str(p1), title="t")
    render_square.render(DETAIL, 3, 3, str(p2), title="t")
    assert p1.read_bytes() == p2.read_bytes(), "square foldsheet render is not byte-deterministic"
