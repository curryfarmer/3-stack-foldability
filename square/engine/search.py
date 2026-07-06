"""search.py — exhaustive 3-stack enumerator.

Cells are (x, y) tuples internally; solution dicts use {"x":, "y":} so records serialize
to plain JSON consumable by the render/generate CLIs without a custom encoder.
"""

import os

import fold as Fold
import twist_jump
from lattice.square import SquareLattice

# ---- helpers ----

def _xy(c):
    return {"x": c[0], "y": c[1]}


# --- Stage 2: footprint enumeration ---

# L footprint templates now live on SquareLattice; re-exported for the enumerator below.
L_BASE = SquareLattice.L_BASE


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
        for d in SquareLattice.fold_directions():
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

# nH/nV parity rule + parallel-fold axis now live on SquareLattice (square symmetry).
# Re-exported so search internals and test_gates resolve the names with one body of record.
parallel_fold_axis = SquareLattice.parallel_fold_axis
parity_check = SquareLattice.parity_check
vector_parity_check = SquareLattice.vector_parity_check   # legacy non-orientation-aware column
set_fold_counts = SquareLattice.set_fold_counts            # unconditional nH/nV annotator


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
    shape = SquareLattice.exit_shape(cells)
    if shape is None:
        return False
    return shape == start_shape


# --- Stage 6: reflection ---

def reflection_check(chains):
    # Orientation-aware: seed the SHARED crease between each adjacent pair of chains as one
    # world segment, reflect each side to its far end, require the images to coincide as oriented
    # grid segments. Covers 2+1 (one pair) and 1+1+1 (the pairwise footprint creases). The old
    # gate seeded an arbitrary T,+1 at baseCells[0] and compared lossy (edge,sign) labels, which
    # false-passed jamming 2+1 folds (e.g. 6x5#1) — see Fold.reflection_verdict.
    res = Fold.reflection_verdict(chains)
    for d in res["pairs"]:
        chains[d["i"]]["finalVector"] = {"edge": d["imgI"]["edge"], "sign": d["imgI"]["sign"]}
        chains[d["j"]]["finalVector"] = {"edge": d["imgJ"]["edge"], "sign": d["imgJ"]["sign"]}
    for c in chains:
        c.setdefault("finalVector", None)   # guarantee the key exists for the solution emit
    return res["pass"]


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
    # 1+1+1 (all single cells): pairwise centroid-loop twist (the historic path, unchanged).
    if all(len(c["baseCells"]) == 1 for c in chains):
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
    # 2+1 (one domino + one monomino): jump-strand twist (Model B). Foldable <=> Tw == 0.
    res = twist_jump.twist_2plus1_from_chains(chains)
    if res["decided"]:
        return {"decided": True, "pass": res["pass"], "pairs": res["pairs"]}
    # anything else stays undecided (non-filtering) -- same shape as before.
    return {"decided": False, "pass": None, "pairs": []}


# --- Stage 8: D4 canonical hash ---

# D4 canonical dedup now lives on SquareLattice (the golden orbit counts ARE D4-orbit counts).
# Re-exported so search and test_gates resolve apply_transform / transform_arrow / canonical_hash
# by name while the bodies live in one place.
apply_transform = SquareLattice.apply_transform
transform_arrow = SquareLattice.transform_arrow
canonical_hash = SquareLattice.canonical_hash


# --- Candidate evaluation / admission (shared by serial + parallel paths) ---
#
# The serial and parallel paths share ONE gate evaluator and ONE admit step so the
# verdict logic exists exactly once. _evaluate_candidate is pure and returns JSON-plain
# data, so a worker process can produce candidates and the parent can replay dedup.

