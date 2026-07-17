"""test_grid_ingest_tri.py — arbitrary drawn-REGION ingest for the triangle 1+1+1 engine (S6).

Drives foldgrid_tri LIVE / in-process (the test_fold_validity.py style, NOT the test_tri_reference.py
snapshot style). Four tiers:

  Tier 1  round-trip equivalence (the key proof, per tiling): every closing fold the SHIPPED authority
          (gen_111 / gen_eq) finds is RE-DISCOVERED when its exact region is fed back through the region
          ingest, with the same loop-index-sigma foldable verdict (non-equilateral, where the authority
          also uses path sigma; equilateral's gen_eq uses the legacy bipartite sigma -- the parked
          eq-111-sigma bug -- so only re-discovery is asserted there).
  Tier 0  invariants that hold on ANY region: chains cover exactly S, no overlap, no escape, the physical
          closure gate actually ran, foldable => Tw == [0,0,0]; malformed regions raise ValueError.
  Tier 3  hand/committed fixture (fixtures/grids/) + the equilateral 1+1+1 obstruction (closes, 0 foldable).
  Tier 4  fuzz (@slow): seeded connected regions per tiling, len % 3 == 0 -> Tier-0 holds, never escapes.

sys.path is set by triangle/tests/conftest.py (via triangle/_bootstrap.py) -- never co-import square/.
Run: python -m pytest triangle/tests/test_grid_ingest_tri.py -q
"""
import itertools
import json
import os
import random
import time
import zlib

import pytest

import find_example as FE     # noqa: E402  gen_111 / gen_eq (the shipped authority = round-trip reference)
import foldgrid_tri as FG     # noqa: E402  the module under test
import foldclose as FC        # noqa: E402  reflection_closes_111 (independent re-check of the gate)
import trilattice as TL       # noqa: E402  fuzz: full equilateral lattice + triangle_cells (scalene faces)
import righttri as RT         # noqa: E402  fuzz: full righttri lattice
import scalene as SC          # noqa: E402  fuzz: full scalene lattice
import hexlattice as HX       # noqa: E402  fuzz: full hex lattice


# Wall-clock budget for the shipped-authority searches that seed the round-trip proof. Generous and
# env-overridable (FOLD_TRI_TEST_BUDGET, seconds) so a slow CI *lengthens* the search rather than
# returning 0 folds -- a too-tight budget would silently turn the core round-trip proof into a no-op
# (the KPLAN cases below are KNOWN-foldable, so they ASSERT folds were found, never skip to green).
BUDGET = float(os.environ.get("FOLD_TRI_TEST_BUDGET", "300"))


# --------------------------------------------------------------------------- helpers
def _ref_chains(cand):
    """The 3 chains of a shipped-authority candidate as tuple-tile lists (gen_111 or gen_eq shape)."""
    src = cand["chains"] if "chains" in cand else cand["rec"]["chains"]
    return [[tuple(t) for t in c] for c in src]


def _rec_chains(rec):
    """The 3 chains of an FG record as tuple-tile lists (FG stores them as JSON-ish lists)."""
    return [[tuple(t) for t in c] for c in rec["chains"]]


def _ref_folds(tiling, K, cap, budget=BUDGET):
    """(lat, [cand,...]) — up to `cap` closing 1+1+1 folds from the shipped authority at chain length K.
    Equilateral goes through gen_eq (PO/solve_foldable); the other three through gen_111."""
    if tiling == "equilateral":
        lat, it = FE.gen_eq("1plus1plus1", K)
    else:
        lat, it = FE.gen_111(tiling, K, hub=None, budget=budget, t0=time.time())
    return lat, list(itertools.islice(it, cap))


def _region_lists(chains):
    """The region (union of chain cells) as a sorted list of id-LISTS (a fold-grid `cells` array)."""
    return [list(t) for t in sorted({t for w in chains for t in w})]


# gen_111's first-closing K per non-equilateral tiling (find_example.KPLAN); equilateral folds at K=12.
ROUNDTRIP_CASES = [("righttri", 12), ("scalene", 14), ("hex", 4), ("equilateral", 12)]


