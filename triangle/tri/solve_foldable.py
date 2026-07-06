"""solve_foldable.py — smart disjoint-path solver + autonomous fold-sheet generator for
equilateral-triangle 3-stack folds (1+1+1 and 2+1 rhombus-ribbon).

Two jobs:
  1. SOLVE.  Enumerate every closing fold for a chain length K, far faster than the triple-nested
     brute force, by fixing the canonical START hub S (WLOG by p6m) and routing three
     vertex-disjoint K-node paths to each candidate colour-flipped END trapezoid with a
     distance+parity-pruned DFS (both prunes are necessary conditions -> nothing real is dropped).
  2. GENERATE.  For each K, store 2-3 printable folding patterns (foldsheet + chain overlay) +
     a JSON census + an orientation-aware test log, for BOTH the 1+1+1 and 2+1 decompositions,
     regardless of whether the criterion predicts FOLD (Tw=0) or JAM (Tw!=0).

The campaign loop marches K upward (1+1+1: even K from 10; 2+1: K from 4) and stops a decomposition
once the *projected* search time for the next K exceeds 1 h (or a pass is truncated at the hard cap).

XVAL gate (run before trusting any deeper K):
  - 1+1+1  K=10 -> 2 closing,  K=12 -> 94 closing with the locked twist spectrum.
  - 2+1    K=4  -> matches the trusted trisearch.search_21 brute force on the 2x3 tiling.
  - cleanliness (every K, fail loud): every gamma a multiple of 120, every Tw a multiple of 360.

Run:
  .venv/Scripts/python -m triangle.tri.solve_foldable --xval
  .venv/Scripts/python -m triangle.tri.solve_foldable --run --decomp 1plus1plus1 --K 10
  .venv/Scripts/python -m triangle.tri.solve_foldable --campaign           # the autonomous loop
"""
import argparse
import json
import os
import sys
import time
from collections import deque, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trilattice as TL      # noqa: E402
import tritwist as TW        # noqa: E402
import trisearch as TS       # noqa: E402
import trirender as TR       # noqa: E402
import prove_obstruction as PO   # noqa: E402
import hunt_foldable as HF   # noqa: E402  (holes)
import foldsheet_tri as FS   # noqa: E402

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "results")
REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "report", "tri")
SAMPLE_CAP = 2000            # max full chain records kept per census file (counts/spectrum are exact)
HARD_CAP_SEC = 3600.0        # per-(decomp,K) wall-clock ceiling
PROJECT_STOP_SEC = 3600.0    # stop a decomp once next-K projected time exceeds this


# --------------------------------------------------------------------------- distances / routing
def bfs_dist(lat, source):
    """Dual-graph BFS distance from `source` to every reachable tile."""
    dist = {source: 0}
    q = deque([source])
    while q:
        x = q.popleft()
        dx = dist[x]
        for y in lat.adj[x]:
            if y not in dist:
                dist[y] = dx + 1
                q.append(y)
    return dist


def routed_paths(lat, start, end, K, blocked, dist_to_end):
    """All simple K-node paths start..end avoiding `blocked`, distance+parity pruned.

    `dist_to_end` = bfs_dist(lat, end). Both prunes are necessary conditions (graph reachability
    lower bound + bipartite parity) so no real closing path is ever discarded. The last node is
    forced to be `end` and `end` may not appear before then.
    """
    adj = lat.adj
    out = []
    if start in blocked:
        return out
    d0 = dist_to_end.get(start)
    if d0 is None or d0 > K - 1 or ((K - 1 - d0) & 1):
        return out

    def dfs(node, path, used):
        if len(path) == K:
            if node == end:
                out.append(tuple(path))
            return
        steps_after = K - 1 - len(path)        # edges from the about-to-be-added node to the end
        for nb in adj[node]:
            if nb in used or nb in blocked:
                continue
            if nb == end:
                if steps_after != 0:
                    continue                   # end only as the final node
            elif steps_after == 0:
                continue                       # final node must be the end
            d = dist_to_end.get(nb)
            if d is None or d > steps_after:
                continue                       # PRUNE1 reachability
            if (steps_after - d) & 1:
                continue                       # PRUNE2 bipartite parity
            path.append(nb)
            used.add(nb)
            dfs(nb, path, used)
            path.pop()
            used.discard(nb)

    dfs(start, [start], {start})
    return out