def _evaluate_candidate(chains, fp, decomp, m, n, store_all=False):
    """Run the per-candidate gates and build the solution record (no id, no dedup).

    Returns (gates_passed, sol). gates_passed in 0..3 mirrors the serial counter bumps
    (0 = failed exit; 1 = passed exit, failed parity; 2 = passed exit+parity, failed
    reflection; 3 = passed all). Deterministic.

    store_all=False (legacy): short-circuits on the first failing gate and emits a sol ONLY
    when gates_passed == 3, with the historic verdict block — byte-identical to past output.
    store_all=True (Phase A): NO pruning — every COVERED candidate yields a sol carrying the
    REAL gate verdicts plus the new `vectorParity` column, so the foldability tests become
    non-destructive filterable columns instead of pruners.
    """
    ev = exit_footprint_check(chains, fp["shape"])
    if not store_all and not ev:
        return 0, None
    pa = parity_check(chains)
    if not store_all and not pa:
        return 1, None
    rf = reflection_check(chains)
    if not store_all and not rf:
        return 2, None
    gates_passed = 3 if (ev and pa and rf) else 2 if (ev and pa) else 1 if ev else 0

    set_fold_counts(chains)          # ensure nH/nV on EVERY chain (parity_check may have bailed early)
    h = canonical_hash(fp, chains, m, n)
    twist = twist_check(chains)
    if store_all:
        verdict = {
            # "equal number of folds in each subchain" — the Phase-A baseline criterion.
            "arithmetic": len({len(c["foldArrows"]) for c in chains}) == 1,
            "exitFootprint": ev, "parity": pa,
            "vectorParity": vector_parity_check(chains),
            "reflection": rf,
            "twist": (twist["pass"] if twist["decided"] else None),
        }
    else:
        # Historic verdict literal (keys + order) — preserves byte-identical legacy JSON.
        verdict = {
            "arithmetic": True, "exitFootprint": True, "parity": True,
            "reflection": True,
            "twist": (twist["pass"] if twist["decided"] else None),
        }
    sol = {
        "id": None,
        "footprint": {
            "shape": fp["shape"], "rotation": fp["rotation"],
            "anchor": _xy(fp["anchor"]),
            "cells": [_xy(c) for c in fp["cells"]],
        },
        "decomposition": decomp["decomp"],
        "chains": [{
            "kind": c["kind"],
            "baseCells": [_xy(b) for b in c["baseCells"]],
            "foldArrows": list(c["foldArrows"]),
            "nH": c["nH"], "nV": c["nV"],
            "finalVector": c["finalVector"],
        } for c in chains],
        "twistPairs": twist["pairs"],
        "verdict": verdict,
        "canonicalHash": h,
    }
    return gates_passed, sol


def _admit(sol, solutions, dedup, ctx, opts, on_solution, next_id):
    """Dedup (first-seen) + assign sequential id + bump afterDedup/twistPass + append.

    The ONLY order-dependent step; for the parallel path it runs in the parent over the
    footprint-ordered candidate stream, so the result is byte-identical to serial.
    """
    h = sol["canonicalHash"]
    if opts.get("dedup"):
        if h in dedup:
            return
        dedup[h] = True
    ctx["afterDedup"] += 1
    if sol["verdict"]["twist"] is True:
        ctx["twistPass"] += 1
    sol["id"] = next_id[0]
    next_id[0] += 1
    solutions.append(sol)
    if on_solution:
        on_solution(sol)


# --- Multiprocessing (orthogonal toggle; jobs=1 routes through the serial path) ---

_CHUNKS_PER_WORKER = 4  # >1 chunk per worker balances uneven per-footprint cost

# Commutative ctx counters a worker accumulates locally and the parent sums.
_WORKER_CTX_KEYS = ("nodeCount", "candidateCount", "coveredCount",
                    "exitPass", "parityPass", "reflPass",
                    "footprintsTried", "decompCount")


def _resolve_jobs(opts):
    """Worker count: opts['jobs'] if set, else env FOLD_JOBS, else 1.
    Empty / non-int / < 1 all clamp to 1 (serial)."""
    j = opts.get("jobs")
    if j is None:
        j = os.environ.get("FOLD_JOBS", "")
    try:
        j = int(j)
    except (TypeError, ValueError):
        return 1
    return j if j >= 1 else 1


def _chunk_bounds(n, k):
    """Split range(n) into k contiguous [lo, hi) chunks, sizes differing by at most 1.
    Requires 1 <= k <= n so no chunk is empty."""
    base, extra = divmod(n, k)
    bounds = []
    lo = 0
    for i in range(k):
        hi = lo + base + (1 if i < extra else 0)
        bounds.append((lo, hi))
        lo = hi
    return bounds


