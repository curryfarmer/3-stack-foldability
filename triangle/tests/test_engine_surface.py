"""test_engine_surface.py — pin the triangle engine's EXTERNAL-global-mutation + call surface.

The engine drives live rendering by two contracts that no other triangle test exercises, so a rename
or signature drift would break a real campaign (`find_example --tiling ...` at render time) with zero
coverage. This pins both so they can FAIL on drift:

  * find_example.set_outdir(sub) redirects a campaign's output by ASSIGNING .OUT on four renderer
    module globals — foldsheet_tri.OUT (FS), render_general.OUT (RG), and, via the solve_foldable
    aliases the equilateral path renders through, solve_foldable.TR.OUT (trirender) and
    solve_foldable.FS.OUT (foldsheet_tri). If set_outdir stops setting one, or a renderer drops its
    OUT attribute (or solve_foldable renames its TR/FS alias), test_set_outdir_sets_renderer_out FAILS.
  * foldsheet_tri.make_sheet(...) is invoked positionally by the engine; a rename or a change to its
    parameter list breaks that call. test_make_sheet_surface pins existence, callability, and the
    exact parameter names + required-vs-defaulted split via inspect.signature. (No live call: make_sheet
    needs a full LatClass with .shared/.adj/.edges + matplotlib render — too heavy to be a cheap,
    deterministic surface check, so existence+signature is the pin.)

TRIANGLE-ONLY: modules imported exactly as the engine imports them (via conftest.py's tri/ path);
NO square.* here. sys.path bootstrap comes from triangle/tests/conftest.py.
"""
import inspect
import os

import pytest

import find_example as FE      # noqa: E402
import foldsheet_tri as FS     # noqa: E402  same module object set_outdir mutates as FS / SF.FS
import render_general as RG    # noqa: E402  set_outdir mutates as RG
import solve_foldable as SF    # noqa: E402  set_outdir mutates SF.TR.OUT (trirender) + SF.FS.OUT


@pytest.fixture
def restore_renderer_out():
    """Save/restore the renderer OUT globals (and find_example's REPORT/RESULTS) that set_outdir
    mutates, so redirecting to tmp_path never leaves a renderer pointing at a stale dir for the rest
    of the suite. SF.FS is the foldsheet_tri module object, so SF.FS.OUT and FS.OUT are one attribute;
    both are saved for symmetry."""
    saved = (FS.OUT, RG.OUT, SF.TR.OUT, SF.FS.OUT, FE.REPORT, FE.RESULTS)
    yield
    (FS.OUT, RG.OUT, SF.TR.OUT, SF.FS.OUT, FE.REPORT, FE.RESULTS) = saved


def test_set_outdir_sets_renderer_out(tmp_path, restore_renderer_out):
    """set_outdir(sub) points EVERY renderer OUT it documents (foldsheet_tri, render_general,
    solve_foldable.TR=trirender, solve_foldable.FS=foldsheet_tri) at the campaign REPORT dir."""
    sub = str(tmp_path)                       # abs path: os.path.join(_REPORT_BASE, sub) -> sub, so
    FE.set_outdir(sub)                        # nothing is created under the real report/tri tree
    expected = FE.REPORT
    assert expected == os.path.join(FE._REPORT_BASE, sub)          # the campaign-dir join itself
    assert FS.OUT == expected, "set_outdir must set foldsheet_tri.OUT"
    assert RG.OUT == expected, "set_outdir must set render_general.OUT"
    assert SF.TR.OUT == expected, "set_outdir must set solve_foldable.TR.OUT (trirender)"
    assert SF.FS.OUT == expected, "set_outdir must set solve_foldable.FS.OUT (foldsheet_tri)"


def test_make_sheet_surface():
    """foldsheet_tri.make_sheet exists, is callable, and its parameter list matches what the engine
    calls positionally. FAILS on a rename or any signature drift (added/removed/reordered param)."""
    fn = getattr(FS, "make_sheet", None)
    assert callable(fn), "foldsheet_tri.make_sheet must exist and be callable"
    params = list(inspect.signature(fn).parameters.values())
    names = [p.name for p in params]
    assert names == [
        "LatClass", "vcart", "tile_cart", "sigma", "chains", "footprint", "title", "out_name", "K",
        "verdict_note", "crease_override", "end_footprint", "rigid_override", "end_chirality",
        "walk_chains",
    ], "make_sheet parameter list drifted"
    # the first nine carry no default -> the required positional contract the engine depends on.
    required = [p.name for p in params if p.default is inspect.Parameter.empty]
    assert required == [
        "LatClass", "vcart", "tile_cart", "sigma", "chains", "footprint", "title", "out_name", "K",
    ], "make_sheet required-parameter contract drifted"
