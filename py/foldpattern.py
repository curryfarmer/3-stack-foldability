"""foldpattern.py — derive a physical make-pattern (creases / slits / rigid joins) for a
stored 3-stack solution, so it can be cut + folded from cardstock and labelled foldable / not.

This is the ground-truth harness for the 2+1 twist work: the cache leaves 2+1 `verdict.twist`
undecided, and entanglement is a 3D phenomenon the 2D reflection model can't show — so labels
must come from physically folding a card model. The search already emits a complete physical
recipe (`foldArrows` + replayable placements); this module turns it into a cut/fold pattern.

Key point: the crease/slit *set* (which grid edges fold vs cut) is recoverable from the replay
WITHOUT the per-panel HC ordering that blocks the twist computation. A crease is the geometric
fold-boundary edge between a cell and its reflected image in consecutive placements.

Edge classification (every interior grid edge is exactly one of):
  * CREASE — a cell `c` in placement P_k and its image `c'` in P_{k+1} are 4-adjacent; their
    shared edge is folded. Carries (chain, step, mountain/valley).
  * RIGID  — the internal edge of a 2-chain domino placement (its two cells stay attached and
    flat, never folded relative to each other). Neither cut nor folded.
  * SLIT   — any other interior edge (separates different chains, or same-chain non-consecutive
    panels). Physically cut.

Usage:
  python3 foldpattern.py --self-check         # assert partition over all cached 2+1 (and 1+1+1)
  python3 foldpattern.py <file> <id>          # print the pattern for one solution
"""
import json
import sys
import glob
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fold  # noqa: E402


# ---------- replay ----------

def replay_placements(base_cells, fold_arrows, m, n):
    """Ordered placements for one chain (base, then one per fold). Cells in grid coords.
    Cell order within a placement is preserved by reflect_cells, so index i in P_k maps to
    index i in P_{k+1} (a cell and its reflected image)."""
    base = [(c["x"], c["y"]) for c in base_cells]
    pl = fold.initial_placement(base)
    placements = [pl]
    active = pl
    for d in fold_arrows:
        active = fold.make_fold(active, d, m, n)
        if active is None:
            raise ValueError(f"fold {d} left grid at {base} / {fold_arrows}")
        placements.append(active)
    return placements


def norm_edge(a, b):
    """Canonical key for the grid edge between two 4-adjacent cells."""
    return tuple(sorted((tuple(a), tuple(b))))


