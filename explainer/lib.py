"""Shared matplotlib primitives for the first-principles twist-theory diagrams.

Standalone: no import of the fold engine. Schematics are hand-placed cell lists.
Palette mirrors grid.js so figures match the live tool. Coordinate convention here
is math-standard (+y up); a cell (x, y) has lower-left corner at (x, y) and centre
at (x+0.5, y+0.5).
"""

import os
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, FancyArrowPatch, Arc, Circle

# ---- palette (grid.js vocabulary + pedagogical tints) ----------------------
PALETTE = {
    "hc": "#39c",          # Hamiltonian circuit path (dotted blue)
    "crease": "#d22",      # crossed edge = fold
    "slit": "#bbb",        # uncrossed interior edge
    "cut": "#2a8",         # cut edge
    "chevron": "#ff7a18",  # fold direction
    "valley": "#3399cc",   # valley fold / odd / +1
    "mountain": "#d83232", # mountain fold / even / -1
    "tintA": "#eaf3fb",    # face-up / even parity fill
    "tintB": "#fdeeee",    # face-down / odd parity fill
    "node": "#333333",
    "edge": "#444444",
    "ink": "#222222",
    "hub": "#6f4fb0",      # rigid fused footprint hub
    "chainA": "#1f77b4",
    "chainB": "#e8820c",
    "chainC": "#2ca02c",
    "ghost": "#9aa0a6",    # reflected/ghost copy
}

SVG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "svg")


# ---- canvas ----------------------------------------------------------------
def new_ax(figsize=(5.2, 5.2)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def save(fig, name):
    os.makedirs(SVG_DIR, exist_ok=True)
    path = os.path.join(SVG_DIR, name + ".svg")
    fig.savefig(path, bbox_inches="tight", transparent=False)
    plt.close(fig)
    return path


def center(x, y, s=1.0):
    return (x + s / 2.0, y + s / 2.0)


# ---- panels / grids --------------------------------------------------------
def panel(ax, x, y, s=1.0, fc="white", ec=None, lw=1.4, alpha=1.0, z=1,
          label=None, label_color=None, fs=12):
    ec = PALETTE["edge"] if ec is None else ec
    ax.add_patch(Rectangle((x, y), s, s, facecolor=fc, edgecolor=ec,
                           linewidth=lw, alpha=alpha, zorder=z))
    if label is not None:
        cx, cy = center(x, y, s)
        ax.text(cx, cy, label, ha="center", va="center",
                color=label_color or PALETTE["ink"], fontsize=fs, zorder=z + 2)


def grid(ax, cells, s=1.0, fc="white", ec=None, lw=1.4, labels=None, fs=12):
    """cells: iterable of (x, y). labels: optional dict (x,y)->str."""
    for (x, y) in cells:
        lab = None if labels is None else labels.get((x, y))
        panel(ax, x, y, s=s, fc=fc, ec=ec, lw=lw, label=lab, fs=fs)


def rect_cells(m, n):
    """m columns x n rows -> list of (x, y)."""
    return [(x, y) for y in range(n) for x in range(m)]


def checkerboard(ax, cells, s=1.0, tintA=None, tintB=None, signs=True,
                 ec=None, lw=1.4, fs=13):
    """Fill cells by (x+y)%2; optionally stamp +/- sign factor sigma."""
    tintA = tintA or PALETTE["tintA"]
    tintB = tintB or PALETTE["tintB"]
    for (x, y) in cells:
        even = (x + y) % 2 == 0
        panel(ax, x, y, s=s, fc=tintA if even else tintB, ec=ec, lw=lw)
        if signs:
            cx, cy = center(x, y, s)
            sym = "+" if even else "−"
            col = PALETTE["valley"] if even else PALETTE["mountain"]
            ax.text(cx, cy, sym, ha="center", va="center", color=col,
                    fontsize=fs, fontweight="bold", zorder=4)


# ---- edges: crease vs slit -------------------------------------------------
def shared_edge(c1, c2, s=1.0):
    """Endpoints of the shared side between two 4-adjacent cells."""
    (x1, y1), (x2, y2) = c1, c2
    if x1 != x2:  # horizontal neighbours -> vertical shared edge
        xe = max(x1, x2) * s
        y0 = y1 * s
        return (xe, y0), (xe, y0 + s)
    else:         # vertical neighbours -> horizontal shared edge
        ye = max(y1, y2) * s
        x0 = x1 * s
        return (x0, ye), (x0 + s, ye)


def crease_edge(ax, c1, c2, s=1.0, lw=3.2, z=5):
    p, q = shared_edge(c1, c2, s)
    ax.plot([p[0], q[0]], [p[1], q[1]], color=PALETTE["crease"],
            linewidth=lw, solid_capstyle="round", zorder=z)


def slit_edge(ax, c1, c2, s=1.0, lw=1.4, z=5):
    p, q = shared_edge(c1, c2, s)
    ax.plot([p[0], q[0]], [p[1], q[1]], color=PALETTE["slit"],
            linewidth=lw, dashes=(2, 2.4), zorder=z)


# ---- paths -----------------------------------------------------------------
def hc_path(ax, cells, s=1.0, closed=False, color=None, lw=1.8, z=6,
            dotted=True, marker=False):
    color = color or PALETTE["hc"]
    pts = [center(x, y, s) for (x, y) in cells]
    if closed:
        pts = pts + [pts[0]]
    xs, ys = zip(*pts)
    kw = dict(color=color, linewidth=lw, zorder=z)
    if dotted:
        kw["dashes"] = (1, 2.2)
        kw["solid_capstyle"] = "round"
    ax.plot(xs, ys, **kw)
    if marker:
        ax.plot(xs, ys, "o", color=color, markersize=3.5, zorder=z + 1)


def line(ax, p, q, color="#222", lw=1.6, dashes=None, z=4):
    kw = dict(color=color, linewidth=lw, zorder=z)
    if dashes:
        kw["dashes"] = dashes
    ax.plot([p[0], q[0]], [p[1], q[1]], **kw)


def mirror_line(ax, p, q, color=None, lw=1.6, z=3):
    color = color or PALETTE["ink"]
    line(ax, p, q, color=color, lw=lw, dashes=(5, 4), z=z)


# ---- arrows ----------------------------------------------------------------
def arrow(ax, p, q, color="#222", lw=2.2, z=7, mut=14, style="-|>"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, color=color,
                                 linewidth=lw, mutation_scale=mut, zorder=z,
                                 shrinkA=0, shrinkB=0))


