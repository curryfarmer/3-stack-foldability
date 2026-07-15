"""test_gates.py — unit tests for the engine's maths primitives and verdict gates.

Hand-derived expected values (no golden files) so these pin the core geometry directly:
reflection arithmetic, fold boundary handling, the parity rule, exit-footprint classification,
twist sign, and canonical-hash invariances. Math fidelity lives or dies here.
"""
import fold as Fold        # noqa: E402  (sys.path set in conftest.py)
import search as Search    # noqa: E402


# ---------- reflect_scalar / make_fold geometry ----------

def test_reflect_scalar_formula():
    # 2c - 1 - v: cell center (v+0.5) mirrored about boundary c.
    assert Fold.reflect_scalar(2, 3) == 3      # 6-1-2
    assert Fold.reflect_scalar(0, 0) == -1     # 0-1-0
    assert Fold.reflect_scalar(1, 2) == 2      # 4-1-1


def test_reflect_scalar_equals_reflect_point_on_axis_crease():
    """The integer cell-reflection fast-path is exactly the generic reflect_point on an
    axis-aligned crease (no float rounding) — the equivalence the 'one primitive' refactor relies
    on. Vertical crease x=c through (c,0)-(c,1); cell center (v+0.5, 0.5) -> (2c-1-v)+0.5."""
    from lattice.reflect import reflect_point
    for v in range(-3, 14):
        for c in range(0, 13):
            assert reflect_point((v + 0.5, 0.5), (c, 0), (c, 1))[0] == Fold.reflect_scalar(v, c) + 0.5
            assert reflect_point((v, 0), (c, 0), (c, 1)) == (float(2 * c - v), 0.0)


def test_make_fold_single_cell_four_dirs():
    p = Fold.initial_placement([(2, 2)])
    assert Fold.make_fold(p, "R", 6, 6)["cells"] == [(3, 2)]
    assert Fold.make_fold(p, "L", 6, 6)["cells"] == [(1, 2)]
    assert Fold.make_fold(p, "D", 6, 6)["cells"] == [(2, 3)]
    assert Fold.make_fold(p, "U", 6, 6)["cells"] == [(2, 1)]


def test_make_fold_parity_toggles():
    p = Fold.initial_placement([(2, 2)])
    r = Fold.make_fold(p, "R", 6, 6)
    assert (r["parityH"], r["parityV"]) == (1, 0)
    d = Fold.make_fold(p, "D", 6, 6)
    assert (d["parityH"], d["parityV"]) == (0, 1)


def test_make_fold_off_grid_returns_none():
    p = Fold.initial_placement([(0, 0)])
    assert Fold.make_fold(p, "L", 6, 6) is None   # -> (-1,0)
    assert Fold.make_fold(p, "U", 6, 6) is None   # -> (0,-1)


def test_make_fold_two_cell_chain():
    p = Fold.initial_placement([(0, 0), (1, 0)])
    r = Fold.make_fold(p, "R", 6, 6)
    assert sorted(r["cells"]) == [(2, 0), (3, 0)]


# ---------- exit_footprint_check ----------

def _leaf(cells):
    """A chain whose only (and final) placement is the given cell list. I/O: (cells)->chain."""
    return {"placements": [Fold.initial_placement(list(cells))]}


def test_exit_footprint_L_and_rect():
    L = [_leaf([(0, 0)]), _leaf([(1, 0)]), _leaf([(0, 1)])]
    assert Search.exit_footprint_check(L, "L") is True
    assert Search.exit_footprint_check(L, "Rect") is False
    R = [_leaf([(0, 0)]), _leaf([(1, 0)]), _leaf([(2, 0)])]
    assert Search.exit_footprint_check(R, "Rect") is True
    assert Search.exit_footprint_check(R, "L") is False


def test_exit_footprint_rejects_overlap_and_bad_shape():
    dup = [_leaf([(0, 0)]), _leaf([(0, 0)]), _leaf([(0, 1)])]
    assert Search.exit_footprint_check(dup, "L") is False
    spread = [_leaf([(0, 0)]), _leaf([(2, 0)]), _leaf([(0, 2)])]
    assert Search.exit_footprint_check(spread, "L") is False


# ---------- parity_check ----------

def test_parity_2plus1_vertical_axis_requires_nV_even():
    # bases (0,0)/(1,0) adjacent to (0,1): vertical A/B crease -> nV must be even.
    base2 = [(0, 0), (1, 0)]
    ok = [{"baseCells": base2, "foldArrows": ["U", "D"]},          # nV=2 even
          {"baseCells": [(0, 1)], "foldArrows": ["U", "U"]}]       # nV=2 even
    assert Search.parity_check(ok) is True
    bad = [{"baseCells": base2, "foldArrows": ["U", "D"]},
           {"baseCells": [(0, 1)], "foldArrows": ["U", "U", "U"]}]  # nV=3 odd
    assert Search.parity_check(bad) is False


