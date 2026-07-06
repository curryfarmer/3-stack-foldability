"""seam_filter.py — STRICT post-emission START<->END footprint gate for fold candidates.

USER GROUND TRUTH (the rule this file enforces). A candidate is a real FOLD only if each labelled
END tile returns onto its own START cell (A->A, B->B, C->C, no permutation) AND the arrival does not
produce a user-visible seam flip. Which arrivals flip is a property of the TILE SHAPE:
  * uniform tile (all edges equal: equilateral, regular hexagon) — a mirror arrival is geometrically
    invisible and physically harmless ("mirroring is fine for shapes that all have the same sides").
  * isosceles-but-not-uniform tile (45-45-90 righttri) — the tile shape is its own mirror image, so
    a MIRROR arrival re-seats the SAME cell with the two equal legs SWAPPED: lengths still match
    (length is a reflection invariant) but the labelled sides come back exchanged — exactly the
    physical seam mismatch the user sees on righttri. ENFORCED: mirror arrival -> JAM.
  * asymmetric tile (30-60-90 scalene) — the tile has no mirror axis, so a mirror arrival can be
    on-cell ONLY when the START cell is the tile's mirror-partner slot (the fold map is a tiling
    symmetry; an odd reflection count flips sigma). There every edge ROLE (V-M / M-G / V-G) still
    lands on its own kind, all sides match — the user's verified-good scalene seating. EXEMPT.

CHIRALITY IS COMPUTED CONVENTION-FREE (bug fixed 2026-07-02). `lat.vertices_cart` list order is a
per-tile-TYPE convention and is NOT winding-uniform (righttri: S,E wind CCW / N,W wind CW;
equilateral: U vs D; scalene: winding == sigma). The old gate compared signed areas of the START
cell's canonical list vs the folded END list — two DIFFERENT tiles — so the verdict absorbed the
convention mismatch and INVERTED whenever the two types wound oppositely: the mirror-image pair
9c7a328f55fb / 327ca6c4fc99 (same physical fold on a reflected sheet) got opposite classes. The
fixed check compares the folded END list against the SAME tile's canonical list; the convention
cancels and the sign equals the crease-reflection parity of the fold map itself (proper rotation
= even number of crease reflections).

K-PARITY LAW (2026-07-02 census). Chains alternate the bipartite sigma and every crease flips it,
so an ON-CELL arrival's chirality is fixed by the chain length: sigma(end) = sigma(start) *
(-1)^(K-1), hence K EVEN -> reflection (mirror), K ODD -> proper rotation. Confirmed 651/651
even-K arrivals mirror and 62/62 odd-K arrivals proper (righttri + scalene, both decomps). All the
old matrix's righttri exemplars were even-K, so its "seam-ok" quadrant was convention noise;
genuinely seam-clean righttri folds live at ODD K only.

WHY THE ENGINE ISN'T ENOUGH.
  * gen_21 labels FOLD/JAM by the strand-twist (abs(Tw)<eps) and discards foldsim's `corr`. A
    Tw=0-but-corr=False fold ships as a "FOLD" whose END trapezoid is permuted/flipped.
  * foldsim's `corr` is a vertex-SET (poly_key) coincidence: it cannot see a flipped arrival.
  So the strict gate = corr (same cell, label order) PLUS the convention-free chirality read-out,
  enforced per the tile-shape rules above.

HOW (pure geometry, NO engine-math edit).
  We reuse foldsim's reflection composition READ-ONLY (import its module-level `_uf_components` /
  `_apply` and rebuild the same crease-path BFS) to obtain the FOLDED vertices of each END-footprint
  tile, then require, per i:
     (1) folded END tile i occupies START cell i  (vertex sets coincide)  -> corr / correspondence;
     (2) on an isosceles-not-uniform tile, the fold map is a proper rotation (uniform + asymmetric
         tiles exempt per the shape rules above).
  foldsim / domino21 / tritwist / foldclose are untouched. Consumers (find_example, gen_testset)
  call `apply` / `strict_fold_ok` to DEMOTE a predicted FOLD to JAM when the gate fails.

`seam_type` / `_is_trapezoid` remain for human-readable sheet annotation (S/L/H tags), not the gate.
"""
import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foldsim as FSIM   # noqa: E402  READ-ONLY reuse of the reflection composition (no edit to it)

