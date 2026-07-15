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
import time

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PHYSTEST = os.path.join(_REPO, "scripts", "phystest")
if _PHYSTEST not in sys.path:
    sys.path.insert(0, _PHYSTEST)

import check as CHECK        # noqa: E402  (subprocess-only; imports no engine)
import logresult as LOG      # noqa: E402
import oracle_cache as OC    # noqa: E402  (stdlib-only)
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


# ---------- oracle_cache.py: fingerprint ----------
#
# All hermetic: a fake package in tmp_path + a counter callable. `pkg_dir` being a parameter (never
# hardcoded) is what makes this testable without touching the real 1.6 GB results/ or any engine.

@pytest.fixture
def pkg(tmp_path):
    """A minimal fake 'engine package' to fingerprint."""
    d = tmp_path / "fakepkg"
    (d / "sub").mkdir(parents=True)
    (d / "a.py").write_text("A = 1\n", encoding="utf-8")
    (d / "sub" / "b.py").write_text("B = 2\n", encoding="utf-8")
    return d


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    """Point the cache at tmp_path. NEVER let a test write to the real results/.oracle_cache."""
    d = tmp_path / "_cache"
    monkeypatch.setattr(OC, "CACHE_DIR", str(d))
    return d


_OPTS = {"m": 6, "n": 6, "stacks": 3, "allowNonCorner": True, "dedup": True,
         "jobs": 4, "storeAll": False}


def test_source_digest_is_deterministic(pkg):
    assert OC.source_digest(str(pkg)) == OC.source_digest(str(pkg))


def test_source_digest_changes_when_source_edited(pkg):
    """THE safety property: any engine edit must invalidate the cache."""
    before = OC.source_digest(str(pkg))
    (pkg / "a.py").write_text("A = 999\n", encoding="utf-8")
    assert OC.source_digest(str(pkg)) != before


def test_source_digest_stable_across_mtime_bump(pkg):
    """The necessary twin of the test above: 'touched' must mean CONTENT, not mtime.

    Without this, a silently mtime-keyed cache still passes the edit test — and then never hits."""
    before = OC.source_digest(str(pkg))
    future = time.time() + 10_000
    os.utime(pkg / "a.py", (future, future))
    assert OC.source_digest(str(pkg)) == before


def test_source_digest_ignores_pycache_and_pyc(pkg):
    before = OC.source_digest(str(pkg))
    (pkg / "__pycache__").mkdir()
    (pkg / "__pycache__" / "a.cpython-311.pyc").write_bytes(b"\x00\x01compiled")
    (pkg / "a.pyc").write_bytes(b"\x00\x01compiled")
    assert OC.source_digest(str(pkg)) == before


def test_source_digest_ignores_line_endings(pkg):
    """autocrlf flips / re-clones must not burn a multi-hour cold run."""
    (pkg / "a.py").write_bytes(b"A = 1\nB = 2\n")
    lf = OC.source_digest(str(pkg))
    (pkg / "a.py").write_bytes(b"A = 1\r\nB = 2\r\n")
    assert OC.source_digest(str(pkg)) == lf


def test_source_digest_changes_on_add_delete_and_rename(pkg):
    before = OC.source_digest(str(pkg))
    (pkg / "c.py").write_text("C = 3\n", encoding="utf-8")
    added = OC.source_digest(str(pkg))
    assert added != before
    os.remove(pkg / "c.py")
    assert OC.source_digest(str(pkg)) == before          # delete restores the original manifest
    # rename with IDENTICAL content must still change it (the relpath is hashed too)
    os.rename(pkg / "a.py", pkg / "renamed.py")
    assert OC.source_digest(str(pkg)) != before


def test_fingerprint_changes_with_opts_and_grid(pkg):
    base = OC.fingerprint("square", str(pkg), _OPTS)
    assert OC.fingerprint("square", str(pkg), dict(_OPTS, n=5)) != base       # different grid
    assert OC.fingerprint("square", str(pkg), dict(_OPTS, allowNonCorner=False)) != base
    assert OC.fingerprint("square", str(pkg), dict(_OPTS, storeAll=True)) != base
    assert OC.fingerprint("square", str(pkg), dict(_OPTS, dedup=False)) != base
    assert OC.fingerprint("triangle", str(pkg), _OPTS) != base                # different engine