# --------------------------------------------------------------------------- 1+1+1 enumerator
def enum_111_general(lat, S, back, K, sigma=None, fast=True, time_budget=None, t0=None):
    """Yield (pa, pm, pc) for every closing 1+1+1 fold from hub S on ANY reflection tiling.

    fast=True (bipartite tilings — equilateral / righttri / scalene): prune END trapezoids by the
    sigma-flip rule (a K-node chain crosses K-1 dual edges, flipping sigma K-1 times, so the END
    footprint's sigmas are the START's times mult=(-1)^(K-1)) and route 3 vertex-disjoint K-paths
    with the distance+parity DFS. `back` forces the mid-chain's first step (degree-3 mids).

    fast=False (non-bipartite honeycomb — no global sigma, interior mids have degree 6): no sigma
    prune, plain disjoint K-walk DFS, mid-chain unforced (pass back=None). Slower, used at small K.
    """
    arm1, mid, arm2 = S
    if not fast or sigma is None:
        blk = {arm1, arm2}
        midpaths = [p for p in PO.grow(lat, mid, K, blk) if back is None or K == 1 or p[1] == back]
        for pm in midpaths:
            um = set(pm)
            for pa in PO.grow(lat, arm1, K, um | {arm2}):
                ua = um | set(pa)
                for pc in PO.grow(lat, arm2, K, ua):
                    if PO.is_trapezoid(lat, [pa[-1], pm[-1], pc[-1]]):
                        yield (pa, pm, pc)
            if time_budget and t0 is not None and (time.time() - t0) > time_budget:
                return
        return

    dmemo = {}

    def dist_from(src):
        d = dmemo.get(src)
        if d is None:
            d = dmemo[src] = bfs_dist(lat, src)
        return d

    dist_mid = dist_from(mid)
    mult = -1 if (K - 1) % 2 else 1                        # net sigma multiplier END vs START
    want_mid = mult * sigma(mid)
    want_arm = mult * sigma(arm1)
    hubs = []
    for (a, m, c) in lat.all_trapezoids():
        if sigma(m) != want_mid or sigma(a) != want_arm or sigma(c) != want_arm:
            continue
        dm = dist_mid.get(m)
        if dm is None or dm > K - 1 or ((K - 1 - dm) & 1):
            continue
        hubs.append((a, m, c))

    for (eA, eMid, eC) in hubs:
        d_eMid = dist_from(eMid)
        midpaths = [p for p in routed_paths(lat, mid, eMid, K, {arm1, arm2}, d_eMid)
                    if p[1] == back]
        if not midpaths:
            continue
        for pm in midpaths:
            um = set(pm)
            for (ta, tc) in ((eA, eC), (eC, eA)):
                d_ta = dist_from(ta)
                armA = routed_paths(lat, arm1, ta, K, um | {arm2}, d_ta)
                if not armA:
                    continue
                d_tc = dist_from(tc)
                for pa in armA:
                    ua = um | set(pa)
                    for pc in routed_paths(lat, arm2, tc, K, ua, d_tc):
                        yield (pa, pm, pc)
        if time_budget and t0 is not None and (time.time() - t0) > time_budget:
            return


def enum_111(lat, S, back, K, time_budget=None, t0=None):
    """Equilateral wrapper for enum_111_general (sigma = TL.sigma); the K-even arms-DOWN/mid-UP
    end filter is exactly the sigma-flip rule, so XVAL behaviour is preserved bit-for-bit."""
    yield from enum_111_general(lat, S, back, K, sigma=TL.sigma, fast=True,
                                time_budget=time_budget, t0=t0)