TOL = 1e-6
UNIFORM = ("equilateral", "hex")   # all edges same length -> seam TYPE carries no info (annotation only)


# --------------------------------------------------------------------- annotation helpers (not gate)
def seam_type(lat, tiling, x, y):
    """Human-readable token for the shared edge between adjacent tiles x,y (sheet annotation only).
    righttri: 'long'(hyp)/'short'(leg); scalene: 'VM'/'MG'/'VG'; equilateral/hex: 'uniform'."""
    if tiling == "righttri":
        import sidematch_scan as SM
        return SM.etype(lat, x, y)
    if tiling == "scalene":
        import scalene as SC
        return SC._shared_type(lat, x, y)
    return "uniform"


def _is_trapezoid(lat, fp):
    """fp=[t0,t1,t2] is a clean trapezoid iff exactly one tile (the middle) is adjacent to both others
    and the other two are NOT adjacent. Return the middle tile, or None."""
    fp = [tuple(t) for t in fp]
    if len(set(fp)) != 3:
        return None
    for t in fp:
        others = [u for u in fp if u != t]
        if (others[0] in lat.adj.get(t, ()) and others[1] in lat.adj.get(t, ())
                and others[1] not in lat.adj.get(others[0], ())):
            return t
    return None


# --------------------------------------------------------------------- geometry primitives
def _signed_area(vs):
    """Shoelace signed area of a polygon vertex list (sign = winding orientation)."""
    s = 0.0
    n = len(vs)
    for i in range(n):
        x1, y1 = vs[i]
        x2, y2 = vs[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def _tile_is_uniform(lat, tile, tol=1e-6):
    """True iff every edge of `tile` has the same length (equilateral triangle / regular hexagon).
    Such a tile is invisible under reflection, so the user's rule permits a mirror arrival for it."""
    return _tile_symmetry(lat, tile, tol) == "uniform"


def _tile_symmetry(lat, tile, tol=1e-6):
    """Shape class deciding how a MIRROR arrival reads physically (see module docstring):
      'uniform'    all edges equal (equilateral / hex)      -> mirror invisible, EXEMPT
      'isosceles'  some equal pair, but not all equal (righttri) -> mirror swaps the equal
                   labelled sides on the SAME cell: the user-visible seam flip, ENFORCED
      'asymmetric' no equal pair (scalene) -> an on-cell mirror seats the mirror-partner slot with
                   every edge role matched, EXEMPT
    Detected from tile geometry, NOT the tiling name (nothing threaded through the candidate)."""
    vs = lat.vertices_cart(tuple(tile))
    n = len(vs)
    lens = sorted((((vs[(i + 1) % n][0] - vs[i][0]) ** 2
                    + (vs[(i + 1) % n][1] - vs[i][1]) ** 2) ** 0.5) for i in range(n))
    if lens[-1] - lens[0] <= tol:
        return "uniform"
    if any(lens[i + 1] - lens[i] <= tol for i in range(n - 1)):
        return "isosceles"
    return "asymmetric"


def _sets_match(a, b, tol=TOL):
    """True iff point lists a,b are the same set within tol (bijective nearest match)."""
    if len(a) != len(b):
        return False
    used = [False] * len(b)
    for pa in a:
        hit = False
        for j, pb in enumerate(b):
            if not used[j] and abs(pa[0] - pb[0]) <= tol and abs(pa[1] - pb[1]) <= tol:
                used[j] = True
                hit = True
                break
        if not hit:
            return False
    return True


def _proper_rotation_onto(start_cell_vs, folded_end_vs, end_canon_vs):
    """(same_cell, proper).
      same_cell : corr / correspondence — the folded END tile occupies the START cell (vertex sets
                  coincide, A->A onto the exact same relative tile);
      proper    : the FOLD MAP that carried the tile is a proper rotation (EVEN number of crease
                  reflections), not a reflection.
    `proper` is read convention-free by comparing the folded list against the SAME tile's canonical
    list: `_apply` preserves list order and each crease reflection flips the signed area once, so
    sign(area(folded)) == sign(area(canonical)) iff the reflection count is even. Comparing against
    the START cell's canonical list instead (the pre-2026-07-02 bug) mixes in the per-tile-TYPE
    winding convention of `vertices_cart` — righttri types wind BOTH ways — and inverts the verdict
    whenever START/END types wind oppositely (mirror-image candidates got opposite verdicts)."""
    same_cell = _sets_match(start_cell_vs, folded_end_vs)
    proper = (_signed_area(folded_end_vs) * _signed_area(end_canon_vs)) > 0.0
    return same_cell, proper


# --------------------------------------------------------------------- read-only fold (reuse foldsim)
def _fold_tiles(lat, region, crease, rigid, anchor, tiles):
    """READ-ONLY reuse of foldsim's reflection composition. Returns {tile: folded [(x,y),...]} for the
    requested `tiles`. This is NOT an edit to engine math: it imports foldsim's module-level helpers
    and rebuilds the SAME crease-path BFS foldsim.simulate uses, purely to read folded coordinates
    (simulate itself returns only poly_key landings, from which winding cannot be recovered)."""
    region = [tuple(t) for t in region]
    rset = set(region)
    crease = {frozenset(map(tuple, fs)) for fs in crease}
    rigid = {frozenset(map(tuple, fs)) for fs in rigid}
    comp = FSIM._uf_components(region, rigid)

    cadj = {}
    for fs in crease:
        u, v = tuple(fs)
        if u not in rset or v not in rset or (u, v) not in lat.shared:
            continue
        cu, cv = comp[u], comp[v]
        e = lat.shared_edge(u, v)
        cadj.setdefault(cu, []).append((cv, e))
        cadj.setdefault(cv, []).append((cu, e))

    ac = comp[tuple(anchor)]
    cmirror = {ac: []}
    q = deque([ac])
    while q:
        c = q.popleft()
        for (d, e) in cadj.get(c, ()):
            if d not in cmirror:
                cmirror[d] = [e] + cmirror[c]
                q.append(d)

    out = {}
    for t in tiles:
        t = tuple(t)
        if comp.get(t) in cmirror:
            out[t] = FSIM._apply(lat.vertices_cart(t), cmirror[comp[t]])
    return out


def _region_edges(lat, cand):
    """(region, crease, rigid, anchor) rebuilt via foldsim's OWN builders (read-only) for this cand."""
    fp = [tuple(t) for t in cand["footprint"]]
    mid = fp[1]
    if cand.get("decomp") == "2plus1":
        strand = [tuple(t) for t in cand["chains"][0]]
        partners = [tuple(t) for t in cand["partners"]]
        one = [tuple(t) for t in cand["chains"][1]]
        crease, rigid = FSIM.edges_21(lat, strand, partners, one, fp)
        region = set(strand) | set(partners) | set(one)
    else:
        chains = [[tuple(t) for t in w] for w in cand["chains"]]
        crease, rigid = FSIM.edges_111(lat, chains, fp)
        region = {t for w in chains for t in w}
    return region, crease, rigid, mid


# --------------------------------------------------------------------- the STRICT gate
def _analyse(lat, cand):
    """ONE shared fold pass behind both `strict_fold_ok` and `tile_chirality`. Returns None for
    geometry-less candidates (nothing to gate), else a dict with the honest per-tile read-out:
    per_tile / n_mirror / symmetry / uniform / klass / single_motion / size_mismatch."""
    # no-op when the candidate carries no chain/footprint geometry (e.g. the equilateral 1+1+1 path
    # emits a solver `rec` instead of chains; it is a proven obstruction, nothing to demote anyway).
    if "footprint" not in cand or "end_footprint" not in cand or "chains" not in cand:
        return None
    if cand.get("decomp") == "2plus1" and "partners" not in cand:
        return None
    fp = [tuple(t) for t in cand["footprint"]]
    efp = [tuple(t) for t in cand["end_footprint"]]
    if len(fp) != len(efp):
        return {"size_mismatch": True}
    region, crease, rigid, anchor = _region_edges(lat, cand)
    folded = _fold_tiles(lat, region, crease, rigid, anchor, efp)
    symmetry = _tile_symmetry(lat, fp[1])

    per, motions = [], []
    for i, (etile, scell) in enumerate(zip(efp, fp)):
        lab = "ABC"[i % 3]
        ev = folded.get(tuple(etile))
        if ev is None:
            per.append({"label": lab, "same_cell": False, "proper": None, "klass": "off-cell"})
            motions.append(None)
            continue
        canon_e = lat.vertices_cart(tuple(etile))
        sv = lat.vertices_cart(tuple(scell))
        same_cell, proper = _proper_rotation_onto(sv, ev, canon_e)
        motions.append(_fold_map(canon_e, ev))
        if not same_cell:
            per.append({"label": lab, "same_cell": False, "proper": proper, "klass": "off-cell"})
        elif symmetry == "uniform":
            per.append({"label": lab, "same_cell": True, "proper": proper, "klass": "uniform"})
        elif proper:
            per.append({"label": lab, "same_cell": True, "proper": True, "klass": "proper"})
        else:
            per.append({"label": lab, "same_cell": True, "proper": False, "klass": "mirror"})

    n_mirror = sum(1 for p in per if p["klass"] == "mirror")
    off = sum(1 for p in per if p["klass"] == "off-cell")
    if off:
        klass = "off-cell"
    elif symmetry == "uniform":
        klass = "uniform"
    elif n_mirror == 0:
        klass = "all-proper"
    elif n_mirror == len(per):
        klass = "all-mirror"
    else:
        klass = "mixed"
    single = _motions_agree(motions) if (off == 0 and all(m is not None for m in motions)) else False
    return {"per_tile": per, "n_mirror": n_mirror, "symmetry": symmetry,
            "uniform": symmetry == "uniform", "klass": klass, "single_motion": single,
            "size_mismatch": False}


def _verdict(a):
    """(ok, detail) from an `_analyse` dict. CHIRALITY IS COSMETIC. Physically confirmed 2026-07-05:
    every 2+1 all-mirror sheet folds flat — righttri twins 327ca6c4fc99/9c7a328f55fb (isosceles) AND
    scalene all-mirror AND all-proper — so a mirror arrival SEATS FLAT with the printed START/END seam
    flipped; it is not a jam. The prior isosceles mirror->JAM enforcement (and the K-parity 'seam law')
    is REFUTED by the mirror pair itself. The only real correspondence failure is OFF-CELL: a folded
    END tile that missed its START cell. (Righttri 1+1+1 jams are TWIST jams, now caught by the
    loop-index-sigma twist fix in find_example.gen_111, not by this gate.) See
    docs/research/GROUND_TRUTH_folds.md and nonsquare_construction.md."""
    if a is None:
        return True, "n/a (no footprint geometry)"
    if a["size_mismatch"]:
        return False, "footprint/end_footprint size mismatch"
    bad = ["%s:off-cell" % p["label"] for p in a["per_tile"] if p["klass"] == "off-cell"]
    if bad:
        return False, "off-cell arrival [%s]" % ",".join(bad)   # tile missed its START cell -> JAM
    if a["n_mirror"]:
        return True, "corr-equivalent (mirror seats flat, printed seam flipped — cosmetic)"
    return True, "rotational-equivalent (A->A B->B C->C, proper rotation)"


def strict_fold_ok(lat, cand):
    """(ok, detail). ok iff the folded END footprint returns onto the START footprint with each end
    tile on its own start cell (label order preserved) and no user-visible seam flip (see module
    docstring for the per-shape mirror rules). Tiling-agnostic; applies to 2+1 and 1+1+1 alike."""
    return _verdict(_analyse(lat, cand))


# --------------------------------------------------------------------- public chirality read-out (render)
# WHOLE-FOOTPRINT RIGID-MOTION CLASS — a COSMETIC annotation the sheet/legend names (user's framing:
# "does START [A,B,C] map onto END [A',B',C'] by a single rigid motion of the WHOLE footprint, vs the
# tiles being rearranged"). Physically confirmed 2026-07-05: chirality does NOT gate foldability — a
# mirror arrival seats flat with the printed seam flipped. Per-tile chirality is the fold-map parity;
# single_motion additionally compares the EXACT per-tile fold maps (rotation/reflection + translation):
#   all-proper : 0 mirrors -> every END tile returns by a proper rotation (occurs at ODD K)
#   all-mirror : every END tile returns REFLECTED; seats flat, printed seam flipped (occurs at EVEN K)
#                (e.g. the folded twins 9c7a328f55fb / 327ca6c4fc99, both FOLD)
#   mixed      : both parities present (rare; still folds unless a tile is off-cell)
#   uniform    : edge-uniform tile (equilateral/hex) -> a mirror is geometrically invisible
#   off-cell   : some END tile missed its START cell -> the one real correspondence failure -> JAM
# Only off-cell demotes (see _verdict); all chirality classes are FOLD annotations. The K-even/all-
# mirror split is a TWIST fact (which parity closes with Tw=0), documented in FINDINGS_nonsquare.
_CLASS_NA = {"per_tile": [], "n_mirror": 0, "uniform": False, "symmetry": None, "klass": "n/a",
             "single_motion": None, "ok": True, "detail": "n/a (no footprint geometry)"}


def tile_chirality(lat, cand):
    """READ-ONLY per-tile orientation read-out for RENDERING — single source of truth = this gate,
    never mutates cand. Returns a dict:
        per_tile      : [{'label','same_cell','proper','klass'} x3 in A,B,C label order]
        n_mirror      : count of mirror END tiles (over non-uniform tiles)
        uniform       : tile is edge-uniform (equilateral/hex)
        symmetry      : tile shape class 'uniform' | 'isosceles' | 'asymmetric' (mirror enforcement
                        applies only to 'isosceles'; see module docstring)
        klass         : whole-footprint class in {all-proper, all-mirror, mixed, uniform, off-cell, n/a}
        single_motion : True iff the 3 END tiles return by ONE shared rigid motion (rotation OR
                        reflection, translation included — exact fold maps, not a fit); False when
                        any tile is off-cell/unreached. all-mirror CAN be single_motion=True (a
                        whole-footprint reflection seating).
        ok, detail    : the gate verdict (strict_fold_ok), for convenience."""
    a = _analyse(lat, cand)
    ok, detail = _verdict(a)
    out = dict(_CLASS_NA)
    out["ok"], out["detail"] = ok, detail
    if a is None or a["size_mismatch"]:
        return out
    for k in ("per_tile", "n_mirror", "uniform", "symmetry", "klass", "single_motion"):
        out[k] = a[k]
    return out


def _fold_map(canon_vs, folded_vs):
    """The EXACT rigid map M with folded == M(canon), keyed as rounded (a,b,c,d,tx,ty) row-major
    ([x';y'] = [a b; c d][x;y] + [tx;ty]). folded[i] pairs with canon[i] by construction (`_apply`
    preserves list order), so M is solved exactly from the first two edge vectors — no fitting, and
    no cross-tile vertex-order convention enters. None if the first three vertices are collinear."""
    (x0, y0), (x1, y1), (x2, y2) = canon_vs[0], canon_vs[1], canon_vs[2]
    (u0, v0), (u1, v1), (u2, v2) = folded_vs[0], folded_vs[1], folded_vs[2]
    s1 = (x1 - x0, y1 - y0); s2 = (x2 - x0, y2 - y0)
    d1 = (u1 - u0, v1 - v0); d2 = (u2 - u0, v2 - v0)
    det = s1[0] * s2[1] - s1[1] * s2[0]
    if abs(det) < 1e-12:
        return None
    a = (d1[0] * s2[1] - d2[0] * s1[1]) / det
    b = (d2[0] * s1[0] - d1[0] * s2[0]) / det
    c = (d1[1] * s2[1] - d2[1] * s1[1]) / det
    d = (d2[1] * s1[0] - d1[1] * s2[0]) / det
    tx = u0 - (a * x0 + b * y0)
    ty = v0 - (c * x0 + d * y0)
    return (a, b, c, d, tx, ty)


def _motions_agree(motions, tol=1e-4):
    """True iff every fold map in `motions` is the SAME rigid motion (linear part AND translation)."""
    motions = [m for m in motions if m is not None]
    if len(motions) < 2:
        return True
    m0 = motions[0]
    return all(all(abs(m[k] - m0[k]) <= tol for k in range(6)) for m in motions[1:])


def cand_seam_ok(lat, cand):
    """Convenience: (ok, detail) for a candidate dict, for both decomps and all tilings."""
    return strict_fold_ok(lat, cand)


def apply(lat, cand):
    """Mutate + return cand: stamp seam_ok/seam_detail, and DEMOTE a predicted FOLD (foldable=True)
    to JAM (foldable=False, + seam_note) when the strict START<->END gate fails."""
    ok, detail = strict_fold_ok(lat, cand)
    cand["seam_ok"] = ok
    cand["seam_detail"] = detail
    if cand.get("foldable") and not ok:
        cand["foldable"] = False
        cand["seam_note"] = detail
    return cand
