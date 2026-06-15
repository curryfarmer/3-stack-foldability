"""test_perf_toggles.py — the two performance toggles must never move a verdict.

Multiprocessing (--jobs / FOLD_JOBS) and PyPy (FOLD_PY) are orthogonal speed switches. Every
combination must reproduce the serial CPython baseline **1:1**: the full solutions list (exact
ordering AND ids), the order-independent solution_digest, AND every integer ctx counter
(including the order-dependent afterDedup / twistPass). These tests compare hashes + order + ctx,
not merely counts, so a parallel merge that silently reorders or keeps the wrong dedup
representative fails here.

Heavy grids are `slow`-marked (opt in with `pytest -m slow`), matching test_golden's SLOW_GRIDS.
The PyPy lane skips unless a PyPy interpreter is reachable (pypy/pypy3 on PATH, or FOLD_PYPY_BIN).
"""
from __future__ import annotations

import glob
import json
import os
from typing import Any

import pytest

import enginelib as EL      # noqa: E402  (py/ + tests/ on sys.path via conftest.py)
import runner as Runner     # noqa: E402
import search as Search     # noqa: E402

SLOW_GRIDS: set[tuple[int, int]] = {(6, 6), (6, 7), (9, 4), (8, 6), (12, 4)}
_HERE: str = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR: str = os.path.join(_HERE, "golden")


def _int_counts(ctx: dict[str, Any]) -> dict[str, int]:
    """Integer (non-bool) counters from a ctx dict. I/O: (ctx) -> {name: int}."""
    return {k: v for k, v in ctx.items() if isinstance(v, int) and not isinstance(v, bool)}


def _jnorm(x: Any) -> Any:
    """JSON round-trip normalize (tuples->lists) so a value produced in-process compares
    equal to one marshalled across the PyPy subprocess boundary. I/O: (obj) -> obj."""
    return json.loads(json.dumps(x))


# ---------- 1. jobs equality: full list + digest + every ctx counter ----------

@pytest.mark.slow
def test_jobs_equality_6x6() -> None:
    """6x6 jobs=1 vs jobs=8 -> identical solutions (order + id), digest, and ctx counters."""
    s1, c1 = EL.run_3stack(6, 6, jobs=1)
    s8, c8 = EL.run_3stack(6, 6, jobs=8)
    assert EL.solution_digest(s1) == EL.solution_digest(s8)   # count + sorted hashes + breakdown
    assert s1 == s8                                            # exact ordering + sequential ids
    assert _int_counts(c1) == _int_counts(c8)                 # incl. afterDedup / twistPass


# ---------- 2. determinism: jobs=4 twice -> identical ORDERING ----------

@pytest.mark.slow
def test_jobs_determinism_6x6() -> None:
    """Two jobs=4 runs must agree on ORDER, not just as sets — catches gather nondeterminism."""
    a, _ = EL.run_3stack(6, 6, jobs=4)
    b, _ = EL.run_3stack(6, 6, jobs=4)
    assert a == b


# ---------- 3. small grid: more workers than footprints still equals serial ----------

@pytest.mark.parametrize("m,n", [(6, 4), (6, 5)])
def test_small_grid_parallel_equals_serial(m: int, n: int) -> None:
    """jobs=8 on a footprint-starved grid (fewer footprints than workers) == serial."""
    s1, c1 = EL.run_3stack(m, n, jobs=1)
    s8, c8 = EL.run_3stack(m, n, jobs=8)
    assert s1 == s8
    assert _int_counts(c1) == _int_counts(c8)


# ---------- 4. dedup=False parallel equality (the no-dedup admit path) ----------

def test_jobs_equality_no_dedup() -> None:
    """With dedup off every candidate is admitted; parallel order must still match serial."""
    s1, c1 = EL.run_3stack(6, 5, jobs=1, dedup=False)
    s8, c8 = EL.run_3stack(6, 5, jobs=8, dedup=False)
    assert s1 == s8
    assert _int_counts(c1) == _int_counts(c8)


# ---------- 5. env parsing: _resolve_jobs is sloppy-input proof ----------

