"""results.py — read an S7 fold-bundle/1 into a verdict table + proven/unproven badge.

parse_bundle is pure (os + json only) so it unit-tests off a fixture bundle with no display. The
ResultsView ttk widget lazy-imports tkinter (like gui/canvas) so importing gui.results for parsing
alone stays light.

The unproven badge reads the explicit `gateValidityUnproven` boolean + per-record `proven` boolean
that S7 stamps -- NEVER string-sniffs a verdict. The per-record `files` dict is disk-scanned by S7
and authoritative: square records lack overlay/reflect, triangle-equilateral lacks reflect, so the
thumbnail picker prefers a known-visual key but falls back to whatever the record actually has.
"""
import json
import os

from gui import foldfilter

# Preferred preview image, best-first. Covers BOTH engines: triangle emits foldsheet/overlay/reflect,
# square emits `schematic` (its primary fold image) -- omitting schematic used to make a square fold
# preview default to the less-intuitive twist diagram (or nothing).
_THUMB_ORDER = ("foldsheet", "schematic", "overlay", "twist", "reflect")


def _pick_thumb(bundle_dir, rec_dir, files):
    """Absolute path to the best preview image for a record, or None. `files` maps kind -> basename;
    prefer a visual key, else any non-json artifact. I/O: (str, str, dict) -> str|None."""
    key = next((k for k in _THUMB_ORDER if k in files), None)
    if key is None:
        key = next((k for k in files if k != "json"), None)
    if key is None:
        return None
    return os.path.join(bundle_dir, rec_dir, files[key])


def parse_bundle(bundle_path):
    """Read a fold-bundle/1 into (rows, gate_unproven). Each row = {uid, stacks, foldable, proven,
    verdict, decomp, vector, dir, files, thumb}; decomp/vector are the normalized filter keys
    fold_grid stamps (decomp None + vector None for records lacking them); thumb is resolved against
    the bundle's own directory. I/O: (str) -> (list[dict], bool)."""
    with open(bundle_path, encoding="utf-8") as f:
        bundle = json.load(f)
    bundle_dir = os.path.dirname(os.path.abspath(bundle_path))
    rows = []
    for rec in bundle.get("records", []):
        files = rec.get("files", {}) or {}
        rec_dir = rec.get("dir", rec.get("uid", ""))
        rows.append({
            "uid": rec.get("uid"),
            "stacks": rec.get("stacks"),
            "foldable": rec.get("foldable"),
            "proven": rec.get("proven"),
            "verdict": rec.get("verdict"),
            "decomp": rec.get("decomp"),        # normalized "2+1"/"1+1+1"/None (fold_grid enriches)
            "vector": rec.get("vector"),        # per-gate dict / None -> foldability-vector filter
            "dir": rec_dir,
            "files": files,
            "thumb": _pick_thumb(bundle_dir, rec_dir, files),
        })
    return rows, bool(bundle.get("gateValidityUnproven", False))