def test_parity_2plus1_horizontal_axis_requires_nH_even():
    base2 = [(0, 0), (0, 1)]
    ok = [{"baseCells": base2, "foldArrows": ["L", "R"]},          # nH=2 even
          {"baseCells": [(1, 0)], "foldArrows": ["L", "R"]}]
    assert Search.parity_check(ok) is True
    bad = [{"baseCells": base2, "foldArrows": ["L", "R", "L"]},    # nH=3 odd
           {"baseCells": [(1, 0)], "foldArrows": ["L", "R"]}]
    assert Search.parity_check(bad) is False


def test_parity_1plus1plus1_legacy_rule():
    # 3 chains -> parallel_fold_axis None -> legacy: each chain needs nH even and nV odd.
    good = [{"baseCells": [(0, 0)], "foldArrows": ["L", "R", "U"]},   # nH=2,nV=1
            {"baseCells": [(1, 0)], "foldArrows": ["U", "L", "R"]},
            {"baseCells": [(0, 1)], "foldArrows": ["D", "R", "L"]}]
    assert Search.parity_check(good) is True
    bad = [{"baseCells": [(0, 0)], "foldArrows": ["L", "U"]},         # nH=1 odd
           {"baseCells": [(1, 0)], "foldArrows": ["U", "L", "R"]},
           {"baseCells": [(0, 1)], "foldArrows": ["D", "R", "L"]}]
    assert Search.parity_check(bad) is False


# ---------- canonical_hash invariances ----------

def _mk_footprint():
    return {"shape": "L", "cells": [(0, 0), (1, 0), (0, 1)]}


def _mk_chains():
    return [{"kind": "2chain", "baseCells": [(0, 0), (1, 0)], "foldArrows": ["R", "D"]},
            {"kind": "1chain", "baseCells": [(0, 1)], "foldArrows": ["D", "R"]}]


def test_canonical_hash_deterministic_and_chain_order_invariant():
    fp = _mk_footprint()
    a = Search.canonical_hash(fp, _mk_chains(), 6, 6)
    b = Search.canonical_hash(fp, list(reversed(_mk_chains())), 6, 6)
    assert a == b               # chain ordering must not change the hash
    assert Search.canonical_hash(fp, _mk_chains(), 6, 6) == a   # determinism


def test_canonical_hash_d4_invariant_under_manual_flip():
    # Apply the engine's own flip transform to footprint+chains; hash must be identical.
    fp = _mk_footprint()
    chains = _mk_chains()
    t = {"rot": 0, "flip": 1}
    fp2 = {"shape": "L",
           "cells": [Search.apply_transform(t, c[0], c[1], 6, 6) for c in fp["cells"]]}
    chains2 = [{"kind": c["kind"],
                "baseCells": [Search.apply_transform(t, b[0], b[1], 6, 6) for b in c["baseCells"]],
                "foldArrows": [Search.transform_arrow(t, a) for a in c["foldArrows"]]}
               for c in chains]
    assert Search.canonical_hash(fp2, chains2, 6, 6) == Search.canonical_hash(fp, chains, 6, 6)


# ---------- twist sign (1+1+1 pairwise loop) ----------

def test_twist_decided_for_2plus1():
    """A 2-chain + 1-chain is now DECIDED by the jump-strand reduction (Model B) — twist_check no
    longer returns the legacy NULL for 2+1. (The Tw values themselves are pinned in
    test_twist_jump.py; here we only assert the dispatch routes a 2+1 to a verdict.)"""
    chains = [{"baseCells": [(0, 0), (1, 0)], "placements": [Fold.initial_placement([(0, 0), (1, 0)])]},
              {"baseCells": [(0, 1)], "placements": [Fold.initial_placement([(0, 1)])]}]
    res = Search.twist_check(chains)
    assert res["decided"] is True and res["pass"] is not None


def test_twist_undecided_for_unhandled_decomposition():
    """A decomposition that is neither 1+1+1 (all monominoes) nor 2+1 (one domino + one monomino) —
    here two dominoes — stays undecided (decided=False), the non-filtering legacy shape."""
    chains = [{"baseCells": [(0, 0), (1, 0)], "placements": [Fold.initial_placement([(0, 0), (1, 0)])]},
              {"baseCells": [(0, 1), (1, 1)], "placements": [Fold.initial_placement([(0, 1), (1, 1)])]}]
    res = Search.twist_check(chains)
    assert res["decided"] is False and res["pass"] is None