def curved_arrow(ax, p, q, rad=0.3, color="#222", lw=2.0, z=7, mut=14):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", color=color,
                                 linewidth=lw, mutation_scale=mut, zorder=z,
                                 connectionstyle=f"arc3,rad={rad}",
                                 shrinkA=0, shrinkB=0))


def angle_arc(ax, c, r, theta1, theta2, color=None, lw=2.0, label=None,
              z=7, lab_r=None, fs=12):
    """Rotation arc from theta1->theta2 (degrees) about centre c."""
    color = color or PALETTE["chevron"]
    ax.add_patch(Arc(c, 2 * r, 2 * r, angle=0, theta1=min(theta1, theta2),
                     theta2=max(theta1, theta2), color=color, linewidth=lw,
                     zorder=z))
    # arrowhead at theta2
    a = np.radians(theta2)
    tip = (c[0] + r * np.cos(a), c[1] + r * np.sin(a))
    da = np.radians(theta2 - np.sign(theta2 - theta1) * 8)
    base = (c[0] + r * np.cos(da), c[1] + r * np.sin(da))
    ax.add_patch(FancyArrowPatch(base, tip, arrowstyle="-|>", color=color,
                                 mutation_scale=12, linewidth=lw, zorder=z,
                                 shrinkA=0, shrinkB=0))
    if label:
        lr = lab_r or (r + 0.28)
        mid = np.radians((theta1 + theta2) / 2.0)
        ax.text(c[0] + lr * np.cos(mid), c[1] + lr * np.sin(mid), label,
                ha="center", va="center", color=color, fontsize=fs, zorder=z)


# ---- text helpers ----------------------------------------------------------
def text(ax, x, y, s, color=None, fs=12, ha="center", va="center",
         weight="normal", z=10, bg=None):
    kw = dict(ha=ha, va=va, color=color or PALETTE["ink"], fontsize=fs,
              fontweight=weight, zorder=z)
    if bg:
        kw["bbox"] = dict(boxstyle="round,pad=0.25", fc=bg, ec="none")
    ax.text(x, y, s, **kw)


def title(ax, s, fs=14):
    ax.set_title(s, fontsize=fs, color=PALETTE["ink"], pad=10)


def node(ax, c, r=0.10, color=None, z=8, label=None, fs=11, lab_dy=0.0):
    color = color or PALETTE["node"]
    ax.add_patch(Circle(c, r, facecolor=color, edgecolor="white",
                        linewidth=1.0, zorder=z))
    if label:
        ax.text(c[0], c[1] + lab_dy, label, ha="center", va="center",
                color="white", fontsize=fs, zorder=z + 1)


def legend(ax, items, x, y, dy=0.42, fs=11):
    """items: list of (color, linestyle, label). linestyle in {'solid','dash','dot','fill'}."""
    for i, (color, ls, lab) in enumerate(items):
        yy = y - i * dy
        if ls == "fill":
            ax.add_patch(Rectangle((x, yy - 0.12), 0.34, 0.24, facecolor=color,
                                   edgecolor="none", zorder=10))
        else:
            dash = {"solid": None, "dash": (5, 3), "dot": (1, 2.2)}[ls]
            kw = dict(color=color, linewidth=2.6, zorder=10)
            if dash:
                kw["dashes"] = dash
            ax.plot([x, x + 0.34], [yy, yy], **kw)
        ax.text(x + 0.46, yy, lab, ha="left", va="center", color=PALETTE["ink"],
                fontsize=fs, zorder=10)
