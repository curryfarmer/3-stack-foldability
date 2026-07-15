"""conftest.py — pytest path + fixture setup for the TRIANGLE engine's test suite.

Puts triangle/ and triangle/tri on sys.path (via triangle/_bootstrap.py, the single source of truth
for that dir set) so test modules can `import foldclose`, `import scalene`, `import trilattice`
exactly as the engine modules import one another.

WHY THIS SUITE IS TRIANGLE-ONLY. square/ and triangle/ each ship a bare-named `lattice` package and
each _bootstrap does sys.path.insert(0, <its own pkg>). Importing both in one interpreter races
whichever bootstrap ran second: `from lattice.square import SquareLattice` then resolves against
triangle/lattice/ (which has no square.py) or vice versa, depending on import order. `lattice.reflect`
and `generate` collide the same way. The two suites therefore never share an interpreter -- see
scripts/run_tests.py, which dispatches each in its own.
"""
import os
import sys

HERE: str = os.path.dirname(os.path.abspath(__file__))
PKG: str = os.path.dirname(HERE)                    # triangle/
ROOT: str = os.path.dirname(PKG)                    # repo root

sys.path.insert(0, PKG)
import _bootstrap  # noqa: E402,F401  (triangle/_bootstrap: triangle/ + tri/)

sys.path.insert(0, HERE)

# Serial by default -- see square/tests/conftest.py for the full rationale (a worker pool under
# pytest is how the multi-hour hang + orphan workers happened). setdefault, so an operator can
# still override it from the environment.
os.environ.setdefault("FOLD_JOBS", "1")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def root_dir() -> str:
    """Absolute path to the repository root. I/O: () -> str."""
    return ROOT


@pytest.fixture(scope="session")
def fixtures_dir() -> str:
    """Absolute path to the tracked test fixtures. I/O: () -> str."""
    return os.path.join(HERE, "fixtures")


@pytest.fixture(scope="session")
def results_dir() -> str:
    """Absolute path to results/ -- GITIGNORED, absent on a fresh clone. Any consumer must guard;
    test_tri_reference.py's _load_or_skip is the reference. I/O: () -> str."""
    return os.path.join(ROOT, "results")