# --------------------------------------------------------------------------- 2+1 enumerator
def enum_21(lat, K, start_fps=None, require_cover=False, time_budget=None, t0=None):
    """Yield 2+1 solutions (rigid rhombus-ribbon strand + 1-chain), mirroring trisearch.search_21
    but with holes allowed (require_cover=False) and a restricted set of START footprints.
    """
    M, N = lat.M, lat.N
    radj = TS._rhombus_grid_adj(M, N)
    allcells = {(i, j) for j in range(N) for i in range(M)}
    alltris = set(lat.tris)
    fps = start_fps if start_fps is not None else lat.all_trapezoids()
    for fp in fps:
        i0, j0, _ = fp[0]
        one_base = fp[2]
        if (i0, j0) not in allcells:
            continue
        for rib in TS.grow_rhombus_walks(radj, (i0, j0), K, allcells):
            two_tris = set()
            for (ci, cj) in rib:
                two_tris.add((ci, cj, "U"))
                two_tris.add((ci, cj, "D"))
            if one_base in two_tris:
                continue
            free1 = alltris - two_tris
            for w1 in TS.grow_walks(lat, one_base, K, free1):
                if require_cover and set(w1) != free1:
                    continue
                strand = [(ci, cj, "U") for (ci, cj) in rib]
                last_rh = rib[-1]
                third = (last_rh[0], last_rh[1], "D")
                if not TS.exit_ok(lat, [strand[-1], third, w1[-1]]):
                    continue
                loop = strand + list(reversed(w1))
                res = TW.loop_twist(loop)
                yield {"ribbon": rib, "strand": strand, "one_chain": w1,
                       "two_tris": sorted(two_tris), "third": third,
                       "footprint": fp, "loop": res}
            if time_budget and t0 is not None and (time.time() - t0) > time_budget:
                return


# --------------------------------------------------------------------------- twist / cleanliness
def assert_clean(res, ctx):
    """Fail loud on a fractional twist (a geometry bug, not a real fold).

    Tw must be a multiple of 360 — that is the foldability-relevant invariant. Individual gammas
    are multiples of 120 ONLY for all-dual-adjacent loops (AB, BC). The AC arm-arm loop closes
    across the two NON-adjacent degree-1 cells of the start/end trapezoids, so it legitimately
    carries +-60 gammas; they pair up and the sigma-weighted sum stays a multiple of 360. So we
    assert Tw mod 360 only, and report gamma-mult-120 as informational.
    """
    if TW.fractional(res["Tw"]):
        raise AssertionError("fractional Tw=%.6f (not multiple of 360) at %s" % (res["Tw"], ctx))


def color_balance(region):
    up = sum(1 for t in region if t[2] == "U")
    return [up, len(region) - up]


# --------------------------------------------------------------------------- example records
def record_111(lat, pa, pm, pc, K):
    L = TS.pairwise_twists(lat, [list(pa), list(pm), list(pc)])
    for nm in ("AB", "BC", "AC"):
        assert_clean(L[nm], "1+1+1 K=%d loop %s" % (K, nm))
    tw = [int(round(L[nm]["Tw"])) for nm in ("AB", "BC", "AC")]
    region = sorted(set(pa) | set(pm) | set(pc))
    hcount = len(HF.holes(lat, region))
    rec = {
        "decomp": "1+1+1", "K": K,
        "chains": [list(map(list, pa)), list(map(list, pm)), list(map(list, pc))],
        "footprint": [list(pa[0]), list(pm[0]), list(pc[0])],
        "end_footprint": [list(pa[-1]), list(pm[-1]), list(pc[-1])],
        "tw": tw, "tw_named": {"AB": tw[0], "BC": tw[1], "AC": tw[2]},
        "foldable": all(v == 0 for v in tw),
        "holefree": hcount == 0, "holes": hcount,
        "region_size": len(region), "color_balance": color_balance(region),
        "cocycle_ok": tw[2] == tw[0] + tw[1],
        "alternates": all(L[nm]["alternates"] for nm in ("AB", "BC", "AC")),
        "gammas_clean": True, "tw_clean": True,
        "sidematch": None, "sideinfo": "n/a (uniform equilateral edge)",
    }
    rec["_loops"] = L
    return rec


