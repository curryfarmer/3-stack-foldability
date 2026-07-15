"""test_physical_suite.py — tracked tests for scripts/phystest (the physical-testing suite).

Two layers:
  * TOOLING (fast, hermetic): exercise records / batch-manifest / log / status / check-aggregation
    on synthetic fixtures in tmp_path. No engine subprocess, no gitignored ground-truth data — these
    run anywhere, including a fresh clone / CI. (phystest modules never import an engine package, so
    importing them into this interpreter is safe.)
  * ACCEPTANCE (slow, data-gated): run `python scripts/phystest check` for real and assert the fresh
    engine verdicts still match every physically-folded record. Skips when the local ground-truth
    data (results/, report/tri/) is absent. Marked `slow`.
"""
import json
import os
import subprocess
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PHYSTEST = os.path.join(_REPO, "scripts", "phystest")
if _PHYSTEST not in sys.path:
    sys.path.insert(0, _PHYSTEST)

import check as CHECK        # noqa: E402  (subprocess-only; imports no engine)
import logresult as LOG      # noqa: E402
import records as R          # noqa: E402
import status as STATUS      # noqa: E402


# ---------- fixtures ----------

def _bundle(uid="aaaa1111bbbb", foldable=True, decomp="2+1", m=6, n=6):
    return {
        "uid": uid, "m": m, "n": n, "lattice": "square", "stacks": 3,
        "decomposition": decomp,
        "canonicalHash": json.dumps({"fp": [[0, 1], [0, 2]], "chains": [{"kind": "1chain"}]}),
        "verdict": {"arithmetic": True, "exitFootprint": True, "parity": True,
                    "reflection": True, "twist": foldable},
    }


# ---------- records.py ----------

def test_norm_hash_is_key_order_independent():
    a = json.dumps({"fp": [[0, 1]], "chains": [1, 2]})
    b = json.dumps({"chains": [1, 2], "fp": [[0, 1]]})  # same content, keys swapped
    assert R.norm_hash(a) == R.norm_hash(b)


def test_physical_record_from_bundle_maps_prediction():
    rec = R.physical_record_from_bundle(_bundle(foldable=True), "raw/x/foldsheet_x.png")
    assert rec["schema"] == "physical-test/1"
    assert rec["grid"] == "6x6"
    assert rec["decomp"] == "2+1"
    assert rec["predicted"]["foldable"] is True
    assert rec["predicted"]["failingGates"] == []
    assert rec["actual"]["folded"] is None


def test_physical_record_flags_failing_gate():
    b = _bundle(foldable=False)
    b["verdict"]["parity"] = False
    rec = R.physical_record_from_bundle(b, "f.png")
    assert "parity" in rec["predicted"]["failingGates"]
    assert rec["predicted"]["foldable"] is False


def test_append_square_finding_writes_and_dedups(tmp_path, monkeypatch):
    db = tmp_path / "foldfindings.json"
    monkeypatch.setattr(R, "FOLDFINDINGS_PATH", str(db))
    h = _bundle()["canonicalHash"]
    rec, created = R.append_square_finding(grid="6x6", canonical_hash=h, folded=True,
                                           by="tester", date="2026-07-14")
    assert created and rec["id"] == 1 and rec["foldable"] is True
    assert db.is_file() and len(R.load_square_findings()) == 1
    # same (grid, hash) must not double-log
    _rec2, created2 = R.append_square_finding(grid="6x6", canonical_hash=h, folded=True,
                                              by="tester", date="2026-07-14")
    assert created2 is False and len(R.load_square_findings()) == 1


# ---------- logresult.py + status.py (batch round-trip) ----------

def _write_batch(tmp_path, foldable=True):
    item = R.physical_record_from_bundle(_bundle(foldable=foldable), "raw/x/foldsheet_x.png")
    manifest = {"schema": "phystest-batch/1", "engine": "square", "grid": "6x6",
                "decomps": "2+1", "policy": "all", "allowNonCorner": True,
                "counts": {}, "items": [item]}
    R.save_batch(str(tmp_path), manifest)
    return item["uid"]


def test_log_square_matched_prediction(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "FOLDFINDINGS_PATH", str(tmp_path / "foldfindings.json"))
    uid = _write_batch(tmp_path, foldable=True)
    rec, created, matched = LOG.log_square(str(tmp_path), uid, folded=True, by="john",
                                           date="2026-07-14")
    assert created and matched is True
    reloaded = R.load_batch(str(tmp_path))["items"][0]
    assert reloaded["actual"]["folded"] is True and reloaded["actual"]["by"] == "john"


