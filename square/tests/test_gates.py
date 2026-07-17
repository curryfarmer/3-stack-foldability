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


# ---------- canonical_hash vs transform_arrow replay-equivariance (all 8 D4 elements) ----------
# The real contract, pinned so nobody "fixes" transform_arrow into false replay-equivariance:
#  * canonical_hash (the dedup KEY) is invariant under EVERY D4 element on a square sheet -- it
#    minimizes over the sheet's automorphism subgroup, which is all 8 of D4 when m == n. Odd rotations
#    included. This is why the transform_arrow non-equivariance never moves a count or a verdict.
#  * transform_arrow is replay-equivariant with apply_transform ONLY on the even-rotation elements
#    (the flip subgroup + rot0/rot2); on the odd rotations it is not (by design -- see
#    square.py transform_arrow and test_physical_deciders.py:9-11). So full-D4 arrow *replay*
#    invariance is false: the "NOT invariant under odd rotations" caveat is about replaying the
#    representative back as geometry, NOT about the hash.

# A small ASYMMETRIC fold on an 8x8 (square) sheet, placed centrally so a replay stays on-grid.
_SQ_M = _SQ_N = 8
_SQ_FP = {"shape": "L", "cells": [(3, 3), (4, 3), (3, 4)]}
_SQ_CHAINS = [{"kind": "1chain", "baseCells": [(3, 3)], "foldArrows": ["R", "D"]},
              {"kind": "1chain", "baseCells": [(4, 3)], "foldArrows": ["R", "U"]},
              {"kind": "1chain", "baseCells": [(3, 4)], "foldArrows": ["U", "L"]}]


def _transform_fold(t):
    """Apply D4 element t to _SQ_FP/_SQ_CHAINS via the engine's own apply_transform (cells) +
    transform_arrow (arrows). I/O: (t) -> (fp, chains)."""
    fp = {"shape": _SQ_FP["shape"],
          "cells": [Search.apply_transform(t, c[0], c[1], _SQ_M, _SQ_N) for c in _SQ_FP["cells"]]}
    chains = [{"kind": c["kind"],
               "baseCells": [Search.apply_transform(t, b[0], b[1], _SQ_M, _SQ_N) for b in c["baseCells"]],
               "foldArrows": [Search.transform_arrow(t, a) for a in c["foldArrows"]]}
              for c in _SQ_CHAINS]
    return fp, chains


def _replay_final(base_cell, arrows, m, n):
    """Replay a 1-chain from `base_cell` following `arrows`; sorted final cells, or None if a fold
    leaves the grid. I/O: ((x,y), [dir], m, n) -> [(x,y), ...] | None."""
    p = Fold.initial_placement([base_cell])
    for a in arrows:
        p = Fold.make_fold(p, a, m, n)
        if p is None:
            return None
    return sorted(p["cells"])


def test_canonical_hash_invariant_under_all_of_d4_on_square_sheet():
    """Dedup key is invariant under ALL 8 D4 elements on a square sheet (odd rotations included),
    because canonical_hash minimizes over the automorphism subgroup = all of D4 when m == n."""
    base = Search.canonical_hash(_SQ_FP, _SQ_CHAINS, _SQ_M, _SQ_N)
    for rot in range(4):
        for flip in range(2):
            fp, chains = _transform_fold({"rot": rot, "flip": flip})
            assert Search.canonical_hash(fp, chains, _SQ_M, _SQ_N) == base, \
                f"canonical_hash moved under rot={rot} flip={flip}"


def test_transform_arrow_replay_equivariant_only_on_even_rotations():
    """transform_arrow is replay-equivariant with apply_transform ONLY for the even-rotation elements
    (flip subgroup + rot0/rot2); the odd rotations (rot1/rot3) are NOT -- full-D4 arrow replay
    invariance is false by design. (The dedup key stays invariant regardless -- see the test above.)"""
    bc, arrows = (3, 3), ["R", "D"]
    orig = _replay_final(bc, arrows, _SQ_M, _SQ_N)
    assert orig is not None
    for rot in range(4):
        for flip in range(2):
            t = {"rot": rot, "flip": flip}
            b2 = Search.apply_transform(t, bc[0], bc[1], _SQ_M, _SQ_N)
            a2 = [Search.transform_arrow(t, a) for a in arrows]
            replayed = _replay_final(b2, a2, _SQ_M, _SQ_N)
            expected = sorted(Search.apply_transform(t, x, y, _SQ_M, _SQ_N) for (x, y) in orig)
            if rot in (0, 2):     # even rotation: replay reproduces the transformed geometry
                assert replayed == expected, f"even element rot={rot} flip={flip} broke replay"
            else:                 # odd rotation: replay does NOT reproduce it (by design)
                assert replayed != expected, f"odd element rot={rot} flip={flip} unexpectedly replayed"


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
