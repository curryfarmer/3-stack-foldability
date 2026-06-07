"""search.py — exhaustive 3-stack enumerator. Port of search.js (pure compute).

Mirrors the JS pipeline stage-for-stage so the two engines can be cross-checked.
Cells are (x, y) tuples internally; solution dicts use {"x":, "y":} for JSON parity
with the browser tool's loader.
"""

import json
import fold as Fold

# ---- helpers ----

def _xy(c):
    return {"x": c[0], "y": c[1]}


# --- Stage 2: footprint enumeration ---

# L base cells: corner at (0,0), arms; 4 rotations of D4 about the corner.
L_BASE = [
    [(0, 0), (1, 0), (0, 1)],     # rot 0
    [(0, 0), (0, 1), (-1, 0)],    # rot 1 (90 CW)
    [(0, 0), (-1, 0), (0, -1)],   # rot 2 (180)
    [(0, 0), (0, -1), (1, 0)],    # rot 3 (270 CW)
]


def enumerate_footprints(m, n, opts):
    out = []
    if opts["shapes"].get("L"):
        for rot in range(4):
            tpl = L_BASE[rot]
            for ay in range(n):
                for ax in range(m):
                    cells = [(x + ax, y + ay) for (x, y) in tpl]
                    if all(0 <= x < m and 0 <= y < n for (x, y) in cells):
                        if not opts.get("allowNonCorner"):
                            xs = [c[0] for c in cells]
                            ys = [c[1] for c in cells]
                            if min(xs) != 0 or min(ys) != 0:
                                continue
                        corner = cells[0]
                        arms = sorted(cells[1:], key=lambda c: (c[0], c[1]))
                        out.append({
                            "shape": "L", "rotation": rot, "anchor": (ax, ay),
                            "cells": [corner] + arms,
                            "cellRoles": ["corner", "arm", "arm"],
                        })
    if opts["shapes"].get("Rect"):
        for orient in ("H", "V"):
            tpl = [(0, 0), (1, 0), (2, 0)] if orient == "H" else [(0, 0), (0, 1), (0, 2)]
            for ay in range(n):
                for ax in range(m):
                    cells = [(x + ax, y + ay) for (x, y) in tpl]
                    if all(0 <= x < m and 0 <= y < n for (x, y) in cells):
                        if not opts.get("allowNonCorner"):
                            if ax != 0 or ay != 0:
                                continue
                        out.append({
                            "shape": "Rect", "rotation": 0 if orient == "H" else 1,
                            "anchor": (ax, ay), "cells": cells,
                            "cellRoles": ["end", "mid", "end"],
                        })
    return out


# --- Stage 3: decomposition enumeration ---

def enumerate_decompositions(footprint, opts):
    out = []
    cells = footprint["cells"]
    if footprint["shape"] == "L":
        corner, armA, armB = cells[0], cells[1], cells[2]
        if opts["decomps"].get("2+1"):
            adj = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
            pairs = [(corner, armA, armB), (corner, armB, armA), (armA, armB, corner)]
            for p0, p1, tail in pairs:
                if not adj(p0, p1):
                    continue
                out.append({
                    "decomp": "2+1",
                    "chains": [
                        {"kind": "2chain", "baseCells": [p0, p1]},
                        {"kind": "1chain", "baseCells": [tail]},
                    ],
                })
        if opts["decomps"].get("1+1+1"):
            out.append({
                "decomp": "1+1+1",
                "chains": [
                    {"kind": "1chain", "baseCells": [corner]},
                    {"kind": "1chain", "baseCells": [armA]},
                    {"kind": "1chain", "baseCells": [armB]},
                ],
            })
    else:  # Rect
        end0, mid, end1 = cells
        if opts["decomps"].get("2+1"):
            out.append({"decomp": "2+1", "chains": [
                {"kind": "2chain", "baseCells": [end0, mid]},
                {"kind": "1chain", "baseCells": [end1]},
            ]})
            out.append({"decomp": "2+1", "chains": [
                {"kind": "2chain", "baseCells": [mid, end1]},
                {"kind": "1chain", "baseCells": [end0]},
            ]})
        if opts["decomps"].get("1+1+1"):
            out.append({"decomp": "1+1+1", "chains": [
                {"kind": "1chain", "baseCells": [end0]},
                {"kind": "1chain", "baseCells": [mid]},
                {"kind": "1chain", "baseCells": [end1]},
            ]})
    return out