class ResultsView:
    """A ttk verdict table + a live filter bar + unproven badge. Lazy-imports tkinter so parse_bundle
    stays display-free. The table shows the subset of the last `show(rows)` matching the filter bar; a
    row click hands the ORIGINAL row dict back to `on_select`. Filtering is delegated to the pure
    gui.foldfilter (shared with the headless CLI), so the two front-ends filter identically."""

    _COLS = ("uid", "stacks", "decomp", "foldable", "proven", "gates")
    _COL_WIDTH = {"uid": 100, "stacks": 50, "decomp": 60, "foldable": 60, "proven": 55, "gates": 150}
    _VECTOR_COMPONENTS = (("exit", "exitFootprint"), ("parity", "parity"),
                          ("refl", "reflection"), ("twist", "twist"))

    def __init__(self, parent, on_select=None):
        import tkinter as tk
        from tkinter import ttk

        self._tk, self._ttk = tk, ttk
        self._on_select = on_select
        self._rows = []          # every row from the last show()
        self._shown = []         # the filtered subset currently in the tree (iid = index here)
        self.badge_visible = False

        self.frame = ttk.Frame(parent)
        self._build_filter_bar()
        self._count = ttk.Label(self.frame, text="")
        self._count.pack(anchor="w", padx=4)
        self._badge = ttk.Label(self.frame, text="", foreground="#c0392b")
        self._badge.pack(anchor="w", padx=4, pady=(2, 0))
        self.tree = ttk.Treeview(self.frame, columns=self._COLS, show="headings", height=8)
        for c in self._COLS:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=self._COL_WIDTH[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    # ---- filter bar ----
    def _build_filter_bar(self):
        """Only the post-fold-only dimensions live here (foldable + gate vector). Stacks/decomp are
        pre-fold search shapers owned by the top bar (gui/app.py); duplicating them here as display
        filters was confusing, so they were removed."""
        tk, ttk = self._tk, self._ttk
        bar = ttk.Frame(self.frame)
        bar.pack(side="top", fill="x", padx=4, pady=(4, 0))

        # Default to foldable-only: a jam is a candidate that cleared exit+parity+reflection but whose
        # end footprint does NOT coincide (twist-fail), so its schematic reads as "footprints don't
        # match". Hiding them by default means every row on first view is a genuine, matching fold;
        # flip this tristate to "any"/"no" to inspect the jams.
        self._foldable_var = tk.StringVar(value="yes")
        self._vector_vars = {key: tk.StringVar(value="any") for _lbl, key in self._VECTOR_COMPONENTS}

        ttk.Label(bar, text="foldable").pack(side="left")
        self._tristate_menu(bar, self._foldable_var, ("any", "yes", "no"))

        bar2 = ttk.Frame(self.frame)
        bar2.pack(side="top", fill="x", padx=4)
        ttk.Label(bar2, text="gate").pack(side="left")
        for lbl, key in self._VECTOR_COMPONENTS:
            ttk.Label(bar2, text=" %s" % lbl).pack(side="left")
            self._tristate_menu(bar2, self._vector_vars[key], ("any", "✓", "✗"))

    def _tristate_menu(self, parent, var, values):
        """A compact ttk.OptionMenu bound to `var` that re-renders on any pick. I/O: (widget, StringVar,
        tuple[str]) -> None."""
        ttk = self._ttk
        menu = ttk.OptionMenu(parent, var, var.get(), *values, command=lambda _v: self._render())
        menu.pack(side="left")

    def _active_filters(self):
        """Read the filter bar into foldfilter.apply kwargs (foldable + gate vector only -- stacks/
        decomp are shaped pre-fold in the top bar). I/O: () -> dict."""
        require_vector = {}
        for _lbl, key in self._VECTOR_COMPONENTS:
            val = self._vector_vars[key].get()
            if val == "✓":
                require_vector[key] = True
            elif val == "✗":
                require_vector[key] = False
        foldable = {"any": None, "yes": True, "no": False}[self._foldable_var.get()]
        return {"require_vector": require_vector or None, "foldable": foldable}

    # ---- populate ----
    def show(self, rows, gate_unproven):
        """Store the full row set + badge, then render through the current filter. I/O:
        (list[dict], bool) -> None."""
        self._rows = rows
        self.badge_visible = bool(gate_unproven)
        self._badge.config(
            text="unproven — exploratory heuristic; physical fold is ground truth"
            if self.badge_visible else "")
        self._render()

    def _render(self):
        """Re-filter self._rows through the bar and repopulate the tree. I/O: () -> None."""
        self._shown = foldfilter.apply(self._rows, **self._active_filters())
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self._shown):
            self.tree.insert("", "end", iid=str(i), values=(
                r.get("uid"), r.get("stacks"), r.get("decomp") or "—",
                r.get("foldable"), r.get("proven"), foldfilter.vector_summary(r.get("vector"))))
        total = len(self._rows)
        shown = len(self._shown)
        if total == 0:
            self._count.config(text="0 records — nothing folded")
        elif shown == total:
            self._count.config(text="%d record(s) — click one to preview" % total)
        else:
            self._count.config(text="%d of %d record(s) (filtered) — click one to preview"
                               % (shown, total))

    def rows(self):
        return self._rows

    def _on_tree_select(self, _evt):
        sel = self.tree.selection()
        if sel and self._on_select:
            self._on_select(self._shown[int(sel[0])])
