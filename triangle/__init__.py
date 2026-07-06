"""triangle — the triangle-tiling 3-stack foldability engine (equilateral / right-isosceles /
scalene / hexagon), independent of the square engine (no cross-imports)."""
from . import _bootstrap  # noqa: E402,F401  side effect: puts triangle/ + triangle/tri on
                           # sys.path so submodules' bare imports (`import lattice`, `import
                           # righttri`) resolve on a plain `import triangle.xxx`, not just via the
                           # CLI entry points.
