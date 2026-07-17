"""test_nstack_sweep.py — unit tests for the n-stack grid-ladder sweep's plumbing.

nstack_sweep.py is the durable, resumable driver that runs each grid in its own subprocess with a
wall-clock timeout. Its RESULT correctness lives in test_nstack.py (the recorded oracle); this file
pins the plumbing that oracle can never exercise -- ladder ORDERING, the subprocess result-row
parsing (JSON scanned from the END past merged stderr), the timeout reap, and resume parsing that
must survive a truncated trailing line. Every subprocess is STUBBED (a fake Popen), so these stay
deterministic and finish in milliseconds -- no real multi-hour worker is ever launched.
"""
import json
import os
import subprocess

import pytest

import nstack as NS            # noqa: E402  (sys.path set in conftest.py)
import nstack_sweep as NSweep  # noqa: E402


# --------------------------------------------------------------------------- grid_ladder ordering
def test_grid_ladder_is_increasing_mn_known_answer():
    """panels=4, max_n=8 has a fixed ladder, ordered by (m*n, then n). Hardcoded because the
    ordering is the contract: (6,6) [product 36] must sort AFTER (4,8) [32] even though n=6 is
    generated before n=8."""
    assert NSweep.grid_ladder(4, max_n=8) == [
        (4, 4), (4, 5), (4, 6), (4, 7), (4, 8), (6, 6), (5, 8), (6, 8), (7, 8), (8, 8)]


def test_grid_ladder_invariants_and_sort_key():
    """Every pair is m<=n, both >=4, mn % panels == 0, n <= max_n; and the list is exactly its own
    (m*n, n)-sort -- the property the known-answer test checks by example."""
    ladder = NSweep.grid_ladder(4, max_n=16)
    for (m, n) in ladder:
        assert 4 <= m <= n <= 16
        assert (m * n) % 4 == 0
    assert ladder == sorted(ladder, key=lambda mn: (mn[0] * mn[1], mn[1]))


def test_grid_ladder_secondary_key_breaks_product_ties_by_n():
    """When two grids share a product the smaller n wins: (6,8) and (4,12) both = 48, so (6,8) (n=8)
    precedes (4,12) (n=12)."""
    ladder = NSweep.grid_ladder(4, max_n=12)
    assert ladder.index((6, 8)) < ladder.index((4, 12))


# --------------------------------------------------------------------------- run_one (stubbed Popen)
def _install_fake_popen(monkeypatch, *, output="", returncode=0, running=False, wait_raises=False):
    """Stub subprocess.Popen so run_one never launches a real worker. The fake writes `output` to the
    stdout FILE run_one hands it, reports `returncode` (or stays alive when `running`), and can make
    wait() raise TimeoutExpired (`wait_raises`) to exercise the reap guard. Returns the killed-pid
    recorder list (_killtree is stubbed to append here)."""
    pid = 424242
    killed = []
    monkeypatch.setattr(NSweep, "_killtree", lambda p: killed.append(p))

    class _FakePopen:
        def __init__(self, argv, stdout=None, stderr=None, **kw):
            self.pid = pid
            self.returncode = returncode
            self._running = running
            if output:
                stdout.write(output)
                stdout.flush()

        def poll(self):
            return None if self._running else self.returncode

        def wait(self, timeout=None):
            if wait_raises:
                raise subprocess.TimeoutExpired(cmd="worker", timeout=timeout)
            self._running = False
            return self.returncode

    monkeypatch.setattr(NSweep.subprocess, "Popen", _FakePopen)
    return killed


def test_run_one_parses_single_json_line(monkeypatch, tmp_path):
    """The happy path: the worker prints exactly one JSON row; run_one returns it with `seconds`."""
    row_out = {"m": 4, "n": 8, "panels": 4, "err": None, "survivors": 3, "fold": 1}
    _install_fake_popen(monkeypatch, output=json.dumps(row_out) + "\n")
    row = NSweep.run_one(4, 8, 4, jobs=None, timeout=60, tmpdir=str(tmp_path))
    assert row["m"] == 4 and row["survivors"] == 3 and row["err"] is None
    assert "seconds" in row


def test_run_one_scans_past_trailing_stderr(monkeypatch, tmp_path):
    """N24: stderr is merged into stdout, so a LATE warning can be the last line. run_one must scan
    from the end and pick the JSON row, not the warning."""
    row_out = {"m": 6, "n": 8, "panels": 4, "err": None, "fold": 0}
    output = json.dumps(row_out) + "\nWARNING: late multiprocessing resource_tracker chatter\n"
    _install_fake_popen(monkeypatch, output=output)
    row = NSweep.run_one(6, 8, 4, jobs=None, timeout=60, tmpdir=str(tmp_path))
    assert row["m"] == 6 and row["n"] == 8 and "err" in row and row["err"] is None


def test_run_one_skips_trailing_non_dict_json(monkeypatch, tmp_path):
    """A trailing line that IS valid JSON but not an object (e.g. a bare number) must be skipped in
    favour of the real result dict."""
    row_out = {"m": 4, "n": 4, "panels": 4, "err": None, "fold": 0}
    output = json.dumps(row_out) + "\n42\n"
    _install_fake_popen(monkeypatch, output=output)
    row = NSweep.run_one(4, 4, 4, jobs=None, timeout=60, tmpdir=str(tmp_path))
    assert row["m"] == 4 and row["fold"] == 0


