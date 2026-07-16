"""render_s3_offgrid_case.py — the S3 canonicalization defect, drawn.

WHAT THIS DOCUMENTS. Until S3, SquareLattice.canonical_hash minimized a fold's signature over all
8 elements of D4 with no `m != n` guard, while apply_transform mixes extents on odd rotations
(rot==1 -> (Y, m-1-X)). On a NON-SQUARE sheet the minimum could therefore be attained at an element
that is not an automorphism of the grid, so the winning representative described the fold on the
TRANSPOSED sheet -- and could land off-grid. This is the concrete witness: a 9x4 bundle whose stored
footprint is [[0,3],[0,4],[0,5]], with y=4 and y=5 two full rows OUTSIDE a sheet whose y stops at 3.
Anything reading a hash back as geometry is unsound on it -- concretely
test_physical_deciders._is_corner_footprint, which tests footprint cells against the grid's corners.
S3 narrowed the group to SquareLattice.automorphisms(m, n) (D2 here), making reps on-grid by
construction. Pinned by square/tests/test_canonical_group.py.

FIGURE 1 (the defect): both representatives' footprints against the real 9x4 sheet, shared frame.
The NEW fp is the OLD one transposed back onto the sheet -- same fold, same dedup class.

FIGURE 2 (the fixed rep, replayed): this NEW rep happens to replay legally on 9x4, so it can be
drawn as a real foldsheet. Do NOT generalize that: a canonical hash is a DEDUP KEY, not a fold path
(transform_arrow is not replay-equivariant with apply_transform), and the OLD rep here replays on
NEITHER 9x4 nor 4x9 -- which is why this module never tries to draw it as a fold. The gate line on
figure 2 is blank because a hash carries no verdict, only fp + bases + arrows.

WHY THE OLD HASH IS A LITERAL. Its source, g_111_9x4/1963d5a3501c, is untracked scratch and its
stored value was rewritten by the migration anyway, so a fresh clone cannot re-read it. It is frozen
here as the historical pre-S3 artifact it is. The AFTER side is NOT frozen: it is computed live by
the shipped migrator, so this figure cannot drift from what the code actually does.

Output lands in report/figures/ (the convention set by report_examples.py; report/ is local-only).
Run: python square/render/render_s3_offgrid_case.py
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.dirname(_HERE))          # square/ on path
sys.path.insert(0, os.path.join(REPO, "scripts"))   # the migrator
import _bootstrap  # noqa: E402,F401

import figstyle as fs                                              # noqa: E402
import matplotlib.pyplot as plt                                    # noqa: E402
from matplotlib.patches import Rectangle                           # noqa: E402
from migrate_canonical_hash import migrate_hash                    # noqa: E402
from render import render_square as R                              # noqa: E402

FIGDIR = os.path.join(REPO, "report", "figures")

# Verbatim pre-S3 canonicalHash of g_111_9x4/1963d5a3501c, captured 2026-07-16 before the migration.
GRID = (9, 4)
OLD_HASH = (
    '{"fp":[[0,3],[0,4],[0,5]],"chains":['
    '{"kind":"1chain","base":[[0,3]],"arrows":["D","D","D","L","L","L","U","U","U","U","U"]},'
    '{"kind":"1chain","base":[[0,4]],"arrows":["L","D","D","D","L","U","U","U","U","U","L"]},'
    '{"kind":"1chain","base":[[0,5]],"arrows":["L","U","R","U","U","L","D","L","U","L","D"]}]}'
)


def detail_of(h):
    """canonical-hash rep -> the detail blob render_square.render consumes."""
    p = json.loads(h)
    return {
        "footprint": {"cells": [{"x": c[0], "y": c[1]} for c in p["fp"]]},
        "chains": [{"kind": c["kind"],
                    "baseCells": [{"x": b[0], "y": b[1]} for b in c["base"]],
                    "foldArrows": list(c["arrows"])} for c in p["chains"]],
        "verdict": {},                          # a hash carries no verdict -- gate line stays blank
    }


def panel(ax, fp, m, n, title, ylim):
    """The m x n sheet plus one rep's footprint cells, flagging any that fall outside.
    ylim is shared across panels so the two reps are directly comparable."""
    fs.draw_grid_cells(ax, m, n)
    off = 0
    for (x, y) in fp:
        inside = 0 <= x < m and 0 <= y < n
        off += not inside
        ax.add_patch(Rectangle((x, y), 1, 1,
                               facecolor=(fs.CHAIN[0] if inside else "#d62728"),
                               edgecolor="black", lw=1.4, alpha=0.9, zorder=3))
        ax.text(x + 0.5, y + 0.5, f"{x},{y}", ha="center", va="center",
                color="white", fontsize=7, fontweight="bold", zorder=4)
    ax.add_patch(Rectangle((0, 0), m, n, fill=False, edgecolor="black", lw=2.4, zorder=5))
    lo_y, hi_y = ylim
    ax.set_xlim(-0.5, m + 0.5)
    ax.set_ylim(hi_y, lo_y)                     # origin top-left, +y down (viewer convention)
    ax.set_aspect("equal")
    ax.set_title(f"{title}\n{off} cell(s) off-grid  —  {'OFF-GRID' if off else 'on-grid'}",
                 fontsize=9, color=("#d62728" if off else "#2ca02c"))
    ax.set_xticks(range(m + 1))
    ax.set_yticks(range(int(lo_y) + 1, int(hi_y) + 1))
    ax.tick_params(labelsize=6)
    if off:
        ax.annotate("outside the sheet", xy=(1.15, n + 1.0), fontsize=8, color="#d62728",
                    fontweight="bold", va="center")


def main():
    os.makedirs(FIGDIR, exist_ok=True)
    m, n = GRID
    new = migrate_hash(OLD_HASH, m, n)          # live: the figure tracks the shipped migrator
    assert new != OLD_HASH, "expected this rep to move under the S3 narrowing"
    fp_old, fp_new = json.loads(OLD_HASH)["fp"], json.loads(new)["fp"]
    assert any(not (0 <= x < m and 0 <= y < n) for (x, y) in fp_old), "old rep should be off-grid"
    assert all(0 <= x < m and 0 <= y < n for (x, y) in fp_new), "new rep must be on-grid"

    fs.apply_style()
    ys = [c[1] for c in fp_old] + [c[1] for c in fp_new] + [0, n]
    ylim = (min(ys) - 0.6, max(ys) + 1.6)       # one frame, sized to whichever rep strays furthest
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    panel(axes[0], fp_old, m, n, f"OLD rep (min over all 8 of D4)\nfp = {fp_old}", ylim)
    panel(axes[1], fp_new, m, n, f"NEW rep (min over Aut = D2)\nfp = {fp_new}", ylim)
    fig.suptitle(f"S3: the off-grid representative — {m}x{n} bundle 1963d5a3501c\n"
                 "same fold, same dedup class, legal representative "
                 "(the NEW fp is the OLD one transposed back onto the sheet)",
                 fontsize=11, y=1.04)
    fig.tight_layout()
    p1 = os.path.join(FIGDIR, "s3_offgrid_rep_before_after.png")
    fig.savefig(p1, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", os.path.relpath(p1, REPO))

    p2 = os.path.join(FIGDIR, "s3_offgrid_rep_new_foldsheet.png")
    R.render(detail_of(new), m, n, p2,
             title=f"S3 NEW rep (automorphism-subgroup min) — on-grid and replayable on {m}x{n}")
    print("wrote", os.path.relpath(p2, REPO))


if __name__ == "__main__":
    main()
