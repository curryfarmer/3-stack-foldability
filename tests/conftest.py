"""conftest.py — pytest path + fixture setup for the foldability test suite.

Puts the Python engine packages on sys.path (py/, py/tri/) so test modules can
`import search`, `import fold`, `import twostack`, etc. exactly as the engine
modules import one another. Also exposes shared directory fixtures.
"""
import os
import sys

HERE: str = os.path.dirname(os.path.abspath(__file__))
ROOT: str = os.path.dirname(HERE)
PY: str = os.path.join(ROOT, "py")

# Engine modules import each other by bare name (e.g. `import fold`), so the py/
# dirs must be on sys.path before any test imports them.
for _p in (HERE, PY, os.path.join(PY, "tri")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def root_dir() -> str:
    """Absolute path to the repository root. I/O: () -> str."""
    return ROOT


@pytest.fixture(scope="session")
def golden_dir() -> str:
    """Absolute path to tests/golden/ (committed engine baselines). I/O: () -> str."""
    return os.path.join(HERE, "golden")


@pytest.fixture(scope="session")
def results_dir() -> str:
    """Absolute path to results/ (committed result + label JSON). I/O: () -> str."""
    return os.path.join(ROOT, "results")
