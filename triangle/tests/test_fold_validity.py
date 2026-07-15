"""test_fold_validity.py — necessary-validity invariants for the printed-sheet flat-fold engine.

Pins the physical FOLD/JAM *closure* authority (py/tri/foldsim.py) against a battery of NECESSARY
conditions that every emitted closing fold must satisfy, plus the core domino-rigidity regression:

  1. every enumerator-emitted fold re-passes foldsim (gate is self-consistent / hash-order stable),
  2. region tiles are FULL-edge connected (no vertex-only attachment) — via lat.adj,
  3. START/END footprints are trapezoids (middle edge-adjacent to both arms),
  4. uniform K-coverage (a == mid == b == K, diag['uniform'] True),
  5. NEGATIVE CONTROL — moving each domino-internal edge from RIGID into CREASE (the OLD BUG)
     must break closure (the over-fold no longer seats),
  6. ground-truth anchors (scalene 1+1+1 K=16; equilateral 1+1+1 K=12 = 94 close, foldsim agrees).

Enumeration is capped (islice) and run at small K where folds exist, so the whole file stays fast.
Families that yield 0 cands at the chosen K are SKIPPED (some families are jam-only), never failed.

sys.path is set by triangle/tests/conftest.py (via triangle/_bootstrap.py) -- never co-import square/.
Run: python -m pytest triangle/tests/test_fold_validity.py -q
"""
import itertools
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))            # repo root

import find_example as FE   # noqa: E402  gen_111 / gen_21 / gen_eq / KPLAN enumerators
import foldsim as FSIM      # noqa: E402  valid_111 / valid_21 / valid_flat_fold / edges_*
import foldclose as FC      # noqa: E402  reflection_closes_111 (1+1+1 physical-closure reference)
import trisearch as TS      # noqa: E402  exit_ok (engine's own trapezoid definition)
import seam_filter as SFILT  # noqa: E402  STRICT START<->END seam gate (mirror/off-cell demotion)
import prove_obstruction as PO  # noqa: E402
import solve_foldable as SF     # noqa: E402
import scalene as SC        # noqa: E402
import righttri as RT       # noqa: E402
import hexlattice as HX     # noqa: E402
import trilattice as TL     # noqa: E402
from lattice.reflect import reflect_point  # noqa: E402
from lattice import foldwalk as FW          # noqa: E402  INDEPENDENT walk-composition fold (oracle)

# TRACKED anchor: promoted out of gitignored results/30-6-2026/ so it travels with the corpus and a
# fresh clone RUNS this assertion instead of erroring on the unguarded read it used to do.
ANCHOR = os.path.join(_HERE, "fixtures", "example_scalene_1plus1_allow.json")

# how many cands to pull per family (cheap: keeps the whole suite well under ~30s)
CAP = 4

# --- family table: (id, tiling, decomp, K). K chosen where closing folds are known to exist. ---
#     2+1: righttri/scalene/hex K=4, equilateral K=6.  1+1+1: each KPLAN K0.
FAM_21 = [
    ("righttri_21", "righttri", 4),
    ("scalene_21", "scalene", 4),
    ("hex_21", "hex", 4),
    ("equilateral_21", "equilateral", 6),
]
FAM_111 = [
    ("righttri_111", "righttri"),
    ("scalene_111", "scalene"),
    ("hex_111", "hex"),
    ("equilateral_111", "equilateral"),
]


# --------------------------------------------------------------------------- enumeration helpers
def _enum_21(tiling, K, cap=CAP):
    """(lat, [cand,...]) — up to `cap` closing 2+1 cands for `tiling` at chain length K."""
    lat, it = FE.gen_21(tiling, K)
    return lat, list(itertools.islice(it, cap))


def _enum_111(tiling, cap=CAP):
    """(lat, K, [cand,...]) — up to `cap` closing 1+1+1 cands at this tiling's KPLAN start K."""
    K = FE.KPLAN[(tiling, "1plus1plus1")][0]
    if tiling == "equilateral":
        lat, it = FE.gen_eq("1plus1plus1", K)
    else:
        lat, it = FE.gen_111(tiling, K, None)
    return lat, K, list(itertools.islice(it, cap))