def test_fingerprint_ignores_jobs(pkg):
    """Pins the ONE deliberate hole in the key as a tested decision, not a silent one.

    `jobs` is behaviour-neutral (search.py's parallel path is documented byte-identical to serial),
    so keying on it would make the cache per-core-count: FOLD_JOBS=4 then =8 would each pay a full
    cold run."""
    assert (OC.fingerprint("square", str(pkg), dict(_OPTS, jobs=4))
            == OC.fingerprint("square", str(pkg), dict(_OPTS, jobs=8)))


def test_fingerprint_changes_with_fold_py(pkg, monkeypatch):
    """FOLD_PY=pypy shells the whole search to another interpreter — invisible to a *.py digest."""
    base = OC.fingerprint("square", str(pkg), _OPTS)
    monkeypatch.setenv("FOLD_PY", "pypy")
    assert OC.fingerprint("square", str(pkg), _OPTS) != base


def test_fingerprint_changes_when_checker_edited(pkg, tmp_path):
    """validate_square.py owns _norm_hash + the opts literal but is not under square/."""
    checker = tmp_path / "validate_fake.py"
    checker.write_text("x = 1\n", encoding="utf-8")
    base = OC.fingerprint("square", str(pkg), _OPTS, extra_files=[str(checker)])
    checker.write_text("x = 2\n", encoding="utf-8")
    assert OC.fingerprint("square", str(pkg), _OPTS, extra_files=[str(checker)]) != base


# ---------- oracle_cache.py: cache behaviour ----------

class _Counter:
    """A compute() that records how many times it actually ran."""

    def __init__(self, result=None, exc=None):
        self.calls = 0
        self.result = {"h1": True, "h2": False} if result is None else result
        self.exc = exc

    def __call__(self):
        self.calls += 1
        if self.exc:
            raise self.exc
        return self.result


def test_cache_miss_then_hit(pkg, cache_dir):
    fp = OC.fingerprint("square", str(pkg), _OPTS)
    c = _Counter()
    m1, hit1 = OC.get_or_compute(fp, c)
    assert (hit1, c.calls) == (False, 1)
    m2, hit2 = OC.get_or_compute(fp, c)
    assert (hit2, c.calls) == (True, 1)          # second call served from disk, compute NOT re-run
    assert m1 == m2


def test_cache_miss_after_source_touched(pkg, cache_dir):
    """The whole safety property, end to end: edit the engine -> the cache must not answer."""
    c = _Counter()
    OC.get_or_compute(OC.fingerprint("square", str(pkg), _OPTS), c)
    assert c.calls == 1
    OC.get_or_compute(OC.fingerprint("square", str(pkg), _OPTS), c)
    assert c.calls == 1                                  # warm
    (pkg / "a.py").write_text("A = 'regression'\n", encoding="utf-8")
    _m, hit = OC.get_or_compute(OC.fingerprint("square", str(pkg), _OPTS), c)
    assert (hit, c.calls) == (False, 2)                  # cold again: re-proved against new source


def test_none_tristate_survives_roundtrip_and_is_not_absent(pkg, cache_dir):
    """Guards the conflation trap: a cached None means 'twist undecided' and is NOT absence.

    validate_square must test membership, not truthiness — otherwise every not-enumerated record is
    misreported as twist_undecided, corrupting the count S3 is blocked on."""
    fp = OC.fingerprint("square", str(pkg), _OPTS)
    OC.get_or_compute(fp, _Counter(result={"undecided": None, "fold": True, "jam": False}))
    m, hit = OC.get_or_compute(fp, _Counter(result={"SHOULD": "NOT RUN"}))
    assert hit
    assert m["undecided"] is None and "undecided" in m
    assert m["fold"] is True and m["jam"] is False
    assert "absent" not in m


def test_corrupt_cache_file_is_a_miss(pkg, cache_dir):
    fp = OC.fingerprint("square", str(pkg), _OPTS)
    os.makedirs(str(cache_dir), exist_ok=True)
    with open(OC._path(fp), "w", encoding="utf-8") as f:
        f.write("{not json at all")
    c = _Counter()
    _m, hit = OC.get_or_compute(fp, c)
    assert (hit, c.calls) == (False, 1)          # degrades to recompute, does not raise


