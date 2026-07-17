"""test_gui_contract.py — the cross-cutting S8 gate for the headless GUI core (gui/).

Four things, modelled on test_orchestrator.py:
  1. THE S8 INVARIANT (no co-import): a clean subprocess importing every gui/ module must pull in
     NEITHER engine -- gui/ reaches the engines only by subprocessing their dump scripts. Proven in a
     fresh interpreter so this test's own imports can't mask a leak.
  2. Dump fidelity, all 5 tilings: gui.geometry_client subprocesses each real dump; the parsed
     geometry must equal the committed golden (smoketest/golden/geometry/<tiling>.json).
  3. Hit-test: every tile's centroid hit-tests to that tile's index; a point outside every polygon
     returns None. (Driven off the goldens -- fast, no subprocess.)
  4. Connectivity: known-connected accepts; a gap rejects; a single cell accepts; empty rejects.

The dumps are sub-second and hermetic (no --jobs pool, no real search), so nothing here is marked
slow -- the gate checks fidelity for real.
"""
import json
import os
import subprocess
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from gui import geometry_client as GC   # noqa: E402  (imports NO engine -- pinned below)
from gui import canvas                  # noqa: E402
from gui import connectivity            # noqa: E402
from gui import tilings                 # noqa: E402

_GOLDEN_DIR = os.path.join(_REPO, "smoketest", "golden", "geometry")
_TILINGS = ["square", "equilateral", "righttri", "scalene", "hex"]


def _golden(tiling):
    with open(os.path.join(_GOLDEN_DIR, tiling + ".json"), encoding="utf-8") as f:
        return json.load(f)


def _centroid(poly):
    n = len(poly)
    return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)


# --------------------------------------------------------------- the no-co-import invariant

_NO_ENGINE_PROBE = '''
import sys
sys.path.insert(0, sys.argv[1])
import gui.geometry_client, gui.canvas, gui.connectivity, gui.tilings, gui.config
import gui.dispatch, gui.results, gui.thumbs, gui.app, gui.foldfilter, gui.cli
ENGINE_MODS = ("lattice", "search", "twostack", "runner", "find_example", "foldgrid_tri",
               "gen_testset", "_bootstrap", "trisearch", "trilattice", "righttri", "scalene",
               "hexlattice")
leaked = sorted(m for m in ENGINE_MODS if m in sys.modules)
print("LEAKED=%s" % ",".join(leaked))
'''


def test_gui_imports_no_engine(tmp_path):
    """THE S8 invariant: square/ and triangle/ each put a bare `lattice` on sys.path, so co-importing
    both races the bootstrap. gui/ must import NEITHER engine -- it only subprocesses their dump
    scripts. Proven in a clean interpreter."""
    probe = tmp_path / "probe.py"
    probe.write_text(_NO_ENGINE_PROBE, encoding="utf-8")
    proc = subprocess.run([sys.executable, str(probe), _REPO],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "LEAKED=" in proc.stdout, proc.stdout
    leaked = proc.stdout.split("LEAKED=", 1)[1].strip()
    assert leaked == "", "gui import pulled in engine module(s): %s" % leaked


# --------------------------------------------------------------- dump fidelity (real subprocess)

@pytest.mark.parametrize("tiling", _TILINGS)
def test_dump_fidelity_vs_golden(tiling):
    """gui.geometry_client subprocesses the real dump; the result must equal the committed golden."""
    GC.clear_cache()
    g = _golden(tiling)
    m, n = g["bounds"]["m"], g["bounds"]["n"]
    got = GC.load(tiling, m, n)
    assert got.tiling == g["tiling"]
    assert got.bounds == g["bounds"]
    assert got.ids == g["ids"]
    assert got.polys == g["polys"]
    assert got.adj == g["adj"]


def test_geometry_client_caches(monkeypatch):
    """A second load of the same (tiling, m, n) must not re-dump."""
    GC.clear_cache()
    GC.load("square", 3, 3)
    calls = {"n": 0}
    real = subprocess.run

    def _counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(subprocess, "run", _counting)
    GC.load("square", 3, 3)          # cached -> no subprocess
    assert calls["n"] == 0


# --------------------------------------------------------------- hit-test (per tiling, off goldens)

@pytest.mark.parametrize("tiling", _TILINGS)
def test_hit_test_centroid_selects_own_tile(tiling):
    polys = _golden(tiling)["polys"]
    for k, poly in enumerate(polys):
        assert canvas.hit_test(_centroid(poly), polys) == k


@pytest.mark.parametrize("tiling", _TILINGS)
def test_hit_test_outside_returns_none(tiling):
    polys = _golden(tiling)["polys"]
    assert canvas.hit_test((10_000.0, 10_000.0), polys) is None


# --------------------------------------------------------------- connectivity (tiling-agnostic)

def test_connectivity_accepts_full_block():
    for tiling in _TILINGS:
        g = _golden(tiling)
        assert connectivity.is_connected(range(len(g["ids"])), g["adj"])


def test_connectivity_single_cell_accepts_empty_rejects():
    g = _golden("square")
    assert connectivity.is_connected([0], g["adj"]) is True
    assert connectivity.is_connected([], g["adj"]) is False


def test_connectivity_rejects_a_gap():
    # square 3x3 golden: indices 0 ((0,0)) and 8 ((2,2)) are opposite corners -> not edge-connected
    g = _golden("square")
    assert connectivity.is_connected([0, 8], g["adj"]) is False
    # but a contiguous L stays connected: (0,0)-(0,1)-(1,1) = indices 0,1,4
    assert connectivity.is_connected([0, 1, 4], g["adj"]) is True


# --------------------------------------------------------------- registry sanity

def test_registry_covers_all_tilings_and_argv():
    assert set(tilings.names()) == set(_TILINGS)
    assert tilings.dump_argv("square", 3, 3) == ["--m", "3", "--n", "3"]
    assert tilings.dump_argv("hex", 2, 2) == ["--tiling", "hex", "--m", "2", "--n", "2"]
    assert tilings.orientation("square") == "down"
    assert tilings.orientation("hex") == "up"
    for t in _TILINGS:
        assert os.path.isfile(tilings.script_path(t))