def _fields(cand):
    """Normalize the two cand shapes into (decomp, chains, partners, footprint, end_footprint) with
    every tile a tuple. Equilateral 1+1+1 (gen_eq) nests everything under `rec` as lists; the general
    gen_111/gen_21 expose the fields at top level. partners is None for 1+1+1."""
    src = cand["rec"] if "rec" in cand else cand
    chains = [[tuple(t) for t in w] for w in src["chains"]]
    fp = [tuple(t) for t in src["footprint"]]
    efp = [tuple(t) for t in src["end_footprint"]]
    partners = [tuple(t) for t in cand["partners"]] if cand.get("partners") is not None else None
    return cand["decomp"], chains, partners, fp, efp


def _revalidate(lat, cand):
    """Re-run the printed-sheet gate for one cand from a fresh (crease,rigid) rebuild.
    Returns (closes, diag). Works for both decomps and both cand shapes."""
    decomp, chains, partners, fp, efp = _fields(cand)
    if decomp == "2plus1":
        return FSIM.valid_21(lat, list(chains[0]), list(partners), list(chains[1]), fp, efp)
    return FSIM.valid_111(lat, chains, fp, efp)


def _skip_if_empty(cands, label):
    if not cands:
        pytest.skip("%s: enumerator yielded 0 closing cands at chosen K (jam-only family)" % label)


# =========================================================================== 1. re-pass foldsim
@pytest.mark.parametrize("fid,tiling,K", FAM_21, ids=[f[0] for f in FAM_21])
def test_every_emitted_fold_closes_21(fid, tiling, K):
    """Every enumerator-emitted 2+1 cand must re-pass foldsim on a fresh rebuild (gate is
    self-consistent / deterministic across a re-run — set iteration is hash-seed dependent)."""
    lat, cands = _enum_21(tiling, K)
    _skip_if_empty(cands, fid)
    for cand in cands:
        closes, diag = _revalidate(lat, cand)
        assert closes is True, "%s cand did not re-close: %s" % (fid, diag)


@pytest.mark.parametrize("fid,tiling", FAM_111, ids=[f[0] for f in FAM_111])
def test_every_emitted_fold_closes_111(fid, tiling):
    """Every enumerator-emitted 1+1+1 cand must re-pass foldsim on a fresh rebuild."""
    lat, K, cands = _enum_111(tiling)
    _skip_if_empty(cands, fid)
    for cand in cands:
        closes, diag = _revalidate(lat, cand)
        assert closes is True, "%s cand (K=%d) did not re-close: %s" % (fid, K, diag)


# =========================================================================== 2. region edge-connected
def _assert_region_edge_connected(lat, cands, label):
    for cand in cands:
        region = {tuple(t) for t in cand["region"]}
        assert len(region) >= 2, "%s region too small: %s" % (label, region)
        for t in region:
            nbrs_in_region = [u for u in lat.adj.get(t, ()) if u in region]
            assert nbrs_in_region, (
                "%s tile %s shares no FULL edge with any other region tile "
                "(vertex-only attachment)" % (label, (t,)))


@pytest.mark.parametrize("fid,tiling,K", FAM_21, ids=[f[0] for f in FAM_21])
def test_region_edge_connected_21(fid, tiling, K):
    """Every region tile shares a full edge (in lat.adj) with >=1 other region tile."""
    lat, cands = _enum_21(tiling, K)
    _skip_if_empty(cands, fid)
    _assert_region_edge_connected(lat, cands, fid)


@pytest.mark.parametrize("fid,tiling", FAM_111, ids=[f[0] for f in FAM_111])
def test_region_edge_connected_111(fid, tiling):
    lat, K, cands = _enum_111(tiling)
    _skip_if_empty(cands, fid)
    _assert_region_edge_connected(lat, cands, fid)


# =========================================================================== 3. footprints are trapezoids
def _assert_trapezoid(lat, fp, label, mid_at_index1=False):
    """A footprint is a trapezoid iff its 3 tiles form a path in the dual graph: within-triple
    degrees sort to [1,1,2] (exactly one MIDDLE tile edge-adjacent to both arms). This is the
    engine's own definition (trisearch.exit_ok). For the START hub the middle is built at index 1,
    so also pin that; the END triple is (chainA_end, chainB_end, chainC_end) and its trapezoid
    middle need NOT sit at index 1, so only the path property is required there."""
    tiles = [tuple(t) for t in fp]
    assert len(set(tiles)) == 3, "%s: footprint not 3 distinct tiles: %s" % (label, tiles)
    assert TS.exit_ok(lat, tiles), (
        "%s: %s is not a trapezoid (within-triple degrees != [1,1,2])" % (label, tiles))
    if mid_at_index1:
        a, mid, b = tiles
        assert mid in lat.adj.get(a, ()) and mid in lat.adj.get(b, ()), (
            "%s: START middle %s not edge-adjacent to both arms %s,%s" % (label, mid, a, b))