def test_run_one_unparseable_output_is_err_row(monkeypatch, tmp_path):
    """No JSON object anywhere -> an `err` row (never a raise), so one bad grid can't stop the sweep."""
    _install_fake_popen(monkeypatch, output="Traceback...\nboom, no json here\n")
    row = NSweep.run_one(4, 5, 4, jobs=None, timeout=60, tmpdir=str(tmp_path))
    assert row["m"] == 4 and "unparseable" in row["err"] and "seconds" in row


def test_run_one_nonzero_exit_is_err_row(monkeypatch, tmp_path):
    """A worker exiting non-zero becomes an `err` row carrying the exit code + tail."""
    _install_fake_popen(monkeypatch, output="some failure output\n", returncode=2)
    row = NSweep.run_one(4, 6, 4, jobs=None, timeout=60, tmpdir=str(tmp_path))
    assert row["err"].startswith("worker exit 2")


def test_run_one_timeout_reaps_tree_and_returns_timeout_row(monkeypatch, tmp_path):
    """A grid that overruns its budget: run_one killtree-reaps the whole tree and returns a
    {err:'timeout'} row. timeout=-1 makes the very first budget check fire, so no real sleep."""
    killed = _install_fake_popen(monkeypatch, running=True)
    row = NSweep.run_one(8, 8, 4, jobs=20, timeout=-1, tmpdir=str(tmp_path))
    assert row["err"] == "timeout" and "seconds" in row
    assert killed == [424242], "the whole process tree must be killtree'd on timeout"


def test_run_one_timeout_survives_a_wedged_wait(monkeypatch, tmp_path):
    """N03: proc.wait(timeout=30) raising TimeoutExpired during the reap must NOT propagate (it would
    kill a multi-hour sweep); run_one still returns a clean timeout row."""
    killed = _install_fake_popen(monkeypatch, running=True, wait_raises=True)
    row = NSweep.run_one(8, 8, 4, jobs=20, timeout=-1, tmpdir=str(tmp_path))
    assert row["err"] == "timeout"
    assert killed == [424242]


def test_run_one_removes_its_temp_file(monkeypatch, tmp_path):
    """The per-grid worker output file is cleaned up (nothing left behind under tmpdir)."""
    _install_fake_popen(monkeypatch, output='{"m":4,"n":4,"panels":4,"err":null}\n')
    NSweep.run_one(4, 4, 4, jobs=None, timeout=60, tmpdir=str(tmp_path))
    assert os.listdir(tmp_path) == []


# --------------------------------------------------------------------------- already_done (resume)
def test_already_done_missing_file_is_empty(tmp_path):
    """No results file yet -> nothing done (a fresh sweep starts from the top)."""
    assert NSweep.already_done(str(tmp_path / "nope.jsonl")) == set()


def test_already_done_collects_grid_keys(tmp_path):
    """Each well-formed row contributes its (m, n, panels) so a resume skips it."""
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps({"m": 4, "n": 4, "panels": 4, "err": None}) + "\n"
        + json.dumps({"m": 4, "n": 8, "panels": 4, "err": "timeout"}) + "\n",
        encoding="utf-8")
    assert NSweep.already_done(str(path)) == {(4, 4, 4), (4, 8, 4)}


def test_already_done_skips_unparseable_trailing_line(tmp_path, capsys):
    """N22: a killed sweep can leave a truncated trailing line. already_done must skip+warn it and
    still return every complete row's key, not crash the whole resume."""
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps({"m": 4, "n": 4, "panels": 4}) + "\n"
        + json.dumps({"m": 6, "n": 6, "panels": 4}) + "\n"
        + '{"m": 8, "n": 8, "pane',           # truncated mid-write, no closing brace
        encoding="utf-8")
    done = NSweep.already_done(str(path))
    assert done == {(4, 4, 4), (6, 6, 4)}
    assert "skipping unparseable line" in capsys.readouterr().out


def test_already_done_skips_row_missing_keys(tmp_path, capsys):
    """A JSON line that parses but lacks m/n/panels is skipped, not a KeyError crash."""
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps({"m": 4, "n": 4, "panels": 4}) + "\n"
        + json.dumps({"note": "no grid keys here"}) + "\n",
        encoding="utf-8")
    assert NSweep.already_done(str(path)) == {(4, 4, 4)}
    assert "skipping unparseable line" in capsys.readouterr().out


# --------------------------------------------------------------------------- nstack CLI guard (N02)
def test_nstack_main_rejects_under_three_panels_with_exit_2():
    """nstack.py --panels 2 is a USAGE error: build_opts raises ValueError, main() catches it and
    returns generate.py's clean exit 2 (was a bare traceback -> exit 1). Reaches build_opts before
    any search, so no worker is launched."""
    assert NS.main(["--m", "4", "--n", "4", "--panels", "2"]) == 2