@pytest.mark.parametrize("env_val,opt_val,expected", [
    ("", None, 1),      # empty -> serial
    ("0", None, 1),     # zero -> clamp
    ("-1", None, 1),    # negative -> clamp
    ("abc", None, 1),   # non-int -> serial
    (None, None, 1),    # unset -> serial
    ("3", None, 3),     # env honored
    ("8", 4, 4),        # explicit opts beats env
    ("", 2, 2),         # opts honored when env empty
    ("5", 1, 1),        # explicit jobs=1 forces serial
])
def test_resolve_jobs(monkeypatch: pytest.MonkeyPatch, env_val: str | None,
                      opt_val: int | None, expected: int) -> None:
    """opts['jobs'] (if set) beats env FOLD_JOBS; anything bad clamps to 1."""
    if env_val is None:
        monkeypatch.delenv("FOLD_JOBS", raising=False)
    else:
        monkeypatch.setenv("FOLD_JOBS", env_val)
    assert Search._resolve_jobs({"jobs": opt_val}) == expected


# ---------- 6. golden-under-load: the whole golden suite with FOLD_JOBS=8 ----------

def _golden_3stack_params() -> list[Any]:
    """Discover 3stack_*.json golden files, slow-marking heavy grids (mirrors test_golden)."""
    paths = sorted(glob.glob(os.path.join(GOLDEN_DIR, "3stack_*.json")))
    if not paths:
        return [pytest.param(None, id="no-golden")]
    out: list[Any] = []
    for p in paths:
        with open(p) as f:
            payload = json.load(f)
        m, n = int(payload["m"]), int(payload["n"])
        slow = (m, n) in SLOW_GRIDS or (payload.get("allowNonCorner") and m * n >= 30)
        out.append(pytest.param(payload, id=os.path.basename(p),
                                marks=[pytest.mark.slow] if slow else []))
    return out


@pytest.mark.parametrize("golden", _golden_3stack_params())
def test_golden_under_load(golden: dict[str, Any] | None,
                           monkeypatch: pytest.MonkeyPatch) -> None:
    """Run each 3-stack golden under FOLD_JOBS=8 (jobs unset -> env) and demand 1:1."""
    if golden is None:
        pytest.skip("no 3stack golden files in tests/golden/")
    monkeypatch.setenv("FOLD_JOBS", "8")
    m, n, nc = int(golden["m"]), int(golden["n"]), bool(golden["allowNonCorner"])
    solutions, ctx = EL.run_3stack(m, n, allow_non_corner=nc)  # jobs=None -> picks FOLD_JOBS
    assert EL.solution_digest(solutions) == EL.solution_digest(golden["solutions"])
    assert solutions == golden["solutions"]
    assert _int_counts(ctx) == golden["ctxCounts"]


# ---------- 7. PyPy lane (skips unless a PyPy interpreter is reachable) ----------

_PYPY = pytest.mark.skipif(not Runner.pypy_available(),
                           reason="no PyPy interpreter (set FOLD_PYPY_BIN or put pypy on PATH)")


@_PYPY
def test_pypy_matches_cpython(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_search under FOLD_PY=pypy reproduces the in-process CPython baseline 1:1."""
    opts = EL.opts_3stack(6, 4)
    s_cp, c_cp, err_cp = Search.run(dict(opts))
    assert err_cp is None
    monkeypatch.setenv("FOLD_PY", "pypy")
    s_py, c_py, err_py = Runner.run_search(dict(opts))
    assert err_py is None
    assert EL.solution_digest(s_py) == EL.solution_digest(s_cp)
    assert s_py == _jnorm(s_cp)
    assert _int_counts(c_py) == _int_counts(c_cp)


@pytest.mark.slow
@_PYPY
def test_pypy_plus_jobs_orthogonal(monkeypatch: pytest.MonkeyPatch) -> None:
    """FOLD_PY=pypy AND FOLD_JOBS=8 together (PyPy child fans across processes) -> 1:1."""
    opts = EL.opts_3stack(6, 6)
    s_cp, c_cp, _ = Search.run(dict(opts))
    monkeypatch.setenv("FOLD_PY", "pypy")
    monkeypatch.setenv("FOLD_JOBS", "8")
    s_py, c_py, err = Runner.run_search(dict(opts))
    assert err is None
    assert EL.solution_digest(s_py) == EL.solution_digest(s_cp)
    assert s_py == _jnorm(s_cp)
    assert _int_counts(c_py) == _int_counts(c_cp)
