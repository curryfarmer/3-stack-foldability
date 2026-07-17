"""test_gui_dispatch.py — gui/dispatch.py (the S7-orchestrator bridge for the GUI).

Fast: grid-file writing, argv, gridUid parsing, the taskkill reap argv, idle cancel. Slow: a REAL
small square fold through fold_once -> a bundle with a proven record (mirrors the S8->S7 round-trip).
No engine import here -- dispatch only subprocesses fold_grid.py.
"""
import json
import os
import subprocess
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from gui import dispatch   # noqa: E402


def test_write_grid_file(tmp_path):
    p = dispatch.write_grid_file("square", [(0, 0), (1, 0)], [2, 3], str(tmp_path / "g.json"))
    spec = json.load(open(p, encoding="utf-8"))
    assert spec["schema"] == "fold-grid/1"
    assert spec["tiling"] == "square"
    assert spec["cells"] == [[0, 0], [1, 0]]      # tuples serialized as lists
    assert spec["stacks"] == [2, 3]


def test_build_argv():
    argv = dispatch.build_argv("g.json", "/out", stacks=[2, 3], jobs=4, timeout=120)
    assert argv[0] == sys.executable and argv[1] == "-u"
    assert argv[2].endswith(os.path.join("scripts", "fold_grid.py"))
    assert argv[3] == "g.json"
    assert argv[argv.index("--out") + 1] == "/out"
    assert argv[argv.index("--stacks") + 1] == "2,3"
    assert argv[argv.index("--jobs") + 1] == "4"
    assert argv[argv.index("--timeout") + 1] == "120"
    # stacks/jobs/timeout omitted when falsy/None
    bare = dispatch.build_argv("g.json", "/out")
    assert "--stacks" not in bare and "--jobs" not in bare and "--timeout" not in bare


def test_parse_grid_uid():
    line = "fold-grid: tiling=square |cells|=6 gridUid=53ec7d583921 stacks=[3] -> /x/out/53ec7d583921"
    assert dispatch.parse_grid_uid(line) == "53ec7d583921"
    assert dispatch.parse_grid_uid("no uid here") is None
    assert dispatch.parse_grid_uid("") is None


@pytest.mark.skipif(os.name != "nt", reason="taskkill is the Windows reap path")
def test_killtree_issues_taskkill(monkeypatch):
    seen = {}
    monkeypatch.setattr(dispatch.subprocess, "run",
                        lambda argv, **k: seen.setdefault("argv", argv))
    dispatch._killtree(4321)
    assert seen["argv"] == ["taskkill", "/F", "/T", "/PID", "4321"]


def test_cancel_when_idle_is_safe():
    d = dispatch.Dispatch()
    d.cancel()                    # no proc in flight -> no error
    assert not d.is_running()


@pytest.mark.slow
def test_fold_once_real_square(tmp_path):
    """A real fold_grid run on a 6-cell square sheet -> bundle with a proven record."""
    from gui import geometry_client as GC
    g = GC.load("square", 3, 3)
    cells = [g.ids[k] for k in range(len(g.ids)) if g.ids[k][0] in (0, 1)]   # 2x3 = 6 cells
    lines = []
    res = dispatch.fold_once("square", cells, out_dir=str(tmp_path), timeout=180,
                             on_line=lines.append)
    assert res.returncode == 0, res.output
    assert res.grid_uid and res.bundle_path and os.path.isfile(res.bundle_path)
    assert any("gridUid=" in ln for ln in lines)
    from gui import results
    rows, gate = results.parse_bundle(res.bundle_path)
    assert rows and isinstance(rows[0]["proven"], bool)
