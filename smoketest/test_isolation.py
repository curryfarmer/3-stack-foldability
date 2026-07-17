"""test_isolation.py — pins the engine-suite ISOLATION invariant.

`square/` and `triangle/` are two independent packages that BOTH ship a bare top-level `lattice`
package (square/lattice/, triangle/lattice/). If both dirs land on one interpreter's sys.path,
`import lattice` silently resolves to whichever was found first -- a shadow/collision that would let
`from lattice.square import SquareLattice` (square-only) or `from lattice import foldwalk`
(triangle-only) hit the wrong engine. The architecture leans entirely on each suite running in its
OWN interpreter; scripts/run_tests.py enforces that by dispatching every suite as a separate python
subprocess. Nothing else tests it, so a refactor that co-imports both engines in one process could
regress the whole design silently. These two tests pin it:

  1. test_run_tests_dispatches_separate_interpreters -- structural proof that run_tests launches each
     suite as its own `python -m pytest <path>` subprocess and never imports an engine in-process.
  2. test_bare_lattice_collides_across_packages -- a fresh subprocess DEMONSTRATES the hazard the
     design avoids: with square/ then triangle/ both on sys.path, the bare `lattice` name stays
     pinned to square's package (the second import is the cached one) and triangle's own submodule
     is unreachable.

This module itself MUST NOT `import square.*` / `import triangle.*` -- doing so in the smoketest
interpreter would itself trip the very collision under test. All co-import experiments are spawned as
subprocesses. Only `scripts.run_tests` (which imports no engine) is imported in-process.
"""
import ast
import inspect
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)              # so `scripts` resolves regardless of pytest invocation

from scripts import run_tests               # noqa: E402  (imports os/subprocess/sys only, no engine)


def _imported_top_level_names(module):
    """Every top-level package name imported ANYWHERE in module's source (nested imports included).

    ast.walk reaches imports inside functions too, so an engine co-import hidden in a helper is still
    caught. I/O: (module) -> set[str]."""
    tree = ast.parse(inspect.getsource(module))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_run_tests_dispatches_separate_interpreters():
    """run_tests must launch each suite as its OWN interpreter and never import an engine in-process.

    A future refactor that collects square + triangle in one process -- either by importing them at
    module scope or by dropping the per-suite subprocess -- fails here."""
    # Both engines are registered as SEPARATE suites, at DISTINCT paths (so each is dispatched alone).
    assert {"square", "triangle", "smoketest"} <= set(run_tests._SUITES), run_tests._SUITES
    assert run_tests._SUITES["square"] != run_tests._SUITES["triangle"]

    # The dispatch spawns a fresh `sys.executable -m pytest <path>` per suite -- not one shared run.
    dispatch_src = inspect.getsource(run_tests._run_suite)
    assert "subprocess.Popen(" in dispatch_src, "suites are no longer spawned as subprocesses"
    assert "sys.executable" in dispatch_src, "suites are no longer run in a fresh interpreter"
    assert '"pytest"' in dispatch_src or "'pytest'" in dispatch_src, "not dispatched via -m pytest"

    # main() must invoke the per-suite dispatcher (one subprocess per selected suite name).
    assert "_run_suite(" in inspect.getsource(run_tests.main)

    # And run_tests itself must NOT drag either engine into its own interpreter.
    imported = _imported_top_level_names(run_tests)
    assert "square" not in imported, f"run_tests imports the square engine in-process: {imported}"
    assert "triangle" not in imported, f"run_tests imports the triangle engine in-process: {imported}"


# A fresh-interpreter script: load square's bare `lattice`, THEN prepend triangle/ and re-import.
# Prints a single SENTINEL line the parent asserts on. sys.argv[1]=square dir, sys.argv[2]=triangle.
_COLLISION_SRC = r"""
import os, sys, importlib
square, triangle = sys.argv[1], sys.argv[2]

# 1) Only square/ on the path -> the bare name resolves to square's lattice package.
sys.path.insert(0, square)
import lattice as sq_lat
sq_file = os.path.normcase(os.path.abspath(sq_lat.__file__))

# 2) Now ALSO put triangle/ FIRST on the path and re-import the bare name.
sys.path.insert(0, triangle)
import lattice as re_lat
re_file = os.path.normcase(os.path.abspath(re_lat.__file__))

# The second import is the ALREADY-CACHED square module (shadowing), despite triangle being first.
same_object = re_lat is sq_lat
re_still_square = re_file.startswith(os.path.normcase(os.path.abspath(square)) + os.sep)

# triangle/lattice ships foldwalk.py; square/lattice does NOT. Through the pinned `lattice` package
# its __path__ is square's, so triangle's own submodule is unreachable -- proving they can't coexist.
try:
    importlib.import_module("lattice.foldwalk")
    tri_reachable = True
except ImportError:
    tri_reachable = False

print("SENTINEL same_object=%s re_still_square=%s tri_submodule_reachable=%s"
      % (same_object, re_still_square, tri_reachable))
"""


def test_bare_lattice_collides_across_packages():
    """DEMONSTRATE the hazard the separate-interpreter design avoids.

    In one fresh interpreter with square/ then triangle/ on sys.path, the bare `lattice` name stays
    pinned to square (the re-import is the cached module) and triangle's own submodule cannot be
    reached. That silent shadow is exactly why the suites must never share a process. If the two
    packages ever stopped colliding, this sentinel changes and the test fails -- flagging that the
    isolation rationale (and this proof) needs revisiting."""
    square_dir = os.path.join(_REPO, "square")
    triangle_dir = os.path.join(_REPO, "triangle")
    assert os.path.isdir(os.path.join(square_dir, "lattice")), "square/lattice missing"
    assert os.path.isdir(os.path.join(triangle_dir, "lattice")), "triangle/lattice missing"

    proc = subprocess.run(
        [sys.executable, "-c", _COLLISION_SRC, square_dir, triangle_dir],
        capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0, f"collision probe crashed:\n{proc.stdout}\n{proc.stderr}"

    sentinel = next((ln for ln in proc.stdout.splitlines() if ln.startswith("SENTINEL")), None)
    assert sentinel is not None, f"no SENTINEL line in probe output:\n{proc.stdout}\n{proc.stderr}"

    # Second import returned the cached square module -> the bare name is shadowed, not re-resolved.
    assert "same_object=True" in sentinel, sentinel
    # Even with triangle/ FIRST on sys.path, the bare name still points into square/ -> collision.
    assert "re_still_square=True" in sentinel, sentinel
    # triangle's distinct submodule is unreachable through the pinned name -> they cannot coexist.
    assert "tri_submodule_reachable=False" in sentinel, sentinel