def _assert_footprints_are_trapezoids(lat, cands, label):
    for cand in cands:
        _, _, _, fp, efp = _fields(cand)
        _assert_trapezoid(lat, fp, "%s START" % label, mid_at_index1=True)
        _assert_trapezoid(lat, efp, "%s END" % label)


@pytest.mark.parametrize("fid,tiling,K", FAM_21, ids=[f[0] for f in FAM_21])
def test_footprints_are_trapezoids_21(fid, tiling, K):
    """START and END footprints each have their middle tile edge-adjacent to BOTH arms."""
    lat, cands = _enum_21(tiling, K)
    _skip_if_empty(cands, fid)
    _assert_footprints_are_trapezoids(lat, cands, fid)


@pytest.mark.parametrize("fid,tiling", FAM_111, ids=[f[0] for f in FAM_111])
def test_footprints_are_trapezoids_111(fid, tiling):
    lat, K, cands = _enum_111(tiling)
    _skip_if_empty(cands, fid)
    _assert_footprints_are_trapezoids(lat, cands, fid)


# =========================================================================== 4. uniform coverage
def _assert_uniform_coverage(lat, cands, expect_K, label):
    for cand in cands:
        closes, diag = _revalidate(lat, cand)
        assert diag["uniform"] is True, "%s: diag['uniform'] not True: %s" % (label, diag)
        cov = diag["cover"]
        a, mid, b = cov.get("a", 0), cov.get("mid", 0), cov.get("b", 0)
        assert a == mid == b == expect_K, (
            "%s: cover not uniform==K (K=%d): a=%d mid=%d b=%d" % (label, expect_K, a, mid, b))


@pytest.mark.parametrize("fid,tiling,K", FAM_21, ids=[f[0] for f in FAM_21])
def test_uniform_coverage_21(fid, tiling, K):
    """For every emitted 2+1 fold, cover a==mid==b==K and diag['uniform'] is True."""
    lat, cands = _enum_21(tiling, K)
    _skip_if_empty(cands, fid)
    _assert_uniform_coverage(lat, cands, K, fid)


@pytest.mark.parametrize("fid,tiling", FAM_111, ids=[f[0] for f in FAM_111])
def test_uniform_coverage_111(fid, tiling):
    lat, K, cands = _enum_111(tiling)
    _skip_if_empty(cands, fid)
    _assert_uniform_coverage(lat, cands, K, fid)


# =========================================================================== 5. NEGATIVE CONTROL
def test_reject_domino_as_crease():
    """CORE REGRESSION: take one righttri 2+1 closing fold, rebuild its edges but MOVE each
    domino-internal edge (strand[k], partner[k]) from RIGID into CREASE (the OLD BUG). foldsim must
    now report closes==False — the over-fold no longer seats. Pins the domino-must-be-RIGID fix."""
    lat, cands = _enum_21("righttri", 4)
    _skip_if_empty(cands, "righttri_21 (negative control)")
    cand = cands[0]
    strand, partners, one = cand["chains"][0], cand["partners"], cand["chains"][1]
    fp, efp = cand["footprint"], cand["end_footprint"]

    # sanity: the correct (domino-rigid) build closes.
    closes0, _ = FSIM.valid_21(lat, list(strand), list(partners), list(one), fp, efp)
    assert closes0 is True, "precondition: the chosen righttri 2+1 fold must close (domino RIGID)"

    crease, rigid = FSIM.edges_21(lat, strand, partners, one, fp)
    region = ({tuple(t) for t in strand} | {tuple(t) for t in partners}
              | {tuple(t) for t in one})
    crease_bug, rigid_bug = set(crease), set(rigid)
    moved = 0
    for k in range(len(strand)):
        e = frozenset((tuple(strand[k]), tuple(partners[k])))
        if e in rigid_bug:
            rigid_bug.discard(e)
            crease_bug.add(e)
            moved += 1
    assert moved > 0, "no domino-internal rigid edges found to move — test setup broken"

    closes_bug, diag_bug = FSIM.valid_flat_fold(lat, region, crease_bug, rigid_bug, fp, efp)
    assert closes_bug is False, (
        "domino-as-crease (OLD BUG) must NOT seat, but it re-closed: %s" % diag_bug)


