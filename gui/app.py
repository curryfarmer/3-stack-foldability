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
import shutil
import sys
import tempfile
import time

from gui import canvas as canvas_mod
from gui import dispatch as dispatch_mod
from gui import geometry_client
from gui import results as results_mod
from gui import runsummary
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
        self._stacks = tk.IntVar(value=3)               # single stack count N (2-stack engine at 2,
                                                        # footprint engine at N>=3; N=4 oracle-validated)
        self._decomp_vars = {"2+1": tk.BooleanVar(value=True), "1+1+1": tk.BooleanVar(value=True)}
        self._find_mode = tk.StringVar(value="all")     # "all" | "example" (find-first)
        self._save_var = tk.BooleanVar(value=False)     # opt-in: persist results (else temp + discard)
        self._save_dir = tk.StringVar(value=self.out_dir)
        self._temp_dirs = []                            # unsaved-run scratch dirs to clean up
        self._preview_kind = tk.StringVar(value="")     # which image kind the viewer shows
        self._preview_row = None                        # the row currently in the viewer
        self._summary_var = tk.StringVar(value="")      # bottom-left post-run search-effort summary
        self._run_started = None                        # wall-clock start of the in-flight fold
        self._progress = None                           # activity bar (built in _build)
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

        # Row 2: search-shaping options (single stack count N + decomp + find-example = faster).
        opts = ttk.Frame(self.root)
        opts.pack(side="top", fill="x", padx=6, pady=(2, 6))
        ttk.Label(opts, text="stacks").pack(side="left")
        self._stacks_spin = ttk.Spinbox(opts, from_=2, to=8, width=3, textvariable=self._stacks)
        self._stacks_spin.pack(side="left")             # locked to 3 for triangle tilings (see pick)
        self._decomp_frame = ttk.Frame(opts)            # rebuilt per-(engine, N)
        self._decomp_frame.pack(side="left")
        ttk.Label(opts, text="  find:").pack(side="left")
        ttk.Radiobutton(opts, text="all", value="all", variable=self._find_mode).pack(side="left")
        ttk.Radiobutton(opts, text="example (fast)", value="example",
                        variable=self._find_mode).pack(side="left")
        self._stacks.trace_add("write", lambda *a: self._on_stacks_change())
        self._rebuild_decomp_row()

        # Row 3: opt-in result storage (default off -> temp dir, discarded after viewing).
        store = ttk.Frame(self.root)
        store.pack(side="top", fill="x", padx=6, pady=(0, 6))
        ttk.Checkbutton(store, text="Save results", variable=self._save_var).pack(side="left")
        ttk.Entry(store, textvariable=self._save_dir, width=40).pack(side="left", padx=4)
        ttk.Button(store, text="Browse…", command=self._on_browse).pack(side="left")

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
        self._thumb.bind("<Double-Button-1>", self._open_preview_popup)   # enlarge in a popup
        self._preview_msg = ttk.Label(preview, text="", foreground="#666666")
        self._preview_msg.pack(side="top")
        self._popup_img = None                          # keeps the enlarged image alive (Tk GC)

        # Bottom status bar. Bottom-LEFT: an indeterminate activity bar (so a running fold doesn't look
        # frozen) + a post-run search-effort summary ("explored: N · foldable: F · Ts"); the running
        # status message fills the rest. The fold runs on gui.dispatch's worker thread, so the Tk loop
        # stays live to animate the bar (and the scripted wait=True path pumps root.update()).
        statusbar = ttk.Frame(self.root)
        statusbar.pack(side="bottom", fill="x")
        self._progress = ttk.Progressbar(statusbar, mode="indeterminate", length=110)
        self._progress.pack(side="left", padx=(6, 6), pady=4)
        ttk.Label(statusbar, textvariable=self._summary_var, anchor="w",
                  foreground="#2c3e50").pack(side="left", padx=(0, 8))
        ttk.Label(statusbar, textvariable=self._status, anchor="w").pack(
            side="left", fill="x", expand=True, padx=6, pady=4)

    # ---- public / testable ----
    def pick(self, tiling, m, n):
        """Load a tiling's m x n ambient block into the canvas. I/O: (str, int, int) -> None."""
        self.tiling = tiling
        self._tiling_var.set(tiling)
        self._m.set(m)
        self._n.set(n)
        # Triangle engines are 3-stack / 1+1+1 only -> lock N to 3 so the size gate + dispatch use the
        # count the engine will actually run; square is n-stack capable (any N in 2..8).
        if tilings.engine(tiling) == "triangle":
            self._stacks.set(3)
            self._stacks_spin.config(state="disabled")
        else:
            self._stacks_spin.config(state="normal")
        self._rebuild_decomp_row()
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
        return (self.canvas is not None and self.canvas.is_valid_sheet()
                and not self._pending and self._size_ok())

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
        out_dir = self._resolve_out_dir()
        self._pending = True
        self._fold_btn.config(state="disabled")
        self._cancel_btn.config(state="normal")
        self._set_status("folding %d cells%s…" % (len(cells), " (first example)" if first else ""))
        self._summary_var.set("")
        self._run_started = time.time()
        self._progress.start(15)
        self.dispatch.start(self.tiling, cells, out_dir=out_dir, stacks=stacks, decomps=decomps,
                            first=first, timeout=timeout, on_done=self._result_q.put)
        self.root.after(150, self._poll_result)
        if wait:
            while self._pending:
                self.root.update()
                time.sleep(0.02)

    def _stacks_n(self):
        """The chosen stack count N (guards a mid-typed spinbox). I/O: () -> int."""
        try:
            return int(self._stacks.get())
        except (self._tk.TclError, ValueError):
            return 3

    def _selected_stacks(self):
        """The single chosen stack count as a one-element list. I/O: () -> list[int]."""
        return [self._stacks_n()]

    def _selected_decomps(self):
        """A single decomp restriction ("2+1"/"1+1+1") for N==3 when exactly one box is checked, else
        None. 2+1 is only defined for the square engine at N==3; the triangle engine is always 1+1+1
        (ignores decomps); N!=3 always searches the engine default (all-singleton). I/O: () -> str | None."""
        if self._engine() == "triangle" or self._stacks_n() != 3:
            return None
        chosen = [name for name, v in self._decomp_vars.items() if v.get()]
        return chosen[0] if len(chosen) == 1 else None

    def _engine(self):
        """The fold engine backing the current tiling ('square' | 'triangle'), defaulting to the
        dropdown selection before any grid is loaded. I/O: () -> str."""
        return tilings.engine(self.tiling or self._tiling_var.get())

    def _rebuild_decomp_row(self):
        """Populate the decomp frame for the current (engine, N): a static 1+1+1 label for triangle
        (engine is 1+1+1-only); for square: nothing at N==2 (no decomposition), both 2+1/1+1+1
        checkboxes at N==3, a static 1+…+1 label at N>=4. I/O: () -> None."""
        ttk = self._ttk
        for child in self._decomp_frame.winfo_children():
            child.destroy()
        if self._engine() == "triangle":
            ttk.Label(self._decomp_frame, text=" decomp 1+1+1").pack(side="left")
            return
        n = self._stacks_n()
        if n == 2:
            return
        ttk.Label(self._decomp_frame, text=" decomp").pack(side="left")
        if n == 3:
            for name, var in self._decomp_vars.items():
                ttk.Checkbutton(self._decomp_frame, text=name, variable=var).pack(side="left")
        else:
            ttk.Label(self._decomp_frame, text="1+…+1").pack(side="left")

    def _on_stacks_change(self):
        """React to a new stack count: rebuild the decomp row + re-evaluate the size gate. I/O: () -> None."""
        self._rebuild_decomp_row()
        self._refresh_fold_btn()

    def _on_browse(self):
        """Pick a save directory (turns Save on). I/O: () -> None."""
        from tkinter import filedialog
        d = filedialog.askdirectory(initialdir=self._save_dir.get() or os.getcwd())
        if d:
            self._save_dir.set(d)
            self._save_var.set(True)

    def _size_ok(self):
        """The drawn sheet has a foldable cell count for N: a positive multiple of N (== the engine's
        cells % panels == 0 and K >= 1 gate). I/O: () -> bool."""
        if self.canvas is None:
            return False
        n = self._stacks_n()
        c = len(self.canvas.selected_cells())
        return c >= n and c % n == 0

    def _resolve_out_dir(self):
        """Where THIS fold writes: the chosen dir when Save is on, else a fresh temp dir tracked for
        cleanup. Cleans any prior unsaved run first. I/O: () -> str."""
        self._cleanup_temp_dirs()
        if self._save_var.get():
            return os.path.abspath(self._save_dir.get().strip() or self.out_dir)
        d = tempfile.mkdtemp(prefix="foldgui_")
        self._temp_dirs.append(d)
        return d

    def _cleanup_temp_dirs(self):
        """Remove every tracked unsaved-run scratch dir. Never touches a user-chosen dir. I/O: () -> None."""
        for d in self._temp_dirs:
            shutil.rmtree(d, ignore_errors=True)
        self._temp_dirs = []

    def close(self):
        """Discard unsaved scratch dirs, then destroy the window. I/O: () -> None."""
        self._cleanup_temp_dirs()
        self.root.destroy()

    # ---- internals ----
    def _poll_result(self):
        try:
            result = self._result_q.get_nowait()
        except queue.Empty:
            self.root.after(150, self._poll_result)
            return
        self._pending = False
        self._cancel_btn.config(state="disabled")
        self._progress.stop()
        elapsed = time.time() - self._run_started if self._run_started else 0.0
        if result.bundle_path:
            rows, gate, diagnosis = results_mod.parse_bundle(result.bundle_path)
            self.results.show(rows, gate, diagnosis)
            self._on_row(None)                          # clear any stale preview from a prior fold
            # Search-effort summary, bottom-left: the engine's printed explored + candidate-tried
            # ("folds attempted") counts + the bundle's authoritative foldable-record count (see
            # gui.runsummary; coveredCount is now printed, so "attempted" is a real number here).
            n_fold = sum(1 for r in rows if r.get("foldable") is True)
            summary = runsummary.summarize(result.output, foldable=n_fold)
            self._summary_var.set(("%s · %.1fs" % (summary, elapsed)) if summary
                                  else "%.1fs" % elapsed)
            # On an EMPTY table, lead the status with the oracle's reason (why nothing folded, and
            # whether a real fold exists that the search can't reach) rather than a bare count.
            if not rows and diagnosis and diagnosis.get("message"):
                self._set_status("no fold: %s" % diagnosis["message"])
            else:
                self._set_status("done: %d record(s)%s%s"
                                 % (len(rows), " — unproven" if gate else "",
                                    "" if self._save_var.get() else " — not saved (temporary)"))
        else:
            self._summary_var.set("no fold · %.1fs" % elapsed)
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
            self._thumb.config(image="", cursor="")
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
            self._thumb.config(image="", cursor="")
            self._thumb_ref = None
            self._preview_msg.config(text="image file missing")
            return
        self._thumb_ref = thumbs.load(path, master=self.root, max_px=360)
        self._thumb.config(image=self._thumb_ref, cursor="hand2")   # clickable -> popup
        self._preview_msg.config(text="double-click image to enlarge")

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

    def _open_preview_popup(self, event=None):
        """Double-click handler: open the selected record's current image in a large, resizable popup
        centred on the screen (~90% of the smaller screen dimension). thumbs.load only downscales, so a
        smaller PNG shows at full native resolution rather than a blurry upscale. Each popup pins its own
        image on the Toplevel (Tk GCs an image with no live reference), so several can be open at once.
        Returns the Toplevel (None when the row has no image) so it is assertable headless.
        I/O: (tk event|None) -> tk.Toplevel|None."""
        path = self._preview_path(self._preview_row, self._preview_kind.get())
        if not path or not os.path.isfile(path):
            return None
        tk, ttk = self._tk, self._ttk
        top = tk.Toplevel(self.root)
        top.transient(self.root)
        top.title(os.path.basename(path))
        big = int(min(self.root.winfo_screenwidth(), self.root.winfo_screenheight()) * 0.9)
        img = thumbs.load(path, master=top, max_px=max(big, 360))
        top._img_ref = img                              # per-window ref (survives multiple popups)
        self._popup_img = img                           # last-opened, for headless assertions
        lbl = ttk.Label(top, image=img)
        lbl.pack(fill="both", expand=True)
        lbl.bind("<Double-Button-1>", lambda e: top.destroy())   # double-click again to close
        top.bind("<Escape>", lambda e: top.destroy())
        top.update_idletasks()                          # realise geometry before centring
        w, h = top.winfo_width(), top.winfo_height()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        top.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
        return top

    def _refresh_fold_btn(self):
        self._fold_btn.config(state="normal" if self.fold_enabled else "disabled")
        self._size_hint()

    def _size_hint(self):
        """When a connected sheet has the wrong cell count for N, say so (front-runs the engine's
        divisibility reject with instant feedback). I/O: () -> None."""
        if self.canvas is None or self._pending or not self.canvas.is_valid_sheet():
            return
        if not self._size_ok():
            n = self._stacks_n()
            c = len(self.canvas.selected_cells())
            mults = ", ".join(str(n * k) for k in (1, 2, 3))
            self._set_status("N=%d needs a sheet of %s, … cells (got %d)" % (n, mults, c))

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
    app = App(root, out_dir=args.out)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
