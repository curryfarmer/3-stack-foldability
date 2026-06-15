"""render_vectors.py — visualise the engine's orientation-aware vector reflection.

For each crease SHARED by two adjacent chains, seed the SAME world director on that crease and
reflect it to each chain's far end (equal #reflections). The two images are drawn; they COINCIDE
as oriented grid segments iff the fold rejoins there (reflection PASS) — exactly what
Fold.reflection_verdict computes and what the engine's reflection_check now gates on. The faint
arrows are the per-fold cascade; the bold arrows are the final (stacked) images you compare.

2+1: one shared crease (2-chain strand cell adjacent to the 1-chain). 1+1+1: each footprint crease.

Usage:
  python render_vectors.py labels            # all decider sheets from results/twoplus1_labels.json
  python render_vectors.py <file> <id>       # one stored solution -> report/foldsheets/
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "explainer"))
import fold as Fold          # noqa: E402
import foldpattern as fp     # noqa: E402
import search as S           # noqa: E402
import lib                   # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

OUT_DIR = os.path.join(HERE, "..", "report", "foldsheets")
LABELS = os.path.join(HERE, "..", "results", "twoplus1_labels.json")
INK = [lib.PALETTE["chainA"], lib.PALETTE["chainB"], lib.PALETTE["chainC"]]
FILL = [lib.PALETTE["tintA"], lib.PALETTE["tintB"], "#eafaef"]


def sigma(x, y):
    return "+" if (x + y) % 2 == 0 else "−"


def edge_arrow(ax, x, y, edge, sign, color, L=0.5, lw=2.4, z=9, alpha=1.0, head=11):
    """Draw the director on the given edge of cell (x,y), pointing in the sign direction."""
    if edge in ("T", "B"):
        ey = y if edge == "T" else y + 1
        mx, my, dx, dy = x + 0.5, ey, sign * L / 2, 0
    else:  # L / R
        ex = x if edge == "L" else x + 1
        mx, my, dx, dy = ex, y + 0.5, 0, sign * L / 2
    ax.annotate("", xy=(mx + dx, my + dy), xytext=(mx - dx, my - dy),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                mutation_scale=head, alpha=alpha), zorder=z)


def _seg_str(v):
    """Human-readable oriented grid segment for the side panel."""
    x, y, e, s = v["x"], v["y"], v["edge"], v["sign"]
    if e == "T":
        pts, d = f"({x},{y})-({x+1},{y})", "+x" if s > 0 else "−x"
    elif e == "B":
        pts, d = f"({x},{y+1})-({x+1},{y+1})", "+x" if s > 0 else "−x"
    elif e == "L":
        pts, d = f"({x},{y})-({x},{y+1})", "+y" if s > 0 else "−y"
    else:
        pts, d = f"({x+1},{y})-({x+1},{y+1})", "+y" if s > 0 else "−y"
    return f"{pts} {d}"


def render(pat, out_path):
    m, n, mta = pat["m"], pat["n"], pat["meta"]
    chains = pat["chains"]
    cell_chain = {}
    for ci, ch in enumerate(chains):
        for c in ch["cells"]:
            cell_chain[c] = ci
    footprint = set()
    for ch in chains:
        footprint.update(ch["baseCells"])

    fig, ax = plt.subplots(figsize=(m * 0.66 + 6.0, max(n * 0.66 + 1.6, 5.2)))
    ax.set_aspect("equal")
    ax.axis("off")

    for (x, y) in [(x, y) for y in range(n) for x in range(m)]:
        ci = cell_chain.get((x, y))
        lib.panel(ax, x, y, fc=FILL[ci] if ci is not None else "white", ec="#ddd", lw=0.8)
        ax.text(x + 0.84, y + 0.84, sigma(x, y), ha="center", va="center",
                color="#bbb", fontsize=8, zorder=2)
    for (x, y) in footprint:
        lib.panel(ax, x, y, fc="none", ec=lib.PALETTE["hub"], lw=2.4)
    for ci, ch in enumerate(chains):
        bx, by = ch["baseCells"][0]
        ax.text(bx + 0.5, by + 0.5, "ABC"[ci], ha="center", va="center",
                color=INK[ci], fontsize=12, fontweight="bold", zorder=11)

    # --- reflection cascade, per shared crease ---
    verdict = Fold.reflection_verdict(chains)
    seedpairs = {}   # chain index -> (Pi, edge) for its cascade (from the pair it participates in)
    for d in verdict["pairs"]:
        eI, eJ = Fold._hub_seed(d["Pi"], d["Pj"])
        seedpairs[d["i"]] = (d["Pi"], eI)
        seedpairs[d["j"]] = (d["Pj"], eJ)
        # the shared seed crease (drawn once, neutral hub colour)
        edge_arrow(ax, d["Pi"][0], d["Pi"][1], eI, 1, lib.PALETTE["hub"],
                   L=0.6, lw=2.0, z=7, alpha=0.7, head=10)

    for ci, ch in enumerate(chains):
        if ci not in seedpairs:
            continue
        cell, edge = seedpairs[ci]
        v0 = {"x": cell[0], "y": cell[1], "edge": edge, "sign": 1}
        pls = ch["placements"]
        last = len(pls) - 1
        for k, p in enumerate(pls):
            v = Fold.project_vector(v0, p["transformChain"])
            is_end = (k == last)
            edge_arrow(ax, v["x"], v["y"], v["edge"], v["sign"], INK[ci],
                       L=0.66 if is_end else 0.42,
                       lw=3.0 if is_end else 1.3,
                       alpha=1.0 if is_end else 0.28,
                       z=10 if is_end else 6,
                       head=14 if is_end else 8)

    ax.set_xlim(-0.6, m + 0.4)
    ax.set_ylim(n + 0.4, -0.6)

    # ---- side panel ----
    tx = m + 0.8
    ax.text(tx, -0.2, f"{m}×{n}  #{mta['id']}   {mta['shape']} {mta['decomp']}",
            ha="left", va="top", fontsize=13, fontweight="bold", color=lib.PALETTE["ink"])
    ax.text(tx, 0.55, "orientation-aware vector reflection\n"
                      "seed the SHARED crease; reflect each side to its far end;\n"
                      "images must COINCIDE (same oriented grid segment) to rejoin",
            ha="left", va="top", fontsize=8.5, color="#666")

    yy = 2.0
    for pi, d in enumerate(verdict["pairs"]):
        ci, cj = d["i"], d["j"]
        ax.text(tx, yy, f"crease {'ABC'[ci]}–{'ABC'[cj]}  @ {d['Pi']}|{d['Pj']}:",
                ha="left", va="top", fontsize=9.5, fontweight="bold", color=lib.PALETTE["ink"])
        yy += 0.55
        ax.text(tx, yy, f"  {'ABC'[ci]} → {_seg_str(d['imgI'])}", ha="left", va="top",
                fontsize=9, color=INK[ci])
        yy += 0.5
        ax.text(tx, yy, f"  {'ABC'[cj]} → {_seg_str(d['imgJ'])}", ha="left", va="top",
                fontsize=9, color=INK[cj])
        yy += 0.5
        ok = d["pass"]
        ax.text(tx, yy, f"  → {'COINCIDE' if ok else 'DIFFERENT grid lines'}",
                ha="left", va="top", fontsize=9.5, fontweight="bold",
                color="#2ca02c" if ok else "#d83232")
        yy += 0.7

    yy += 0.2
    ax.text(tx, yy, f"reflection: {'PASS (rejoins)' if verdict['pass'] else 'FAIL (jams)'}",
            ha="left", va="top", fontsize=12, fontweight="bold",
            color="#2ca02c" if verdict["pass"] else "#d83232")
    yy += 0.7
    pred = mta.get("physical")
    if pred:
        ax.text(tx, yy, f"physical fold: {pred}", ha="left", va="top",
                fontsize=10, fontweight="bold", color="#444")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", dpi=130)
    plt.close(fig)
    return out_path


_OPTS = {"shapes": {"L": True, "Rect": True}, "decomps": {"1+1+1": True, "2+1": True},
         "allowNonCorner": False, "dedup": True}
_grid_cache = {}


def _grid_candidates(m, n):
    """All distinct closing candidates for (m,n), keyed by canonical hash, with GRID-VALID chains
    (baseCells as [{x,y}] in the actual grid frame — unlike the D4-canonical coords in the stored
    hash, which aren't replayable). Used to recover a renderable pattern for a labelled decider."""
    if (m, n) in _grid_cache:
        return _grid_cache[(m, n)]
    out = {}
    K = m * n // 3
    for footprint in S.enumerate_footprints(m, n, _OPTS):
        for decomp in S.enumerate_decompositions(footprint, _OPTS):
            ctx = {"nodeCount": 0, "candidateCount": 0, "coveredCount": 0, "cancelled": False}

            def on_candidate(chains, _fp=footprint):
                if not S.exit_footprint_check(chains, _fp["shape"]):
                    return
                h = S.canonical_hash(_fp, chains, m, n)
                if h in out:
                    return
                out[h] = [{"kind": c["kind"],
                           "baseCells": [{"x": b[0], "y": b[1]} for b in c["baseCells"]],
                           "foldArrows": list(c["foldArrows"])} for c in chains]

            S.search_decomposition(m, n, K, decomp, on_candidate, ctx)
    _grid_cache[(m, n)] = out
    return out


def pat_from_label(entry):
    """Recover a renderable pattern for a labelled decider by matching its canonical hash to a
    grid-valid enumerated candidate (the stored hash's coords are canonical, not replayable)."""
    m, n = (int(v) for v in entry["grid"].split("x"))
    chains = _grid_candidates(m, n).get(entry["canonicalHash"])
    if chains is None:
        raise KeyError(f"no grid-valid candidate matches hash for {entry['grid']}#{entry['id']}")
    pat = fp.classify(chains, m, n)
    sizes = sorted((len(c["baseCells"]) for c in chains), reverse=True)
    phys = {True: "FOLD", False: "JAM"}.get(entry.get("foldable"))
    pat["meta"] = {"m": m, "n": n, "id": entry["id"], "shape": entry["shape"],
                   "decomp": "+".join(str(s) for s in sizes), "K": m * n // 3,
                   "physical": phys}
    return pat


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "labels":
        labels = json.load(open(LABELS))
        for e in labels:
            out = os.path.join(OUT_DIR, f"vectors_{e['grid']}_{e['id']}.png")
            print("wrote", render(pat_from_label(e), out))
    elif len(args) == 2:
        pat = fp.pattern_for(args[0], int(args[1]))
        base = os.path.splitext(os.path.basename(args[0]))[0].split("_")[0]
        out = os.path.join(OUT_DIR, f"vectors_{base}_{args[1]}.png")
        print("wrote", render(pat, out))
    else:
        print(__doc__)
