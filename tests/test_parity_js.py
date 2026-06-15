"""test_parity_js.py — cross-engine parity: the JS engine and the Python engine must agree.

Runs the browser JS 3-stack engine (fold.js + search.js) head-lessly through the Node shim
tests/js_shim/run_engine.mjs, runs the Python engine via enginelib.run_3stack, and asserts the
two produce the SAME solution set (compared by canonical hash) and the same count for a fixed
set of grids.

Hash normalization: JS `JSON.stringify` and Python `json.dumps` can format the canonicalHash
string differently (key order / spacing) even when the underlying object is identical. We parse
each hash string and re-serialize it with sorted keys + compact separators before comparing as
sets, so the comparison is on geometric content, not byte-for-byte string equality.

Gate drift: the JS engine enforces stricter arithmetic gates (mn%6==0, K=mn/3 even, n>=4) while
the Python engine is relaxed to mn%3==0. For grids where that drift makes JS return 0 but Python
return >0 we xfail rather than hard-fail (see KNOWN_DIFFS) — that reconciliation is tracked
separately. The three GRIDS below pass every gate on both sides, so a mismatch there is a real bug
and fails hard.

Requires `node` on PATH; the whole module skips if node is unavailable. All tests carry the
`parity` marker (registered in pytest.ini). Pure compute + subprocess, no disk writes.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any

import pytest

import enginelib as EL  # noqa: E402  (py/ + tests/ put on sys.path by conftest.py)

# ---------- locations ----------

_HERE: str = os.path.dirname(os.path.abspath(__file__))
_ROOT: str = os.path.dirname(_HERE)
SHIM: str = os.path.join(_HERE, "js_shim", "run_engine.mjs")

# Grids exercised. Each satisfies BOTH engines' gates (mn%6==0, K=mn/3 even, n>=4), so the
# JS and Python solution sets are expected to be identical.
GRIDS: list[tuple[int, int]] = [(6, 4), (6, 5), (6, 6)]

# Grids whose parity check runs BOTH engines' full search and so is slow (6x6: Py ~20s + JS ~20s).
# Marked `slow` so the default suite stays fast; opt in with `-m slow`.
SLOW_PARITY: set[tuple[int, int]] = {(6, 6)}


def _grid_params() -> list[Any]:
    """pytest params for GRIDS, slow-marking the expensive ones. I/O: () -> list[pytest.param]."""
    out: list[Any] = []
    for g in GRIDS:
        marks = [pytest.mark.slow] if g in SLOW_PARITY else []
        out.append(pytest.param(g, id=f"{g[0]}x{g[1]}", marks=marks))
    return out

# Expected JS<->Py divergences keyed by grid. Empty for now: all GRIDS above match. Populate with
# {(m, n): "reason"} when a grid is added that the documented arithmetic-gate drift makes differ.
KNOWN_DIFFS: dict[tuple[int, int], str] = {}


# ---------- node availability ----------

def node_available() -> bool:
    """Whether a runnable `node` is on PATH. I/O: () -> bool (True iff `node --version` succeeds)."""
    try:
        subprocess.run(
            ["node", "--version"],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


# Skip the whole module (at collection time) when node is missing — the JS side cannot run.
pytestmark = [
    pytest.mark.parity,
    pytest.mark.skipif(not node_available(), reason="node not on PATH; JS engine cannot run"),
]


# ---------- helpers ----------

def run_js(m: int, n: int, **flags: bool) -> dict[str, Any]:
    """Run the Node shim for one grid and return its parsed JSON result.

    Flags mirror the Python opts and map to shim CLI switches (default: L+Rect, both decomps,
    allowNonCorner false, dedup true): no_rect, no_l, decomp2only, decomp3only, allow_non_corner,
    no_dedup. The shim prints exactly one JSON line on stdout; diagnostics go to stderr.
    I/O: (m, n, **bool flags) -> {"count": int, "hashes": list[str], "ctx": dict}.
    """
    argv: list[str] = ["node", SHIM, "--m", str(m), "--n", str(n)]
    flag_map = {
        "no_rect": "--no-rect", "no_l": "--no-L",
        "decomp2only": "--decomp2only", "decomp3only": "--decomp3only",
        "allow_non_corner": "--allow-non-corner", "no_dedup": "--no-dedup",
    }
    for key, on in flags.items():
        if on:
            argv.append(flag_map[key])
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=600, cwd=_ROOT)
    if proc.returncode != 0:
        raise RuntimeError(f"node shim failed ({m}x{n}) rc={proc.returncode}:\n{proc.stderr}")
    return json.loads(proc.stdout)


def norm_hashes(hashes: list[str]) -> set[str]:
    """Normalize canonicalHash strings to a comparable set (sorted keys, compact separators).

    Re-serializing after json.loads erases JS/Py formatting differences so equal geometry compares
    equal. I/O: (list of canonicalHash json strings) -> set of normalized json strings.
    """
    return {json.dumps(json.loads(h), sort_keys=True, separators=(",", ":")) for h in hashes}


# ---------- the parity test ----------

@pytest.mark.parametrize("grid", _grid_params())
def test_js_py_parity(grid: tuple[int, int]) -> None:
    """Assert JS and Python engines yield the same 3-stack solution set + count for a grid.

    Compares normalized canonicalHash SETS (and counts). A divergence is a hard failure UNLESS the
    grid is in the explicit KNOWN_DIFFS allowlist (which documents the arithmetic-gate drift). We do
    NOT auto-xfail on "JS returned 0": that would silently mask a real JS regression. Adding a
    divergent grid requires a deliberate KNOWN_DIFFS entry. I/O: ((m, n)) -> None.
    """
    m, n = grid
    if grid in KNOWN_DIFFS:
        pytest.xfail(f"known JS<->Py divergence on {m}x{n}: {KNOWN_DIFFS[grid]}")

    js = run_js(m, n)
    py_solutions, _ctx = EL.run_3stack(m, n)

    js_set = norm_hashes(js["hashes"])
    py_set = norm_hashes([s["canonicalHash"] for s in py_solutions])

    # Counts first for a readable failure, then the set equality (the real cross-engine assertion).
    assert js["count"] == len(py_solutions), (
        f"{m}x{n}: JS count {js['count']} != Py count {len(py_solutions)}"
    )
    assert js_set == py_set, (
        f"{m}x{n}: canonical-hash sets differ.\n"
        f"  JS-only: {sorted(js_set - py_set)}\n"
        f"  Py-only: {sorted(py_set - js_set)}"
    )
