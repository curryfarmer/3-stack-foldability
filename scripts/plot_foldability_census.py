"""plot_foldability_census.py -- report figures for the "2+1 stays rare, 1+1+1 explodes" finding.

Reads the store-all census summaries on disk (results/census/*.summary.json) -- so the figures are
regenerable and never drift from the numbers -- and emits four PNGs into report/tri/foldability/:

  1. headline_righttri.png   -- right-isoceles 1+1+1 vs 2+1 on one axis (the cleanest contrast).
  2. foldable_vs_k.png        -- 2x2 small multiples, foldable count vs K, all four tilings.
  3. twoloop_violators.png    -- 2-loop-reduction violators vs K (closing 1+1+1 with a (0,0,x!=0) triple).
  4. count_vs_nt_righttri.png -- grouped log bars, "why 2+1 is rare and 1+1+1 is common".

Figure 4 used to live in square/render/report_examples.py with its counts TYPED IN as module
constants (RIGHTTRI_2P1 / RIGHTTRI_111) -- a triangle figure, in the square package, disconnected
from the census. Those literals had already drifted from the data they claimed to show. It is
data-driven here so it cannot drift again.

COUNTS ARE SWEEP-DEPENDENT, NOT INTRINSIC. A 2+1 cell's count scales with how many start hubs were
enumerated (census.py --hubs; righttri has 8 hub classes and the original census swept 8 hubs
covering only 4 of them), and a 1+1+1 cell is a SINGLE ambient hub variant (righttri LL vs HL,
build_ambient_right) -- so the two series are not sampled alike. Whatever `hubs` provenance the
summaries carry is stamped onto the figures; cells written before that field existed report "?".
Read the y values as "folds found under this sweep", never as "the number of folds".

Only K values present for BOTH decomps are plotted in figure 4: 1+1+1 is censused at even K only
(census.py even_111), and drawing a bar at an uncomputed K would render "not searched" as "zero".

Run:  .\.venv\Scripts\python.exe scripts\plot_foldability_census.py
      python scripts\plot_foldability_census.py --census-dir results\census_hubs20
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "triangle", "tri"))
import tristyle as TS   # noqa: E402  (palette + save + shared rcParams; stdlib+matplotlib only)
from matplotlib.lines import Line2D   # noqa: E402

CENSUS = os.path.join(REPO, "results", "census")
OUT = os.path.join(REPO, "report", "tri", "foldability")
REPORT_FIGS = os.path.join(REPO, "report", "figures")     # the slots report/draft.md embeds

C111, C21 = TS.CHAIN[0], TS.CHAIN[1]            # blue = 1+1+1, orange = 2+1 (house palette)
TILE_ORDER = ["equilateral", "righttri", "scalene", "hex"]
TILE_LABEL = {"equilateral": "Equilateral △", "righttri": "Right-isoceles ◺",
              "scalene": "Scalene ▹", "hex": "Hexagonal ⬢"}
# distinct line colour per tiling for the violator figure (house CHAIN + two semantic hexes)
TCOLOR = {"equilateral": TS.MUTED, "righttri": TS.CHAIN[0], "scalene": TS.CHAIN[2],
          "hex": TS.FOOTPRINT_EDGE}


def _viol_from_spectrum(spec):
    """Count closing candidates whose twist triple has exactly two 0s and one nonzero -- the
    two-loops-pass-third-fails population that kills the 2-loop reduction."""
    n = 0
    for key, cnt in spec.items():
        t = [int(x) for x in key.strip("()").split(",")]
        if sum(1 for x in t if x == 0) == 2:
            n += cnt
    return n


def load(census_dir=None):
    """<census_dir>/*.summary.json -> (data, prov).

    data[(tiling, decomp)][K] = (closing, foldable, viol, trunc, distinct, distinct_flat)
    prov[(tiling, decomp)]    = set of `hubs` values seen ({None} for cells written before the
                                field existed) -- the sweep width behind those counts.

    `closing`/`foldable` are PLACEMENT counts: every candidate every start hub yielded, with
    congruent folds at different positions counted separately. They grow with the sweep width even
    when no new shape appears, so they are not reproducible. `distinct`/`distinct_flat` are
    congruence classes, stamped in by triangle.tri.census_distinct; they fall back to the placement
    counts on summaries written before that pass existed, so an un-deduped census still plots (and
    _sweep_footer says which it was).
    I/O: (census_dir | None -> results/census) -> (data, prov)."""
    data, prov = {}, {}
    for p in glob.glob(os.path.join(census_dir or CENSUS, "*.summary.json")):
        with open(p) as fh:
            d = json.load(fh)
        key = (d["tiling"], d["decomp"])
        viol = _viol_from_spectrum(d.get("spectrum", {})) if d["decomp"] == "1plus1plus1" else None
        data.setdefault(key, {})[d["K"]] = (d["closing"], d["tw0"], viol, bool(d["truncated"]),
                                            d.get("distinct"), d.get("distinct_tw0"))
        variants = d.get("hub_variants")
        prov.setdefault(key, set()).add((d.get("hubs"),
                                         len(variants) if variants else None))
    return data, prov


def _flat(cell, K):
    """The flat-fold count to PLOT at this K: distinct shapes when the census has been deduped,
    otherwise the raw placement count. Never mix the two silently in one series -- see _deduped."""
    rec = cell[K]
    return rec[1] if len(rec) < 6 or rec[5] is None else rec[5]


def _deduped(cell):
    """True iff every K in this series carries a distinct count (so the series is shapes, not
    placements). A partially-deduped census would otherwise draw two different quantities on one
    axis and label them the same."""
    return bool(cell) and all(len(r) >= 6 and r[5] is not None for r in cell.values())


def _sweep_note(prov, key):
    """One-line human description of how wide the sweep behind a series was.
    I/O: (prov, (tiling, decomp)) -> str, e.g. "20 hubs" / "8 hubs" / "hubs ?"."""
    seen = {h for (h, _) in prov.get(key, ()) if h is not None}
    if not seen:
        return "hubs ?"                      # pre-provenance census -- unknowable from the file
    if len(seen) == 1:
        return "%d hub%s" % (next(iter(seen)), "" if next(iter(seen)) == 1 else "s")
    return "hubs " + "/".join(str(h) for h in sorted(seen))   # mixed sweep widths: say so


def _series(cell):
    """sorted (Ks, foldable, truncated-flags) for a decomp cell."""
    ks = sorted(cell)
    return ks, [cell[k][1] for k in ks], [cell[k][3] for k in ks]


def _draw_series(ax, ks, ys, trunc, color, label):
    """Line + solid markers for exhaustive points, open markers for truncated ones."""
    ax.plot(ks, ys, "-", color=color, lw=2, label=label, zorder=3)
    sx = [k for k, t in zip(ks, trunc) if not t]
    sy = [y for y, t in zip(ys, trunc) if not t]
    tx = [k for k, t in zip(ks, trunc) if t]
    ty = [y for y, t in zip(ys, trunc) if t]
    ax.plot(sx, sy, "o", color=color, ms=5, zorder=4)
    ax.plot(tx, ty, "o", mfc="white", mec=color, mew=1.6, ms=6, zorder=4)


def _symlog(ax, ymax):
    ax.set_yscale("symlog", linthresh=1)
    ax.set_ylim(-0.4, ymax)
    ax.set_yticks([0, 1, 10, 100, 1000, 10000, 100000])
    ax.set_yticklabels(["0", "1", "10", "100", "1k", "10k", "100k"])
    ax.grid(True, which="major", axis="y", color=TS.GRID_EDGE, lw=0.8, zorder=0)
    ax.axhline(0, color=TS.INK, lw=0.8, zorder=1)
    ax.set_axisbelow(True)


def _nocompute_band(ax):
    """Faint shade over K=19-20: requested but not computed (honest frontier marker)."""
    ax.axvspan(18.4, 20, color=TS.MUTED, alpha=0.06, zorder=0, lw=0)
    ax.text(19.2, ax.get_ylim()[1], "K19–20\nnot computed", ha="center", va="top",
            fontsize=6.5, color=TS.MUTED, linespacing=1.1)


def _sweep_footer(fig, prov, tiling="righttri", shapes=False, y=0.005):
    """Stamp the sweep width onto the figure. A raw count is "folds found by THIS sweep" -- a 2+1
    cell scales with --hubs -- so a figure that does not carry its sweep is not reproducible.
    Deduped bars are reproducible, but only above the saturation width, which is why the hub count
    is still stamped when `shapes` is true.

    `tiling` may be several, for a figure covering more than one. They do NOT always agree -- the
    1+1+1 ambient sweep is 2 variants on righttri and 3 on scalene -- so the note reports the range
    rather than one panel's number standing in for the sheet.
    I/O: (fig, prov, str|seq, shapes) -> None."""
    tilings = [tiling] if isinstance(tiling, str) else list(tiling)
    n21 = " / ".join(sorted({_sweep_note(prov, (t, "2plus1")) for t in tilings}))
    # Derived, never asserted: how many ambient variants the 1+1+1 cells actually swept. A census
    # written before that field existed says so rather than claiming coverage it may not have had.
    vs = {v for t in tilings for (_, v) in prov.get((t, "1plus1plus1"), ()) if v is not None}
    if not vs:
        n111 = "variants ?"
    elif len(vs) == 1:
        n = vs.pop()
        n111 = "%d ambient variant%s" % (n, "" if n == 1 else "s")
    else:
        n111 = "%d–%d ambient variants" % (min(vs), max(vs))
    note = "sweep: 2+1 %s · 1+1+1 %s" % (n21, n111)
    note += ("  ·  bars are congruence classes (sweep-independent above saturation)" if shapes
             else "  ·  bars are placements, NOT deduped (scale with the sweep)")
    fig.text(0.995, y, note, ha="right", va="bottom", fontsize=6, color=TS.MUTED, style="italic")


def fig_headline(data, prov=None):
    """Right-isoceles 1+1+1 vs 2+1 on one axis -- the report's lead figure."""
    plt = TS.plt
    prov = prov or {}
    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    k1, y1, t1 = _series(data[("righttri", "1plus1plus1")])
    k2, y2, t2 = _series(data[("righttri", "2plus1")])
    _symlog(ax, 60000)
    _draw_series(ax, k1, y1, t1, C111, "1+1+1  (three free panels)")
    _draw_series(ax, k2, y2, t2, C21, "2+1  (two panels fused)")
    ax.set_xlim(3, 20)
    ax.set_xticks(range(4, 21, 2))
    _nocompute_band(ax)
    ax.set_xlabel("sheet size  K  (tiles per chain)")
    ax.set_ylabel("flat-folds found  (exhaustive)")
    ax.set_title("Right-isoceles: fusing two panels caps the fold; three free panels explode")
    # annotate the two regimes -- the growth run is READ OFF the series, never typed in (the
    # previous hardcoded "40 -> 953 -> 18,936" is exactly how a caption drifts from its data)
    grew = [(k, y) for k, y in zip(k1, y1) if y > 0][-3:]
    if grew:
        kmax, ymax = grew[-1]
        ax.annotate("explodes\n" + " → ".join("{:,}".format(y) for _, y in grew),
                    xy=(kmax, ymax), xytext=(kmax - 3.8, 30000),
                    fontsize=8, color=C111, fontweight="bold", ha="center",
                    arrowprops=dict(arrowstyle="->", color=C111, lw=1.2))
    cap = [(k, y) for k, y in zip(k2, y2) if y > 0]
    if cap:
        kcap, ycap = cap[-1]
        ax.annotate("capped at a few, then 0", xy=(kcap, ycap), xytext=(kcap + 1.6, 0.25),
                    fontsize=8, color=C21, fontweight="bold", ha="left",
                    arrowprops=dict(arrowstyle="->", color=C21, lw=1.2))
    ax.legend(loc="upper left", fontsize=8)
    _sweep_footer(fig, prov)
    return TS.save(fig, os.path.join(OUT, "headline_righttri.png"))


def fig_smallmultiples(data):
    """2x2 foldable-count vs K, one panel per tiling."""
    plt = TS.plt
    fig, axes = plt.subplots(2, 2, figsize=(8.2, 5.8), sharex=True)
    for ax, tiling in zip(axes.flat, TILE_ORDER):
        _symlog(ax, 60000)
        for decomp, col, lab in [("1plus1plus1", C111, "1+1+1"), ("2plus1", C21, "2+1")]:
            cell = data.get((tiling, decomp))
            if cell:
                ks, ys, tr = _series(cell)
                _draw_series(ax, ks, ys, tr, col, lab)
        ax.set_xlim(3, 20)
        ax.set_xticks(range(4, 21, 4))
        _nocompute_band(ax)
        ax.set_title(TILE_LABEL[tiling], fontsize=10)
    for ax in axes[-1]:
        ax.set_xlabel("sheet size  K")
    for ax in axes[:, 0]:
        ax.set_ylabel("flat-folds found")
    handles = [Line2D([], [], color=C111, marker="o", lw=2, label="1+1+1  (three free panels)"),
               Line2D([], [], color=C21, marker="o", lw=2, label="2+1  (two panels fused)"),
               Line2D([], [], color=TS.INK, marker="o", mfc="white", lw=0, label="truncated (cap hit)")]
    fig.legend(handles=handles, loc="upper center", ncol=3, fontsize=8, bbox_to_anchor=(0.5, 1.02))
    fig.suptitle("Flat-folds found vs. sheet size, all tilings  (log scale; 0 = searched, none found)",
                 y=1.06, fontsize=10, fontweight="bold")
    return TS.save(fig, os.path.join(OUT, "foldable_vs_k.png"))


def fig_violators(data):
    """2-loop-reduction violators vs K -- closing 1+1+1 with a (0,0,x!=0) triple."""
    plt = TS.plt
    fig, ax = plt.subplots(figsize=(6.8, 4.1))
    _symlog(ax, 120000)
    for tiling in TILE_ORDER:
        cell = data.get((tiling, "1plus1plus1"))
        if not cell:
            continue
        ks = sorted(cell)
        vs = [cell[k][2] or 0 for k in ks]
        tr = [cell[k][3] for k in ks]
        col = TCOLOR[tiling]
        flat = all(v == 0 for v in vs)
        ax.plot(ks, vs, "-" if not flat else "--", color=col, lw=2,
                alpha=1.0 if not flat else 0.55,
                label=TILE_LABEL[tiling] + (" (none)" if flat else ""), zorder=3)
        sx = [k for k, t in zip(ks, tr) if not t]
        sy = [v for v, t in zip(vs, tr) if not t]
        tx = [k for k, t in zip(ks, tr) if t]
        ty = [v for v, t in zip(vs, tr) if t]
        ax.plot(sx, sy, "o", color=col, ms=5, zorder=4)
        ax.plot(tx, ty, "o", mfc="white", mec=col, mew=1.6, ms=6, zorder=4)
    ax.set_xlim(3, 20)
    ax.set_xticks(range(4, 21, 2))
    _nocompute_band(ax)
    ax.set_xlabel("sheet size  K")
    ax.set_ylabel("closing folds with  Tw = (0, 0, x≠0)")
    ax.set_title("The 2-loop shortcut is refuted: two loops vanish, the third does not")
    ax.annotate("(0, 0, −573)\nrighttri K12", xy=(12, 8), xytext=(9.2, 200),
                fontsize=7.5, color=TCOLOR["righttri"], ha="center",
                arrowprops=dict(arrowstyle="->", color=TCOLOR["righttri"], lw=1))
    ax.text(4.2, 0.13, "equilateral ≡ 0  (like the square grids)", fontsize=7.5,
            color=TS.MUTED, style="italic")
    ax.legend(loc="upper left", fontsize=7.5)
    return TS.save(fig, os.path.join(OUT, "twoloop_violators.png"))


def _draw_count_vs_nt(ax, data, tiling, ymax=None):
    """Draw the grouped log bars for one tiling onto `ax`; return (shapes, dropped, peak).

    Split out of fig_count_vs_nt so the single-tiling figure and the side-by-side pair draw from
    ONE routine -- two copies of this would be two chances for the panels to disagree."""
    import numpy as np
    cell21 = data.get((tiling, "2plus1"), {})
    cell111 = data.get((tiling, "1plus1plus1"), {})
    # BOTH-or-neither: 1+1+1 is censused at even K only, so a bar at a K it never searched would
    # draw "not computed" as a confident zero.
    nts = sorted(set(cell21) & set(cell111))
    dropped = sorted((set(cell21) | set(cell111)) - set(nts))
    if not nts:
        raise SystemExit("no K is present for both decomps of %s -- nothing to plot" % tiling)

    y21 = [_flat(cell21, k) for k in nts]
    y111 = [_flat(cell111, k) for k in nts]
    shapes = _deduped(cell21) and _deduped(cell111)
    x = np.arange(len(nts))
    w = 0.38

    def plot_bars(ys, offset, color, label):
        ax.bar(x + offset, [y if y > 0 else 0.0 for y in ys], w, color=color, label=label, zorder=3)
        for xi, h in zip(x + offset, ys):
            if h == 0:
                ax.text(xi, 1.15, "0", ha="center", va="bottom", fontsize=8, color=color)
            else:
                ax.text(xi, h * 1.08, str(h), ha="center", va="bottom", fontsize=8,
                        color=color, fontweight="bold")

    # legend claims are COMPUTED, so they cannot contradict the bars they label
    nz21 = [k for k, y in zip(nts, y21) if y > 0]
    cap = ("caps ≤ N_t = %d" % max(nz21)) if nz21 else "none found"
    nz111 = [(k, y) for k, y in zip(nts, y111) if y > 0]
    if len(nz111) >= 2:
        ratios = [b / a for (_, a), (_, b) in zip(nz111, nz111[1:]) if a]
        steps = [kb - ka for (ka, _), (kb, _) in zip(nz111, nz111[1:])]
        grow = "grows ~%.0f× per +%d" % (sum(ratios) / len(ratios), steps[0] if steps else 2)
    else:
        grow = "onset at N_t = %d" % nz111[0][0] if nz111 else "none found"

    plot_bars(y21, -w / 2, TS.CHAIN[0], "2+1  (bounded, %s)" % cap)
    plot_bars(y111, w / 2, TS.CHAIN[2], "1+1+1  (%s)" % grow)
    ax.set_yscale("log")
    ax.set_ylim(0.8, ymax or max(60000, max(y111 + y21) * 3))
    ax.set_xticks(x)
    ax.set_xticklabels([str(k) for k in nts])
    ax.set_xlabel("sub-chain length  N_t  (%s tiling)" % TILE_LABEL.get(tiling, tiling))
    # A placement count is a fact about the sweep as much as about the tiling; a shape count is not.
    # Say which one the bars are, so the axis cannot be read as the other.
    ax.set_ylabel("distinct flat (Tw = 0) folds  [log]" if shapes
                  else "flat (Tw = 0) folds found by this sweep  [log]")
    ax.legend(loc="upper left", fontsize=8, frameon=True)
    ax.grid(axis="y", which="both", color=TS.GRID_EDGE, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    return shapes, dropped, max(y111 + y21)


def fig_count_vs_nt(data, prov=None, tiling="righttri", out_path=None):
    """Grouped log bars: flat-fold count vs N_t, 2+1 against 1+1+1.

    Formerly square/render/report_examples.py:census_count_vs_nt, where the counts were typed in as
    module constants and had already drifted from the census. Everything here -- bar heights, the
    cap, the growth factor in the legend -- is derived from the summaries."""
    plt = TS.plt
    prov = prov or {}
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    shapes, dropped, _ = _draw_count_vs_nt(ax, data, tiling)
    ax.set_title("Why 2+1 is rare and 1+1+1 is common", fontsize=11, fontweight="bold")
    # Two separate bottom lines: the omitted-K list is long enough to run under a right-aligned
    # footer set at the same height, and the two overlapping renders as one unreadable smear.
    if dropped:
        ax.text(0.005, 0.005, "K not searched for both decomps, omitted: %s"
                % ", ".join(str(k) for k in dropped),
                transform=fig.transFigure, fontsize=6, color=TS.MUTED, style="italic")
    _sweep_footer(fig, prov, tiling, shapes, y=0.030)
    fig.tight_layout(rect=[0, 0.055, 1, 1])
    return TS.save(fig, out_path or os.path.join(OUT, "count_vs_nt_%s.png" % tiling))


def _table_rows(data, tiling):
    """Per-K `closing / flat-shapes` rows for one tiling, as (header, row21, row111) text lists."""
    cell21 = data.get((tiling, "2plus1"), {})
    cell111 = data.get((tiling, "1plus1plus1"), {})
    ks = sorted(set(cell21) | set(cell111))
    # Only the K where SOMETHING happens, else the row is a wall of 0/0 that hides the signal.
    ks = [k for k in ks if (cell21.get(k) or [0])[0] or (cell111.get(k) or [0])[0]]

    def num(n):
        # Six-figure closing counts blow the column width out at any readable font size. Abbreviate
        # only past 10 000, where the exact digit is not what the row is for -- the small counts,
        # which ARE the finding, stay exact.
        return str(n) if n < 10000 else ("%.0fk" % (n / 1000.0) if n >= 100000
                                         else "%.1fk" % (n / 1000.0))

    def cell(c, k):
        if k not in c:
            return "–"                       # not searched -- distinct from a searched zero
        closing = c[k][0]
        return "%s/%s" % (num(closing), num(_flat(c, k))) if closing else "0"

    return (["N_t"] + [str(k) for k in ks],
            ["2+1"] + [cell(cell21, k) for k in ks],
            ["1+1+1"] + [cell(cell111, k) for k in ks])


def fig_count_vs_nt_pair(data, prov=None, tilings=("righttri", "scalene"), out_path=None):
    """The two both-decomposition tilings side by side, over their census tables.

    One sheet rather than two figures: the finding is that the SAME shape appears on two different
    tilings, and that is only visible when they share an axis scale. Both panels are drawn by
    _draw_count_vs_nt with a common ymax so the bar heights are directly comparable."""
    plt = TS.plt
    prov = prov or {}
    fig = plt.figure(figsize=(13.0, 6.9))
    # No tight_layout below: a table Axes has no tight-layout geometry, and letting it run both
    # warns and shoves the panels around. The margins here are set once, explicitly.
    gs = fig.add_gridspec(2, len(tilings), height_ratios=[4.0, 1.0], hspace=0.34, wspace=0.12,
                          left=0.055, right=0.985, top=0.855, bottom=0.075)

    peak = max(max(_flat(data.get((t, d), {}), k) for d in ("2plus1", "1plus1plus1")
                   for k in data.get((t, d), {})) for t in tilings)
    ymax = max(60000, peak * 3)

    shapes_all, dropped_any = True, []
    for i, tiling in enumerate(tilings):
        ax = fig.add_subplot(gs[0, i])
        shapes, dropped, _ = _draw_count_vs_nt(ax, data, tiling, ymax=ymax)
        ax.set_title(TILE_LABEL.get(tiling, tiling), fontsize=10, fontweight="bold")
        if i:                                     # one y-label on the sheet, not one per panel
            ax.set_ylabel("")
            ax.tick_params(labelleft=False)
        shapes_all = shapes_all and shapes
        dropped_any += [(tiling, dropped)] if dropped else []

        tax = fig.add_subplot(gs[1, i])
        tax.axis("off")
        header, r21, r111 = _table_rows(data, tiling)
        tbl = tax.table(cellText=[r21, r111], colLabels=header, loc="center",
                        cellLoc="center", colLoc="center", bbox=[0.0, 0.30, 1.0, 0.66])
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(7.0)
        for (row, col), c in tbl.get_celld().items():
            c.set_edgecolor(TS.GRID_EDGE)
            c.set_linewidth(0.6)
            if row == 0:
                c.set_text_props(fontweight="bold")
            elif col == 0:
                c.set_text_props(fontweight="bold",
                                 color=TS.CHAIN[0] if row == 1 else TS.CHAIN[2])
        tax.text(0.5, 0.16, "closing placements / distinct flat shapes   ·   "
                            "– = K not censused   ·   k = thousands",
                 ha="center", va="top", transform=tax.transAxes,
                 fontsize=6.5, color=TS.MUTED, style="italic")

    fig.suptitle("Why 2+1 is rare and 1+1+1 is common", fontsize=13, fontweight="bold", y=0.965)
    fig.text(0.5, 0.915, "the two triangle tilings that carry both decompositions — "
                         "2+1 stops exactly where 1+1+1 starts, on each of them",
             ha="center", fontsize=8.5, color=TS.MUTED, style="italic")
    if dropped_any:
        fig.text(0.005, 0.008, "bars omit the odd N_t, where 1+1+1 was censused at even K only "
                               "(the tables keep them): %s"
                 % "; ".join("%s %s" % (t, ", ".join(str(k) for k in d)) for t, d in dropped_any),
                 fontsize=6, color=TS.MUTED, style="italic")
    _sweep_footer(fig, prov, tilings, shapes_all, y=0.030)
    return TS.save(fig, out_path or os.path.join(OUT, "count_vs_nt_pair.png"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--census-dir", default=None,
                    help="directory of *.summary.json (default results/census)")
    args = ap.parse_args(argv)
    data, prov = load(args.census_dir)
    if not data:
        raise SystemExit("no summaries under %s" % (args.census_dir or CENSUS))
    # count_vs_nt is per tiling: righttri and scalene are the two where BOTH decompositions have
    # flat folds, so the 2+1-bounded / 1+1+1-explodes contrast is visible on one axis. Equilateral
    # 1+1+1 is a proven obstruction (no flat fold at any K) and every hex cell is truncated, so
    # neither carries a comparison; they are covered by fig_smallmultiples instead.
    paths = [fig_headline(data, prov), fig_smallmultiples(data), fig_violators(data)]
    paths += [fig_count_vs_nt(data, prov, tiling=t) for t in ("righttri", "scalene")]
    # Also emit under report/figures/ at the names report/draft.md embeds. Those slots used to be
    # filled by square/render/report_examples.py from module constants that had drifted from the
    # census; regenerating them from the summaries is what keeps the draft's figures honest.
    for tiling, name in (("righttri", "fig3_count_vs_Nt.png"),
                         ("scalene", "fig3_count_vs_Nt_scalene.png")):
        paths.append(fig_count_vs_nt(data, prov, tiling=tiling,
                                     out_path=os.path.join(REPORT_FIGS, name)))
    # Both tilings on one sheet, over their census tables -- the standalone summary figure.
    paths.append(fig_count_vs_nt_pair(data, prov))
    paths.append(fig_count_vs_nt_pair(
        data, prov, out_path=os.path.join(REPORT_FIGS, "fig3_count_vs_Nt_pair.png")))
    for p in paths:
        print("wrote", os.path.relpath(p, REPO))


if __name__ == "__main__":
    main()