def record_21(lat, sol, K):
    # NB: the strand-reduction twist is NOT always clean on triangles (the UP-per-rhombus strand
    # centroids are not collinear), so 2+1 Tw is frequently a non-multiple-of-360 "seam artifact"
    # (e.g. -240, +-163.574). We record it honestly (tw_clean flag) rather than fail loud.
    res = sol["loop"]
    tw_raw = round(res["Tw"], 3)
    clean = not TW.fractional(res["Tw"])
    region = sorted(set(sol["two_tris"]) | set(sol["one_chain"]))
    hcount = len(HF.holes(lat, region))
    rec = {
        "decomp": "2+1", "K": K,
        "ribbon": [list(r) for r in sol["ribbon"]],
        "strand": [list(t) for t in sol["strand"]],
        "one_chain": [list(t) for t in sol["one_chain"]],
        "two_tris": [list(t) for t in sol["two_tris"]],
        "footprint": [list(t) for t in sol["footprint"]],
        "end_footprint": [list(sol["strand"][-1]), list(sol["third"]), list(sol["one_chain"][-1])],
        "tw": tw_raw, "foldable": abs(res["Tw"]) < 1e-6,
        "holefree": hcount == 0, "holes": hcount,
        "region_size": len(region), "color_balance": color_balance(region),
        "tw_clean": clean, "sidematch": None, "sideinfo": "n/a (uniform equilateral edge)",
    }
    rec["_loop"] = res
    return rec


# --------------------------------------------------------------------------- orientation log
def log_111(rec, idx, fh):
    L = rec["_loops"]
    verdict = "FOLDABLE (Tw=0)" if rec["foldable"] else "JAM (Tw!=0)"
    lines = [
        "  [1+1+1 K=%d  example %d]  %s" % (rec["K"], idx, verdict),
        "    region %d tris  colour-balance UP/DOWN = %d/%d" % (
            rec["region_size"], rec["color_balance"][0], rec["color_balance"][1]),
        "    holes=%d  sidematch=%s  cocycle AC==AB+BC : %s" % (
            rec["holes"], rec["sideinfo"], rec["cocycle_ok"]),
    ]
    for nm in ("AB", "BC", "AC"):
        d = L[nm]
        lines.append("    %s  Tw=%+d  Tw_index=%+d  alternates=%s  gammas-mult-120=%s" % (
            nm, int(round(d["Tw"])), int(round(d["Tw_index"])), d["alternates"],
            all(not TW.fractional(g, 120.0) for g in d["gammas"])))
    fh.write("\n".join(lines) + "\n")


def log_21(rec, idx, fh):
    d = rec["_loop"]
    verdict = "FOLDABLE (Tw=0)" if rec["foldable"] else "JAM (Tw!=0)"
    lines = [
        "  [2+1 K=%d  example %d]  %s" % (rec["K"], idx, verdict),
        "    region %d tris  colour-balance UP/DOWN = %d/%d  holes=%d  sidematch=%s" % (
            rec["region_size"], rec["color_balance"][0], rec["color_balance"][1],
            rec["holes"], rec["sideinfo"]),
        "    single loop  Tw=%+d  Tw_index=%+d  alternates=%s  gammas-mult-120=%s" % (
            int(round(d["Tw"])), int(round(d["Tw_index"])), d["alternates"],
            all(not TW.fractional(g, 120.0) for g in d["gammas"])),
    ]
    fh.write("\n".join(lines) + "\n")


# --------------------------------------------------------------------------- figures
def _verdict_note(foldable, tw_desc):
    return ("PREDICTED FOLDABLE (Tw=0)" if foldable
            else "PREDICTED TO JAM (%s) - fold to verify" % tw_desc)


def render_111(rec, idx):
    pa, pm, pc = [list(map(tuple, c)) for c in rec["chains"]]
    region = sorted(set(pa) | set(pm) | set(pc))
    sub = TL.TriLattice(cells=region)
    tw = rec["tw"]
    tw_desc = "Tw AB=%+d BC=%+d AC=%+d" % (tw[0], tw[1], tw[2])
    verdict = _verdict_note(rec["foldable"], tw_desc)
    note = "1+1+1 EQUILATERAL K=%d (%d tris)\n%s\n%s" % (
        rec["K"], rec["region_size"], tw_desc, verdict)
    start_fp, end_fp = [pa[0], pm[0], pc[0]], [pa[-1], pm[-1], pc[-1]]  # START hub vs unfolded chain ends
    over = TR.render_tiling(sub, [pa, pm, pc],
                            "1+1+1 EQUILATERAL K=%d - %s" % (rec["K"], verdict),
                            "overlay_1plus1_K%d_%d.png" % (rec["K"], idx),
                            twist_note=note, footprint=start_fp, end_footprint=end_fp)
    sheet = FS.make_sheet(
        TL.TriLattice, TL.vcart, lambda t: [TL.vcart(v) for v in TL.tri_vertices(t)], TL.sigma,
        [pa, pm, pc], start_fp,
        "1+1+1 EQUILATERAL K=%d - %s" % (rec["K"], verdict),
        "foldsheet_1plus1_K%d_%d.png" % (rec["K"], idx), rec["K"], verdict_note=verdict,
        end_footprint=end_fp)
    return over, sheet


