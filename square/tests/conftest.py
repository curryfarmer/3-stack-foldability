"""conftest.py — pytest path + fixture setup for the SQUARE engine's test suite.

Puts square/ and its subdirs on sys.path (via square/_bootstrap.py, the single source of truth for
that dir set) so test modules can `import search`, `import fold`, `import twostack` exactly as the
engine modules import one another. Also puts this dir on sys.path for `import enginelib`.

WHY THIS SUITE IS SQUARE-ONLY. square/ and triangle/ each ship a bare-named `lattice` package and
each _bootstrap does sys.path.insert(0, <its own pkg>). Importing both in one interpreter races
whichever bootstrap ran second: `from lattice.square import SquareLattice` then resolves against
triangle/lattice/ (which has no square.py) or vice versa, depending on import order. `lattice.reflect`
and `generate` collide the same way. The two suites therefore never share an interpreter -- see
scripts/run_tests.py, which dispatches each in its own.
"""
import os
import sys

HERE: str = os.path.dirname(os.path.abspath(__file__))
PKG: str = os.path.dirname(HERE)                    # square/
ROOT: str = os.path.dirname(PKG)                    # repo root

sys.path.insert(0, PKG)
import _bootstrap  # noqa: E402,F401  (square/_bootstrap: square/ + engine/ + twist/ + render/)

sys.path.insert(0, HERE)                            # for `import enginelib`

# Serial by default. Search.run consults FOLD_JOBS only when opts["jobs"] is None
# (square/engine/search.py:457-467), and enginelib.opts_3stack passes jobs straight through, so this
# actually takes effect. A worker pool under pytest is how the multi-hour hang + orphan workers
# happened; the suite is small enough that serial costs nothing. setdefault, so an operator can
# still override it from the environment.
os.environ.setdefault("FOLD_JOBS", "1")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def root_dir() -> str:
    """Absolute path to the repository root. I/O: () -> str."""
    return ROOT


@pytest.fixture(scope="session")
def golden_dir() -> str:
    """Absolute path to the tracked engine baselines. I/O: () -> str."""
    return os.path.join(HERE, "golden")


@pytest.fixture(scope="session")
def fixtures_dir() -> str:
    """Absolute path to the tracked test fixtures. I/O: () -> str."""
    return os.path.join(HERE, "fixtures")


@pytest.fixture(scope="session")
def results_dir() -> str:
    """Absolute path to results/ -- GITIGNORED, absent on a fresh clone. Any consumer must guard.
    I/O: () -> str."""
    return os.path.join(ROOT, "results")
