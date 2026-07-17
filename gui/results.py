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

_THUMB_ORDER = ("foldsheet", "overlay", "twist", "reflect")   # preferred preview, best first


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
    verdict, dir, files, thumb}; thumb is resolved against the bundle's own directory. I/O:
    (str) -> (list[dict], bool)."""
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
            "dir": rec_dir,
            "files": files,
            "thumb": _pick_thumb(bundle_dir, rec_dir, files),
        })
    return rows, bool(bundle.get("gateValidityUnproven", False))


class ResultsView:
    """A ttk verdict table + unproven badge. Lazy-imports tkinter so parse_bundle stays display-free."""

    _COLS = ("uid", "stacks", "foldable", "proven")

    def __init__(self, parent, on_select=None):
        import tkinter as tk                    # noqa: F401  (lazy: keep parse-only imports light)
        from tkinter import ttk

        self._on_select = on_select
        self._rows = []
        self.badge_visible = False

        self.frame = ttk.Frame(parent)
        self._badge = ttk.Label(self.frame, text="", foreground="#c0392b")
        self._badge.pack(anchor="w", padx=4, pady=(4, 0))
        self.tree = ttk.Treeview(self.frame, columns=self._COLS, show="headings", height=8)
        for c in self._COLS:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=110, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def show(self, rows, gate_unproven):
        """Populate the table + badge. I/O: (list[dict], bool) -> None."""
        self._rows = rows
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(rows):
            self.tree.insert("", "end", iid=str(i),
                             values=(r["uid"], r["stacks"], r["foldable"], r["proven"]))
        self.badge_visible = bool(gate_unproven)
        self._badge.config(
            text="unproven — exploratory heuristic; physical fold is ground truth"
            if self.badge_visible else "")

    def rows(self):
        return self._rows

    def _on_tree_select(self, _evt):
        sel = self.tree.selection()
        if sel and self._on_select:
            self._on_select(self._rows[int(sel[0])])