def test_fingerprint_mismatch_inside_file_is_a_miss(pkg, cache_dir):
    """The truncated-filename collision guard: full 64-hex is verified on load."""
    fp = OC.fingerprint("square", str(pkg), _OPTS)
    os.makedirs(str(cache_dir), exist_ok=True)
    with open(OC._path(fp), "w", encoding="utf-8") as f:
        json.dump({"schema": OC.SCHEMA, "fingerprint": "f" * 64, "map": {"x": True}}, f)
    assert OC.load(fp) is None
    c = _Counter()
    _m, hit = OC.get_or_compute(fp, c)
    assert (hit, c.calls) == (False, 1)


def test_compute_exception_is_not_cached(pkg, cache_dir):
    """A failed search must never be memoized as a verdict."""
    fp = OC.fingerprint("square", str(pkg), _OPTS)
    boom = _Counter(exc=RuntimeError("search rejected"))
    with pytest.raises(RuntimeError):
        OC.get_or_compute(fp, boom)
    assert OC.load(fp) is None
    good = _Counter()
    _m, hit = OC.get_or_compute(fp, good)
    assert (hit, good.calls) == (False, 1)


def test_store_leaves_no_tmp_files(pkg, cache_dir):
    fp = OC.fingerprint("square", str(pkg), _OPTS)
    OC.get_or_compute(fp, _Counter())
    assert [p for p in os.listdir(str(cache_dir)) if p.endswith(".tmp")] == []


def test_cache_write_failure_does_not_fail_oracle(pkg, cache_dir, monkeypatch):
    """Read-only results/, full disk, AV lock -> a SLOW oracle, never a broken one."""
    def _boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(OC.os, "replace", _boom)
    c = _Counter()
    m, hit = OC.get_or_compute(OC.fingerprint("square", str(pkg), _OPTS), c)
    assert (hit, c.calls) == (False, 1)
    assert m == c.result                          # the computed answer still comes back


def test_gc_keeps_newest_k(cache_dir):
    os.makedirs(str(cache_dir), exist_ok=True)
    for i in range(8):
        p = os.path.join(str(cache_dir), "%016d.json" % i)
        with open(p, "w", encoding="utf-8") as f:
            f.write("{}")
        os.utime(p, (1_000_000 + i, 1_000_000 + i))     # deterministic mtime order
    OC._gc(keep=3)
    left = sorted(os.listdir(str(cache_dir)))
    assert len(left) == 3
    assert left == ["%016d.json" % i for i in (5, 6, 7)]   # the newest survive


def test_no_cache_env_forces_compute(pkg, cache_dir, monkeypatch):
    """ORACLE_CACHE=0 is the kill-switch that forces a cold, from-scratch proof."""
    fp = OC.fingerprint("square", str(pkg), _OPTS)
    c = _Counter()
    OC.get_or_compute(fp, c)
    assert c.calls == 1
    monkeypatch.setenv("ORACLE_CACHE", "0")
    _m, hit = OC.get_or_compute(fp, c)
    assert (hit, c.calls) == (False, 2)          # ignores a present, valid entry


# ---------- check.py: infra ERROR vs data FAIL ----------

def test_check_verdict_error_on_timeout(monkeypatch):
    """A timeout is a BROKEN HARNESS, not a regression. This distinction is the whole point:
    the 30-min timeout firing against an hours-long checker used to read as a real disagreement."""
    monkeypatch.setattr(CHECK, "_run_checker", _canned(
        square={"engine": "square", "skipped": False, "nAgree": None, "nTotal": None,
                "mismatches": [{"kind": "timeout", "detail": "checker exceeded 1800s"}],
                "returncode": -1, "hardError": True},
        triangle={"engine": "triangle", "skipped": False, "nAgree": 3, "nTotal": 3,
                  "mismatches": [], "returncode": 0, "hardError": False}))
    rep = CHECK.run_checks()
    assert rep["verdict"] == "ERROR"
    assert rep["anyError"] and not rep["anyMismatch"]    # NOT reported as a data disagreement


