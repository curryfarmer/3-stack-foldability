#!/usr/bin/env python3
"""render_twostack.py — matplotlib report figures for a 2-stack (RSPA Hamiltonian-circuit) pattern.

Two figure kinds, both styled by figstyle (the single source of truth shared with render_square +
enumerate_twist), so 2-stack / 2+1 / 3-stack report PNGs all look the same:

  - FOLDSHEET — the printable pattern a person folds: every grid edge classified as a CREASE (the
    Hamiltonian circuit's crossed edges — fold lines), a SLIT (uncrossed interior edge — cut), or the
    cut-around outer BOUNDARY; the single CUT EDGE that opens the loop is highlighted.
  - ANALYSIS — the circuit drawn as a directed loop with every turn's signed twist contribution
    labelled, titled with the total twist value and the FOLD/JAM verdict.

Reads a 2-stack result JSON (`results/*_2stack_*.json`: meta.m/n + solutions[{circuit, cutEdge,
twistValue, verdict}]). Reuses py/twostack.twist_value for the total — no re-search. Convention
matches the viewer (origin top-left, +y down). Cells are integer (x, y); centres (x+0.5, y+0.5);
edges are unit cell-boundary segments in corner coords.

Usage:
  python -m square.render.render_twostack results/6x4_2stack_dc0a9114.json --mode both --out scratch/2stack.png
  python -m square.render.render_twostack results/6x4_2stack_dc0a9114.json --id 3 --mode foldsheet --out fs.png
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # square/ on path
import _bootstrap  # noqa: E402,F401  (puts square/{engine,twist,render} on sys.path)

import figstyle as fs          # noqa: E402  (shared palette/grid/legend/save)
import twostack as T2          # noqa: E402  (twist_value — reused, not re-derived)


# ----------------------------------------------------------------- geometry ----

def _edge_key(a, b):
    """Corner-coord G1 segment shared by adjacent cells a, b (integer (x,y)). Returns
    ((cx1,cy1),(cx2,cy2)) with endpoints sorted, usable as a dict/set key."""
    ax, ay = a
    bx, by = b
    if ay == by:                                               # horizontal neighbours -> vertical edge
        x = max(ax, bx)
        seg = ((x, ay), (x, ay + 1))
    else:                                                      # vertical neighbours -> horizontal edge
        y = max(ay, by)
        seg = ((ax, y), (ax + 1, y))
    return tuple(sorted(seg))


def _creases(circuit):
    """Crease edge keys = the cell-boundary segments the closed circuit crosses (cyclic)."""
    out = set()
    n = len(circuit)
    for i in range(n):
        out.add(_edge_key(circuit[i], circuit[(i + 1) % n]))
    return out


def _interior_edges(m, n):
    """All interior cell-boundary segments (between two in-grid cells), as a set of edge keys."""
    out = set()
    for y in range(n):
        for x in range(m):
            if x + 1 < m:
                out.add(_edge_key((x, y), (x + 1, y)))
            if y + 1 < n:
                out.add(_edge_key((x, y), (x, y + 1)))
    return out


def _seg_pts(key):
    """Edge key -> ([x1,x2],[y1,y2]) for ax.plot."""
    (p, q) = key
    return [p[0], q[0]], [p[1], q[1]]


# ---------------------------------------------------------------- foldsheet ----

def _draw_circuit_path(ax, circuit, color, *, prominent=True):
    """Overlay the Hamiltonian circuit as a directed loop through cell centres (shared by the
    foldsheet and the analysis figures so the traversal is visible on every 2-stack render).
    `prominent=False` draws a thinner/lighter variant for laying on top of an already-busy
    foldsheet; the analysis figure (where the loop IS the subject) keeps the bold default."""
    from matplotlib.patches import FancyArrowPatch
    ctr = lambda c: (c[0] + 0.5, c[1] + 0.5)
    nc = len(circuit)
    scale, lw, alpha, ms = (11, 2.0, 1.0, 4.0) if prominent else (9, 1.6, 0.85, 3.0)
    for i in range(nc):
        p, q = ctr(circuit[i]), ctr(circuit[(i + 1) % nc])
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=scale,
                                     color=color, lw=lw, zorder=6, alpha=alpha,
                                     shrinkA=2, shrinkB=2))
    for c in circuit:
        p = ctr(c)
        ax.plot(p[0], p[1], "o", ms=ms, color=color, zorder=8)


def render_foldsheet(sol, m, n, out_path, *, title=None):
    """Printable 2-stack fold-sheet: creases / slits / boundary / highlighted cut edge + the
    Hamiltonian circuit path itself (directed loop through cell centres) + legend."""
    circuit = [tuple(c) for c in sol["circuit"]]
    crease = _creases(circuit)
    interior = _interior_edges(m, n)
    cut = tuple(sorted((tuple(sol["cutEdge"][0]), tuple(sol["cutEdge"][1])))) if sol.get("cutEdge") else None

    fig, ax = fs.new_grid_axes(m, n, extra_w=2.4, ticklabels=False)   # foldsheet: cells locate position
    fs.draw_grid_cells(ax, m, n)

    for key in interior:                                       # creases (fold) vs slits (cut)
        xs, ys = _seg_pts(key)
        if key in crease:
            ax.plot(xs, ys, color=fs.VLY, lw=3.0, solid_capstyle="round", zorder=6)
        else:
            ax.plot(xs, ys, color=fs.CUT, lw=2.2, dashes=fs.DASH[1], solid_capstyle="round", zorder=5)

    ax.add_patch(fs.Rectangle((0, 0), m, n, facecolor="none", edgecolor=fs.BOUNDARY,
                              lw=2.4, zorder=7))               # cut-around outer boundary

    if cut is not None:                                        # the one crease you cut to open the loop
        xs, ys = _seg_pts(cut)
        ax.plot(xs, ys, color=fs.JUMP, lw=3.6, solid_capstyle="round", zorder=8)

    PATH_C = fs.CHAIN[0]
    _draw_circuit_path(ax, circuit, PATH_C, prominent=False)

    tw = T2.twist_value(circuit)
    badge, bcolor = fs.verdict_badge(sol.get("verdict", {}).get("foldable"))
    ax.set_title(title or f"2-stack  {m}x{n}", color=fs.INK)

    handles = [
        fs.line_handle(fs.VLY, "crease (fold line)", lw=3.0),
        fs.line_handle(fs.CUT, "slit (interior cut)", ls=(0, fs.DASH[1])),
        fs.line_handle(fs.BOUNDARY, "cut around boundary", lw=2.4),
        fs.line_handle(fs.JUMP, "cut edge (opens the loop)", lw=3.0),
        fs.line_handle(PATH_C, "Hamiltonian circuit path"),
    ]
    fs.legend_panel(ax, handles)
    fs.draw_subnotes(ax, [f"twist = {tw:+d}    reflection={'✓' if sol.get('verdict',{}).get('reflection') else '✗'}",
                          f"verdict: {badge}"])
    return fs.save(fig, out_path)


# ----------------------------------------------------------------- analysis ----

def render_analysis(sol, m, n, out_path, *, title=None):
    """2-stack twist analysis: the circuit as a directed loop with per-turn signed contributions,
    a red/blue tile-parity background, and angles in units of π (standardised with the square
    track's other analysis figure, render_twist_2plus1.py)."""
    circuit = [tuple(c) for c in sol["circuit"]]
    nc = len(circuit)
    LOOP_C = fs.CHAIN[0]
    ctr = lambda c: (c[0] + 0.5, c[1] + 0.5)                   # cell -> centre

    fig, ax = fs.new_grid_axes(m, n, extra_w=2.6, ticklabels=False)
    fs.draw_grid_cells(ax, m, n, checker=True)                 # sigma = (-1)^(x+y) red/blue parity tint

    _draw_circuit_path(ax, circuit, LOOP_C)

    # per-vertex signed twist contribution (matches twostack.twist_value: total = sum over odd i
    # of ang minus sum over even i, so contrib_i = +ang if i odd else -ang; turn is at vertex i+1).
    for i in range(nc):
        p1, p2, p3 = circuit[i], circuit[(i + 1) % nc], circuit[(i + 2) % nc]
        v1 = (p2[0] - p1[0], p2[1] - p1[1])
        v2 = (p3[0] - p2[0], p3[1] - p2[1])
        dot = v1[0] * v2[0] + v1[1] * v2[1]
        cross = v1[0] * v2[1] - v1[1] * v2[0]
        ang = round(math.degrees(math.atan2(cross, dot))) * 2
        if ang == 0:
            continue
        contrib = ang if i % 2 else -ang
        piv = ctr(p2)
        ax.annotate(fs.pi_label(contrib), piv, textcoords="offset points", xytext=(4, -10),
                    fontsize=7.5, fontweight="bold", color=fs.POS if contrib > 0 else fs.NEG, zorder=10)

    if sol.get("cutEdge"):                                     # mark where the loop is cut open
        cut = tuple(sorted((tuple(sol["cutEdge"][0]), tuple(sol["cutEdge"][1]))))
        xs, ys = _seg_pts(cut)
        ax.plot(xs, ys, color=fs.JUMP, lw=3.6, solid_capstyle="round", zorder=9)

    tw = T2.twist_value(circuit)
    verdict = "FOLD (flat)" if tw == 0 else f"JAM (twist={fs.pi_label(tw)})"
    stem = title or f"2-stack  {m}x{n}"
    ax.set_title(f"{stem}   turn-angle balance:  twist = {fs.pi_label(tw)}  →  {verdict}")

    handles = [
        fs.line_handle(LOOP_C, "Hamiltonian circuit (fold loop)"),
        fs.line_handle(fs.JUMP, "cut edge (opens the loop)", lw=3.0),
        fs.line_handle(fs.POS, "+ / − signed turn contribution"),
    ]
    fs.legend_panel(ax, handles)
    return fs.save(fig, out_path)


# ---------------------------------------------------------------------- cli ----

def _pick(solutions, sid):
    """Choose the solution to render: by --id if given, else the first foldable, else the first."""
    if sid is not None:
        for s in solutions:
            if s.get("id") == sid:
                return s
        raise SystemExit(f"no solution id={sid} in file")
    for s in solutions:
        if s.get("verdict", {}).get("foldable"):
            return s
    return solutions[0]


def _outs(out_path, mode):
    """Map (out_path, mode) -> {kind: path}. 'both' splits into _foldsheet / _analysis siblings."""
    if mode != "both":
        return {mode: out_path}
    stem, ext = os.path.splitext(out_path)
    ext = ext or ".png"
    return {"foldsheet": f"{stem}_foldsheet{ext}", "analysis": f"{stem}_analysis{ext}"}


def main(argv=None):
    p = argparse.ArgumentParser(description="Render a 2-stack pattern as a report figure (foldsheet/analysis).")
    p.add_argument("json", help="2-stack result JSON (results/*_2stack_*.json)")
    p.add_argument("--id", type=int, default=None, help="solution id (default: first foldable, else first)")
    p.add_argument("--mode", choices=("foldsheet", "analysis", "both"), default="both")
    p.add_argument("--out", required=True, help="output PNG path ('both' -> _foldsheet/_analysis siblings)")
    ns = p.parse_args(sys.argv[1:] if argv is None else argv)

    data = json.load(open(ns.json, encoding="utf-8"))
    m, n = data["meta"]["m"], data["meta"]["n"]
    sol = _pick(data["solutions"], ns.id)
    label = f"2-stack  {m}x{n}  #{sol.get('id', '?')}"

    for kind, path in _outs(ns.out, ns.mode).items():
        if kind == "foldsheet":
            render_foldsheet(sol, m, n, path, title=label)
        else:
            render_analysis(sol, m, n, path, title=label + "   turn-angle balance")
        print(f"  {kind} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
