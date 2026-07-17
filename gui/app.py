"""app.py — the fold-gui desktop shell: pick a tiling, draw a connected sheet, fold it, see verdicts.

Run: `python -m gui.app` (the `fold-gui` entry point + gui packaging are wired in S11).

Wiring only -- all compute is the S7 orchestrator via gui.dispatch, all geometry is the S8 dump via
gui.geometry_client. Imports NO engine (co-import safe). The dispatch worker thread never touches tk:
it drops its DispatchResult on a queue that the UI thread drains via root.after, so results marshal
back safely. The small public methods (pick / select / fold / fold_enabled / badge_visible) let the
scripted end-to-end drive the whole app headlessly (Tk constructs without a display on Windows).
"""
import os
import queue
import sys
import time

from gui import canvas as canvas_mod
from gui import dispatch as dispatch_mod
from gui import geometry_client
from gui import results as results_mod
from gui import thumbs
from gui import tilings

_DEFAULT_TIMEOUT = 600.0        # per-fold wall-clock budget (fold_grid --timeout)


class App:
    """The application object. Construct with a tk root; `main()` does that + mainloop. Also drivable
    programmatically (pick/select/fold) for the scripted end-to-end test."""

    def __init__(self, root, out_dir=None):
        import tkinter as tk
        from tkinter import ttk

        self.root = root
        self.out_dir = os.path.abspath(out_dir) if out_dir else os.path.join(os.getcwd(), "out")
        self.dispatch = dispatch_mod.Dispatch()

        self.tiling = None
        self.geometry = None
        self.canvas = None
        self._pending = False
        self._result_q = queue.Queue()
        self._thumb_ref = None          # keep a ref so Tk doesn't GC the image

        self._tk = tk
        self._ttk = ttk
        self._m = tk.IntVar(value=3)
        self._n = tk.IntVar(value=3)
        self._tiling_var = tk.StringVar(value=tilings.names()[0])
        self._status = tk.StringVar(value="pick a tiling, draw a sheet, then Fold")
        self._build()

    # ---- widgets ----
    def _build(self):
        tk, ttk = self._tk, self._ttk
        self.root.title("fold-gui")

        controls = ttk.Frame(self.root)
        controls.pack(side="top", fill="x", padx=6, pady=6)
        ttk.OptionMenu(controls, self._tiling_var, self._tiling_var.get(), *tilings.names()).pack(side="left")
        ttk.Label(controls, text="m").pack(side="left", padx=(8, 0))
        ttk.Spinbox(controls, from_=1, to=12, width=3, textvariable=self._m).pack(side="left")
        ttk.Label(controls, text="n").pack(side="left", padx=(4, 0))
        ttk.Spinbox(controls, from_=1, to=12, width=3, textvariable=self._n).pack(side="left")
        ttk.Button(controls, text="Load", command=self._on_load).pack(side="left", padx=8)
        self._fold_btn = ttk.Button(controls, text="Fold", command=self.fold, state="disabled")
        self._fold_btn.pack(side="left")
        self._cancel_btn = ttk.Button(controls, text="Cancel", command=self.dispatch.cancel,
                                      state="disabled")
        self._cancel_btn.pack(side="left", padx=(4, 0))

        body = ttk.Frame(self.root)
        body.pack(side="top", fill="both", expand=True)
        self._canvas_frame = ttk.Frame(body)
        self._canvas_frame.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(body)
        right.pack(side="right", fill="both", expand=True)
        self.results = results_mod.ResultsView(right, on_select=self._on_row)
        self.results.frame.pack(side="top", fill="both", expand=True)
        self._thumb = ttk.Label(right)
        self._thumb.pack(side="top", pady=4)

        ttk.Label(self.root, textvariable=self._status, anchor="w").pack(side="bottom", fill="x", padx=6, pady=4)

    # ---- public / testable ----
    def pick(self, tiling, m, n):
        """Load a tiling's m x n ambient block into the canvas. I/O: (str, int, int) -> None."""
        self.tiling = tiling
        self._tiling_var.set(tiling)
        self._m.set(m)
        self._n.set(n)
        self.geometry = geometry_client.load(tiling, m, n)
        if self.canvas is not None:
            self.canvas.widget.destroy()
        self.canvas = canvas_mod.CanvasView(self._canvas_frame, self.geometry, tiling,
                                            on_change=self._refresh_fold_btn)
        self.canvas.widget.pack(fill="both", expand=True)
        self._refresh_fold_btn()
        self._set_status("loaded %s %dx%d — draw a connected sheet" % (tiling, m, n))

    def select(self, indices):
        """Set the drawn selection by tile index (test hook for clicking). I/O: (iterable[int]) -> None."""
        self.canvas.set_selection(indices)

    @property
    def fold_enabled(self):
        return self.canvas is not None and self.canvas.is_valid_sheet() and not self._pending

    @property
    def badge_visible(self):
        return self.results.badge_visible

    def fold(self, timeout=_DEFAULT_TIMEOUT, wait=False):
        """Fold the current selection via the S7 orchestrator on a worker thread. `wait=True` pumps the
        tk loop until the result lands (scripted use). I/O: (float, bool) -> None."""
        if self.canvas is None or not self.canvas.is_valid_sheet():
            return
        cells = self.canvas.selected_cells()
        self._pending = True
        self._fold_btn.config(state="disabled")
        self._cancel_btn.config(state="normal")
        self._set_status("folding %d cells…" % len(cells))
        self.dispatch.start(self.tiling, cells, out_dir=self.out_dir, timeout=timeout,
                            on_done=self._result_q.put)
        self.root.after(150, self._poll_result)
        if wait:
            while self._pending:
                self.root.update()
                time.sleep(0.02)

    # ---- internals ----
    def _poll_result(self):
        try:
            result = self._result_q.get_nowait()
        except queue.Empty:
            self.root.after(150, self._poll_result)
            return
        self._pending = False
        self._cancel_btn.config(state="disabled")
        if result.bundle_path:
            rows, gate = results_mod.parse_bundle(result.bundle_path)
            self.results.show(rows, gate)
            self._set_status("done: %d record(s)%s"
                             % (len(rows), " — unproven" if gate else ""))
        else:
            self._set_status("no bundle (rc=%s) — see console" % result.returncode)
        self._refresh_fold_btn()

    def _on_load(self):
        self.pick(self._tiling_var.get(), int(self._m.get()), int(self._n.get()))

    def _on_row(self, row):
        if not row.get("thumb") or not os.path.isfile(row["thumb"]):
            return
        self._thumb_ref = thumbs.load(row["thumb"], master=self.root)
        self._thumb.config(image=self._thumb_ref)

    def _refresh_fold_btn(self):
        self._fold_btn.config(state="normal" if self.fold_enabled else "disabled")

    def _set_status(self, msg):
        self._status.set(msg)


def main(argv=None):
    """CLI entry. --help works with NO display (argparse exits before Tk). I/O: (list[str]|None) -> int."""
    import argparse
    ap = argparse.ArgumentParser(prog="fold-gui", description="draw a sheet on any tiling, then fold it")
    ap.add_argument("--out", default=None, help="output root for bundles (default: ./out)")
    args = ap.parse_args(argv)

    import tkinter as tk
    root = tk.Tk()
    App(root, out_dir=args.out)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