# --- Stage 4: connectivity pruning ---

def can_partition(component_sizes, sizes):
    N = len(sizes)
    if sum(component_sizes) != sum(sizes):
        return False

    def recur(idx, used):
        if idx == len(component_sizes):
            return used == (1 << N) - 1
        target = component_sizes[idx]
        sub = (1 << N) - 1
        while sub >= 0:
            if not (sub & used) and sub != 0:
                s = sum(sizes[i] for i in range(N) if sub & (1 << i))
                if s == target and recur(idx + 1, used | sub):
                    return True
            sub -= 1
        return False

    return recur(0, 0)


def connectivity_ok(reserved, m, n, remaining_sizes):
    component_sizes = []
    visited = set()
    for y in range(n):
        for x in range(m):
            if (x, y) in reserved or (x, y) in visited:
                continue
            size = 0
            stack = [(x, y)]
            while stack:
                cur = stack.pop()
                if cur in visited:
                    continue
                visited.add(cur)
                size += 1
                cx, cy = cur
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nb = (cx + dx, cy + dy)
                    if 0 <= nb[0] < m and 0 <= nb[1] < n and nb not in reserved and nb not in visited:
                        stack.append(nb)
            component_sizes.append(size)
    return can_partition(component_sizes, remaining_sizes)


# --- Stage 4 driver: DFS ---

def search_decomposition(m, n, K, decomposition, on_candidate, ctx):
    chains = [{
        "kind": c["kind"],
        "baseCells": list(c["baseCells"]),
        "placements": [],
        "foldArrows": [],
    } for c in decomposition["chains"]]
    total_cells = m * n

    order = sorted(range(len(chains)),
                   key=lambda i: (-(len(chains[i]["baseCells"]) * K),
                                  chains[i]["baseCells"][0][0], chains[i]["baseCells"][0][1]))
    chain_size = [K * len(c["baseCells"]) for c in chains]
    reserved = set()

    def search_chains(idx):
        ctx["nodeCount"] += 1
        if ctx.get("cancelled"):
            return
        if idx == len(chains):
            if len(reserved) == total_cells:
                ctx["coveredCount"] += 1
                on_candidate(chains)
            return
        real_idx = order[idx]
        chain = chains[real_idx]
        base = chain["baseCells"]
        for c in base:
            if c in reserved:
                return
        for c in base:
            reserved.add(c)
        chain["placements"] = [Fold.initial_placement(base)]
        chain["foldArrows"] = []
        dfs_chain(idx, real_idx, 1)
        for c in base:
            reserved.discard(c)
        chain["placements"] = []
        chain["foldArrows"] = []

    def dfs_chain(order_idx, real_idx, depth):
        if ctx.get("cancelled"):
            return
        if depth == K:
            remaining = [chain_size[order[i]] for i in range(order_idx + 1, len(chains))]
            if not remaining or connectivity_ok(reserved, m, n, remaining):
                search_chains(order_idx + 1)
            return
        chain = chains[real_idx]
        active = chain["placements"][-1]
        for d in ("L", "R", "U", "D"):
            if ctx.get("cancelled"):
                return
            np_ = Fold.make_fold(active, d, m, n)
            if np_ is None:
                continue
            if any(c in reserved for c in np_["cells"]):
                continue
            for c in np_["cells"]:
                reserved.add(c)
            chain["placements"].append(np_)
            chain["foldArrows"].append(d)
            ctx["candidateCount"] += 1
            dfs_chain(order_idx, real_idx, depth + 1)
            chain["foldArrows"].pop()
            chain["placements"].pop()
            for c in np_["cells"]:
                reserved.discard(c)

    search_chains(0)


# --- Stage 5: parity (orientation-aware vector symmetry) ---
# The A/B vector lies ALONG the inter-block crease. The per-chain count of folds whose crease
# line is PARALLEL to that A/B crease must be even (perpendicular count forced odd, total odd).
# L/R folds (nH) crease on VERTICAL lines; U/D folds (nV) on HORIZONTAL lines. So:
#   horizontally-adjacent bases (dx) -> A/B crease vertical   -> parallel folds = nH -> nH even
#   vertically-adjacent bases  (dy) -> A/B crease horizontal  -> parallel folds = nV -> nV even
# 2+1 only; 1+1+1 (two perpendicular corner creases) falls back to legacy nH-even/nV-odd.