def _run_footprint_chunk(payload):
    """Worker entry (module-level => picklable under the spawn start method).

    Enumerates a contiguous slice of footprints and returns its pre-dedup candidate
    records in serial order plus the commutative ctx counters. No dedup / id here — the
    parent replays those over the gathered, footprint-ordered stream.
    """
    m, n, K, opts, ordinal, i_start, i_end = payload
    store_all = opts.get("storeAll", False)
    footprints = enumerate_footprints(m, n, opts)
    local_ctx = {k: 0 for k in _WORKER_CTX_KEYS}
    records = []
    for footprint in footprints[i_start:i_end]:
        local_ctx["footprintsTried"] += 1
        for decomp in enumerate_decompositions(footprint, opts):
            local_ctx["decompCount"] += 1

            def on_candidate(chains, _fp=footprint, _decomp=decomp):
                gp, sol = _evaluate_candidate(chains, _fp, _decomp, m, n, store_all)
                if gp >= 1:
                    local_ctx["exitPass"] += 1
                if gp >= 2:
                    local_ctx["parityPass"] += 1
                if gp >= 3:
                    local_ctx["reflPass"] += 1
                if sol is not None:
                    records.append(sol)

            search_decomposition(m, n, K, decomp, on_candidate, local_ctx)
    return ordinal, records, local_ctx


def _search_parallel(m, n, K, opts, footprints, jobs, ctx, solutions, dedup, next_id):
    """Fan the per-footprint enumeration across processes, then replay dedup + id in the
    parent over the footprint-ordered candidate stream (byte-identical to serial)."""
    from concurrent.futures import ProcessPoolExecutor

    n_fp = len(footprints)
    n_chunks = min(n_fp, jobs * _CHUNKS_PER_WORKER)
    payloads = [(m, n, K, opts, ordinal, lo, hi)
                for ordinal, (lo, hi) in enumerate(_chunk_bounds(n_fp, n_chunks))]
    results = [None] * len(payloads)
    workers = min(jobs, len(payloads), os.cpu_count() or 1)  # never oversubscribe cores
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for ordinal, records, local_ctx in ex.map(_run_footprint_chunk, payloads):
            results[ordinal] = (records, local_ctx)  # index by ordinal => order-proof
    for records, local_ctx in results:
        for key in _WORKER_CTX_KEYS:
            ctx[key] += local_ctx[key]
        for sol in records:
            _admit(sol, solutions, dedup, ctx, opts, None, next_id)


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

    store_all = opts.get("storeAll", False)
    footprints = enumerate_footprints(m, n, opts)
    ctx["footprintsTotal"] = len(footprints)

    # Multiprocessing toggle: jobs>1 fans the per-footprint enumeration across processes
    # then replays dedup/id serially in the parent. Live callbacks force the serial path
    # (cooperative cancellation / streaming can't cross the process boundary cleanly).
    # Need >=2 footprints to split; worker count is capped at the chunk count, so having
    # fewer footprints than jobs just uses fewer workers (corner grids have only 6).
    jobs = _resolve_jobs(opts)
    if (jobs > 1 and len(footprints) >= 2
            and on_solution is None and is_cancelled is None):
        _search_parallel(m, n, K, opts, footprints, jobs, ctx, solutions, dedup, next_id)
        return solutions, ctx, None

    for footprint in footprints:
        if ctx["cancelled"]:
            break
        ctx["footprintsTried"] += 1
        for decomp in enumerate_decompositions(footprint, opts):
            if ctx["cancelled"]:
                break
            ctx["decompCount"] += 1

            def on_candidate(chains, _fp=footprint, _decomp=decomp):
                gp, sol = _evaluate_candidate(chains, _fp, _decomp, m, n, store_all)
                if gp >= 1:
                    ctx["exitPass"] += 1
                if gp >= 2:
                    ctx["parityPass"] += 1
                if gp >= 3:
                    ctx["reflPass"] += 1
                if sol is not None:
                    _admit(sol, solutions, dedup, ctx, opts, on_solution, next_id)

            search_decomposition(m, n, K, decomp, on_candidate, ctx)
            if is_cancelled and is_cancelled():
                ctx["cancelled"] = True

    return solutions, ctx, None
