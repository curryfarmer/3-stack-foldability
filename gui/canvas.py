"""canvas.py — the drawing canvas: hit-test (S8) + the embedded render view (S9).

hit_test (top of file) stays backend-free: it imports only matplotlib.path, so gui.canvas can be
imported for hit-testing (and the S8 no-co-import guard) without pulling a GUI backend. CanvasView
(the render half) lazy-imports Figure + FigureCanvasTkAgg + Polygon INSIDE __init__, so only actually
constructing a view commits a backend. It uses matplotlib.figure.Figure (NOT pyplot), so there is no
"set backend before pyplot" trap and no pyplot global state.

One code path for all five geometries: CanvasView fills the engine-dumped polygons and hit-tests
clicks against them (via hit_test), inverting y only for square (+y-down); triangle draws native
+y-up. Selection validity is the S8 connectivity check on the dumped adjacency.
"""
from matplotlib.path import Path


def hit_test(point, polys):
    """Index of the first polygon in `polys` that contains `point`, else None. Tiles in a tiling are
    disjoint, so at most one contains an interior point (e.g. a tile centroid). I/O:
    ((x, y), list[list[[x, y]]]) -> int | None."""
    for k, poly in enumerate(polys):
        if Path(poly).contains_point(point):
            return k
    return None


class CanvasView:
    """An embedded matplotlib canvas that draws a Geometry and lets you toggle tiles by clicking.

    `parent` is a tk widget; `geometry` is a gui.geometry_client.Geometry; `tiling` selects the y
    orientation. `on_change()` (optional) fires after every selection change. `.widget` is the tk
    widget to pack. I/O: constructed once per (tiling, bounds)."""

    def __init__(self, parent, geometry, tiling, on_change=None):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.patches import Polygon

        from gui import config, connectivity, tilings

        self._Polygon = Polygon
        self._connectivity = connectivity
        self._cfg = config
        self.geometry = geometry
        self.tiling = tiling
        self.on_change = on_change
        self.selected = set()            # tile indices into geometry.ids / .polys
        self._stroke = None              # active paint stroke: {"mode": "add"|"erase", "touched": set}

        self.fig = Figure(figsize=(5.5, 5.5))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.widget = self.canvas.get_tk_widget()

        self._patches = []
        self._draw_all(tilings.orientation(tiling))
        # Paint-select: press starts a stroke (mode from the start tile — empty->add, selected->erase,
        # right-button always erases), motion extends it over every tile the cursor crosses, release
        # ends it. A press+release with no motion touches exactly one tile, so a plain click still
        # toggles. Live feedback paints each tile as it is touched; the full validity recolor (+ the
        # on_change callback) fires once at release, not per motion event.
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        self.canvas.draw()

    # ---- drawing ----
    def _draw_all(self, orientation):
        polys = self.geometry.polys
        self.ax.clear()
        self.ax.set_aspect("equal")
        self.ax.axis("off")
        self._patches = []
        for poly in polys:
            patch = self._Polygon(poly, closed=True, facecolor=self._cfg.CELL_FILL,
                                  edgecolor=self._cfg.GRID_EDGE, lw=0.8, zorder=1)
            self.ax.add_patch(patch)
            self._patches.append(patch)
        xs = [x for poly in polys for (x, _y) in poly]
        ys = [y for poly in polys for (_x, y) in poly]
        pad = 0.3
        self.ax.set_xlim(min(xs) - pad, max(xs) + pad)
        if orientation == "down":                        # square: origin top-left, +y down
            self.ax.set_ylim(max(ys) + pad, min(ys) - pad)
        else:                                            # triangle: native +y up
            self.ax.set_ylim(min(ys) - pad, max(ys) + pad)

    def _recolor(self):
        valid = self.is_valid_sheet()
        for k, patch in enumerate(self._patches):
            if k in self.selected:
                patch.set_facecolor(self._cfg.SELECTED_FILL)
                patch.set_edgecolor(self._cfg.SELECTED_EDGE if valid else self._cfg.INVALID_EDGE)
                patch.set_linewidth(2.2)
            else:
                patch.set_facecolor(self._cfg.CELL_FILL)
                patch.set_edgecolor(self._cfg.GRID_EDGE)
                patch.set_linewidth(0.8)
        self.canvas.draw_idle()
        if self.on_change:
            self.on_change()

    # ---- interaction (paint-select) ----
    def _event_idx(self, event):
        """The tile under a mouse event, or None (off-axes / off-tile). I/O: (event) -> int | None."""
        if event.inaxes is not self.ax or event.xdata is None:
            return None
        return hit_test((event.xdata, event.ydata), self.geometry.polys)

    def _on_press(self, event):
        idx = self._event_idx(event)
        if idx is None:
            return
        # right button (3) always erases; otherwise the start tile's state picks the whole stroke's
        # mode, so dragging never flip-flops tile-by-tile.
        mode = "erase" if (event.button == 3 or idx in self.selected) else "add"
        self._stroke = {"mode": mode, "touched": set()}
        self._apply_stroke(idx)

    def _on_motion(self, event):
        if self._stroke is None:
            return
        idx = self._event_idx(event)
        if idx is not None:
            self._apply_stroke(idx)

    def _on_release(self, _event):
        if self._stroke is None:
            return
        self._stroke = None
        self._recolor()                  # full validity recolor + one on_change for the whole stroke

    def _apply_stroke(self, idx):
        """Apply the active stroke's mode to tile `idx` once, painting it immediately. I/O:
        (int) -> None."""
        touched = self._stroke["touched"]
        if idx in touched:
            return
        touched.add(idx)
        if self._stroke["mode"] == "add":
            self.selected.add(idx)
            self._paint_patch(idx, True)
        else:
            self.selected.discard(idx)
            self._paint_patch(idx, False)
        self.canvas.draw_idle()

    def _paint_patch(self, idx, on):
        """Provisional per-tile paint during a stroke (no BFS validity check -- _recolor at release
        settles the valid/invalid edge color). I/O: (int, bool) -> None."""
        patch = self._patches[idx]
        if on:
            patch.set_facecolor(self._cfg.SELECTED_FILL)
            patch.set_edgecolor(self._cfg.SELECTED_EDGE)
            patch.set_linewidth(2.2)
        else:
            patch.set_facecolor(self._cfg.CELL_FILL)
            patch.set_edgecolor(self._cfg.GRID_EDGE)
            patch.set_linewidth(0.8)

    def toggle(self, idx):
        """Flip tile `idx`'s selection and recolor. I/O: (int) -> None."""
        self.selected.symmetric_difference_update({idx})
        self._recolor()

    def set_selection(self, indices):
        """Replace the selection with `indices` and recolor. I/O: (iterable[int]) -> None."""
        self.selected = set(indices)
        self._recolor()

    def selected_cells(self):
        """The selected tiles as native fold-grid/1 cells, sorted. I/O: () -> list[list]."""
        return [self.geometry.ids[k] for k in sorted(self.selected)]

    def is_valid_sheet(self):
        """True iff the selection is a non-empty connected sheet (S8 connectivity on dumped adj).
        I/O: () -> bool."""
        return self._connectivity.is_connected(self.selected, self.geometry.adj)
