"""test_orchestrator.py — tracked tests for scripts/fold_grid.py (the S7 grid-file orchestrator).

Two layers, same split as test_physical_suite.py:
  * AGGREGATION + IDENTITY (fast, hermetic): drive fold_grid's pure functions (gridUid, sheetCells,
    stack resolution, proven stamping, bundle roll-up) on hand-built <uid>.json fixtures in tmp_path.
    No engine subprocess. Importing fold_grid here is safe *because* it is the whole point of S7 that
    the orchestrator imports NO engine — a dedicated subprocess test pins that invariant.
  * ROUND-TRIPS (slow): actually shell fold_grid.py at each engine and assert the on-disk bundle. Marked
    `slow` (deselected by default, like the acceptance oracle) — they spawn the real search.

The orchestrator is invoked as a SUBPROCESS with output redirected to a FILE, never capture_output: it
live-streams its children's (verbose) stdout, and a PIPE could deadlock on a large triangle twist dump.
"""
import glob
import json
import os
import subprocess
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.join(_REPO, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import fold_grid as FG      # noqa: E402  (stdlib + subprocess only; imports NO engine — pinned below)

_FOLD_GRID = os.path.join(_SCRIPTS, "fold_grid.py")


# --------------------------------------------------------------------------- record fixtures

def _sq2_rec(uid="sq2aaaa", foldable=True):
    return {"uid": uid, "lattice": "square2stack", "stacks": 2, "m": 3, "n": 3,
            "circuit": [[0, 0], [1, 0]], "cutEdge": None,
            "verdict": {"reflection": foldable, "twist": foldable, "foldable": foldable},
            "twistValue": 0}


def _sq3_rec(uid="sq3bbbb", twist=True):
    return {"uid": uid, "lattice": "square", "stacks": 3, "m": 2, "n": 3,
            "canonicalHash": json.dumps({"fp": [[0, 1]], "chains": [1]}),
            "verdict": {"arithmetic": True, "exitFootprint": True, "parity": True,
                        "reflection": True, "twist": twist}}


def _tri_rec(uid="tricccc", tiling="hex", foldable=False):
    return {"uid": uid, "schema": "tri-fold/1", "tiling": tiling, "decomp": "1plus1plus1", "K": 4,
            "foldable": foldable, "verdict": "PREDICTED TO JAM (...) - fold to verify",
            "chains": [], "region": [], "holes": 0}


def _write_record(workdir, rec, *, pngs=()):
    """Materialize a <uid>/<uid>.json (+ optional PNG basenames) the way an engine worker would."""
    sub = os.path.join(workdir, rec["uid"])
    os.makedirs(sub, exist_ok=True)
    with open(os.path.join(sub, "%s.json" % rec["uid"]), "w", encoding="utf-8") as f:
        json.dump(rec, f)
    for name in pngs:
        with open(os.path.join(sub, name), "w", encoding="utf-8") as f:
            f.write("png")
    return sub


# --------------------------------------------------------------------------- gridUid identity

def test_grid_uid_is_deterministic_and_order_independent():
    a = FG._grid_uid("square", [[0, 0], [1, 0], [2, 0]], [3])
    b = FG._grid_uid("square", [[2, 0], [0, 0], [1, 0]], [3])   # cells reordered
    assert a == b and len(a) == 12


def test_grid_uid_separates_distinct_inputs():
    base = FG._grid_uid("square", [[0, 0], [1, 0]], [2])
    assert FG._grid_uid("square", [[0, 0], [1, 0], [2, 0]], [2]) != base   # different cells
    assert FG._grid_uid("hex", [[0, 0], [1, 0]], [2]) != base              # different tiling
    assert FG._grid_uid("square", [[0, 0], [1, 0]], [2, 3]) != base        # different stack set


# --------------------------------------------------------------------------- sheetCells framing

def test_sheet_cells_square_is_origin_normalized():
    """The square engine shifts the bbox min corner to (0,0); the bundle's sheetCells must match that
    frame so an S10 mask lines up."""
    cells = [[5, 5], [6, 5], [5, 6]]
    assert FG._sheet_cells("square", cells) == [[0, 0], [0, 1], [1, 0]]


def test_sheet_cells_triangle_is_native_untouched():
    """The triangle engine folds native ids (hex may be negative); sheetCells stays in that frame."""
    cells = [[-2, 2], [0, 0], [1, -1]]
    assert FG._sheet_cells("hex", cells) == sorted(cells)


# --------------------------------------------------------------------------- stack resolution

def test_resolve_stacks_triangle_is_always_three():
    assert FG._resolve_stacks("hex", None, [3]) == [3]
    assert FG._resolve_stacks("equilateral", [2, 3], "auto") == [3]   # override ignored for triangle


def test_resolve_stacks_square_precedence():
    assert FG._resolve_stacks("square", [2, 3], "auto") == [2, 3]     # CLI override wins
    assert FG._resolve_stacks("square", None, [2, 3]) == [2, 3]       # file hint
    assert FG._resolve_stacks("square", None, "auto") == [3]          # auto -> default
    assert FG._resolve_stacks("square", None, None) == [3]            # missing -> default
    assert FG._resolve_stacks("square", [3, 2, 3], "auto") == [2, 3]  # dedup + sort


def test_resolve_stacks_rejects_below_two():
    with pytest.raises(ValueError):
        FG._resolve_stacks("square", [1], "auto")


# --------------------------------------------------------------------------- proven stamping

def test_proven_true_for_square_any_stack_count():
    assert FG._record_proven(_sq2_rec()) is True     # 2-stack (method-proven RSPA)
    assert FG._record_proven(_sq3_rec()) is True     # 3-stack (oracle-gated)


def test_proven_true_only_for_equilateral_among_triangles():
    assert FG._record_proven(_tri_rec(tiling="equilateral")) is True
    for t in ("righttri", "scalene", "hex"):
        assert FG._record_proven(_tri_rec(tiling=t)) is False


def test_record_foldable_tristate():
    assert FG._record_foldable(_sq2_rec(foldable=True)) is True
    assert FG._record_foldable(_sq2_rec(foldable=False)) is False
    assert FG._record_foldable(_sq3_rec(twist=True)) is True
    assert FG._record_foldable(_sq3_rec(twist=False)) is False
    assert FG._record_foldable(_sq3_rec(twist=None)) is None        # twist undecided
    assert FG._record_foldable(_tri_rec(foldable=False)) is False


def test_record_stacks_defaults_to_three_when_absent():
    assert FG._record_stacks(_sq2_rec()) == 2
    assert FG._record_stacks(_tri_rec()) == 3          # triangle records carry no `stacks` key


# --------------------------------------------------------------------------- bundle roll-up

def test_build_bundle_rolls_up_proven_and_configs(tmp_path):
    """A mixed workdir: a proven square 2-stack fold + an unproven hex fold. The bundle must group
    nRecords by each record's self-reported stack count and flag gateValidityUnproven from the hex one."""
    workdir = str(tmp_path)
    _write_record(workdir, _sq2_rec(uid="sq2xxxx"), pngs=["foldsheet_sq2xxxx.png"])
    _write_record(workdir, _tri_rec(uid="trihexx", tiling="hex"),
                  pngs=["overlay_trihexx.png", "foldsheet_trihexx.png"])
    configs = [{"stacks": 2, "status": "ok", "reason": None},
               {"stacks": 3, "status": "ok", "reason": None}]
    bundle = FG._build_bundle("deadbeef1234", "square", [[0, 0]], [2, 3], configs, workdir)

    assert bundle["schema"] == "fold-bundle/1" and bundle["gridUid"] == "deadbeef1234"
    assert bundle["gateValidityUnproven"] is True          # the hex record is unproven
    byuid = {r["uid"]: r for r in bundle["records"]}
    assert byuid["sq2xxxx"]["proven"] is True and byuid["sq2xxxx"]["stacks"] == 2
    assert byuid["trihexx"]["proven"] is False and byuid["trihexx"]["stacks"] == 3
    assert byuid["sq2xxxx"]["files"]["foldsheet"] == "foldsheet_sq2xxxx.png"
    cfg = {c["stacks"]: c for c in bundle["configs"]}
    assert cfg[2]["nRecords"] == 1 and cfg[3]["nRecords"] == 1


def test_build_bundle_all_proven_clears_unproven_flag(tmp_path):
    workdir = str(tmp_path)
    _write_record(workdir, _sq3_rec(uid="sq3aaaa"))
    _write_record(workdir, _sq3_rec(uid="sq3bbbb"))
    bundle = FG._build_bundle("cafe12345678", "square", [[0, 0]], [3],
                              [{"stacks": 3, "status": "ok", "reason": None}], workdir)
    assert bundle["gateValidityUnproven"] is False
    assert {c["stacks"]: c["nRecords"] for c in bundle["configs"]} == {3: 2}


def test_build_bundle_records_a_rejection_with_zero_count(tmp_path):
    """A rejected config (its N never wrote a record) stays visible as a configs entry with nRecords 0
    — the whole point of the refined multi-stack exit policy (a per-N rejection must not vanish)."""
    workdir = str(tmp_path)
    _write_record(workdir, _sq2_rec(uid="sq2only"))
    configs = [{"stacks": 2, "status": "ok", "reason": None},
               {"stacks": 3, "status": "rejected", "reason": "cell count not divisible by 3"}]
    bundle = FG._build_bundle("00ff00ff00ff", "square", [[0, 0]], [2, 3], configs, workdir)
    cfg = {c["stacks"]: c for c in bundle["configs"]}
    assert cfg[3]["status"] == "rejected" and cfg[3]["nRecords"] == 0
    assert cfg[2]["nRecords"] == 1


def test_reject_reason_extracted_from_stderr_line():
    out = "some progress\nrejected: cell count not divisible by 3 (K must be integer)\n"
    assert FG._reject_reason(out) == "cell count not divisible by 3 (K must be integer)"
    assert "no reason" in FG._reject_reason("no marker line here")


def test_collect_records_skips_bundle_json(tmp_path):
    """_collect_records must not treat a previously-written bundle.json as a fold record."""
    workdir = str(tmp_path)
    _write_record(workdir, _sq2_rec(uid="realrec"))
    with open(os.path.join(workdir, "bundle.json"), "w", encoding="utf-8") as f:
        json.dump({"schema": "fold-bundle/1"}, f)
    uids = [uid for uid, _rec, _files in FG._collect_records(workdir)]
    assert uids == ["realrec"]


# --------------------------------------------------------------------------- the no-co-import invariant

_NO_ENGINE_PROBE = '''
import sys, os
sys.path.insert(0, os.path.join(sys.argv[1], "scripts"))
import fold_grid  # noqa: the whole S7 isolation contract: importing the orchestrator pulls in NO engine
ENGINE_MODS = ("lattice", "search", "twostack", "runner", "find_example", "foldgrid_tri",
               "gen_testset", "_bootstrap", "trisearch")
leaked = sorted(m for m in ENGINE_MODS if m in sys.modules)
print("LEAKED=%s" % ",".join(leaked))
'''


def test_orchestrator_imports_no_engine(tmp_path):
    """THE S7 invariant: square/ and triangle/ each put a bare `lattice` on sys.path, so co-importing
    both races the bootstrap. fold_grid must import NEITHER engine — it only subprocesses them. Proven
    in a clean interpreter so this test's own imports can't mask a leak."""
    probe = tmp_path / "probe.py"
    probe.write_text(_NO_ENGINE_PROBE, encoding="utf-8")
    proc = subprocess.run([sys.executable, str(probe), _REPO],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "LEAKED=" in proc.stdout, proc.stdout
    leaked = proc.stdout.split("LEAKED=", 1)[1].strip()
    assert leaked == "", "orchestrator import pulled in engine module(s): %s" % leaked


# --------------------------------------------------------------------------- round-trips (slow)

def _write_grid(tmp_path, name, tiling, cells, stacks):
    p = tmp_path / name
    p.write_text(json.dumps({"schema": "fold-grid/1", "tiling": tiling,
                             "cells": cells, "stacks": stacks}), encoding="utf-8")
    return str(p)


def _run_orchestrator(grid_file, out_dir):
    """Shell fold_grid.py with output to a FILE (never a PIPE — its children stream verbosely). Returns
    (returncode, parsed bundle dict | None)."""
    log = os.path.join(out_dir, "_run.log")
    os.makedirs(out_dir, exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        proc = subprocess.run([sys.executable, "-u", _FOLD_GRID, grid_file, "--out", out_dir],
                              stdout=f, stderr=subprocess.STDOUT, cwd=_REPO)
    hits = glob.glob(os.path.join(out_dir, "*", "bundle.json"))
    bundle = json.load(open(hits[0], encoding="utf-8")) if hits else None
    return proc.returncode, bundle


@pytest.mark.slow
def test_square_rectangle_roundtrip_all_proven(tmp_path):
    """A full-rectangle square grid-file at 3-stack -> proven records, gateValidityUnproven False."""
    grid = _write_grid(tmp_path, "rect.json", "square",
                       [[x, y] for y in range(2) for x in range(3)], [3])
    rc, bundle = _run_orchestrator(grid, str(tmp_path / "out"))
    assert rc == 0 and bundle is not None
    assert bundle["records"], "expected at least one 3-stack solution"
    assert all(r["proven"] for r in bundle["records"])
    assert bundle["gateValidityUnproven"] is False
    assert {c["stacks"]: c["status"] for c in bundle["configs"]} == {3: "ok"}


@pytest.mark.slow
def test_square_2_and_3_stack_sheet_records_rejection_but_writes_bundle(tmp_path):
    """The refined exit policy end to end: an 8-cell ring at [2,3] folds at 2-stack; 3-stack rejects
    (8 % 3 != 0). The bundle is STILL written, with 2-stack records AND a 3-stack rejection config."""
    ring8 = [[0, 0], [1, 0], [2, 0], [0, 1], [2, 1], [0, 2], [1, 2], [2, 2]]
    grid = _write_grid(tmp_path, "ring8.json", "square", ring8, [2, 3])
    rc, bundle = _run_orchestrator(grid, str(tmp_path / "out"))
    assert rc == 0 and bundle is not None
    cfg = {c["stacks"]: c for c in bundle["configs"]}
    assert cfg[2]["status"] == "ok"
    assert cfg[3]["status"] == "rejected" and "divisible" in (cfg[3]["reason"] or "")
    assert all(r["stacks"] == 2 for r in bundle["records"])
    assert all(r["proven"] for r in bundle["records"])   # square is method-proven


@pytest.mark.slow
def test_triangle_hex_roundtrip_unproven_with_pngs(tmp_path):
    """Reuse the committed hex fixture -> tri-fold records, all unproven, PNG bundle rendered."""
    fixture = os.path.join(_REPO, "triangle", "tests", "fixtures", "grids", "hex_small_K4.json")
    if not os.path.isfile(fixture):
        pytest.skip("hex fixture absent")
    rc, bundle = _run_orchestrator(fixture, str(tmp_path / "out"))
    assert rc == 0 and bundle is not None
    assert bundle["records"], "hex K=4 region should yield closing folds"
    assert bundle["tiling"] == "hex"
    assert all(not r["proven"] for r in bundle["records"])
    assert bundle["gateValidityUnproven"] is True
    r0 = bundle["records"][0]
    assert "schematic" in r0["files"] and "twist" in r0["files"]   # --render produced the PNGs
    # (render_record_json emits schematic_/twist_/analysis per triangle/tri/render.py; the older
    # foldsheet_/overlay_ names this once checked no longer exist.)


@pytest.mark.slow
def test_equilateral_empty_result_exits_zero(tmp_path):
    """A valid region that admits no closing 1+1+1 fold still exits 0 with an empty (but written)
    bundle. The 6-tile strip yields nothing because its dual graph has degree-1 ends, NOT because of
    the equilateral obstruction -- that one is about flatness (Tw = 0) and only applies to folds that
    close in the first place. triangle/tests/test_grid_edge_cases.py catalogues these zero shapes."""
    strip = [[0, 0, "U"], [0, 0, "D"], [1, 0, "U"], [1, 0, "D"], [2, 0, "U"], [2, 0, "D"]]
    grid = _write_grid(tmp_path, "eq.json", "equilateral", strip, [3])
    rc, bundle = _run_orchestrator(grid, str(tmp_path / "out"))
    assert rc == 0 and bundle is not None
    assert bundle["records"] == []
    assert bundle["gateValidityUnproven"] is False       # any() over no records
    assert {c["stacks"]: c["status"] for c in bundle["configs"]} == {3: "ok"}


@pytest.mark.slow
def test_equilateral_hexagon_of_six_is_an_empty_bundle_not_a_crash(tmp_path):
    """The reported shape, end to end through the path the GUI actually drives: six equilateral
    triangles round one vertex. It is edge-connected and 6 % 3 == 0, so it is NOT rejected -- it is
    searched, and legitimately yields nothing (the region's dual graph is a 6-cycle, so no trapezoid
    hub can seat three 2-tile chains; see triangle/tests/test_grid_edge_cases.py for the argument).
    What this pins is that the orchestrator reports that as a normal empty result rather than an
    error, so the GUI's "no fold" is a searched answer and not a swallowed failure."""
    hexagon = [[1, 0, "U"], [0, 0, "D"], [1, 0, "D"], [0, 1, "U"], [1, 1, "U"], [0, 1, "D"]]
    grid = _write_grid(tmp_path, "hexagon.json", "equilateral", hexagon, [3])
    rc, bundle = _run_orchestrator(grid, str(tmp_path / "out"))
    assert rc == 0 and bundle is not None
    assert bundle["records"] == []
    assert {c["stacks"]: c["status"] for c in bundle["configs"]} == {3: "ok"}
    assert bundle["configs"][0]["nRecords"] == 0         # searched, not rejected