def parallel_fold_axis(chains):
    """2+1 only: 'H' => require nH even, 'V' => require nV even. Else None (legacy)."""
    if len(chains) != 2:
        return None
    A, B = chains[0]["baseCells"], chains[1]["baseCells"]
    for a in A:
        for b in B:
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1:
                return "H" if a[0] != b[0] else "V"
    return None


def parity_check(chains):
    axis = parallel_fold_axis(chains)
    for c in chains:
        nH = sum(1 for a in c["foldArrows"] if a in ("L", "R"))
        nV = len(c["foldArrows"]) - nH
        c["nH"], c["nV"] = nH, nV
        if axis == "H":      # vertical A/B crease: parallel folds = nH must be even
            if nH % 2 != 0:
                return False
        elif axis == "V":    # horizontal A/B crease: parallel folds = nV must be even
            if nV % 2 != 0:
                return False
        else:
            if nH % 2 != 0 or nV % 2 != 1:
                return False
    return True


# --- Stage 5.5: exit footprint ---

def exit_footprint_check(chains, start_shape):
    cells = []
    for c in chains:
        for cell in c["placements"][-1]["cells"]:
            cells.append(cell)
    if len(cells) != 3:
        return False
    if len(set(cells)) != 3:
        return False
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    dx, dy = max(xs) - min(xs), max(ys) - min(ys)
    if (dx == 2 and dy == 0) or (dx == 0 and dy == 2):
        shape = "Rect"
    elif dx == 1 and dy == 1:
        shape = "L"
    else:
        return False
    return shape == start_shape


# --- Stage 6: reflection ---

def reflection_check(chains):
    ref = None
    for c in chains:
        base = c["baseCells"][0]
        v0 = {"x": base[0], "y": base[1], "edge": "T", "sign": 1}
        last = c["placements"][-1]
        vf = Fold.project_vector(v0, last["transformChain"])
        c["finalVector"] = {"edge": vf["edge"], "sign": vf["sign"]}
        if ref is None:
            ref = c["finalVector"]
        elif vf["edge"] != ref["edge"] or vf["sign"] != ref["sign"]:
            return False
    return True


# --- Stage 7: twist (pairwise-loop; decided only for all-1chain / 1+1+1) ---

def _chain_center_path(chain):
    pts = []
    for p in chain["placements"]:
        cs = p["cells"]
        sx = sum(c[0] + 0.5 for c in cs)
        sy = sum(c[1] + 0.5 for c in cs)
        k = len(cs) or 1
        pts.append((sx / k, sy / k))
    return pts


def _pair_loop_twist(path_a, path_b):
    import math
    pts = path_a + list(reversed(path_b))
    n = len(pts)
    odd = even = 0
    for i in range(n):
        p1, p2, p3 = pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        v1 = (p2[0] - p1[0], p2[1] - p1[1])
        v2 = (p3[0] - p2[0], p3[1] - p2[1])
        ang = 0
        if math.hypot(*v1) > 1e-9 and math.hypot(*v2) > 1e-9:
            dot = v1[0] * v2[0] + v1[1] * v2[1]
            cross = v1[0] * v2[1] - v1[1] * v2[0]
            ang = round(math.degrees(math.atan2(cross, dot)))
        ang *= 2
        if i % 2 == 0:
            even += ang
        else:
            odd += ang
    return odd - even


def twist_check(chains):
    if not all(len(c["baseCells"]) == 1 for c in chains):
        return {"decided": False, "pass": None, "pairs": []}
    paths = [_chain_center_path(c) for c in chains]
    pairs = []
    ok = True
    for i in range(len(chains)):
        for j in range(i + 1, len(chains)):
            tw = _pair_loop_twist(paths[i], paths[j])
            pairs.append({"i": i, "j": j, "tw": tw})
            if tw != 0:
                ok = False
    return {"decided": True, "pass": ok, "pairs": pairs}


# --- Stage 8: D4 canonical hash ---

def apply_transform(t, x, y, m, n):
    X, Y = x, y
    if t["flip"]:
        X = m - 1 - X
    rot = t["rot"]
    if rot == 0:
        return (X, Y)
    if rot == 1:
        return (Y, m - 1 - X)
    if rot == 2:
        return (m - 1 - X, n - 1 - Y)
    return (n - 1 - Y, X)