def test_log_square_missed_prediction(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "FOLDFINDINGS_PATH", str(tmp_path / "foldfindings.json"))
    uid = _write_batch(tmp_path, foldable=True)  # engine predicted FOLD
    _rec, _created, matched = LOG.log_square(str(tmp_path), uid, folded=False, by="john")  # it JAMmed
    assert matched is False


def test_status_batch_summary_counts_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "FOLDFINDINGS_PATH", str(tmp_path / "foldfindings.json"))
    uid = _write_batch(tmp_path, foldable=True)
    assert STATUS.batch_summary(str(tmp_path))["pending"] == 1
    LOG.log_square(str(tmp_path), uid, folded=True, by="john")
    s = STATUS.batch_summary(str(tmp_path))
    assert s["pending"] == 0 and s["logged"] == 1


# ---------- check.py aggregation (monkeypatched checkers, no subprocess) ----------

def _canned(**by_engine):
    def fake(engine, script, timeout):
        return by_engine[engine]
    return fake


def test_check_verdict_pass(monkeypatch):
    monkeypatch.setattr(CHECK, "_run_checker", _canned(
        square={"engine": "square", "skipped": False, "nAgree": 5, "nTotal": 5,
                "mismatches": [], "returncode": 0, "hardError": False},
        triangle={"engine": "triangle", "skipped": False, "nAgree": 3, "nTotal": 3,
                  "mismatches": [], "returncode": 0, "hardError": False}))
    rep = CHECK.run_checks()
    assert rep["verdict"] == "PASS" and rep["totalAgree"] == 8 and not rep["anyMismatch"]


def test_check_verdict_fail_on_mismatch(monkeypatch):
    monkeypatch.setattr(CHECK, "_run_checker", _canned(
        square={"engine": "square", "skipped": False, "nAgree": 4, "nTotal": 5,
                "mismatches": [{"kind": "verdict_disagree", "id": 9}], "returncode": 1,
                "hardError": False},
        triangle={"engine": "triangle", "skipped": True, "nAgree": None, "nTotal": None,
                  "mismatches": [], "returncode": 0, "hardError": False}))
    rep = CHECK.run_checks()
    assert rep["verdict"] == "FAIL" and rep["anyMismatch"]


def test_check_verdict_partial_skip(monkeypatch):
    monkeypatch.setattr(CHECK, "_run_checker", _canned(
        square={"engine": "square", "skipped": False, "nAgree": 5, "nTotal": 5,
                "mismatches": [], "returncode": 0, "hardError": False},
        triangle={"engine": "triangle", "skipped": True, "nAgree": None, "nTotal": None,
                  "mismatches": [], "returncode": 0, "hardError": False}))
    assert CHECK.run_checks()["verdict"] == "PASS (with skip)"


def test_check_verdict_nothing_validated(monkeypatch):
    monkeypatch.setattr(CHECK, "_run_checker", _canned(
        square={"engine": "square", "skipped": True, "nAgree": None, "nTotal": None,
                "mismatches": [], "returncode": 0, "hardError": False},
        triangle={"engine": "triangle", "skipped": True, "nAgree": None, "nTotal": None,
                  "mismatches": [], "returncode": 0, "hardError": False}))
    assert CHECK.run_checks()["verdict"] == "NOTHING VALIDATED"


# ---------- acceptance (slow, data-gated) ----------

@pytest.mark.slow
def test_acceptance_ground_truth_agrees():
    """The real oracle: fresh engine verdicts must still match every physically-folded record."""
    has_sq = os.path.isfile(os.path.join(_REPO, "results", "foldfindings.json"))
    has_tri = os.path.isdir(os.path.join(_REPO, "report", "tri"))
    if not has_sq and not has_tri:
        pytest.skip("no local ground-truth data (fresh clone)")
    proc = subprocess.run([sys.executable, os.path.join(_REPO, "scripts", "phystest"),
                           "check", "--json"], capture_output=True, text=True, timeout=1200)
    report = json.loads(proc.stdout.strip().splitlines()[-1])
    assert not report["anyMismatch"], report["engines"]
    assert proc.returncode == 0
