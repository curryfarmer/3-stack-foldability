"""tilings.py — the GUI's tiling registry: the single source of truth for which dump script backs
each tiling, how to build its argv from a uniform (m, n), and which way its native y-axis points.

The dump CLI is uniform `--m/--n` for all five tilings (the per-tiling (m,n)->constructor branch
lives INSIDE the dumps). So the only asymmetry here is: the square dump takes no `--tiling`, the
four triangle tilings do. `orientation` records each engine's native convention (square emits
+y-down, triangle +y-up) for the S9 render half to flip; the S8 hit-test works in dumped-coord
space and never needs it.
"""
import os

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# token = the dump's --tiling value (None => the square dump, which has no --tiling flag).
TILINGS = {
    "square":      dict(engine="square",   token=None,          orientation="down",
                        script=("square", "dump_geometry.py")),
    "equilateral": dict(engine="triangle", token="equilateral", orientation="up",
                        script=("triangle", "tri", "dump_geometry.py")),
    "righttri":    dict(engine="triangle", token="righttri",    orientation="up",
                        script=("triangle", "tri", "dump_geometry.py")),
    "scalene":     dict(engine="triangle", token="scalene",     orientation="up",
                        script=("triangle", "tri", "dump_geometry.py")),
    "hex":         dict(engine="triangle", token="hex",         orientation="up",
                        script=("triangle", "tri", "dump_geometry.py")),
}


def names():
    """Registered tiling names, in a stable order. I/O: () -> list[str]."""
    return list(TILINGS)


def script_path(tiling):
    """Absolute path to the dump script that backs `tiling`. I/O: (str) -> str."""
    return os.path.join(_REPO, *TILINGS[tiling]["script"])


def dump_argv(tiling, m, n):
    """The dump script's argument list for an m x n ambient block (excludes the interpreter + script
    path -- gui.geometry_client prepends those). I/O: (str, int, int) -> list[str]."""
    entry = TILINGS[tiling]
    argv = []
    if entry["token"] is not None:
        argv += ["--tiling", entry["token"]]
    argv += ["--m", str(m), "--n", str(n)]
    return argv


def orientation(tiling):
    """The tiling's native y convention, 'down' (square) or 'up' (triangle). I/O: (str) -> str."""
    return TILINGS[tiling]["orientation"]


def engine(tiling):
    """Which fold engine backs `tiling`: 'square' (n-stack capable, any N>=2) or 'triangle' (3-stack /
    1+1+1 only). Lets the GUI lock the stack count for triangle tilings. I/O: (str) -> str."""
    return TILINGS[tiling]["engine"]
