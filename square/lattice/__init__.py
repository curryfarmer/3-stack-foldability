"""lattice — shared tiling abstraction (UnitTile + Lattice base) and the single reflection
primitive. Square and triangle engines are lattice subclasses over one geometry layer.

The triangle subclasses (TriLattice / RightTriLattice / ScaleneLattice) live under py/tri and
import lattice.base; they are imported from their own modules to avoid a package-init cycle.
"""
from lattice.base import Lattice, UnitTile  # noqa: F401
from lattice.reflect import reflect_point  # noqa: F401
from lattice.square import SquareLattice  # noqa: F401

__all__ = ["Lattice", "UnitTile", "SquareLattice", "reflect_point"]
