"""find_example.py — find ONE concrete 3-stack fold example per case and render it.

Produces a starting footprint + a CLOSING fold (region reflects back to a congruent trapezoid),
rendered as a chain-overlay PNG + a printable foldsheet PNG, regardless of whether the twist
criterion predicts FOLD or JAM. Covers four tilings x two decompositions x two hole modes:

  --tiling {equilateral,righttri,scalene,hex}
  --decomp {1plus1plus1,2plus1}
  --holes  {allow,none}          (none = simply-connected region, no enclosed holes)
  --K / --kcap / --hub / --budget

Edge-type matching (short<->short etc.) needs NO separate gate: reflection_closes_111 already
implies the YYR position+direction condition on every tiling (each chain's end folds onto its start
as an orientation-consistent congruent copy; the START-vs-END long/short "seam swap" only touches
rigid hub-trapezoid joins that never re-bind, so it is harmless). 2+1 on righttri/scalene/hex uses
the generalized domino model (domino21) with the PATH-FOLLOWING twist (the only well-defined sigma
on non-bipartite honeycomb); it is a model prediction, not a proof. Equilateral keeps the validated
solvers (solve_foldable.enum_111/enum_21).

Run:
  .venv/Scripts/python -m triangle.tri.find_example --tiling hex --decomp 1plus1plus1 --holes allow
  .venv/Scripts/python -m triangle.tri.find_example --all          # every case, summary table
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trilattice as TL       # noqa: E402
import tritwist as TW         # noqa: E402
import prove_obstruction as PO  # noqa: E402
import hunt_foldable as HF    # noqa: E402
import foldsheet_tri as FS    # noqa: E402
import render_general as RG   # noqa: E402
import righttri as RT         # noqa: E402
import scalene as SC          # noqa: E402
import hexlattice as HX       # noqa: E402
import domino21 as D21        # noqa: E402
import solve_foldable as SF   # noqa: E402
import foldclose as FC        # noqa: E402  physical closure gate for 1+1+1 (reflection coincidence)
import foldsim as FSIM        # noqa: E402  printed-sheet flat-fold gate for 2+1 (domino-rigid)
import seam_filter as SFILT   # noqa: E402  post-emission START<->END seam-match filter (no engine math)

REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "report", "tri")
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "results")
_REPORT_BASE, _RESULTS_BASE = REPORT, RESULTS


def set_outdir(sub):
    """Park every figure + JSON under a subfolder (e.g. a date). Redirects find_example AND the
    sub-renderers (foldsheet_tri / render_general / trirender all share their module OUT)."""
    global REPORT, RESULTS
    REPORT = os.path.join(_REPORT_BASE, sub)
    RESULTS = os.path.join(_RESULTS_BASE, sub)
    os.makedirs(REPORT, exist_ok=True)
    os.makedirs(RESULTS, exist_ok=True)
    FS.OUT = REPORT
    RG.OUT = REPORT
    SF.TR.OUT = REPORT      # equilateral overlay renderer (trirender)
    SF.FS.OUT = REPORT      # equilateral sheet renderer (same foldsheet_tri module)

# equilateral rendering adapter: expose the module-level hooks the general renderer expects
# (tile_cart/centroid/sigma), so equilateral 2+1 can use the SAME fixed general path as the others.
import types as _types                                       # noqa: E402
_EQMOD = _types.SimpleNamespace(
    tile_cart=lambda t: [TL.vcart(v) for v in TL.tri_vertices(t)],
    centroid=TL.centroid, sigma=TL.sigma, vcart=TL.vcart)

# per-tiling rendering hooks for the GENERAL path. Equilateral 1+1+1 still uses the SF renderer;
# equilateral 2+1 now uses this general path (unified domino model).
GEN = {
    "equilateral": dict(mod=_EQMOD, LatClass=TL.TriLattice, vcart=TL.vcart,
                        tile_cart=_EQMOD.tile_cart, sigma=TL.sigma, cent=TL.centroid, interior_deg=3,
                        label="EQUILATERAL"),
    "righttri": dict(mod=RT, LatClass=RT.RightTriLattice, vcart=RT.vcart,
                     tile_cart=RT.tile_cart, sigma=RT.sigma, cent=RT.centroid, interior_deg=3,
                     label="45-45-90 RIGHT-ISO"),
    "scalene":  dict(mod=SC, LatClass=SC.ScaleneLattice, vcart=SC.vkey_cart,
                     tile_cart=SC.tile_cart, sigma=SC.sigma, cent=SC.centroid, interior_deg=3,
                     label="30-60-90 SCALENE"),
    "hex":      dict(mod=HX, LatClass=HX.HexLattice, vcart=HX.vkey_cart,
                     tile_cart=HX.tile_cart, sigma=HX.sigma, cent=HX.centroid, interior_deg=6,
                     label="HEXAGON"),
}

# default (start K, step, K-cap) per (tiling, decomp). Known first-closing K from prior scans:
# equilateral 1+1+1=10, righttri HL=12, scalene omitMG=14; hex + all non-equilateral 2+1 unknown.
KPLAN = {
    ("equilateral", "1plus1plus1"): (10, 2, 16),
    ("equilateral", "2plus1"):      (4, 1, 9),
    ("righttri", "1plus1plus1"):    (12, 1, 18),   # step 1: K-parity law — seam-clean (proper)
                                                   # arrivals exist ONLY at odd K; the old even-only
                                                   # step 2 was structurally blind to them. Start 12
                                                   # (first K with closing cands; K=11 yields none)
    ("righttri", "2plus1"):         (3, 1, 8),
    ("scalene", "1plus1plus1"):     (14, 2, 20),
    ("scalene", "2plus1"):          (3, 1, 8),
    ("hex", "1plus1plus1"):         (4, 1, 10),
    ("hex", "2plus1"):              (3, 1, 8),
}


# --------------------------------------------------------------------------- twist helper
def pairwise(chains, cent, sig):
    """Three theta-graph pairwise-loop twists. `sig` is a callable (bipartite) or "path"."""
    names, pairs, out = ["AB", "BC", "AC"], [(0, 1), (1, 2), (0, 2)], {}
    for nm, (i, j) in zip(names, pairs):
        loop = list(chains[i]) + list(reversed(chains[j]))
        s = TW.path_sigma(len(loop)) if sig == "path" else sig
        out[nm] = TW.loop_twist(loop, cent=cent, sigma=s)
    return out


def central_trapezoid(lat, interior_deg):
    cx = sum(c[0] for c in lat.cent.values()) / len(lat.cent)
    cy = sum(c[1] for c in lat.cent.values()) / len(lat.cent)
    interior = [t for t in lat.tris if len(lat.adj[t]) >= interior_deg]
    mid = min(interior, key=lambda t: (lat.cent[t][0] - cx) ** 2 + (lat.cent[t][1] - cy) ** 2)
    return next(f for f in lat.all_trapezoids() if f[1] == mid)


def central_hubs(lat, interior_deg, n):
    """The n most-central start trapezoids (distinct hubs). Each interior tile can be the middle of
    several trapezoids (different arm pairs), and nearby mids give more — a single central hub yields
    only ~1 distinct foldable 2+1 REGION, so covering a few hubs is how a 2nd example is found."""
    cx = sum(c[0] for c in lat.cent.values()) / len(lat.cent)
    cy = sum(c[1] for c in lat.cent.values()) / len(lat.cent)
    interior = {t for t in lat.tris if len(lat.adj[t]) >= interior_deg}
    traps = [f for f in lat.all_trapezoids() if f[1] in interior]
    traps.sort(key=lambda f: (lat.cent[f[1]][0] - cx) ** 2 + (lat.cent[f[1]][1] - cy) ** 2)
    return traps[:n]


# --------------------------------------------------------------------------- enumerators
def gen_111(tiling, K, hub, stats=None):
    """(lat, iterator of cand) for a general 1+1+1 case (righttri/scalene/hex).

    `stats`, if given, is mutated in place with "tried" (raw pairwise-enumerated candidates) and
    "closure_pass" (passed reflection_closes_111 -- same count as what's yielded)."""
    g = GEN[tiling]
    if tiling == "righttri":
        lat, S, back = RT.build_ambient_right(K, hub=hub or "HL")
        sig, fast = RT.sigma, True
    elif tiling == "scalene":
        lat, S, back = SC.build_ambient_scalene(K, hub=hub or "omitMG")
        sig, fast = SC.sigma, True
    else:  # hex (non-bipartite)
        lat, S, back = HX.build_ambient_hex(K)
        sig, fast = None, False
    # Twist is scored with LOOP-INDEX sigma (path_sigma), not the tiling's bipartite sigma. On a
    # non-alternating pairwise loop the bipartite sigma reads a spurious Tw=0 (it fails to alternate
    # round the loop), mislabelling a physically TWISTED fold as foldable — the righttri K=12 folds
    # 22924/74271 both engine-Tw0 yet physically twist. Loop-index sigma matches ALL 1+1+1 physical
    # ground truth (righttri K12 jams, scalene folds, eq obstruction). `sig` above stays bipartite:
    # enum_111_general uses it only for the END-footprint parity/reachability prune, not for twist.
    # See docs/research/GROUND_TRUTH_folds.md and nonsquare_construction.md.
    twsig = "path"

    def it():
        for (pa, pm, pc) in SF.enum_111_general(lat, S, back, K, sigma=sig, fast=fast):
            if stats is not None:
                stats["tried"] += 1
            chains = [list(pa), list(pm), list(pc)]
            if not FC.reflection_closes_111(lat, chains):    # physical closure gate
                continue
            if stats is not None:
                stats["closure_pass"] += 1
            L = pairwise(chains, g["cent"], twsig)
            tw = [int(round(L[nm]["Tw"])) for nm in ("AB", "BC", "AC")]
            yield {"decomp": "1plus1plus1", "chains": chains,
                   "footprint": [pa[0], pm[0], pc[0]],
                   "end_footprint": [pa[-1], pm[-1], pc[-1]],
                   "region": set(pa) | set(pm) | set(pc), "tw": tw,
                   "foldable": all(v == 0 for v in tw),
                   "tw_desc": "Tw AB=%+d BC=%+d AC=%+d" % (tw[0], tw[1], tw[2])}
    return lat, it()


def gen_21(tiling, K, hubs=1, stats=None):
    """(lat, iterator of cand) for a general 2+1 case (equilateral/righttri/scalene/hex). `hubs` = how
    many distinct central start trapezoids to enumerate from (1 = the single most-central hub, the
    single-example default; gen_testset passes more so a 2nd distinct foldable region can surface).

    `stats`, if given, is passed through to domino21.enum_domino_21 (see its docstring for keys)."""
    g = GEN[tiling]
    if tiling == "righttri":
        lat = RT.RightTriLattice(2 * K + 4, 2 * K + 4)
    elif tiling == "scalene":
        lat = SC.ScaleneLattice(faces=TL.triangle_cells(2 * K + 6))
    elif tiling == "equilateral":
        lat = TL.TriLattice(2 * K + 4, 2 * K + 4)
    else:
        lat = HX.HexLattice(R=K + 2)
    hub_list = central_hubs(lat, g["interior_deg"], hubs)

    def it():
        for S in hub_list:
            for sol in D21.enum_domino_21(lat, S, K, cent=g["cent"], stats=stats):
                r = sol["loop"]
                tw = round(r["Tw"], 3)
                yield {"decomp": "2plus1", "chains": [sol["strand"], sol["one_chain"]],
                       "partners": sol["partners"], "two_tris": sol["two_tris"],
                       "footprint": sol["footprint"], "end_footprint": sol["end_footprint"],
                       "region": set(sol["two_tris"]) | set(sol["one_chain"]), "tw": tw,
                       "foldable": abs(r["Tw"]) < 1e-6, "tw_desc": "Tw(path)=%g" % tw}
    return lat, it()


def gen_eq(decomp, K, stats=None):
    """(lat, iterator of cand) for equilateral; reuses solve_foldable records (carry rec for SF render).

    `stats`, if given, is mutated/threaded the same way as gen_111/gen_21 (see their docstrings)."""
    if decomp == "1plus1plus1":
        lat, S, back = PO.build_ambient(K)

        def it():
            for (pa, pm, pc) in SF.enum_111(lat, S, back, K):
                if stats is not None:
                    stats["tried"] += 1
                if not FC.reflection_closes_111(lat, [list(pa), list(pm), list(pc)]):
                    continue                                  # physical closure gate (additive on eq)
                if stats is not None:
                    stats["closure_pass"] += 1
                rec = SF.record_111(lat, pa, pm, pc, K)
                yield {"decomp": decomp, "rec": rec, "region": set(pa) | set(pm) | set(pc),
                       "foldable": rec["foldable"],
                       "tw_desc": "Tw AB=%+d BC=%+d AC=%+d" % tuple(rec["tw"])}
        return lat, it()
    # 2+1: unified onto the general domino model (the legacy rhombus enum_21 used an incompatible
    # footprint convention — its trapezoid `mid` is a bridge tile outside the region — and its
    # rhombus-diagonal-as-crease over-folded the rigid domino). gen_21 + foldsim is the correct path.
    return gen_21("equilateral", K, stats=stats)


def build_lat(tiling, decomp, K):
    """Rebuild ONLY the ambient lattice for (tiling, decomp, K), matching the generators exactly (2+1
    -> gen_21's builder, equilateral 1+1+1 -> PO.build_ambient, else gen_111's). The generators build
    the lattice eagerly and only the candidate iterator lazily, so taking [0] costs no enumeration.
    Used by render_fold to redraw a saved fold from its JSON without re-searching."""
    if decomp == "2plus1":
        return gen_21(tiling, K)[0]
    if tiling == "equilateral":
        return gen_eq(decomp, K)[0]
    return gen_111(tiling, K, hub=None)[0]


# --------------------------------------------------------------------------- search (find first)
def find_first(tiling, decomp, holes_mode, K0, step, kcap, hub, budget, stats=None):
    """March K upward; PREFER a foldable (Tw=0) closing fold matching the hole mode, returning it
    immediately. If none turns up within the K range / time budget, fall back to the first closing
    JAM example that matched the hole mode (a proof-of-concept is still useful even when it jams).

    `stats`, if given, is threaded into whichever gen_* this calls (see their docstrings) and also
    gets "holes_filtered" bumped here for candidates skipped by holes_mode -- pure counters, no
    effect on which candidate is returned."""
    t0 = time.time()
    interior_deg = 3 if tiling != "hex" else 6
    fallback = None
    for K in range(K0, kcap + 1, step):
        if tiling == "equilateral":
            lat, gen = gen_eq(decomp, K, stats=stats)
        elif decomp == "1plus1plus1":
            lat, gen = gen_111(tiling, K, hub, stats=stats)
        else:
            lat, gen = gen_21(tiling, K, stats=stats)
        for cand in gen:
            SFILT.apply(lat, cand)          # STRICT START<->END seam gate: demote a mirror/off-cell FOLD to JAM
            hc = len(HF.holes(lat, cand["region"], interior_deg))
            cand["holes"] = hc
            if holes_mode == "none" and hc > 0:
                if stats is not None:
                    stats["holes_filtered"] += 1
                if time.time() - t0 > budget:
                    return fallback
                continue
            if cand["foldable"]:
                return lat, K, cand                 # Tw=0 -> take it right away
            if fallback is None:
                fallback = (lat, K, cand)            # first closing JAM -> keep as backup
            if time.time() - t0 > budget:
                return fallback
        if time.time() - t0 > budget:
            return fallback
    return fallback


# --------------------------------------------------------------------------- rendering
def verdict_text(cand):
    # STRICT seam gate demotion overrides the twist label: the END footprint does not return onto the
    # START footprint as a rotational equivalent (mirror flip on an unequal-sided tile, or off-cell).
    if cand.get("seam_note"):
        return "PREDICTED TO JAM - START/END seams not rotational-equivalent %s - fold to verify" % cand["seam_note"]
    if cand["decomp"] == "1plus1plus1":
        return ("PREDICTED FOLDABLE (Tw=0)" if cand["foldable"]
                else "PREDICTED TO JAM (%s) - fold to verify" % cand["tw_desc"])
    if cand["foldable"]:
        return "Tw=0 (strand-twist MODEL prediction, not proof) - fold to verify"
    return "PREDICTED TO JAM (%s) - fold to verify" % cand["tw_desc"]


def render_case(tiling, decomp, holes_mode, lat, K, cand, suffix="", name_stem=None):
    # name_stem overrides the descriptive tag so the sheets can be keyed by a stable fold uid
    # (overlay_<uid>.png / foldsheet_<uid>.png) — see gen_testset --quadrants + render_fold.py.
    stem = name_stem or ("%s_%s_%s%s" % (tiling, "1plus1" if decomp == "1plus1plus1" else "2plus1",
                                         holes_mode, suffix))
    over_name, sheet_name = "overlay_%s.png" % stem, "foldsheet_%s.png" % stem
    verdict = verdict_text(cand)
    holes_lab = "NO HOLES" if cand["holes"] == 0 else "%d hole(s)" % cand["holes"]

    if tiling == "equilateral" and decomp == "1plus1plus1":   # 1+1+1 keeps the validated SF renderer
        rec = cand["rec"]
        over, sheet = SF.render_111(rec, 1)
        over = _rename(over, over_name)
        sheet = _rename(sheet, sheet_name)
        return over, sheet, verdict

    g = GEN[tiling]                                            # general path (incl. equilateral 2+1)
    title = "%s %s K=%d - %s" % (g["label"], "1+1+1" if decomp == "1plus1plus1" else "2+1", K, verdict)
    note = "%s  region %d tiles  %s\n%s\n%s" % (
        decomp, len(cand["region"]), holes_lab, cand["tw_desc"], verdict)
    # CLOSED footprint = the START trapezoid: a closing fold returns every chain end onto its start,
    # so the 3-stack lands back on the start footprint (real positions, start adjacencies preserved).
    footprint = cand["footprint"]                # START hub (chain starts)
    end_footprint = cand["end_footprint"]        # unfolded chain ENDS (fold back onto the hub)

    if decomp == "1plus1plus1":
        sheet_chains, crease, rigid_ov, partners = cand["chains"], None, None, None
    else:
        # 2+1: the 2-chain is a rigid domino ribbon. Overlay must draw ALL region tiles (incl.
        # partners) so no footprint tile floats; the sheet marks the domino-internal edge RIGID.
        partners = cand["partners"]
        sheet_chains = [sorted(set(cand["two_tris"])), cand["chains"][1]]
        crease = D21.crease_set_21(lat, cand["chains"][0], partners, cand["chains"][1], sig=g["sigma"])
        rigid_ov = D21.rigid_set_21(lat, cand["chains"][0], partners)

    # per-END-tile return orientation (proper/mirror/off-cell + whole-footprint class), single source
    # of truth = the seam gate. Drives the orientation-aware END colouring on BOTH the overlay + sheet.
    end_chir = SFILT.tile_chirality(lat, cand)
    over = RG.render(g["mod"], cand["chains"], footprint, title, over_name, note=note,
                     end_footprint=end_footprint, region=cand["region"], partners=partners,
                     end_chirality=end_chir)
    sheet = FS.make_sheet(g["LatClass"], g["vcart"], g["tile_cart"], g["sigma"],
                          sheet_chains, footprint, title, sheet_name, K,
                          verdict_note=verdict, crease_override=crease, end_footprint=end_footprint,
                          rigid_override=rigid_ov, end_chirality=end_chir)
    return over, sheet, verdict


def _rename(src, newbase):
    dst = os.path.join(REPORT, newbase)
    if os.path.abspath(src) != os.path.abspath(dst):
        os.replace(src, dst)
    return dst


def _jsonable(cand):
    out = {}
    for k, v in cand.items():
        if k in ("rec",):
            continue
        if k == "region":
            out[k] = sorted(list(t) for t in v)
        elif isinstance(v, list):
            out[k] = [list(x) if isinstance(x, (tuple,)) else
                      ([list(y) for y in x] if isinstance(x, list) else x) for x in v]
        else:
            out[k] = v
    return out


# --------------------------------------------------------------------------- one case
def run_case(tiling, decomp, holes_mode, K0=None, step=None, kcap=None, hub=None, budget=120.0,
             kmin=None, suffix="", quiet=False):
    pk, ps, pc = KPLAN[(tiling, decomp)]
    K0 = K0 or pk
    step = step or ps
    kcap = kcap or pc
    if kmin:                                  # K>=kmin battery: raise start, preserve step/parity
        while K0 < kmin:
            K0 += step
        kcap = max(kcap, K0 + (pc - pk))
    res = find_first(tiling, decomp, holes_mode, K0, step, kcap, hub, budget)
    if res is None:
        if not quiet:
            print("  [%s %s holes=%s%s] NONE found (K %d..%d, budget %.0fs)"
                  % (tiling, decomp, holes_mode, suffix, K0, kcap, budget))
        return None
    lat, K, cand = res
    over, sheet, verdict = render_case(tiling, decomp, holes_mode, lat, K, cand, suffix=suffix)
    os.makedirs(RESULTS, exist_ok=True)
    jpath = os.path.join(RESULTS, "example_%s_%s_%s%s.json"
                         % (tiling, "1plus1" if decomp == "1plus1plus1" else "2plus1",
                            holes_mode, suffix))
    rec = _jsonable(cand)
    rec.update({"tiling": tiling, "decomp": decomp, "holes_mode": holes_mode, "K": K,
                "verdict": verdict, "overlay": os.path.relpath(over),
                "foldsheet": os.path.relpath(sheet)})
    with open(jpath, "w") as f:
        json.dump(rec, f, indent=1)
    summary = {"tiling": tiling, "decomp": decomp, "holes": holes_mode, "K": K,
               "tw": cand.get("tw"), "n_holes": cand["holes"], "foldable": cand["foldable"],
               "verdict": verdict, "overlay": os.path.relpath(over),
               "foldsheet": os.path.relpath(sheet)}
    if not quiet:
        print("  [%s %s holes=%s] K=%d  %s  holes=%d  foldable=%s"
              % (tiling, decomp, holes_mode, K, cand["tw_desc"], cand["holes"], cand["foldable"]))
        print("     overlay:  %s" % summary["overlay"])
        print("     foldsheet:%s" % summary["foldsheet"])
    return summary


# --------------------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description="find + render one 3-stack fold example per case")
    ap.add_argument("--tiling", choices=["equilateral", "righttri", "scalene", "hex"])
    ap.add_argument("--decomp", choices=["1plus1plus1", "2plus1"])
    ap.add_argument("--holes", choices=["allow", "none"], default="allow")
    ap.add_argument("--K", type=int)
    ap.add_argument("--step", type=int)
    ap.add_argument("--kcap", type=int)
    ap.add_argument("--hub", help="righttri: LL/HL ; scalene: omitVM/omitMG/omitVG")
    ap.add_argument("--budget", type=float, default=120.0, help="per-case wall-clock budget (s)")
    ap.add_argument("--kmin", type=int, help="enforce chain length K >= this (raises start K)")
    ap.add_argument("--suffix", default="", help="appended to output filenames (separate battery)")
    ap.add_argument("--all", action="store_true", help="run the full 16-case matrix + summary table")
    ap.add_argument("--outdir", help="park figures+JSON under report/tri/<outdir> and results/<outdir>")
    args = ap.parse_args()

    if args.outdir:
        set_outdir(args.outdir)

    if args.all:
        rows = []
        for tiling in ("equilateral", "righttri", "scalene", "hex"):
            for decomp in ("1plus1plus1", "2plus1"):
                for holes in ("allow", "none"):
                    print("=== %s / %s / holes=%s ===" % (tiling, decomp, holes), flush=True)
                    r = run_case(tiling, decomp, holes, budget=args.budget,
                                 kmin=args.kmin, suffix=args.suffix)
                    rows.append(r if r else {"tiling": tiling, "decomp": decomp, "holes": holes,
                                             "K": None, "verdict": "NONE found"})
        print("\n================ SUMMARY ================")
        print("%-12s %-12s %-6s %-4s %-9s %s" % ("tiling", "decomp", "holes", "K", "foldable", "verdict"))
        for r in rows:
            print("%-12s %-12s %-6s %-4s %-9s %s" % (
                r["tiling"], r["decomp"], r["holes"], str(r.get("K")),
                str(r.get("foldable")), r["verdict"][:54]))
        return
    if not (args.tiling and args.decomp):
        ap.error("give --tiling and --decomp (or --all)")
    run_case(args.tiling, args.decomp, args.holes, K0=args.K, step=args.step, kcap=args.kcap,
             hub=args.hub, budget=args.budget, kmin=args.kmin, suffix=args.suffix)


if __name__ == "__main__":
    main()
