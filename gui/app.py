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


def _failure_reason(output):
    """A short human reason for a bundle-less fold, pulled from the orchestrator's captured output:
    prefer an explicit `error:` / `rejected:` line, else the last non-empty line (usually an engine
    traceback's message), else a generic pointer. rc=1 is an engine hard-fail (square usage / a
    triangle bad-region traceback); rejects (empty / not-connected / not divisible) still write a
    bundle, so they don't reach here. I/O: (str|None) -> str."""
    lines = [ln.strip() for ln in (output or "").splitlines() if ln.strip()]
    for ln in reversed(lines):
        low = ln.lower()
        if low.startswith("error:") or low.startswith("rejected:"):
            return ln[:200]
    return lines[-1][:200] if lines else "see console for details"


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
        # pre-fold search controls (shape what the engine computes -> faster)
        self._stacks_vars = {2: tk.BooleanVar(value=False), 3: tk.BooleanVar(value=True)}
        self._decomp_vars = {"2+1": tk.BooleanVar(value=True), "1+1+1": tk.BooleanVar(value=True)}
        self._find_mode = tk.StringVar(value="all")     # "all" | "example" (find-first)
        self._preview_kind = tk.StringVar(value="")     # which image kind the viewer shows
        self._preview_row = None                        # the row currently in the viewer
        self._build()

    # ---- widgets ----
    def _build(self):
        tk, ttk = self._tk, self._ttk
        self.root.title("fold-gui")

        # Row 1: pick a tiling + grid size, (re)draw the grid, fold.
        controls = ttk.Frame(self.root)
        controls.pack(side="top", fill="x", padx=6, pady=(6, 0))
        ttk.OptionMenu(controls, self._tiling_var, self._tiling_var.get(), *tilings.names()).pack(side="left")
        ttk.Label(controls, text="m").pack(side="left", padx=(8, 0))
        ttk.Spinbox(controls, from_=1, to=12, width=3, textvariable=self._m).pack(side="left")
        ttk.Label(controls, text="n").pack(side="left", padx=(4, 0))
        ttk.Spinbox(controls, from_=1, to=12, width=3, textvariable=self._n).pack(side="left")
        # "New grid" (was "Load") only dumps a fresh empty grid to draw on -- it never loads a result.
        ttk.Button(controls, text="New grid", command=self._on_load).pack(side="left", padx=8)
        self._fold_btn = ttk.Button(controls, text="Fold", command=self.fold, state="disabled")
        self._fold_btn.pack(side="left")
        self._cancel_btn = ttk.Button(controls, text="Cancel", command=self.dispatch.cancel,
                                      state="disabled")
        self._cancel_btn.pack(side="left", padx=(4, 0))

        # Row 2: search-shaping options (fewer stacks/decomps + find-example = faster).
        opts = ttk.Frame(self.root)
        opts.pack(side="top", fill="x", padx=6, pady=(2, 6))
        ttk.Label(opts, text="stacks").pack(side="left")
        for n, var in self._stacks_vars.items():
            ttk.Checkbutton(opts, text=str(n), variable=var).pack(side="left")
        ttk.Label(opts, text=" decomp").pack(side="left")
        for name, var in self._decomp_vars.items():
            ttk.Checkbutton(opts, text=name, variable=var).pack(side="left")
        ttk.Label(opts, text="  find:").pack(side="left")
        ttk.Radiobutton(opts, text="all", value="all", variable=self._find_mode).pack(side="left")
        ttk.Radiobutton(opts, text="example (fast)", value="example",
                        variable=self._find_mode).pack(side="left")

        body = ttk.Frame(self.root)
        body.pack(side="top", fill="both", expand=True)
        self._canvas_frame = ttk.Frame(body)
        self._canvas_frame.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(body)
        right.pack(side="right", fill="both", expand=True)
        self.results = results_mod.ResultsView(right, on_select=self._on_row)
        self.results.frame.pack(side="top", fill="both", expand=True)
        # Result viewer: an image-kind picker (rebuilt per selected row) + a large preview + a
        # fallback message when the record has no image.
        preview = ttk.Frame(right)
        preview.pack(side="top", fill="x", pady=4)
        self._kind_frame = ttk.Frame(preview)
        self._kind_frame.pack(side="top", fill="x")
        self._thumb = ttk.Label(preview)
        self._thumb.pack(side="top", pady=4)
        self._preview_msg = ttk.Label(preview, text="", foreground="#666666")
        self._preview_msg.pack(side="top")

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
        """Fold the current selection via the S7 orchestrator on a worker thread, shaped by the
        search-options row (stacks / decomps / find-example). `wait=True` pumps the tk loop until the
        result lands (scripted use). I/O: (float, bool) -> None."""
        if self.canvas is None or not self.canvas.is_valid_sheet():
            return
        cells = self.canvas.selected_cells()
        stacks = self._selected_stacks()
        decomps = self._selected_decomps()
        first = self._find_mode.get() == "example"
        self._pending = True
        self._fold_btn.config(state="disabled")
        self._cancel_btn.config(state="normal")
        self._set_status("folding %d cells%s…" % (len(cells), " (first example)" if first else ""))
        self.dispatch.start(self.tiling, cells, out_dir=self.out_dir, stacks=stacks, decomps=decomps,
                            first=first, timeout=timeout, on_done=self._result_q.put)
        self.root.after(150, self._poll_result)
        if wait:
            while self._pending:
                self.root.update()
                time.sleep(0.02)

    def _selected_stacks(self):
        """The checked stack counts, or None (search the grid-file default). I/O: () -> list[int]|None."""
        chosen = sorted(n for n, v in self._stacks_vars.items() if v.get())
        return chosen or None

    def _selected_decomps(self):
        """A single decomp restriction ("2+1"/"1+1+1") when exactly one box is checked, else None
        (search both -- the engine default). I/O: () -> str | None."""
        chosen = [name for name, v in self._decomp_vars.items() if v.get()]
        return chosen[0] if len(chosen) == 1 else None

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
            self._on_row(None)                          # clear any stale preview from a prior fold
            self._set_status("done: %d record(s)%s"
                             % (len(rows), " — unproven" if gate else ""))
        else:
            self._set_status("no fold (rc=%s): %s"
                             % (result.returncode, _failure_reason(result.output)))
        self._refresh_fold_btn()

    def _on_load(self):
        self.pick(self._tiling_var.get(), int(self._m.get()), int(self._n.get()))

    # ---- result viewer ----
    def _on_row(self, row):
        """Show the selected record's fold image (or a fallback). Rebuilds the image-kind picker from
        the record's own files. `row=None` clears the viewer. I/O: (dict|None) -> None."""
        self._preview_row = row
        for child in self._kind_frame.winfo_children():
            child.destroy()
        kinds = self._preview_kinds(row)
        if not kinds:
            self._preview_kind.set("")
            self._thumb.config(image="")
            self._thumb_ref = None
            self._preview_msg.config(
                text="" if row is None else "no image for this record")
            return
        if self._preview_kind.get() not in kinds:
            self._preview_kind.set(kinds[0])
        ttk = self._ttk
        for k in kinds:
            ttk.Radiobutton(self._kind_frame, text=k, value=k, variable=self._preview_kind,
                            command=self._show_preview).pack(side="left")
        self._show_preview()

    def _preview_kinds(self, row):
        """Every image kind available for `row` -- the preferred ones first, then any other non-json
        artifact -- so no engine's image is ever hidden. [] when there is no row / no image. I/O:
        (dict|None) -> list[str]."""
        if not row:
            return []
        files = row.get("files") or {}
        preferred = [k for k in results_mod._THUMB_ORDER if k in files]
        extras = sorted(k for k in files if k != "json" and k not in preferred)
        return preferred + extras

    def _show_preview(self):
        """Load the chosen image kind for the current row into the preview label. I/O: () -> None."""
        row, kind = self._preview_row, self._preview_kind.get()
        path = self._preview_path(row, kind)
        if not path or not os.path.isfile(path):
            self._thumb.config(image="")
            self._thumb_ref = None
            self._preview_msg.config(text="image file missing")
            return
        self._thumb_ref = thumbs.load(path, master=self.root, max_px=360)
        self._thumb.config(image=self._thumb_ref)
        self._preview_msg.config(text="")

    def _preview_path(self, row, kind):
        """Absolute path to `kind`'s image for `row`, resolved against the record's own directory (the
        picked `thumb` already sits in it), or None. I/O: (dict|None, str) -> str|None."""
        if not row or not kind:
            return None
        files = row.get("files") or {}
        if kind not in files:
            return None
        anchor = row.get("thumb")                       # <bundle>/<dir>/<some image> -> its dir
        if not anchor:
            return None
        return os.path.join(os.path.dirname(anchor), files[kind])

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
