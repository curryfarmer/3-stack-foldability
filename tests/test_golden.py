"""test_golden.py — assert the current Python engine reproduces the committed golden baselines 1:1.

The files in tests/golden/ (written by tests/gen_golden.py) are the fidelity lock: they were
produced by the engine and committed. Here we re-run the same engine entrypoints and demand the
output match those baselines exactly — same counts, same ordering, same dicts. Any drift in the
search, gate, or hashing maths shows up as a failing golden case.

Three golden schemas are covered (discovered dynamically by glob, so new baselines are picked up):
  3stack_{m}x{n}_{c|nc}.json  -> EL.run_3stack
  2stack_{m}x{n}.json         -> EL.run_2stack
  vet_{m}x{n}_{c|nc}.json     -> EL.closing_candidates

Heavy grids (SLOW_GRIDS) are marked `slow` and only run under `-m slow`. Pure compute, no disk writes.
"""
from __future__ import annotations

import glob
import json
import os
from typing import Any

import pytest

import enginelib as EL  # noqa: E402  (py/ + tests/ put on sys.path by conftest.py)

# Grids whose engine re-run is expensive (large K / non-corner explosion). Cases on these grids
# are marked `slow` so the default test run stays fast; opt in with `pytest -m slow`.
SLOW_GRIDS: set[tuple[int, int]] = {(6, 6), (6, 7), (9, 4), (8, 6), (12, 4)}

_HERE: str = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR: str = os.path.join(_HERE, "golden")


# ---------- golden-file discovery / parametrization ----------

def _load_golden(path: str) -> dict[str, Any]:
    """Read one golden JSON file into a dict. I/O: (abs path) -> parsed payload dict."""
    with open(path) as f:
        return json.load(f)


def _is_slow(payload: dict[str, Any]) -> bool:
    """Whether a golden case is expensive to re-run. I/O: (golden payload) -> bool.

    Slow if the grid is in SLOW_GRIDS, OR it is a non-corner run on a non-trivial grid
    (allowNonCorner explodes combinatorially — e.g. 6x5 nc=True takes ~100s)."""
    m, n = int(payload["m"]), int(payload["n"])
    if (m, n) in SLOW_GRIDS:
        return True
    if payload.get("allowNonCorner") and m * n >= 30:
        return True
    return False


def _params(prefix: str) -> list[Any]:
    """Build pytest params for every golden file matching a prefix, id = filename, slow-marked by grid.

    If tests/golden/ is missing or has no matching files, returns a single param carrying None so the
    test body can emit one clean skip instead of erroring at collection.
    I/O: (filename prefix, e.g. '3stack_') -> list[pytest.param].
    """
    paths = sorted(glob.glob(os.path.join(GOLDEN_DIR, f"{prefix}*.json")))
    if not paths:
        return [pytest.param(None, id=f"no-golden-{prefix.rstrip('_')}")]
    out: list[Any] = []
    for p in paths:
        payload = _load_golden(p)
        marks = [pytest.mark.slow] if _is_slow(payload) else []
        out.append(pytest.param(payload, id=os.path.basename(p), marks=marks))
    return out


# ---------- comparison helpers ----------

def _int_counts(ctx: dict[str, Any]) -> dict[str, int]:
    """Extract the integer (non-bool) counters from a ctx dict, as gen_golden recorded them.
    I/O: (engine ctx dict) -> {name: int}."""
    return {k: v for k, v in ctx.items() if isinstance(v, int) and not isinstance(v, bool)}


def _skip_if_empty(payload: dict[str, Any] | None) -> None:
    """Skip the current test with a clear message when no golden file was found.
    I/O: (golden payload or None) -> None (raises pytest.skip on None)."""
    if payload is None:
        pytest.skip("no matching golden files in tests/golden/ — run tests/gen_golden.py to create them")


# ---------- 3-stack golden ----------

@pytest.mark.parametrize("golden", _params("3stack_"))
def test_3stack_golden(golden: dict[str, Any] | None) -> None:
    """Re-run run_3stack and assert solutions + integer ctx counts match the golden baseline exactly.
    I/O: (3stack golden payload | None) -> None (asserts engine reproduces baseline)."""
    _skip_if_empty(golden)
    m, n, nc = int(golden["m"]), int(golden["n"]), bool(golden["allowNonCorner"])
    solutions, ctx = EL.run_3stack(m, n, allow_non_corner=nc)
    # Digest first: an order-independent summary gives a readable diff before the strict equality.
    assert EL.solution_digest(solutions) == EL.solution_digest(golden["solutions"])
    assert solutions == golden["solutions"]
    assert _int_counts(ctx) == golden["ctxCounts"]


# ---------- 2-stack golden ----------

@pytest.mark.parametrize("golden", _params("2stack_"))
def test_2stack_golden(golden: dict[str, Any] | None) -> None:
    """Re-run run_2stack and assert the solution list matches the golden baseline exactly.
    I/O: (2stack golden payload | None) -> None (asserts engine reproduces baseline)."""
    _skip_if_empty(golden)
    m, n = int(golden["m"]), int(golden["n"])
    solutions, _ctx = EL.run_2stack(m, n)
    assert solutions == golden["solutions"]


# ---------- vet (closing-candidate) golden ----------

@pytest.mark.parametrize("golden", _params("vet_"))
def test_vet_golden(golden: dict[str, Any] | None) -> None:
    """Re-run closing_candidates and assert the candidate list (same order) and K match the baseline.
    I/O: (vet golden payload | None) -> None (asserts engine reproduces baseline)."""
    _skip_if_empty(golden)
    m, n, nc = int(golden["m"]), int(golden["n"]), bool(golden["allowNonCorner"])
    candidates, K = EL.closing_candidates(m, n, allow_non_corner=nc)
    assert K == golden["K"]
    assert candidates == golden["candidates"]
