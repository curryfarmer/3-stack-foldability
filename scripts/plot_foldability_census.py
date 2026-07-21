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

    data[(tiling, decomp)][K] = (closing, foldable, viol, trunc)
    prov[(tiling, decomp)]    = set of `hubs` values seen ({None} for cells written before the
                                field existed) -- the sweep width behind those counts.
    I/O: (census_dir | None -> results/census) -> (data, prov)."""
    data, prov = {}, {}
    for p in glob.glob(os.path.join(census_dir or CENSUS, "*.summary.json")):
        with open(p) as fh:
            d = json.load(fh)
        key = (d["tiling"], d["decomp"])
        viol = _viol_from_spectrum(d.get("spectrum", {})) if d["decomp"] == "1plus1plus1" else None
        data.setdefault(key, {})[d["K"]] = (d["closing"], d["tw0"], viol, bool(d["truncated"]))
        prov.setdefault(key, set()).add(d.get("hubs"))
    return data, prov


def _sweep_note(prov, key):
    """One-line human description of how wide the sweep behind a series was.
    I/O: (prov, (tiling, decomp)) -> str, e.g. "20 hubs" / "8 hubs" / "hubs ?"."""
    seen = {h for h in prov.get(key, ()) if h is not None}
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


def _sweep_footer(fig, prov, tiling="righttri"):
    """Stamp the sweep width onto the figure. A count here is "folds found by THIS sweep", and a
    2+1 cell scales with --hubs while a 1+1+1 cell is one ambient hub variant -- so a figure that
    does not carry its sweep is not reproducible. I/O: (fig, prov, tiling) -> None."""
    n21 = _sweep_note(prov, (tiling, "2plus1"))
    n111 = _sweep_note(prov, (tiling, "1plus1plus1"))
    fig.text(0.995, 0.005, "sweep: 2+1 %s · 1+1+1 %s (single ambient variant)" % (n21, n111),
             ha="right", va="bottom", fontsize=6, color=TS.MUTED, style="italic")


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


def fig_count_vs_nt(data, prov=None, tiling="righttri"):
    """Grouped log bars: flat-fold count vs N_t, 2+1 against 1+1+1.

    Formerly square/render/report_examples.py:census_count_vs_nt, where the counts were typed in as
    module constants and had already drifted from the census. Everything here -- bar heights, the
    cap, the growth factor in the legend -- is derived from the summaries."""
    import numpy as np
    plt = TS.plt
    prov = prov or {}
    cell21 = data.get((tiling, "2plus1"), {})
    cell111 = data.get((tiling, "1plus1plus1"), {})
    # BOTH-or-neither: 1+1+1 is censused at even K only, so a bar at a K it never searched would
    # draw "not computed" as a confident zero.
    nts = sorted(set(cell21) & set(cell111))
    dropped = sorted((set(cell21) | set(cell111)) - set(nts))
    if not nts:
        raise SystemExit("no K is present for both decomps of %s -- nothing to plot" % tiling)

    y21 = [cell21[k][1] for k in nts]
    y111 = [cell111[k][1] for k in nts]
    x = np.arange(len(nts))
    w = 0.38
    fig, ax = plt.subplots(figsize=(7.6, 4.6))

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
    ax.set_ylim(0.8, max(60000, max(y111 + y21) * 3))
    ax.set_xticks(x)
    ax.set_xticklabels([str(k) for k in nts])
    ax.set_xlabel("sub-chain length  N_t  (%s tiling)" % TILE_LABEL.get(tiling, tiling))
    ax.set_ylabel("flat (Tw = 0) folds found by this sweep  [log]")
    ax.set_title("Why 2+1 is rare and 1+1+1 is common", fontsize=11, fontweight="bold")
    ax.legend(loc="upper left", fontsize=8, frameon=True)
    ax.grid(axis="y", which="both", color=TS.GRID_EDGE, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    if dropped:
        ax.text(0.005, 0.005, "K not searched for both decomps, omitted: %s"
                % ", ".join(str(k) for k in dropped),
                transform=fig.transFigure, fontsize=6, color=TS.MUTED, style="italic")
    _sweep_footer(fig, prov, tiling)
    fig.tight_layout()
    return TS.save(fig, os.path.join(OUT, "count_vs_nt_%s.png" % tiling))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--census-dir", default=None,
                    help="directory of *.summary.json (default results/census)")
    args = ap.parse_args(argv)
    data, prov = load(args.census_dir)
    if not data:
        raise SystemExit("no summaries under %s" % (args.census_dir or CENSUS))
    paths = [fig_headline(data, prov), fig_smallmultiples(data), fig_violators(data),
             fig_count_vs_nt(data, prov)]
    for p in paths:
        print("wrote", os.path.relpath(p, REPO))


if __name__ == "__main__":
    main()