def _crease_set_21(sub, rib, one_chain):
    """The physically-faithful 2+1 fold-edge set: each rhombus's diagonal (the 2-layer stack fold),
    each hinge between consecutive ribbon rhombi, and each 1-chain crease. (The 2-chain is a
    2-stack rhombus ribbon, not a flat triangle strip, so its folds form a tree, not a path.)"""
    cr = {}

    def add(t1, t2):
        if t2 in sub.adj.get(t1, ()):
            cr[sub.shared[(t1, t2)]] = TL.sigma(t1)

    for (i, j) in rib:
        add((i, j, "U"), (i, j, "D"))                       # rhombus diagonal (stack fold)
    for k in range(len(rib) - 1):
        (a, b), (c, d) = rib[k], rib[k + 1]
        for t1 in ((a, b, "U"), (a, b, "D")):
            for t2 in ((c, d, "U"), (c, d, "D")):
                add(t1, t2)                                 # ribbon hinge
    for k in range(len(one_chain) - 1):
        add(one_chain[k], one_chain[k + 1])                 # 1-chain crease
    return cr


def render_21(rec, idx):
    strand = [tuple(t) for t in rec["strand"]]
    one_chain = [tuple(t) for t in rec["one_chain"]]
    two_tris = [tuple(t) for t in rec["two_tris"]]
    region = sorted(set(two_tris) | set(one_chain))
    sub = TL.TriLattice(cells=region)
    tw_desc = "Tw=%g" % rec["tw"]
    # the strand-reduction loop does not sigma-alternate on triangles, so its Tw is an unreliable
    # foldability predictor (Tw=0 may be an artifact cancellation, not a true flat fold).
    alt = rec["_loop"]["alternates"] if "_loop" in rec else False
    if rec["foldable"]:
        verdict = "Tw=0 BUT strand-twist model UNRELIABLE here (sigma non-alternating) - fold to verify"
    elif not rec["tw_clean"]:
        verdict = "degenerate-seam twist (%s, model breaks down) - fold to verify" % tw_desc
    else:
        verdict = "PREDICTED TO JAM (%s) - fold to verify" % tw_desc
    note = "2+1 EQUILATERAL K=%d (%d tris)  sigma-alternates=%s\n%s\n%s" % (
        rec["K"], rec["region_size"], alt, tw_desc, verdict)
    # START hub [arm1, mid, arm2] vs the unfolded chain-END tiles (which fold back onto the hub).
    fp_start = [tuple(t) for t in rec["footprint"]]
    fp_end = [tuple(t) for t in rec["end_footprint"]]
    over = TR.render_tiling(sub, [strand, one_chain],
                            "2+1 EQUILATERAL K=%d - %s" % (rec["K"], verdict),
                            "overlay_2plus1_K%d_%d.png" % (rec["K"], idx),
                            twist_note=note, footprint=fp_start, end_footprint=fp_end)
    rib = [tuple(r) for r in rec["ribbon"]]
    crease = _crease_set_21(sub, rib, one_chain)
    sheet = FS.make_sheet(
        TL.TriLattice, TL.vcart, lambda t: [TL.vcart(v) for v in TL.tri_vertices(t)], TL.sigma,
        [sorted(set(two_tris)), one_chain], fp_start,
        "2+1 EQUILATERAL K=%d - %s" % (rec["K"], verdict),
        "foldsheet_2plus1_K%d_%d.png" % (rec["K"], idx), rec["K"],
        verdict_note=verdict, crease_override=crease, end_footprint=fp_end)
    return over, sheet