# =========================================================================== 6. ground-truth anchors
def _anchor_or_skip():
    """Load the tracked scalene anchor. Backstop guard: the file is tracked, so absence means a
    broken checkout rather than a fresh clone. I/O: () -> anchor dict."""
    if not os.path.exists(ANCHOR):
        pytest.skip(f"anchor missing: {ANCHOR}")
    with open(ANCHOR) as f:
        return json.load(f)


def test_scalene_anchor_foldsim_closes():
    """The confirmed-foldable scalene 1+1+1 (K=16) must close under foldsim with uniform cover=16."""
    d = _anchor_or_skip()
    assert d["tiling"] == "scalene" and d["decomp"] == "1plus1plus1" and d["K"] == 16
    chains = [[tuple(t) for t in c] for c in d["chains"]]
    region = sorted({t for c in chains for t in c})
    lat = SC.ScaleneLattice(cells=region)
    fp = [chains[0][0], chains[1][0], chains[2][0]]
    efp = [chains[0][-1], chains[1][-1], chains[2][-1]]
    closes, diag = FSIM.valid_111(lat, chains, fp, efp)
    assert closes is True, "scalene anchor must close under foldsim: %s" % diag
    cov = diag["cover"]
    assert cov.get("a") == cov.get("mid") == cov.get("b") == 16, "anchor cover not uniform 16: %s" % cov


def test_equilateral_K12_foldsim_agrees_with_reference():
    """Equilateral 1+1+1 K=12: every fold that FC.reflection_closes_111 accepts must also close
    under foldsim with uniform cover=12. Uses reflection_closes_111 as the closure reference (the
    same anchor test_foldclose_truth pins at 94), and checks foldsim agrees on ALL of them."""
    lat, S, back = PO.build_ambient(12)
    n_ref = 0
    for (pa, pm, pc) in SF.enum_111(lat, S, back, 12):
        ch = [list(pa), list(pm), list(pc)]
        if not FC.reflection_closes_111(lat, ch):
            continue
        n_ref += 1
        fp = [pa[0], pm[0], pc[0]]
        efp = [pa[-1], pm[-1], pc[-1]]
        closes, diag = FSIM.valid_111(lat, ch, fp, efp)
        assert closes is True, "foldsim disagreed with reflection_closes_111 (should close): %s" % diag
        cov = diag["cover"]
        assert cov.get("a") == cov.get("mid") == cov.get("b") == 12, "cover not uniform 12: %s" % cov
    assert n_ref == 94, "expected 94 reflection-closing folds at eq K=12, got %d" % n_ref


# =========================================================================== 7. STRICT seam gate
# The user's ground-truth rule: a FOLD is real only if the END footprint returns onto the START
# footprint A->A B->B C->C onto the exact same relative cell, with no user-visible seam flip.
# Mirror enforcement is by TILE SHAPE (see seam_filter module docstring): ISOSCELES-not-uniform
# (righttri) -> a mirror arrival swaps the equal labelled legs on the same cell = JAM; edge-UNIFORM
# (equilateral/hex) -> mirror invisible, allowed; ASYMMETRIC (scalene) -> an on-cell mirror seats
# the mirror-partner slot with every edge role matched, allowed. Chirality itself is the fold-map
# crease parity, read convention-free (folded vs the SAME tile's canonical list).
def test_tile_uniform_detection():
    """_tile_is_uniform: True for equal-sided tiles (equilateral tri, regular hexagon), False for the
    unequal-sided ones (45-45-90 legs!=hyp, 30-60-90 all-different)."""
    cases = [(TL.TriLattice(8, 8), True, "equilateral"),
             (HX.HexLattice(R=4), True, "hex"),
             (RT.RightTriLattice(8, 8), False, "righttri"),
             (SC.ScaleneLattice(faces=TL.triangle_cells(10)), False, "scalene")]
    for lat, want, name in cases:
        t = next(iter(lat.tris))
        assert SFILT._tile_is_uniform(lat, t) is want, "uniform[%s] should be %s" % (name, want)


