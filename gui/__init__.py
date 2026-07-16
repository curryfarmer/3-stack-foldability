"""gui/ — the desktop sheet editor's HEADLESS core (S8).

Pure-logic modules only: the geometry client (subprocess the engine dumps), hit-test, and the
connected-sheet check. These import NEITHER engine -- square/ and triangle/ each put a bare
`lattice` on sys.path and co-importing both races the bootstrap, so the GUI reaches the engines
ONLY by subprocessing their dump_geometry.py scripts (mirrors scripts/fold_grid.py).

The tkinter shell, rendering, and search dispatch are S9 -- not here.
"""
