"""square — the square-grid 3-stack/2-stack folding engine (independent of the triangle package)."""
from . import _bootstrap  # noqa: E402,F401  side effect: puts square/{engine,twist,render} on
                           # sys.path so submodules' bare imports (`import lattice`, `import fold`)
                           # resolve on a plain `import square.xxx`, not just via the CLI entry points.
