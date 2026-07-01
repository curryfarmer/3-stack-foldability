"""seam_filter.py — STRICT post-emission START<->END footprint gate for fold candidates.

USER GROUND TRUTH (the rule this file enforces). A candidate is a real FOLD only if the ending
footprint returns onto the starting footprint as a ROTATIONAL EQUIVALENT: each labelled tile maps
A->A, B->B, C->C onto precisely the exact same relative cell, by a PROPER ROTATION (no mirror/flip,
no permutation). This is stricter than the engine and OVERRIDES it where they disagree; it is the
side-side match the user verifies by hand (short-short/long-long on the 45-45-90 right triangle, all
sides matched on the 30-60-90 scalene), and it applies to EVERY tiling and BOTH decompositions
(2+1 and 1+1+1), per the user's "all sides must match, even 1+1+1".

WHY THE ENGINE ISN'T ENOUGH.
  * gen_21 labels FOLD/JAM by the strand-twist (abs(Tw)<eps) and discards foldsim's `corr`. A
    Tw=0-but-corr=False fold ships as a "FOLD" whose END trapezoid is permuted/flipped.
  * foldsim's `corr` = "does END tile i land on START cell i, in order" — that is the user's rule in
    plain English, BUT it is a vertex-SET (poly_key) coincidence. On tilings whose tile has a mirror
    axis (equilateral, and the 45-45-90 right-iso triangle) a MIRRORED (twisted) arrival lands on the
    same 3 vertices, so corr=True even though the piece came back flipped -> the physical seam
    mismatch the user sees. The 30-60-90 scalene tile has no symmetry, so there corr is already tight.
  So the strict gate = corr (same cell, label order) PLUS a winding-sign check that the arrival is a
  proper rotation, not a reflection.

UNIFORM-TILE EXEMPTION (user ground truth: "mirroring is fine for shapes that all have the same
  sides"). The no-reflection requirement is enforced ONLY for tiles with UNEQUAL edge lengths
  (30-60-90 scalene, 45-45-90 right-iso). For a fully edge-uniform tile (equilateral triangle,
  regular hexagon) a mirror arrival is geometrically invisible and physically harmless, so the winding
  check is skipped and only corr is required. We detect uniformity from the tile geometry (all edges
  equal length), NOT the tiling name -> no tiling string has to be threaded through the candidate.

HOW (pure geometry, NO engine-math edit).
  We reuse foldsim's reflection composition READ-ONLY (import its module-level `_uf_components` /
  `_apply` and rebuild the same crease-path BFS) to obtain the FOLDED vertices of each END-footprint
  tile, then require, per i:
     (1) folded END tile i occupies START cell i  (vertex sets coincide)  -> corr / correspondence;
     (2) if the tile has unequal sides, its folded winding sign equals the START cell's
         -> proper rotation, no flip (skipped for edge-uniform tiles per the exemption above).
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
    vs = lat.vertices_cart(tuple(tile))
    n = len(vs)
    lens = []
    for i in range(n):
        x1, y1 = vs[i]
        x2, y2 = vs[(i + 1) % n]
        lens.append(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5)
    return max(lens) - min(lens) <= tol


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


def _proper_rotation_onto(start_cell_vs, folded_end_vs):
    """(same_cell, proper). The folded END tile must occupy the START cell (vertex sets coincide) AND
    arrive by a PROPER ROTATION (same winding sign) rather than a mirror flip.
      same_cell : corr / correspondence  (A->A onto the exact same relative tile);
      proper    : rotation, not reflection (rejects the mirror-symmetric 'twist' jam)."""
    same_cell = _sets_match(start_cell_vs, folded_end_vs)
    sa_s, sa_e = _signed_area(start_cell_vs), _signed_area(folded_end_vs)
    proper = (sa_s * sa_e) > 0.0
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
def strict_fold_ok(lat, cand):
    """(ok, detail). ok iff the folded END footprint returns onto the START footprint as a rotational
    equivalent (each end tile onto its start cell, label order preserved, by a proper rotation).
    Tiling-agnostic; applies to 2+1 and 1+1+1 alike."""
    # no-op when the candidate carries no chain/footprint geometry (e.g. the equilateral 1+1+1 path
    # emits a solver `rec` instead of chains; it is a proven obstruction, nothing to demote anyway).
    if "footprint" not in cand or "end_footprint" not in cand or "chains" not in cand:
        return True, "n/a (no footprint geometry)"
    if cand.get("decomp") == "2plus1" and "partners" not in cand:
        return True, "n/a (no domino partners)"
    fp = [tuple(t) for t in cand["footprint"]]
    efp = [tuple(t) for t in cand["end_footprint"]]
    if len(fp) != len(efp):
        return False, "footprint/end_footprint size mismatch"
    region, crease, rigid, anchor = _region_edges(lat, cand)
    folded = _fold_tiles(lat, region, crease, rigid, anchor, efp)
    # uniform tiles (all edges equal) are mirror-invisible -> the no-reflection rule does not apply.
    uniform = _tile_is_uniform(lat, fp[1])

    bad = []
    for i, (etile, scell) in enumerate(zip(efp, fp)):
        ev = folded.get(tuple(etile))
        if ev is None:
            bad.append("%s:unreached" % "ABC"[i % 3])
            continue
        sv = lat.vertices_cart(tuple(scell))
        same_cell, proper = _proper_rotation_onto(sv, ev)
        if not same_cell:
            bad.append("%s:off-cell" % "ABC"[i % 3])       # corr fails: landed on wrong/no cell
        elif not proper and not uniform:
            bad.append("%s:mirror" % "ABC"[i % 3])          # flipped arrival on an unequal-sided tile
    if bad:
        return False, "seam mismatch [%s]" % ",".join(bad)
    tag = "corr-equivalent (uniform tile, mirror allowed)" if uniform \
        else "rotational-equivalent (A->A B->B C->C, proper rotation)"
    return True, tag


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