def test_winding_primitive_reflection_vs_rotation():
    """_proper_rotation_onto: a rotated copy of a tile reads proper=True, a reflected copy
    proper=False — judged against the SAME tile's canonical list (convention-free fold-map parity),
    never against another tile's list. Checked on a triangle AND a hexagon tile."""
    import math
    for lat in (TL.TriLattice(8, 8), RT.RightTriLattice(8, 8), HX.HexLattice(R=4)):
        vs = lat.vertices_cart(next(iter(lat.tris)))
        th = math.radians(37)
        rot = [(x * math.cos(th) - y * math.sin(th) + 2.0, x * math.sin(th) + y * math.cos(th) - 1.0)
               for (x, y) in vs]
        ref = [tuple(reflect_point(p, (0.0, 0.0), (1.0, 0.4))) for p in vs]
        assert _proper(vs, rot) is True, "rotation must be proper"
        assert _proper(vs, ref) is False, "reflection must be improper"


def _proper(canon, ev):
    return SFILT._proper_rotation_onto(canon, ev, canon)[1]


@pytest.mark.parametrize("fid,tiling,K", FAM_21, ids=[f[0] for f in FAM_21])
def test_fold_implies_seam_ok_after_apply(fid, tiling, K):
    """INVARIANT: after SFILT.apply, no candidate can be BOTH foldable and seam-mismatched — a
    mirror/off-cell fold is demoted (foldable->False) so foldable ALWAYS implies seam_ok."""
    lat, cands = _enum_21(tiling, K)
    _skip_if_empty(cands, fid)
    for cand in cands:
        SFILT.apply(lat, cand)
        if cand["foldable"]:
            assert cand["seam_ok"] is True, "%s: foldable but seam_ok False: %s" % (fid, cand.get("seam_detail"))


def test_righttri_2plus1_mirror_seats_flat():
    """PHYSICAL GROUND TRUTH (2026-07-05): the 45-45-90 mirror-twin sheets 327ca6c4fc99 / 9c7a328f55fb
    (righttri 2+1, K=4, all-mirror) BOTH fold flat. Chirality is COSMETIC — a mirror arrival seats
    with the printed START/END seam flipped, not a jam (the prior isosceles mirror->JAM 'K-parity seam
    law' is refuted by the mirror pair itself). So the strict gate must KEEP every corr=True righttri
    2+1 fold; it may demote only a genuine off-cell miss, which does not occur here."""
    lat, it = FE.gen_21("righttri", 4, hubs=8)
    kept = 0
    for cand in itertools.islice(it, 6):
        if not cand["foldable"]:
            continue
        _, diag = _revalidate(lat, cand)
        ok, detail = SFILT.strict_fold_ok(lat, cand)
        assert diag["corr"] is True, "precondition: enumerated righttri 2+1 folds are corr=True"
        assert ok is True, "righttri 2+1 mirror fold must seat flat (cosmetic), got demote: %s" % detail
        kept += 1
    assert kept >= 1, "expected >=1 righttri 2+1 all-mirror fold at K=4 (the folded twins)"


def test_scalene_2plus1_folds_are_kept():
    """30-60-90 scalene is ASYMMETRIC (no equal edge pair): its on-cell mirror arrivals seat the
    mirror-partner cell with every edge role (V-M/M-G/V-G) matched — the user's verified-good
    scalene seating — so the strict gate must NOT demote any scalene 2+1 twist-fold, even though
    the honest chirality reads those arrivals as reflections."""
    lat, cands = _enum_21("scalene", 4)
    _skip_if_empty(cands, "scalene_21")
    seen_fold = 0
    for cand in cands:
        if not cand["foldable"]:
            continue
        seen_fold += 1
        ok, detail = SFILT.strict_fold_ok(lat, cand)
        assert ok is True, "scalene 2+1 fold wrongly demoted: %s" % detail
    if seen_fold == 0:
        pytest.skip("no scalene 2+1 twist-fold enumerated at K=4")


def test_apply_noop_on_equilateral_111_rec_cand():
    """The equilateral 1+1+1 path emits a solver `rec` (no top-level chains); SFILT.apply must no-op
    cleanly (no KeyError) and never demote — that family is a proven obstruction with correct labels."""
    lat, it = FE.gen_eq("1plus1plus1", 12)
    cand = next(itertools.islice(it, 1), None)
    if cand is None:
        pytest.skip("no equilateral 1+1+1 closing cand at K=12")
    foldable_before = cand["foldable"]
    SFILT.apply(lat, cand)                      # must not raise
    assert cand["foldable"] == foldable_before, "apply changed foldable on a rec-shaped 1+1+1 cand"
    assert cand.get("seam_ok") is True and "n/a" in cand.get("seam_detail", ""), \
        "apply should record a no-op (n/a) for geometry-less cands"