def test_check_verdict_error_on_no_output(monkeypatch):
    monkeypatch.setattr(CHECK, "_run_checker", _canned(
        square={"engine": "square", "skipped": False, "nAgree": None, "nTotal": None,
                "mismatches": [{"kind": "no_output", "detail": "Traceback..."}],
                "returncode": 1, "hardError": True},
        triangle={"engine": "triangle", "skipped": True, "nAgree": None, "nTotal": None,
                  "mismatches": [], "returncode": 0, "hardError": False}))
    rep = CHECK.run_checks()
    assert rep["verdict"] == "ERROR" and rep["anyError"] and not rep["anyMismatch"]


def test_check_data_fail_outranks_infra_error(monkeypatch):
    """A real disagreement is the more actionable answer, so FAIL wins — but anyError still tells."""
    monkeypatch.setattr(CHECK, "_run_checker", _canned(
        square={"engine": "square", "skipped": False, "nAgree": 4, "nTotal": 5,
                "mismatches": [{"kind": "verdict_disagree", "id": 9}], "returncode": 1,
                "hardError": False},
        triangle={"engine": "triangle", "skipped": False, "nAgree": None, "nTotal": None,
                  "mismatches": [{"kind": "timeout"}], "returncode": -1, "hardError": True}))
    rep = CHECK.run_checks()
    assert rep["verdict"] == "FAIL"
    assert rep["anyMismatch"] and rep["anyError"]


def test_check_unknown_mismatch_kind_is_data_not_infra(monkeypatch):
    """An unrecognised kind must FAIL the gate, never be downgraded to an infra hiccup."""
    monkeypatch.setattr(CHECK, "_run_checker", _canned(
        square={"engine": "square", "skipped": False, "nAgree": 4, "nTotal": 5,
                "mismatches": [{"kind": "some_future_kind"}], "returncode": 1, "hardError": False},
        triangle={"engine": "triangle", "skipped": True, "nAgree": None, "nTotal": None,
                  "mismatches": [], "returncode": 0, "hardError": False}))
    assert CHECK.run_checks()["verdict"] == "FAIL"


def test_check_exit_codes_are_distinct(monkeypatch):
    """0 PASS / 1 FAIL / 2 ERROR — so a broken harness cannot read as a regression."""
    def _run(**kw):
        monkeypatch.setattr(CHECK, "_run_checker", _canned(**kw))
        return CHECK.main([])
    ok = {"skipped": False, "nAgree": 1, "nTotal": 1, "mismatches": [], "returncode": 0,
          "hardError": False}
    assert _run(square=dict(ok, engine="square"), triangle=dict(ok, engine="triangle")) == 0
    assert _run(square=dict(ok, engine="square", nAgree=0,
                            mismatches=[{"kind": "verdict_disagree"}]),
                triangle=dict(ok, engine="triangle")) == 1
    assert _run(square=dict(ok, engine="square", mismatches=[{"kind": "timeout"}],
                            hardError=True),
                triangle=dict(ok, engine="triangle")) == 2


def test_check_timeout_flag_parsing():
    """--timeout was previously unreachable: run_checks() was called with no args."""
    assert CHECK._parse_timeout(["--timeout", "60"]) == 60
    assert CHECK._parse_timeout(["--timeout=90"]) == 90
    assert CHECK._parse_timeout(["--json"]) == CHECK._DEFAULT_TIMEOUT


def test_check_reports_cache_attribution(monkeypatch, capsys):
    """A PASS must state whether it came from a fresh search or from disk — otherwise a
    permanently-warm gate is green by memory rather than by proof."""
    monkeypatch.setattr(CHECK, "_run_checker", _canned(
        square={"engine": "square", "skipped": False, "nAgree": 61, "nTotal": 61,
                "mismatches": [], "returncode": 0, "hardError": False,
                "cache": {"6x4": "hit", "6x6": "miss"}},
        triangle={"engine": "triangle", "skipped": False, "nAgree": 22, "nTotal": 22,
                  "mismatches": [], "returncode": 0, "hardError": False}))
    rep = CHECK.run_checks()
    assert rep["engines"]["square"]["cache"] == {"6x4": "hit", "6x6": "miss"}
    CHECK._print_report(rep)
    out = capsys.readouterr().out
    assert "6x4=hit" in out and "6x6=miss" in out