# --------------------------------------------------------------------------- Tier 1: round-trip
@pytest.mark.parametrize("tiling,K", ROUNDTRIP_CASES)
def test_roundtrip_rediscovers_authority_folds(tiling, K):
    """Every closing fold gen_111/gen_eq finds is re-discovered by the region ingest on its exact
    region, with the same foldable verdict (path-sigma tilings). This simultaneously proves the Path-A
    exact-cover enumeration is correct/complete on all four tilings."""
    _, folds = _ref_folds(tiling, K, cap=4)
    assert folds, ("no closing %s fold at K=%d within %.0fs -- this is a KNOWN-foldable KPLAN case, "
                   "so 0 folds is a real failure (raise FOLD_TRI_TEST_BUDGET if the CI is merely slow)"
                   % (tiling, K, BUDGET))
    for cand in folds:
        chains = _ref_chains(cand)
        recs = FG.run(tiling, _region_lists(chains))
        keys = {FG._canon(_rec_chains(r)) for r in recs}
        assert FG._canon(chains) in keys, "%s K=%d fold not re-discovered by region ingest" % (tiling, K)
        if tiling != "equilateral":                    # gen_eq uses the legacy bipartite sigma (parked bug)
            matched = next(r for r in recs if FG._canon(_rec_chains(r)) == FG._canon(chains))
            assert matched["foldable"] == cand["foldable"], \
                "%s K=%d: ingest foldable verdict disagrees with gen_111" % (tiling, K)


# --------------------------------------------------------------------------- Tier 0: invariants
def _assert_tier0(lat, tiling, recs):
    """Invariants every emitted record must satisfy on ANY region."""
    S = set(lat.tris)
    for r in recs:
        chains = _rec_chains(r)
        cells = [t for w in chains for t in w]
        cover = set(cells)
        assert cover == S, "chains must cover exactly the region"
        assert len(cells) == len(cover), "chains must not overlap"
        assert cover <= S, "no chain cell may escape the region"
        assert FC.reflection_closes_111(lat, chains), "every emitted fold must pass the closure gate"
        assert r["decomp"] == "1plus1plus1"
        assert set(map(tuple, r["region"])) == S
        if r["foldable"]:
            assert r["tw"] == [0, 0, 0], "foldable => Tw == [0,0,0]"


@pytest.mark.parametrize("tiling,K", [("righttri", 12), ("hex", 4)])
def test_tier0_invariants_live(tiling, K):
    _, folds = _ref_folds(tiling, K, cap=1)
    assert folds, ("no closing %s fold at K=%d within %.0fs -- KNOWN-foldable KPLAN case "
                   "(raise FOLD_TRI_TEST_BUDGET if the CI is merely slow)" % (tiling, K, BUDGET))
    cells = _region_lists(_ref_chains(folds[0]))
    lat = FG.build_lattice(tiling, cells)
    recs = FG.enumerate_folds(lat, tiling)
    assert recs, "region derived from a known closing fold must yield >= 1 closing fold"
    _assert_tier0(lat, tiling, recs)


def test_first_toggle_returns_one():
    """--first / first=True short-circuits at the first closing fold."""
    _, folds = _ref_folds("hex", 4, cap=1)
    assert folds, ("no closing hex fold at K=4 within %.0fs -- KNOWN-foldable KPLAN case "
                   "(raise FOLD_TRI_TEST_BUDGET if the CI is merely slow)" % BUDGET)
    cells = _region_lists(_ref_chains(folds[0]))
    one = FG.run("hex", cells, first=True)
    allf = FG.run("hex", cells)
    assert len(one) == 1
    assert len(allf) >= 1
    assert FG._canon(_rec_chains(one[0])) in {FG._canon(_rec_chains(r)) for r in allf}


# --------------------------------------------------------------------------- Tier 0: guards
def test_guard_empty_region():
    with pytest.raises(ValueError):
        FG.build_lattice("equilateral", [])


def test_guard_not_divisible_by_three():
    lat = TL.TriLattice(2, 3)
    with pytest.raises(ValueError):
        FG.build_lattice("equilateral", [list(t) for t in lat.tris[:4]])   # 4 % 3 != 0


def test_guard_disconnected_region():
    lat = TL.TriLattice(3, 3)
    tiles = [list(t) for t in lat.tris]
    # two opposite-corner tiles + one neighbor of the first -> 3 cells, not edge-connected as a set
    with pytest.raises(ValueError):
        FG.build_lattice("equilateral", [tiles[0], tiles[1], tiles[-1]])


def test_guard_unknown_tiling():
    with pytest.raises(ValueError):
        FG.build_lattice("penrose", [[0, 0], [1, 0], [2, 0]])