# =========================================================================== 8. chirality: gate vs
# INDEPENDENT oracle + the tile_chirality read-out contract. The seam gate reads the folded END winding
# from foldsim's component-BFS (seam_filter._fold_tiles); foldwalk folds the SAME tile by composing
# reflect_point along the literal tile WALK — a different code path. They must agree, else foldsim's
# folded geometry (hence the gate + the no-engine-edit constraint) is in doubt.
def _oracle_chirality(lat, chain):
    """(same_cell, proper) for a 1+1+1 chain's END tile folded back to its (rigid-hub) START tile via
    foldwalk's independent walk composition. `proper` is read convention-free: folded winding vs the
    SAME end tile's canonical winding = the walk's reflection parity (comparing against the START
    tile's canonical list instead was the pre-2026-07-02 bug — vertices_cart winding is a
    per-tile-TYPE convention, not uniform)."""
    walk = [tuple(t) for t in chain]
    foldM = FW.fold_transform(lat, walk)
    folded_end = FW.folded_polygon(lat, foldM, walk[-1])
    start_vs = lat.vertices_cart(walk[0])
    end_canon = lat.vertices_cart(walk[-1])
    same = SFILT._sets_match(start_vs, folded_end)
    proper = (SFILT._signed_area(end_canon) * SFILT._signed_area(folded_end)) > 0.0
    return same, proper


def test_righttri_111_foldwalk_oracle_confirms_gate_chirality():
    """INDEPENDENT PROOF (vindicates no-engine-edit): on righttri 1+1+1, foldwalk's walk-composition
    per-tile (same_cell, proper) must match seam_filter's foldsim-BFS chirality on EVERY chain end.
    Census law: closing righttri chains ALWAYS return mirrored (odd reflection parity), so the sweep
    must exercise mirror arrivals; proper arrivals do not occur on this family (asserting their
    absence is the sigma-parity test's job, per tile)."""
    n = agree = n_mirror = 0
    for K in (12, 14):
        lat, gen = FE.gen_111("righttri", K, hub=None)
        for cand in itertools.islice(gen, 200):
            tc = SFILT.tile_chirality(lat, cand)
            if not tc["per_tile"]:
                continue
            for i, ch in enumerate(cand["chains"]):
                g = tc["per_tile"][i]
                o_same, o_proper = _oracle_chirality(lat, ch)
                n += 1
                if (o_same == g["same_cell"]) and (not o_same or (o_proper == g["proper"])):
                    agree += 1
                n_mirror += (g["klass"] == "mirror")
    assert n > 0, "no righttri 1+1+1 chains enumerated"
    assert agree == n, "foldwalk oracle disagrees with gate chirality on %d/%d chains" % (n - agree, n)
    assert n_mirror > 0, "sweep must exercise mirror arrivals (got %d)" % n_mirror


def test_tile_chirality_contract():
    """tile_chirality read-out: klass in the closed vocabulary, n_mirror consistent with per-tile,
    symmetry='isosceles' on righttri, mixed never a single motion (one rigid map has ONE parity).
    Chirality is COSMETIC (2026-07-05 ground truth): all-mirror/mixed are NOT demoted — only a genuine
    off-cell arrival is. K-parity CHIRALITY fact (unchanged): K=4 is EVEN, so every closing arrival is
    a reflection -> NO all-proper here (they live at odd K); the JAM implication is what was removed."""
    lat, gen = FE.gen_21("righttri", 4, hubs=8)
    seen_proper = seen_mirror = 0
    for cand in itertools.islice(gen, 40):
        tc = SFILT.tile_chirality(lat, cand)
        assert tc["klass"] in ("all-proper", "all-mirror", "mixed", "uniform", "off-cell", "n/a")
        if not tc["per_tile"]:
            continue
        assert tc["symmetry"] == "isosceles", "righttri tile must classify isosceles"
        nm = sum(1 for p in tc["per_tile"] if p["klass"] == "mirror")
        assert tc["n_mirror"] == nm, "n_mirror %d != counted %d" % (tc["n_mirror"], nm)
        if tc["klass"] == "all-proper":
            seen_proper += 1
        if tc["klass"] == "mixed":
            assert tc["single_motion"] is False, \
                "mixed parities cannot share one rigid motion (a rigid map has one parity)"
        if tc["klass"] in ("all-mirror", "mixed"):
            assert tc["ok"] is True, \
                "%s is cosmetic and must NOT be demoted (only off-cell jams)" % tc["klass"]
            seen_mirror += 1
    assert seen_proper == 0, \
        "K-parity chirality: %d all-proper righttri folds at EVEN K=4 (expected none)" % seen_proper
    assert seen_mirror > 0, "righttri 2+1 K=4 must exercise mirror/mixed arrivals"


