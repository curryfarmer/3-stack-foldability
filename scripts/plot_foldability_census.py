"""plot_foldability_census.py -- report figures for the "2+1 stays rare, 1+1+1 explodes" finding.

Reads the store-all census summaries on disk (results/census/*.summary.json) -- so the figures are
regenerable and never drift from the numbers -- and emits three PNGs into report/tri/foldability/:

  1. headline_righttri.png   -- right-isoceles 1+1+1 vs 2+1 on one axis (the cleanest contrast).
  2. foldable_vs_k.png        -- 2x2 small multiples, foldable count vs K, all four tilings.
  3. twoloop_violators.png    -- 2-loop-reduction violators vs K (closing 1+1+1 with a (0,0,x!=0) triple).

"Foldable" = census tw0 (all three pairwise twist loops vanish). "Violator" is recomputed here from the
stored twist SPECTRUM: a triple with exactly two zero components and one nonzero -- a closing candidate
that passes two loops but fails the third, refuting the "two loops suffice" shortcut. y axes are symlog
(linthresh=1) so a genuine 0 (size searched, nothing found) sits on the baseline while the counts above
read on a log scale. Truncated cells (a cap hit, not an exhaustive count) are drawn as open markers.

Run:  .\.venv\Scripts\python.exe scripts\plot_foldability_census.py
"""
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


def load():
    """results/census/*.summary.json -> data[(tiling, decomp)][K] = (closing, foldable, viol, trunc)."""
    data = {}
    for p in glob.glob(os.path.join(CENSUS, "*.summary.json")):
        d = json.load(open(p))
        key = (d["tiling"], d["decomp"])
        viol = _viol_from_spectrum(d.get("spectrum", {})) if d["decomp"] == "1plus1plus1" else None
        data.setdefault(key, {})[d["K"]] = (d["closing"], d["tw0"], viol, bool(d["truncated"]))
    return data


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


def fig_headline(data):
    """Right-isoceles 1+1+1 vs 2+1 on one axis -- the report's lead figure."""
    plt = TS.plt
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
    # annotate the two regimes
    ax.annotate("explodes\n40 → 953 → 18,936", xy=(18, 18936), xytext=(14.2, 30000),
                fontsize=8, color=C111, fontweight="bold", ha="center",
                arrowprops=dict(arrowstyle="->", color=C111, lw=1.2))
    ax.annotate("capped at a few, then 0", xy=(8, 4), xytext=(9.6, 0.25),
                fontsize=8, color=C21, fontweight="bold", ha="left",
                arrowprops=dict(arrowstyle="->", color=C21, lw=1.2))
    ax.legend(loc="upper left", fontsize=8)
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


def main():
    data = load()
    paths = [fig_headline(data), fig_smallmultiples(data), fig_violators(data)]
    for p in paths:
        print("wrote", os.path.relpath(p, REPO))


if __name__ == "__main__":
    main()
