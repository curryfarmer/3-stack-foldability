"""config.py — GUI palette + sizing, as LITERALS mirrored from the report style spec.

Deliberately does NOT import square/render/figstyle.py: that module runs matplotlib.use("Agg") and
apply_style() at import, which would fight the TkAgg backend the S9 shell needs. The few values the
headless half cares about are copied here as plain constants; the full render palette waits for S9.

Anchor colors (INK / GRID_EDGE / CHAIN[0] / DPI) are kept byte-identical to figstyle.py so a future
GUI render matches the report figures.
"""

# --- mirrored from square/render/figstyle.py (keep in sync) ---
INK = "#222222"           # text / near-black borders
GRID_EDGE = "#dddddd"     # unselected cell outline (light grey)
ACCENT = "#1f77b4"        # figstyle CHAIN[0] blue -- the selection accent
DPI = 150                 # one dpi for the whole track

# --- GUI-only selection state colors ---
CELL_FILL = "#ffffff"     # unselected tile interior
SELECTED_FILL = "#c6d5f2" # a selected tile (figstyle PARITY_BLUE tint)
SELECTED_EDGE = ACCENT    # selected tile outline
INVALID_EDGE = "#c0392b"  # a selection that is not a single connected sheet (figstyle JAM red)