def _mirror_cand_righttri(cand, W):
    """Global mirror image of a righttri candidate about the W-square block's vertical mid-axis:
    square column i -> W-1-i, orientation E<->W (N,S fixed). Order-preserving on all lists, so
    label pairing (A->A ...) and domino pairing (strand[k]<->partners[k]) mirror exactly."""
    def mt(t):
        i, j, o = t
        return (W - 1 - i, j, {"E": "W", "W": "E", "N": "N", "S": "S"}[o])
    out = dict(cand)
    for k in ("footprint", "end_footprint", "partners", "two_tris"):
        if k in cand:
            out[k] = [mt(tuple(t)) for t in cand[k]]
    out["chains"] = [[mt(tuple(t)) for t in ch] for ch in cand["chains"]]
    if "region" in cand:
        out["region"] = {mt(tuple(t)) for t in cand["region"]}
    return out


def test_righttri_chirality_is_mirror_invariant():
    """PIN of the 2026-07-02 defect: a candidate and its global mirror image are the SAME physical
    fold (the sheet flipped over), so tile_chirality must give identical klass/single_motion/ok.
    The old cross-tile signed-area compare violated exactly this — the mirror pair 9c7a328f55fb /
    327ca6c4fc99 shipped with OPPOSITE seam classes (all-proper FOLD vs all-mirror JAM)."""
    lat, gen = FE.gen_21("righttri", 4, hubs=8)
    n = 0
    for cand in itertools.islice(gen, 12):
        mc = _mirror_cand_righttri(cand, lat.M)
        a = SFILT.tile_chirality(lat, cand)
        b = SFILT.tile_chirality(lat, mc)
        if not a["per_tile"] or not b["per_tile"]:
            continue
        n += 1
        assert (a["klass"], a["single_motion"], a["ok"]) == (b["klass"], b["single_motion"], b["ok"]), \
            "mirror-image candidate got a different seam read-out (chirality not mirror-invariant)"
    assert n > 0, "no righttri 2+1 candidates enumerated for the mirror-invariance pin"


def test_righttri_chirality_matches_sigma_parity():
    """INDEPENDENT combinatorial oracle covering BOTH decomps (the 2+1 oracle that didn't exist):
    righttri is a kaleidoscope tiling — every crease is a mirror line and every mirror flips the
    bipartite sigma — so an ON-CELL arrival is a proper rotation iff sigma(START)==sigma(END).
    The gate's convention-free per-tile `proper` must equal that, tile by tile. Ks cover BOTH
    parities (K-parity law: even K -> mirror arrivals, odd K -> proper arrivals)."""
    checked = 0
    for decomp, K in (("2plus1", 4), ("2plus1", 5), ("1plus1plus1", 12), ("1plus1plus1", 13)):
        lat, gen = (FE.gen_21("righttri", K, hubs=8) if decomp == "2plus1"
                    else FE.gen_111("righttri", K, hub=None))
        for cand in itertools.islice(gen, 60):
            tc = SFILT.tile_chirality(lat, cand)
            if not tc["per_tile"]:
                continue
            for p, etile, scell in zip(tc["per_tile"], cand["end_footprint"], cand["footprint"]):
                if not p["same_cell"]:
                    continue
                want = lat.sigma(tuple(scell)) == lat.sigma(tuple(etile))
                assert p["proper"] == want, \
                    "%s: gate proper=%s but sigma-parity law says %s" % (decomp, p["proper"], want)
                checked += 1
    assert checked > 0, "sigma-parity pin checked no tiles"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
