"""lattice — shared tiling abstraction (UnitTile + Lattice base) and the single reflection
primitive. Square and triangle engines are independent packages built on the same geometry
layer (base.py + reflect.py are duplicated verbatim into both triangle/lattice/ and here —
no cross-package import).
"""
from lattice.base import Lattice, UnitTile  # noqa: F401
from lattice.reflect import reflect_point  # noqa: F401
from lattice.square import SquareLattice  # noqa: F401

__all__ = ["Lattice", "UnitTile", "SquareLattice", "reflect_point"]