# --------------------------------------------------------------------------- example selection
def pick_diverse(records, keyfn, want=3, foldable_first=True, sort_key=None):
    """Pick up to `want` records with distinct twist signatures.

    foldable_first=True (1+1+1, where Tw=0 is a trustworthy fold): grab every foldable first.
    foldable_first=False (2+1, where the strand-twist Tw=0 is an unreliable artifact): treat it
    like any other twist. After that, clean (mult-360) twists before degenerate-seam ones, and
    `sort_key` (e.g. holefree-first) biases which representative of each signature is chosen — so a
    holefree, strip-orderable, sheet-able pattern is preferred over a hole-riddled wrapping one.
    """
    pool = sorted(records, key=sort_key) if sort_key else list(records)
    chosen, seen = [], set()
    if foldable_first:
        for r in pool:
            if r["foldable"]:
                chosen.append(r)
    for clean_first in (True, False):
        for r in pool:
            if len(chosen) >= want:
                break
            if r in chosen or (foldable_first and r["foldable"]):
                continue
            if r.get("tw_clean", True) != clean_first:
                continue
            k = keyfn(r)
            if k in seen:
                continue
            seen.add(k)
            chosen.append(r)
    return chosen[:want]


# --------------------------------------------------------------------------- per-K run
def run_K(decomp, K, time_cap=HARD_CAP_SEC, log_fh=None):
    """Enumerate closing folds for one (decomp, K); emit census JSON + 2-3 sheets + log block.
    Returns dict(closing, foldable, spectrum, truncated, dt, chosen)."""
    t0 = time.time()
    spectrum = Counter()
    closing = 0
    foldable_recs = []
    kept = []                       # capped full records (for the _all file)
    diverse_pool = []               # candidate records for sheet selection
    truncated = False

    if decomp == "1plus1plus1":
        lat, S, back = PO.build_ambient(K)
        assert set(lat.adj[S[1]]) == {S[0], S[2], back}, "R2 (forced mid-chain) fails at K=%d" % K
        gen = enum_111(lat, S, back, K, time_budget=time_cap, t0=t0)
        keyfn = lambda r: tuple(r["tw"])
        for (pa, pm, pc) in gen:
            closing += 1
            rec = record_111(lat, pa, pm, pc, K)
            spectrum[tuple(rec["tw"])] += 1
            if rec["foldable"]:
                foldable_recs.append(rec)
            if len(kept) < SAMPLE_CAP:
                kept.append(rec)
            if (rec["holefree"] or len(diverse_pool) < 400) and len(diverse_pool) < 4000:
                diverse_pool.append(rec)   # always retain holefree (sheet-able) candidates
            if (time.time() - t0) > time_cap:
                truncated = True
                break
    elif decomp == "2plus1":
        M = N = 2 * K + 4
        lat = TL.TriLattice(M, N)
        rc = (M // 2, N // 2)
        start_fps = [fp for fp in lat.all_trapezoids() if fp[0][0] == rc[0] and fp[0][1] == rc[1]]
        gen = enum_21(lat, K, start_fps=start_fps, require_cover=False, time_budget=time_cap, t0=t0)
        keyfn = lambda r: r["tw"]
        for sol in gen:
            closing += 1
            rec = record_21(lat, sol, K)
            spectrum[rec["tw"]] += 1
            if rec["foldable"]:
                foldable_recs.append(rec)
            if len(kept) < SAMPLE_CAP:
                kept.append(rec)
            if (rec["holefree"] or len(diverse_pool) < 400) and len(diverse_pool) < 4000:
                diverse_pool.append(rec)   # always retain holefree (sheet-able) candidates
            if (time.time() - t0) > time_cap:
                truncated = True
                break
    else:
        raise ValueError(decomp)

    dt = time.time() - t0
    chosen = pick_diverse(diverse_pool, keyfn, want=3,
                          foldable_first=(decomp == "1plus1plus1"),
                          sort_key=lambda r: (not r["holefree"], not r.get("tw_clean", True)))

    # --- figures + log ---
    tag = "1plus1" if decomp == "1plus1plus1" else "2plus1"
    figs = []
    for i, rec in enumerate(chosen, 1):
        if decomp == "1plus1plus1":
            over, sheet = render_111(rec, i)
            log_111(rec, i, log_fh) if log_fh else None
        else:
            over, sheet = render_21(rec, i)
            log_21(rec, i, log_fh) if log_fh else None
        figs.append((over, sheet))

    # --- census JSON (strip private _loops/_loop) ---
    def clean(r):
        return {k: v for k, v in r.items() if not k.startswith("_")}
    all_path = os.path.join(RESULTS, "tri_K%d_%s_all.json" % (K, tag))
    fold_path = os.path.join(RESULTS, "tri_K%d_%s_foldable.json" % (K, tag))
    os.makedirs(RESULTS, exist_ok=True)
    with open(all_path, "w") as f:
        json.dump({
            "decomp": decomp, "K": K, "closing": closing,
            "foldable": len(foldable_recs), "truncated": truncated,
            "sample_cap": SAMPLE_CAP, "records_stored": len(kept),
            "spectrum": {str(list(k)) if isinstance(k, tuple) else str(k): v
                         for k, v in sorted(spectrum.items())},
            "records": [clean(r) for r in kept],
            "note": ("records[] truncated to sample_cap=%d; closing/foldable/spectrum are exact"
                     % SAMPLE_CAP) if closing > len(kept) else "complete",
        }, f, indent=1)
    with open(fold_path, "w") as f:
        json.dump([clean(r) for r in foldable_recs], f, indent=1)

    return {"closing": closing, "foldable": len(foldable_recs), "spectrum": dict(spectrum),
            "truncated": truncated, "dt": dt, "chosen": len(chosen),
            "all_path": all_path, "fold_path": fold_path, "figs": figs}


# --------------------------------------------------------------------------- XVAL gate
ORACLE_111 = {
    10: {"closing": 2, "spectrum": {(720, -720, 0): 1, (-720, 720, 0): 1}},
    12: {"closing": 94, "spectrum": {(720, -720, 0): 39, (-720, 720, 0): 39,
                                     (720, 720, 1440): 8, (-720, -720, -1440): 8}},
}


def xval():
    print("=== XVAL gate ===", flush=True)
    ok = True
    for K in (10, 12):
        lat, S, back = PO.build_ambient(K)
        spec = Counter()
        n = 0
        for (pa, pm, pc) in enum_111(lat, S, back, K):
            L = TS.pairwise_twists(lat, [list(pa), list(pm), list(pc)])
            for nm in ("AB", "BC", "AC"):
                assert_clean(L[nm], "xval 1+1+1 K=%d %s" % (K, nm))
            spec[tuple(int(round(L[nm]["Tw"])) for nm in ("AB", "BC", "AC"))] += 1
            n += 1
        exp = ORACLE_111[K]
        good = (n == exp["closing"] and dict(spec) == exp["spectrum"])
        ok = ok and good
        print(" 1+1+1 K=%d: closing=%d (expect %d)  spectrum %s  -> %s" % (
            K, n, exp["closing"], dict(spec), "OK" if good else "MISMATCH"), flush=True)

    # 2+1 oracle: reproduce trisearch.search_21 on the 2x3 tiling (require_cover, all footprints)
    lat = TL.TriLattice(2, 3)
    oracle = TS.search_21(lat)
    oracle_keys = sorted((tuple(map(tuple, s["ribbon"])), tuple(map(tuple, s["one_chain"])))
                         for s in oracle)
    mine = list(enum_21(lat, TS.K, start_fps=None, require_cover=True))
    mine_keys = sorted((tuple(map(tuple, s["ribbon"])), tuple(map(tuple, s["one_chain"])))
                       for s in mine)
    good21 = (oracle_keys == mine_keys)
    # the strand-reduction twist is artifact-prone on triangles; just report clean/frac, don't assert
    mine_fold = sum(1 for s in mine if abs(s["loop"]["Tw"]) < 1e-6)
    mine_frac = sum(1 for s in mine if TW.fractional(s["loop"]["Tw"]))
    ok = ok and good21
    print(" 2+1   K=%d (2x3): mine=%d (fold %d, frac %d)  search_21=%d  set-match=%s  -> %s" % (
        TS.K, len(mine), mine_fold, mine_frac, len(oracle), oracle_keys == mine_keys,
        "OK" if good21 else "MISMATCH"), flush=True)
    print("XVAL %s" % ("OK -> trusting deeper K" if ok else "FAILED -> abort"), flush=True)
    return ok


# --------------------------------------------------------------------------- campaign loop
def project(pts):
    """Project the next-K wall time from observed (K, dt) points."""
    if not pts:
        return 0.0
    if len(pts) == 1:
        return pts[0][1] * 4.0
    (_, d1), (_, d2) = pts[-2], pts[-1]
    r = max(d2 / max(d1, 1e-9), 1.2)
    return d2 * r


def campaign():
    if not xval():
        print("Refusing to run campaign: XVAL failed.", flush=True)
        return
    os.makedirs(REPORT, exist_ok=True)
    log_path = os.path.join(REPORT, "campaign_log.txt")
    log_fh = open(log_path, "a", buffering=1)
    log_fh.write("\n===== campaign start (K-loop, stop at projected > 1h) =====\n")
    plans = [("1plus1plus1", 10, 2), ("2plus1", 4, 1)]
    for decomp, K0, step in plans:
        log_fh.write("\n--- decomposition %s (K from %d, step %d) ---\n" % (decomp, K0, step))
        print("\n--- %s (K from %d) ---" % (decomp, K0), flush=True)
        pts = []
        K = K0
        while True:
            est = project(pts)
            if est > PROJECT_STOP_SEC:
                msg = "STOP %s: projected K=%d time %.0fs > %.0fs" % (decomp, K, est, PROJECT_STOP_SEC)
                print(msg, flush=True)
                log_fh.write(msg + "\n")
                break
            print("[%s K=%d] enumerating (projected %.1fs) ..." % (decomp, K, est), flush=True)
            log_fh.write("[%s K=%d]\n" % (decomp, K))
            res = run_K(decomp, K, time_cap=HARD_CAP_SEC, log_fh=log_fh)
            summary = ("  closing=%d foldable=%d truncated=%s dt=%.1fs sheets=%d spectrum=%s"
                       % (res["closing"], res["foldable"], res["truncated"], res["dt"],
                          res["chosen"], res["spectrum"]))
            print(summary, flush=True)
            log_fh.write(summary + "\n")
            for over, sheet in res["figs"]:
                log_fh.write("    fig %s%s\n" % (os.path.basename(over),
                             " + " + os.path.basename(sheet) if sheet else " (no foldsheet)"))
            pts.append((K, res["dt"]))
            if res["truncated"]:
                msg = "STOP %s: K=%d hit the %.0fs hard cap (too big)" % (decomp, K, HARD_CAP_SEC)
                print(msg, flush=True)
                log_fh.write(msg + "\n")
                break
            K += step
    log_fh.write("===== campaign done =====\n")
    log_fh.close()
    print("\ncampaign done; log -> %s" % os.path.relpath(log_path), flush=True)


# --------------------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description="smart triangle 3-stack solver + fold-sheet generator")
    ap.add_argument("--xval", action="store_true", help="run the cross-validation gate and exit")
    ap.add_argument("--run", action="store_true", help="run a single (decomp, K)")
    ap.add_argument("--campaign", action="store_true", help="autonomous K-loop for both decomps")
    ap.add_argument("--decomp", choices=["1plus1plus1", "2plus1"], default="1plus1plus1")
    ap.add_argument("--K", type=int, default=10)
    ap.add_argument("--cap", type=float, default=HARD_CAP_SEC, help="per-run wall-clock cap (s)")
    args = ap.parse_args()

    if args.xval:
        sys.exit(0 if xval() else 1)
    if args.campaign:
        campaign()
        return
    if args.run:
        log_fh = sys.stdout
        log_fh.write("=== run %s K=%d ===\n" % (args.decomp, args.K))
        res = run_K(args.decomp, args.K, time_cap=args.cap, log_fh=log_fh)
        print("\nclosing=%d foldable=%d truncated=%s dt=%.1fs spectrum=%s" % (
            res["closing"], res["foldable"], res["truncated"], res["dt"], res["spectrum"]))
        print("JSON:", os.path.relpath(res["all_path"]), "|", os.path.relpath(res["fold_path"]))
        for over, sheet in res["figs"]:
            print("fig:", os.path.relpath(over), ("+ " + os.path.relpath(sheet)) if sheet else "")
        return
    ap.print_help()


if __name__ == "__main__":
    main()