def transform_arrow(t, d):
    if t["flip"]:
        d = {"L": "R", "R": "L", "U": "U", "D": "D"}[d]
    for _ in range(t["rot"]):
        d = {"L": "U", "U": "R", "R": "D", "D": "L"}[d]
    return d


def canonical_hash(footprint, chains, m, n):
    best = None
    for rot in range(4):
        for flip in range(2):
            t = {"rot": rot, "flip": flip}
            fp = sorted([list(apply_transform(t, c[0], c[1], m, n)) for c in footprint["cells"]])
            chain_sigs = []
            for c in chains:
                base = sorted([list(apply_transform(t, b[0], b[1], m, n)) for b in c["baseCells"]])
                arrows = [transform_arrow(t, a) for a in c["foldArrows"]]
                chain_sigs.append({"kind": c["kind"], "base": base, "arrows": arrows})
            chain_sigs.sort(key=lambda s: (s["kind"], json.dumps(s["base"])))
            sig = json.dumps({"fp": fp, "chains": chain_sigs}, separators=(",", ":"))
            if best is None or sig < best:
                best = sig
    return best


# --- Top-level runner ---

def run(opts, on_solution=None, is_cancelled=None):
    m, n = opts["m"], opts["n"]
    ctx = {k: 0 for k in ("nodeCount", "candidateCount", "coveredCount", "exitPass",
                          "parityPass", "reflPass", "afterDedup", "twistPass",
                          "footprintsTried", "footprintsTotal", "decompCount")}
    ctx["cancelled"] = False
    solutions = []
    dedup = {}
    next_id = [1]

    # TEST gates (relaxed): removed the mn-even/%6 requirement, the K-even gate,
    # and the n>=4 gate so tiny/odd grids (e.g. 3x1) can be probed. Only mn%3==0
    # is kept — it is structural (K = mn/3 must be a positive integer to tile).
    if (m * n) % 3 != 0:
        return solutions, ctx, "mn not divisible by 3 (K must be integer)"
    K = (m * n) // 3
    if K < 1:
        return solutions, ctx, "K < 1 (empty grid)"

    footprints = enumerate_footprints(m, n, opts)
    ctx["footprintsTotal"] = len(footprints)

    for footprint in footprints:
        if ctx["cancelled"]:
            break
        ctx["footprintsTried"] += 1
        for decomp in enumerate_decompositions(footprint, opts):
            if ctx["cancelled"]:
                break
            ctx["decompCount"] += 1

            def on_candidate(chains, _fp=footprint, _decomp=decomp):
                if not exit_footprint_check(chains, _fp["shape"]):
                    return
                ctx["exitPass"] += 1
                if not parity_check(chains):
                    return
                ctx["parityPass"] += 1
                if not reflection_check(chains):
                    return
                ctx["reflPass"] += 1
                h = canonical_hash(_fp, chains, m, n)
                if opts.get("dedup"):
                    if h in dedup:
                        return
                    dedup[h] = True
                ctx["afterDedup"] += 1
                twist = twist_check(chains)
                if twist["decided"] and twist["pass"]:
                    ctx["twistPass"] += 1
                sol = {
                    "id": next_id[0],
                    "footprint": {
                        "shape": _fp["shape"], "rotation": _fp["rotation"],
                        "anchor": _xy(_fp["anchor"]),
                        "cells": [_xy(c) for c in _fp["cells"]],
                    },
                    "decomposition": _decomp["decomp"],
                    "chains": [{
                        "kind": c["kind"],
                        "baseCells": [_xy(b) for b in c["baseCells"]],
                        "foldArrows": list(c["foldArrows"]),
                        "nH": c["nH"], "nV": c["nV"],
                        "finalVector": c["finalVector"],
                    } for c in chains],
                    "twistPairs": twist["pairs"],
                    "verdict": {
                        "arithmetic": True, "exitFootprint": True, "parity": True,
                        "reflection": True,
                        "twist": (twist["pass"] if twist["decided"] else None),
                    },
                    "canonicalHash": h,
                }
                next_id[0] += 1
                solutions.append(sol)
                if on_solution:
                    on_solution(sol)

            search_decomposition(m, n, K, decomp, on_candidate, ctx)
            if is_cancelled and is_cancelled():
                ctx["cancelled"] = True

    return solutions, ctx, None