def test_guard_duplicate_cells():
    lat = TL.TriLattice(2, 3)
    t = list(lat.tris[0])
    with pytest.raises(ValueError):
        FG.build_lattice("equilateral", [t, t, list(lat.tris[1])])


# --------------------------------------------------------------------------- Tier 3: fixture + obstruction
def test_fixture_hex_small(fixtures_dir):
    """Committed fold-grid fixture: a fixed 12-cell hex region. Deterministic golden counts."""
    path = os.path.join(fixtures_dir, "grids", "hex_small_K4.json")
    spec = json.load(open(path))
    assert spec["schema"] == "fold-grid/1" and spec["tiling"] == "hex" and spec["stacks"] == [3]
    lat = FG.build_lattice("hex", spec["cells"])
    recs = FG.enumerate_folds(lat, "hex")
    _assert_tier0(lat, "hex", recs)
    assert len(recs) == 22, "hex_small_K4 closing-fold count drifted (was 22): %d" % len(recs)
    assert sum(r["foldable"] for r in recs) == 2, "hex_small_K4 foldable count drifted (was 2)"


def test_equilateral_obstruction_zero_foldable():
    """The equilateral 1+1+1 obstruction (cf. test_foldclose_truth K=12: closes, 0 foldable). Any region
    from a K=12 equilateral closing fold re-enumerates to closing folds but ZERO predicted foldable
    (loop-index sigma)."""
    _, folds = _ref_folds("equilateral", 12, cap=3)
    assert folds, ("no closing equilateral fold at K=12 within %.0fs -- KNOWN-closing KPLAN case "
                   "(raise FOLD_TRI_TEST_BUDGET if the CI is merely slow)" % BUDGET)
    for cand in folds:
        lat = FG.build_lattice("equilateral", _region_lists(_ref_chains(cand)))
        recs = FG.enumerate_folds(lat, "equilateral")
        assert recs, "an equilateral K=12 closing region must yield closing folds"
        assert sum(r["foldable"] for r in recs) == 0, "equilateral 1+1+1 is obstructed -> 0 foldable"


# --------------------------------------------------------------------------- Tier 4: fuzz
def _full_lattice(tiling):
    if tiling == "equilateral":
        return TL.TriLattice(6, 6)
    if tiling == "righttri":
        return RT.RightTriLattice(4, 4)
    if tiling == "scalene":
        return SC.ScaleneLattice(faces=TL.triangle_cells(6))
    return HX.HexLattice(R=3)


def _grow_region(lat, size, rng):
    """A connected sub-region of exactly `size` tiles, grown by random BFS over lat.adj (so it is always
    edge-connected). None if the component is smaller than `size`."""
    start = rng.choice(lat.tris)
    region, inreg = [start], {start}
    frontier = set(lat.adj[start])
    while len(region) < size and frontier:
        nxt = rng.choice(sorted(frontier, key=repr))
        frontier.discard(nxt)
        region.append(nxt)
        inreg.add(nxt)
        for nb in lat.adj[nxt]:
            if nb not in inreg:
                frontier.add(nb)
    return region if len(region) == size else None


@pytest.mark.slow
@pytest.mark.parametrize("tiling", ["equilateral", "righttri", "scalene", "hex"])
def test_fuzz_tier0_never_escapes(tiling):
    """Seeded connected regions (len % 3 == 0): ingest never crashes/escapes; Tier-0 holds on whatever
    it emits (which may be zero closing folds -- that is fine, only that it never emits a bad one)."""
    # crc32 (deterministic) not the built-in hash (PYTHONHASHSEED-salted per process), so every run
    # sweeps the SAME per-tiling regions -- a reproducible fuzz, not a flaky guard that changes nightly.
    rng = random.Random(0xF01D + zlib.crc32(tiling.encode()))
    full = _full_lattice(tiling)
    checked = 0
    for _ in range(8):
        size = 3 * rng.randint(1, 4)
        region = _grow_region(full, size, rng)
        if region is None:
            continue
        cells = [list(t) for t in region]
        lat = FG.build_lattice(tiling, cells)          # connected by construction
        recs = FG.enumerate_folds(lat, tiling)
        _assert_tier0(lat, tiling, recs)               # empty recs vacuously passes
        checked += 1
    assert checked >= 1, "fuzz generated no valid region for %s" % tiling
