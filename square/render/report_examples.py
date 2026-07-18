"""report_examples.py — extra report figures for the 3-stack chapters.

Driver (not a library) that renders the additional Chapter 3/4 figures:
  (a) how the math works, step by step   -> Model B reduction strip + twist-accumulation plot
  (b) 3-stack on different grids          -> 2+1 and 1+1+1 foldsheet montages
  (c) why 2+1 is rare vs 1+1+1 common     -> census count-vs-N_t bars + sparsity/wrapping schematic

Every figure is built from real solved bundles (square/generate.py --stacks 3 ... --out <dir>) or from
the published non-square census (docs/research/FINDINGS_nonsquare_2026-07.md, density table). Palette,
grid convention (origin top-left, +y down), fonts and dpi all come from figstyle so these match the rest
of the report. Output lands in report/figures/ by default.

Run: .venv/Scripts/python.exe square/render/report_examples.py
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                       # square/render on path (figstyle, render_square, ...)
sys.path.insert(0, os.path.dirname(HERE))      # square/ on path
import _bootstrap  # noqa: E402,F401           # puts square/{engine,twist,render} on sys.path

import matplotlib.pyplot as plt                # noqa: E402
import figstyle as fs                          # noqa: E402
import twist_jump as tj                        # noqa: E402
import render_square as rsq                    # noqa: E402
import search as Search                        # noqa: E402
from render_twist_2plus1 import build_loop, _cell_of, _step_kind   # noqa: E402  (new-style twist prims)

REPO = os.path.dirname(os.path.dirname(HERE))
FIGDIR = os.path.join(REPO, "report", "figures")
SCRATCH = os.path.join(REPO, "scratch_examples")
os.makedirs(SCRATCH, exist_ok=True)


# --------------------------------------------------------------------- data ----

def load_bundle(out_dir, uid=None):
    """Load one solved bundle dict from out_dir. If uid given, that one; else the first."""
    if uid:
        return json.load(open(os.path.join(REPO, out_dir, uid, f"{uid}.json")))
    paths = sorted(glob.glob(os.path.join(REPO, out_dir, "*", "*.json")))
    if not paths:
        raise FileNotFoundError(f"no bundles under {out_dir}")
    return json.load(open(paths[0]))


def _find_uid(out_dir, uid):
    """Return the bundle with this uid from out_dir, or None if absent."""
    p = os.path.join(REPO, out_dir, uid, f"{uid}.json")
    return json.load(open(p)) if os.path.exists(p) else None


# ---------------------------------------------------------------- montages ----

def foldsheet_montage(items, out_path, suptitle):
    """items = [(bundle_dict, label), ...]. Render each foldsheet to a temp PNG (render_square), then
    top-align them into one canvas: pad every image to the tallest height with white and concatenate
    horizontally, so panels of different grid sizes line up along the top edge (no per-axes scaling
    drift). I/O: (list, path, str) -> path."""
    import numpy as np
    imgs = []
    for i, (b, label) in enumerate(items):
        p = os.path.join(SCRATCH, f"_mont_{i}.png")
        rsq.render(b, b["m"], b["n"], p, title=label)
        im = plt.imread(p)
        if im.ndim == 2:                                   # greyscale -> RGB
            im = np.stack([im] * 3, axis=-1)
        if im.shape[2] == 3:                               # RGB -> RGBA
            im = np.concatenate([im, np.ones(im.shape[:2] + (1,), im.dtype)], axis=2)
        imgs.append(im)

    H = max(im.shape[0] for im in imgs)
    pad_w = max(6, H // 40)                                # thin white gutter between panels

    def pad_top(im):
        h, w, c = im.shape
        if h == H:
            return im
        block = np.ones((H - h, w, c), dtype=im.dtype)     # white pad below (top-align)
        return np.concatenate([im, block], axis=0)

    gutter = np.ones((H, pad_w, 4), dtype=imgs[0].dtype)
    pieces = []
    for j, im in enumerate(imgs):
        if j:
            pieces.append(gutter)
        pieces.append(pad_top(im))
    canvas = np.concatenate(pieces, axis=1)

    aspect = canvas.shape[1] / canvas.shape[0]
    fig, ax = plt.subplots(figsize=(min(20.0, 5.6 * aspect), 5.6))
    ax.imshow(canvas)
    ax.axis("off")
    fig.suptitle(suptitle, fontsize=12, fontweight="bold")
    fig.tight_layout()
    return fs.save(fig, out_path)


# ------------------------------------------------------ twist accumulation ----

def _running_total(sol, m, n):
    """Cumulative Σ σ·γ along the canonical jump-strand loop (degrees), vertex by vertex.
    Sign convention matches render_twist_2plus1: sig = +1 on odd index, -1 on even. Returns
    (xs, running, tw)."""
    info = build_loop(sol, m, n)
    terms = info["terms"]
    running, s = [], 0.0
    for i, g in enumerate(terms):
        sig = 1 if i % 2 else -1
        s += sig * g
        running.append(s)
    return list(range(1, len(running) + 1)), running, info["tw"]


def twist_accumulation(fold, jam, out_path):
    """Overlay the running twist total for a FOLD (returns to 0) and a JAM (diverges to ±720°).
    fold/jam = (bundle_dict,). I/O: (dict, dict, path) -> path."""
    fs.apply_style()
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    for sol, color, lbl in ((fold, fs.FOLD_BADGE, "FOLD"), (jam, fs.JAM_BADGE, "JAM")):
        xs, run, tw = _running_total(sol, sol["m"], sol["n"])
        tw_deg = "0°" if abs(tw) < 1e-6 else f"{tw:+.0f}°"
        ax.plot([0] + xs, [0.0] + run, "-o", ms=3.5, color=color, lw=2.0,
                label=f"{lbl}  {sol['m']}×{sol['n']}  (Tw = {tw_deg})")
    ax.axhline(0, color=fs.INK, lw=0.8, ls=(0, (4, 2)))
    for y in (-720, -360, 360, 720):
        ax.axhline(y, color="#cccccc", lw=0.7, zorder=0)
    ax.set_xlabel("loop vertex index")
    ax.set_ylabel("cumulative  Σ σ·γ  (degrees)")
    ax.set_title("How the verdict is decided: running twist total along the loop",
                 fontsize=11, fontweight="bold")
    ax.legend(loc="lower left", fontsize=8, frameon=True)
    ax.set_yticks([-720, -360, 0, 360, 720])
    fig.tight_layout()
    return fs.save(fig, out_path)


# ------------------------------------------------------- Model B step strip ----

def _mb_seg(ax, p, q, color, lw, *, ls="-", z=4):
    ax.plot([p[0], q[0]], [p[1], q[1]], color=color, lw=lw, ls=ls, zorder=z,
            solid_capstyle="round")


def _mb_arrow(ax, p, q, color, *, z=7):
    from matplotlib.patches import FancyArrowPatch
    ax.add_patch(FancyArrowPatch((p[0], p[1]), (q[0], q[1]), arrowstyle="-|>",
                                 mutation_scale=11, color=color, lw=0, zorder=z))


def model_b_steps(sol, out_dir):
    """Model B story on a real 2+1 FOLD, as three SEPARATE single-panel figures (one file each, meant
    to sit side by side in the report), in the STANDARDISED twist style that render_twist_2plus1 uses:
    parity checkerboard (sigma = (-1)^(x+y) tint), directed strands, red 3-jumps, green hub seams,
    per-vertex sigma*gamma labels, right-hand legend, FOLD/JAM badge title. Steps: (1) decompose +
    replay, (2) keep one strand (twin = hole, along-axis fold = 3-jump), (3) close the loop -> twist.
    Geometry comes from build_loop — the same canonical strand the twist figure scores.
    I/O: (dict, dir) -> [path1, path2, path3]."""
    m, n = sol["m"], sol["n"]
    info = build_loop(sol, m, n)                              # canonical body/path1/loop/terms/tw
    body, path1, loop = info["body"], info["path1"], info["loop"]
    terms, tw, K, idx = info["terms"], info["tw"], info["K"], info["idx"]
    two = next(c for c in sol["chains"] if len(c["baseCells"]) == 2)
    one = next(c for c in sol["chains"] if len(c["baseCells"]) == 1)
    twin = tj.strand_path(tj.replay(two["baseCells"], two["foldArrows"], m, n), 1 - idx)
    BODY, PATH1 = fs.CHAIN[0], fs.CHAIN[1]
    fp = sol.get("footprint", {}).get("cells", [])
    out_paths = []

    def _panel():                                            # checker grid + footprint + legend gutter
        fig, ax = fs.new_grid_axes(m, n, pad=0.5, extra_w=2.6, ticklabels=False)
        fs.draw_grid_cells(ax, m, n, checker=True)
        fs.draw_footprint(ax, fp)
        return fig, ax

    def _numbered(ax, strand, color, ms=4.5):
        for k, p in enumerate(strand):
            ax.plot(p[0], p[1], "o", ms=ms, color=color, zorder=8)
            ax.annotate(str(k), (p[0], p[1]), textcoords="offset points", xytext=(3, 3),
                        fontsize=6.5, color=color, zorder=9)

    # panel 1 — decompose + replay: the domino (both parallel panels) + the monomino, both directed
    fig, ax = _panel()
    fs.draw_base_cells(ax, fs.cells(two["baseCells"]), BODY, "A")
    fs.draw_base_cells(ax, fs.cells(one["baseCells"]), PATH1, "B")
    for strand in (body, twin):                              # rigid domino: two panels sweep parallel
        for i in range(len(strand) - 1):
            _mb_seg(ax, strand[i], strand[i + 1], BODY, 2.0)
            _mb_arrow(ax, strand[i], strand[i + 1], BODY)
    for i in range(len(path1) - 1):
        _mb_seg(ax, path1[i], path1[i + 1], PATH1, 2.0)
        _mb_arrow(ax, path1[i], path1[i + 1], PATH1)
    ax.set_title("1.  Decompose (A = domino, B = monomino) and replay each fold sequence",
                 fontsize=10, fontweight="bold")
    fs.legend_panel(ax, [fs.line_handle(BODY, "domino A (both panels)"),
                         fs.line_handle(PATH1, "monomino B")])
    out_paths.append(fs.save(fig, os.path.join(out_dir, "fig3_modelB_step1_decompose.png")))

    # panel 2 — keep ONE strand; twin = hole; along-axis fold = 3-jump
    fig, ax = _panel()
    for p in twin:
        ax.plot(p[0], p[1], "o", ms=9, mfc="none", mec=fs.MUTED, mew=1.4, zorder=6)
    for i in range(len(body) - 1):
        is3 = _step_kind(_cell_of(body[i]), _cell_of(body[i + 1])) == "3JMP"
        _mb_seg(ax, body[i], body[i + 1], fs.JUMP if is3 else BODY, 3.0 if is3 else 2.0,
                ls=fs.DASH if is3 else "-", z=5 if is3 else 4)
        _mb_arrow(ax, body[i], body[i + 1], fs.JUMP if is3 else BODY)
    _numbered(ax, body, BODY)
    ax.set_title("2.  Keep ONE strand; the twin fills the gap (hole).\n"
                 "An along-axis fold lands the strand 3 away — the 3-jump.",
                 fontsize=10, fontweight="bold")
    fs.legend_panel(ax, [fs.line_handle(BODY, "kept strand (body)"),
                         fs.patch_handle("none", "twin panel (hole)", alpha=1.0, edgecolor=fs.MUTED),
                         fs.line_handle(fs.JUMP, "3-jump (along-axis fold)", ls=fs.DASH)])
    out_paths.append(fs.save(fig, os.path.join(out_dir, "fig3_modelB_step2_strand.png")))

    # panel 3 — close the loop; per-vertex sigma*gamma -> Tw (identical scoring to the twist figure)
    fig, ax = _panel()
    nloop = len(loop)
    seam_pairs = {(K - 1, K % nloop), (nloop - 1, 0)}
    for i in range(nloop):
        p, q = loop[i], loop[(i + 1) % nloop]
        if (i, (i + 1) % nloop) in seam_pairs:
            _mb_seg(ax, p, q, fs.SEAM, 3.4, z=5)
        elif _step_kind(_cell_of(p), _cell_of(q)) == "3JMP":
            _mb_seg(ax, p, q, fs.JUMP, 3.2, ls=fs.DASH, z=5)
        else:
            _mb_seg(ax, p, q, BODY if i < K - 1 else PATH1, 2.2, z=4)
        _mb_arrow(ax, p, q, BODY if i < K else PATH1)
    _numbered(ax, body, BODY)
    for p in path1:
        ax.plot(p[0], p[1], "o", ms=3.2, color=PATH1, zorder=8)
    for i in range(nloop):                                   # only turning vertices move the total
        if abs(terms[i]) < 1e-6:
            continue
        contrib = (1 if i % 2 else -1) * terms[i]
        piv = loop[(i + 1) % nloop]
        ax.annotate(fs.pi_label(contrib), (piv[0], piv[1]), textcoords="offset points",
                    xytext=(4, -10), fontsize=7.5, fontweight="bold",
                    color=fs.POS if contrib > 0 else fs.NEG, zorder=10)
    verdict = "FOLD (flat)" if tj.is0(tw) else f"JAM (Tw = {fs.pi_label(tw)})"
    badge = fs.FOLD_BADGE if tj.is0(tw) else fs.JAM_BADGE
    ax.set_title("3.  Close: loop = body + reversed(path1).   "
                 f"Tw = Σ σ·γ = {fs.pi_label(tw)}  →  {verdict}",
                 fontsize=10, fontweight="bold", color=badge)
    fs.legend_panel(ax, [fs.line_handle(BODY, "2-chain kept strand (body)"),
                         fs.line_handle(PATH1, "1-chain strand (path1)"),
                         fs.line_handle(fs.JUMP, "3-jump (along-axis fold)", ls=fs.DASH),
                         fs.line_handle(fs.SEAM, "hub seam (chains rejoin)")])
    out_paths.append(fs.save(fig, os.path.join(out_dir, "fig3_modelB_step3_close.png")))

    return out_paths


# --------------------------------------------------- census: 2+1 vs 1+1+1 ----

# Right-triangle (tetrakis) flat-fold counts per sub-chain length N_t, from the EXHAUSTIVE store-all
# census (results/census/, driver triangle/tri/census.py; tables in
# docs/research/FINDINGS_nonsquare_2026-07.md §5.0). Both decompositions live on this tiling, so it is
# the clean single-tiling contrast. Every cell below ran to exhaustion — no time-budget floors, which
# is why the old '>= 931' at N_t=16 is now an exact 953 and N_t=18 exists at all.
RIGHTTRI_2P1 = {4: 5, 6: 2, 8: 4, 10: 0, 12: 0, 14: 0, 16: 0, 18: 0}
RIGHTTRI_111 = {4: 0, 6: 0, 8: 0, 10: 0, 12: 0, 14: 40, 16: 953, 18: 18936}
FLOOR_111 = set()   # exhaustive: no '>=' floors


def census_count_vs_nt(out_path):
    """Grouped log-bar chart: right-triangle flat-fold count vs N_t for 2+1 (bounded, dies after N_t=8)
    vs 1+1+1 (zero until N_t=14, then explodes). I/O: (path) -> path."""
    fs.apply_style()
    nts = sorted(set(RIGHTTRI_2P1) | set(RIGHTTRI_111))
    import numpy as np
    x = np.arange(len(nts))
    w = 0.38
    fig, ax = plt.subplots(figsize=(7.6, 4.6))

    def plot_bars(data, floors, offset, color, label):
        heights = [max(data.get(k, 0), 0) for k in nts]
        plotted = [h if h > 0 else 0.0 for h in heights]
        bars = ax.bar(x + offset, plotted, w, color=color, label=label, zorder=3)
        for xi, h, k in zip(x + offset, heights, nts):
            if h == 0:
                ax.text(xi, 1.15, "0", ha="center", va="bottom", fontsize=8, color=color)
            else:
                tag = ("≥" if k in floors else "") + str(h)
                ax.text(xi, h * 1.08, tag, ha="center", va="bottom", fontsize=8,
                        color=color, fontweight="bold")
        return bars

    plot_bars(RIGHTTRI_2P1, set(), -w / 2, fs.CHAIN[0], "2+1  (bounded, caps ≤ N_t = 8)")
    plot_bars(RIGHTTRI_111, FLOOR_111, w / 2, fs.CHAIN[2], "1+1+1  (grows ~20× per +2)")
    ax.set_yscale("log")
    ax.set_ylim(0.8, 60000)
    ax.set_xticks(x)
    ax.set_xticklabels([str(k) for k in nts])
    ax.set_xlabel("sub-chain length  N_t  (right-triangle tiling)")
    ax.set_ylabel("number of flat (Tw = 0) folds  [log]")
    ax.set_title("Why 2+1 is rare and 1+1+1 is common", fontsize=11, fontweight="bold")
    ax.legend(loc="upper left", fontsize=8, frameon=True)
    ax.grid(axis="y", which="both", color="#eeeeee", zorder=0)
    fig.tight_layout()
    return fs.save(fig, out_path)


# ----------------------------------------------- sparsity vs wrapping (schematic)

def sparsity_vs_wrapping(out_path):
    """Two-panel intuition schematic: LEFT 2+1 — a rigid domino (dark, pinned frame) plus one
    returning chain that must come home to a bounded radius (few closers). RIGHT 1+1+1 — three
    equal chains, two wrapping the boundary ring, one interior (many closers). I/O: (path) -> path."""
    from matplotlib.patches import Rectangle, Circle
    m = n = 6
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 6.2))

    # LEFT: 2+1 pinned frame
    ax = axes[0]; _grid_panel(ax, m, n)
    # rigid domino (pinned) — two dark cells at a corner-ish spot
    for (cx, cy) in [(2, 0), (3, 0)]:
        ax.add_patch(Rectangle((cx, cy), 1, 1, facecolor=fs.INK, edgecolor="none", alpha=0.85, zorder=4))
    ax.text(2.5, 0.5, "rigid", ha="center", va="center", color="white", fontsize=8,
            fontweight="bold", zorder=6)
    ax.text(3.5, 0.5, "domino", ha="center", va="center", color="white", fontsize=8,
            fontweight="bold", zorder=6)
    # bounded return radius for the single chain
    ax.add_patch(Circle((2.5, 0.9), 2.3, facecolor=fs.CHAIN[1], edgecolor=fs.CHAIN[1],
                        alpha=0.12, lw=1.6, ls=(0, (5, 3)), zorder=2))
    ax.annotate("returning 1-chain must\nclose inside a bounded radius\n→ few closers, capped N_t",
                (2.5, 3.1), ha="center", va="center", fontsize=9, color=fs.CHAIN[1], zorder=7)
    ax.set_title("2+1:  one pinned frame + one returning chain\n(near-measure-zero closure → SPARSE)",
                 fontsize=10, fontweight="bold")

    # RIGHT: 1+1+1 wrapping
    ax = axes[1]; _grid_panel(ax, m, n)
    ring = [(x, y) for x in range(m) for y in range(n) if x in (0, m - 1) or y in (0, n - 1)]
    interior = [(x, y) for x in range(m) for y in range(n) if (x, y) not in ring]
    # two wrapping chains split the ring (top/left vs bottom/right), interior chain fills the middle
    for (cx, cy) in ring:
        col = fs.CHAIN[0] if (cx <= cy) else fs.CHAIN[2]
        ax.add_patch(Rectangle((cx, cy), 1, 1, facecolor=col, edgecolor="none", alpha=0.55, zorder=3))
    for (cx, cy) in interior:
        ax.add_patch(Rectangle((cx, cy), 1, 1, facecolor=fs.CHAIN[1], edgecolor="none",
                               alpha=0.55, zorder=3))
    ax.annotate("2 chains wrap the ring", (3.0, -0.15), ha="center", va="bottom",
                fontsize=9, color=fs.INK, zorder=7)
    ax.text(3.0, 3.0, "3rd chain\ninterior", ha="center", va="center", fontsize=9,
            color=fs.CHAIN[1], fontweight="bold", zorder=7)
    ax.set_title("1+1+1:  three equal chains, no pinned frame\n(2 wrap the ring, 1 fills interior → COMMON)",
                 fontsize=10, fontweight="bold")

    fig.suptitle("Why the two decompositions differ so sharply", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return fs.save(fig, out_path)


# ------------------------------------------------------ gate funnel, per grid ----

def gate_stats(m, n, decomp_key):
    """Run the real search on one grid and return the funnel stage counts, straight from
    Search.run's ctx (no SQLite/webapp layer). 'candidates' is coveredCount // 4 -- the covered-
    candidate enumeration counts every D4 rotation of a footprint separately, a 4x redundancy over
    the canonical-orientation count the report's §3.6 table already publishes (verified equal to
    that table's candidates column on all four grids: 153/285/1990/3406 for 2+1 on 6x4..6x7).
    I/O: (int, int, '2+1'|'1+1+1') -> dict."""
    opts = {"m": m, "n": n, "panels": 3, "shapes": {"L": True, "Rect": True},
            "decomps": {"2+1": decomp_key == "2+1", "1+1+1": decomp_key == "1+1+1"},
            "allowNonCorner": True, "dedup": True, "jobs": 20}
    sols, ctx, err = Search.run(opts)
    if err:
        raise RuntimeError(f"{m}x{n} {decomp_key}: {err}")
    fold = sum(1 for s in sols if s["verdict"]["twist"] is True)
    return {
        "candidates": ctx["coveredCount"] // 4,
        "exit": ctx["exitPass"], "parity": ctx["parityPass"],
        "survivors": ctx["afterDedup"], "fold": fold, "jam": ctx["afterDedup"] - fold,
    }


def gate_funnel_by_grid(grids, decomp_key, out_path, title):
    """Grouped log-bar chart: one group per grid, 4 bars per group (exit-footprint -> parity ->
    reflection survivors -> twist-FOLD), the same funnel stages as the report's survivor-census
    tables. No legend box -- the stage color key is spelled out in the title instead.
    I/O: ([(m,n), ...], '2+1'|'1+1+1', path, str) -> path."""
    fs.apply_style()
    import numpy as np
    stats = [gate_stats(m, n, decomp_key) for (m, n) in grids]
    stages = ["exit", "parity", "survivors", "fold"]
    colors = [fs.CHAIN[0], fs.CHAIN[1], fs.JUMP, fs.SEAM]
    x = np.arange(len(grids))
    w = 0.2
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    for i, (stage, color) in enumerate(zip(stages, colors)):
        offset = (i - 1.5) * w
        heights = [max(s[stage], 1) for s in stats]
        ax.bar(x + offset, heights, w, color=color, zorder=3)
        for xi, s in zip(x + offset, stats):
            ax.text(xi, max(s[stage], 1) * 1.08, str(s[stage]), ha="center", va="bottom",
                    fontsize=7, color=color, fontweight="bold", rotation=90)
    ax.set_yscale("log")
    max_h = max(max(s[stage] for stage in stages) for s in stats)
    ax.set_ylim(0.8, max_h * 60)          # headroom for the rotated value labels + 2-line title
    ax.set_xticks(x)
    ax.set_xticklabels([f"{m}×{n}" for (m, n) in grids])
    ax.set_xlabel("grid")
    ax.set_ylabel("count  [log]")
    ax.set_title(f"{title}\nbars left→right per grid:  exit-footprint → parity → reflection "
                 f"(survivors) → twist-FOLD",
                 fontsize=11, fontweight="bold")
    ax.grid(axis="y", which="both", color="#eeeeee", zorder=0)
    fig.tight_layout()
    return fs.save(fig, out_path)


# --------------------------------------------------------------------- main ----

def main():
    made = []

    # (b) grids — 2+1 montage (real solved foldsheets)
    b64 = load_bundle("g_2p1_6x4", "07dff02ba5c9")
    b66 = load_bundle("g_2p1_6x6")
    made.append(foldsheet_montage(
        [(b64, "2+1 on 6×4  (N_t = 8)"), (b66, "2+1 on 6×6  (N_t = 12)")],
        os.path.join(FIGDIR, "fig3_2plus1_grids.png"),
        "The 2+1 decomposition on different square grids"))

    # (a) math — Model B steps on the 6×4 FOLD, as 3 separate side-by-side figures
    made.extend(model_b_steps(b64, FIGDIR))
    jam = _find_uid("g_2p1_6x7", "4cc6f36d0ca4")
    if jam is None:                     # fall back to any Tw!=0 6x7 survivor
        for p in sorted(glob.glob(os.path.join(REPO, "g_2p1_6x7", "*", "*.json"))):
            d = json.load(open(p))
            tps = d.get("twistPairs") or [{}]
            if tps and abs((tps[0] or {}).get("tw") or 0) > 1:
                jam = d; break
    if jam is not None:
        made.append(twist_accumulation(b64, jam,
                    os.path.join(FIGDIR, "fig3_twist_accumulation.png")))
    else:
        print("!! no 6x7 JAM bundle yet — skipping twist_accumulation")

    # (b) grids — 1+1+1 montage
    items111 = []
    for d, lbl in (("g_111_6x4", "1+1+1 on 6×4  (N_t = 8)"),
                   ("g_111_6x6", "1+1+1 on 6×6  (N_t = 12)"),
                   ("g_111_9x4", "1+1+1 on 9×4  (N_t = 12)")):
        try:
            items111.append((load_bundle(d), lbl))
        except FileNotFoundError:
            print(f"!! no bundle for {d} yet — skipping in montage")
    if items111:
        made.append(foldsheet_montage(items111, os.path.join(FIGDIR, "fig4_1plus1_grids.png"),
                    "The 1+1+1 decomposition on different square grids"))

    # (c) rarity — census bars + sparsity/wrapping schematic
    made.append(census_count_vs_nt(os.path.join(FIGDIR, "fig3_count_vs_Nt.png")))
    made.append(sparsity_vs_wrapping(os.path.join(FIGDIR, "fig3_sparsity_vs_wrapping.png")))

    # (d) gate funnel — per-grid gate-survival, one chart per decomposition
    grids = [(6, 4), (6, 5), (6, 6), (6, 7)]
    made.append(gate_funnel_by_grid(grids, "2+1", os.path.join(FIGDIR, "fig3_funnel_by_grid.png"),
                "2+1: gate survival per grid"))
    made.append(gate_funnel_by_grid(grids, "1+1+1", os.path.join(FIGDIR, "fig4_funnel_by_grid.png"),
                "1+1+1: gate survival per grid"))

    for p in made:
        print("wrote", os.path.relpath(p, REPO))


if __name__ == "__main__":
    main()
