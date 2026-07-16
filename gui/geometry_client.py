"""geometry_client.py — run an engine's dump_geometry.py as a SUBPROCESS and parse fold-geometry/1.

This is the GUI's only bridge to the engines. It imports NEITHER engine (square/ and triangle/ each
put a bare `lattice` on sys.path; co-importing both races the bootstrap), reaching them purely by
shelling their dump scripts -- exactly as scripts/fold_grid.py does.

A PIPE (capture_output) is safe HERE: the dump spawns no --jobs worker pool and prints one bounded
JSON line. Do NOT copy this pattern into S9's search dispatch, which runs the real (verbose,
pool-spawning) engine and MUST file-redirect + taskkill /F /T to avoid the Windows orphan trap.

Results are cached by (tiling, m, n), so re-selecting a tiling never re-dumps.
"""
import json
import subprocess
import sys

from gui import tilings


class Geometry:
    """A parsed fold-geometry/1 dump. `ids[k]` <-> `polys[k]`; `adj` is undirected i<j index pairs
    into `ids`. `ids` are the tiling's native tile ids (a drawn subset is a valid fold-grid/1 cells
    list)."""

    __slots__ = ("tiling", "bounds", "ids", "polys", "adj")

    def __init__(self, tiling, bounds, ids, polys, adj):
        self.tiling = tiling
        self.bounds = bounds
        self.ids = ids        # list[list] -- native tile ids, sorted
        self.polys = polys    # list[list[[x, y]]] -- Cartesian boundary per tile
        self.adj = adj         # list[[i, j]] -- undirected edges, i < j, into ids

    def __len__(self):
        return len(self.ids)


_CACHE = {}


def load(tiling, m, n):
    """Dump `tiling`'s m x n ambient block and return its Geometry (cached). Raises ValueError for an
    unknown tiling, RuntimeError if the dump subprocess fails. I/O: (str, int, int) -> Geometry."""
    if tiling not in tilings.TILINGS:
        raise ValueError("unknown tiling %r (expected one of %s)" % (tiling, tilings.names()))
    key = (tiling, m, n)
    if key not in _CACHE:
        _CACHE[key] = _dump(tiling, m, n)
    return _CACHE[key]


def _dump(tiling, m, n):
    argv = [sys.executable, tilings.script_path(tiling), *tilings.dump_argv(tiling, m, n)]
    proc = subprocess.run(argv, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("dump_geometry failed for %s %dx%d (exit %d):\n%s"
                           % (tiling, m, n, proc.returncode, proc.stderr.strip()))
    d = json.loads(proc.stdout)
    return Geometry(d["tiling"], d["bounds"], d["ids"], d["polys"], d["adj"])


def clear_cache():
    """Drop the memoized dumps (tests / a bounds change). I/O: () -> None."""
    _CACHE.clear()