# ---------- the orphan regression test (the actual bug) ----------

# A fake checker that spawns a ProcessPoolExecutor whose workers keep writing heartbeat files.
# This is the shape that broke the old oracle: kill()ing the direct child leaves the grandchildren
# running (and, with capture_output, holding the stdout pipe open forever).
_ORPHAN_CHECKER = '''
import os, sys, time
from concurrent.futures import ProcessPoolExecutor

def _beat(i):
    p = os.path.join(os.environ["BEAT_DIR"], "beat_%d.txt" % i)
    for k in range(2000):
        with open(p, "w") as f:
            f.write(str(k))
        time.sleep(0.05)
    return i

if __name__ == "__main__":
    print("progress: spawning pool", flush=True)
    with ProcessPoolExecutor(max_workers=3) as ex:
        list(ex.map(_beat, range(3)))
    print('{"engine": "fake", "skipped": false, "nAgree": 0, "nTotal": 0, "mismatches": []}')
'''


def test_forced_timeout_leaves_zero_orphans(tmp_path, monkeypatch):
    """THE regression test for the actual bug: a timeout must reap the whole descendant tree.

    Proves it without process enumeration: the grandchildren heartbeat to files, so if any survived
    the kill, those files keep changing after _run_checker returns."""
    beat_dir = tmp_path / "beats"
    beat_dir.mkdir()
    script = tmp_path / "fake_checker.py"
    script.write_text(_ORPHAN_CHECKER, encoding="utf-8")
    monkeypatch.setenv("BEAT_DIR", str(beat_dir))

    t0 = time.time()
    r = CHECK._run_checker("fake", str(script), timeout=6)
    elapsed = time.time() - t0

    assert r["mismatches"][0]["kind"] == "timeout"       # infra, not data
    assert r["hardError"] is True
    assert elapsed < 60, "timeout did not actually bound the run (%.1fs)" % elapsed

    # let any survivor keep beating, then prove nothing moved
    snap = {p: (beat_dir / p).read_text() for p in os.listdir(str(beat_dir))}
    assert snap, "fixture never started: no heartbeats were written"
    time.sleep(2.0)
    after = {p: (beat_dir / p).read_text() for p in os.listdir(str(beat_dir))}
    assert after == snap, "ORPHANS SURVIVED the timeout: heartbeats still advancing %s -> %s" % (
        snap, after)


# ---------- acceptance (slow, data-gated) ----------

@pytest.mark.slow
def test_acceptance_ground_truth_agrees(tmp_path):
    """The real oracle: fresh engine verdicts must still match every physically-folded record.

    Deselected by default (pytest.ini addopts). Run with `pytest -m slow`, or prefer the real gate:
    `python scripts/phystest check`.

    NB the redirect-to-file: this test used to be `subprocess.run(capture_output=True,
    timeout=1200)`, which reproduced the very bug check.py exists to fix. Two ways it bit: the pipe
    kept the whole run alive until the search finished naturally, and 1200s was SHORTER than
    check.py's own timeout, so the outer bound always fired first and orphaned the worker tree.
    Bounding is check.py's job now; this test just must not re-introduce a pipe."""
    has_sq = os.path.isfile(os.path.join(_REPO, "results", "foldfindings.json"))
    has_tri = os.path.isdir(os.path.join(_REPO, "report", "tri"))
    if not has_sq and not has_tri:
        pytest.skip("no local ground-truth data (fresh clone)")
    out_path = tmp_path / "check.out"
    with open(out_path, "w", encoding="utf-8") as f:
        proc = subprocess.run([sys.executable, os.path.join(_REPO, "scripts", "phystest"),
                               "check", "--json"], stdout=f, stderr=subprocess.STDOUT)
    content = out_path.read_text(encoding="utf-8", errors="replace")
    report = json.loads(content.strip().splitlines()[-1])
    assert not report["anyMismatch"], report["engines"]
    assert not report["anyError"], report["engines"]
    assert proc.returncode == 0
