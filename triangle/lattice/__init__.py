"""triangle/lattice — shared tiling abstraction (Lattice base) and the single reflection primitive
for the triangle engine. Deliberately empty of re-exports: every consumer imports the submodules it
needs directly (`from lattice.base import Lattice`, `from lattice.reflect import reflect_point`,
`from lattice import foldwalk`) so this package init does not need to know about any tiling.
"""