def adjacent(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


def interior_edges(m, n):
    """All interior grid edges (shared between two in-grid cells)."""
    edges = set()
    for y in range(n):
        for x in range(m):
            if x + 1 < m:
                edges.add(norm_edge((x, y), (x + 1, y)))
            if y + 1 < n:
                edges.add(norm_edge((x, y), (x, y + 1)))
    return edges


# ---------- classification ----------

def classify(chains, m, n):
    """chains: list of {kind, baseCells, foldArrows}. Returns the pattern dict."""
    crease = {}   # edge -> {chain, step, mv}
    rigid = set()
    chain_cells = []
    chain_placements = []

    for ci, ch in enumerate(chains):
        pls = replay_placements(ch["baseCells"], ch["foldArrows"], m, n)
        chain_placements.append(pls)
        cells = set()
        for p in pls:
            cells.update(p["cells"])
        chain_cells.append(cells)

        # rigid: internal edges within each placement (2-chain dominoes)
        for p in pls:
            cs = p["cells"]
            for i in range(len(cs)):
                for j in range(i + 1, len(cs)):
                    if adjacent(cs[i], cs[j]):
                        rigid.add(norm_edge(cs[i], cs[j]))

        # crease: reflected-neighbour edges between consecutive placements
        for k in range(len(pls) - 1):
            a_cells, b_cells = pls[k]["cells"], pls[k + 1]["cells"]
            mv = "V" if (k % 2 == 0) else "M"   # alternate along the chain (paper sigma start)
            n_edges = 0
            for i in range(len(a_cells)):
                c, c2 = a_cells[i], b_cells[i]
                if adjacent(c, c2):
                    e = norm_edge(c, c2)
                    crease[e] = {"chain": ci, "step": k + 1, "mv": mv}
                    n_edges += 1
            if n_edges == 0:
                raise AssertionError(f"chain {ci} fold {k+1} produced no crease edge")

    all_int = interior_edges(m, n)
    crease_set = set(crease)
    slit = all_int - crease_set - rigid

    return {
        "m": m, "n": n,
        "chains": [{"kind": ch["kind"], "baseCells": [(c["x"], c["y"]) for c in ch["baseCells"]],
                    "foldArrows": ch["foldArrows"], "cells": chain_cells[i],
                    "placements": chain_placements[i]}
                   for i, ch in enumerate(chains)],
        "crease": crease, "rigid": rigid, "slit": slit, "interior": all_int,
    }


def check_partition(pat):
    """Assert crease/rigid/slit partition the interior edges, and chains tile the grid."""
    m, n = pat["m"], pat["n"]
    crease, rigid, slit, interior = set(pat["crease"]), pat["rigid"], pat["slit"], pat["interior"]
    errs = []
    if crease & rigid:
        errs.append(f"crease∩rigid={len(crease & rigid)}")
    if crease & slit:
        errs.append(f"crease∩slit={len(crease & slit)}")
    if rigid & slit:
        errs.append(f"rigid∩slit={len(rigid & slit)}")
    if (crease | rigid | slit) != interior:
        missing = interior - (crease | rigid | slit)
        extra = (crease | rigid | slit) - interior
        errs.append(f"partition!=interior (missing={len(missing)} extra={len(extra)})")
    covered = set()
    overlap = 0
    for ch in pat["chains"]:
        if covered & ch["cells"]:
            overlap += len(covered & ch["cells"])
        covered |= ch["cells"]
    if len(covered) != m * n or overlap:
        errs.append(f"cells cover {len(covered)}/{m*n} overlap={overlap}")
    return errs


def degree_hist(pat):
    """Degree histogram of the crease graph (cross-check vs known 1+1+1 reconstruction)."""
    deg = {}
    for (a, b) in pat["crease"]:
        deg[a] = deg.get(a, 0) + 1
        deg[b] = deg.get(b, 0) + 1
    hist = {}
    for v in deg.values():
        hist[v] = hist.get(v, 0) + 1
    return hist


# ---------- loading ----------

def load_solution(path, sol_id):
    data = json.load(open(path))
    meta = data["meta"]
    for s in data["solutions"]:
        if s["id"] == sol_id:
            return meta, s
    raise KeyError(f"id {sol_id} not in {path}")


def pattern_for(path, sol_id):
    meta, s = load_solution(path, sol_id)
    pat = classify(s["chains"], meta["m"], meta["n"])
    pat["meta"] = {"m": meta["m"], "n": meta["n"], "id": s["id"],
                   "shape": s["footprint"]["shape"], "decomp": s["decomposition"],
                   "canonicalHash": s.get("canonicalHash"), "K": meta["m"] * meta["n"] // 3}
    return pat


# ---------- CLI ----------

def self_check(files):
    total = 0
    fails = 0
    onep_hists = []
    for f in files:
        data = json.load(open(f))
        if not isinstance(data, dict) or "meta" not in data:
            continue
        if data["meta"].get("stacks") == 2:
            continue
        m, n = data["meta"]["m"], data["meta"]["n"]
        for s in data["solutions"]:
            pat = classify(s["chains"], m, n)
            errs = check_partition(pat)
            total += 1
            if errs:
                fails += 1
                print(f"  FAIL {os.path.basename(f)} #{s['id']} ({s['decomposition']}): {errs}")
            if s["decomposition"] == "1+1+1":
                onep_hists.append((m, n, degree_hist(pat)))
    print(f"\nedge-partition self-check: {total - fails}/{total} solutions OK")
    # 1+1+1 cross-check: 6x6 should be degHist {1:6, 2:30} (twist_diagnosis.md)
    for (m, n, h) in onep_hists:
        if (m, n) == (6, 6):
            ok = h.get(1) == 6 and h.get(2) == 30 and len(h) == 2
            print(f"  1+1+1 6x6 crease degHist={h}  expect {{1:6, 2:30}}  {'PASS' if ok else 'CHECK'}")
            break
    return fails == 0


def print_pattern(path, sol_id):
    pat = pattern_for(path, sol_id)
    mta = pat["meta"]
    print(f"{mta['m']}x{mta['n']} #{mta['id']} {mta['shape']} {mta['decomp']} K={mta['K']}")
    for i, ch in enumerate(pat["chains"]):
        print(f"  chain {i} [{ch['kind']}] base={ch['baseCells']} folds={''.join(ch['foldArrows'])}")
    print(f"  creases={len(pat['crease'])}  rigid={len(pat['rigid'])}  slits={len(pat['slit'])}"
          f"  (interior={len(pat['interior'])})")
    errs = check_partition(pat)
    print(f"  partition: {'OK' if not errs else errs}")


if __name__ == "__main__":
    args = sys.argv[1:]
    here = os.path.dirname(os.path.abspath(__file__))
    if args and args[0] == "--self-check":
        files = sorted(glob.glob(os.path.join(here, "..", "results", "*.json")))
        ok = self_check(files)
        sys.exit(0 if ok else 1)
    elif len(args) == 2:
        print_pattern(args[0], int(args[1]))
    else:
        print(__doc__)
