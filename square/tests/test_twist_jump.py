"""test_twist_jump.py — the shipped 2+1 jump-strand twist (square/twist/twist_jump.py) is Model B.

twist_jump promotes the experimental Model-B reduction into the production engine so
search.twist_check decides 2+1. This pins the two shipped entry points to the known Tw on three
patterns spanning every outcome:

  * a 6x4 fold              -> Tw = 0     (foldable)
  * 6x7 jam 4cc6f36d0ca4    -> Tw = -720  (left-handed self-twist, physically JAMmed)
  * 6x7 jam 8b33b2ba5329    -> Tw = +720  (right-handed self-twist, physically JAMmed)

and checks the two shipped entry points agree:
  twist_2plus1_from_sol (re-replays a stored blob)  ==  twist_2plus1_from_chains (live placements).

A mismatch here means the shipped engine has drifted from the validated math. Pure compute; no disk.

WHAT WAS DROPPED AND WHY. This file used to cross-check the shipped result against the research
reference `twist_models.modelB` (which rode on experimental/common.py). `twist_models` was deleted
with the SQLite/validation layer and exists nowhere in the tree -- it survives only in git history
(b1c24b4, e928819, f17ddcb). The reference comparison is therefore gone, but the EXPECTED Tw values
it agreed with are hand-recorded above and still pinned: the three `want_tw` constants ARE Model B's
answer for these patterns. This suite keeps the shipped-vs-known and entry-point-agreement checks;
only the second opinion is lost.
"""
import twist_jump            # noqa: E402  (square/ on sys.path via conftest.py)

# (label, expected_tw, {m, n, sol}) — sol carries chains with baseCells/foldArrows only (the stored
# blob shape). Extracted from results/folddb.sqlite3 (the jams are the physically-folded deciders).
CASES = [
    ("fold_6x4_Tw0", 0, {
        "m": 6, "n": 4, "sol": {"decomposition": "2+1", "chains": [
            {"baseCells": [{"x": 2, "y": 0}, {"x": 2, "y": 1}],
             "foldArrows": ["L", "L", "D", "R", "R", "R", "R"]},
            {"baseCells": [{"x": 3, "y": 0}],
             "foldArrows": ["D", "R", "U", "R", "D", "D", "D"]}]}}),
    ("jam_6x7_minus720", -720, {
        "m": 6, "n": 7, "sol": {"decomposition": "2+1", "chains": [
            {"baseCells": [{"x": 0, "y": 1}, {"x": 1, "y": 1}],
             "foldArrows": ["U", "R", "R", "D", "D", "D", "D", "D", "D", "L", "L", "U", "U"]},
            {"baseCells": [{"x": 2, "y": 1}],
             "foldArrows": ["R", "D", "L", "L", "L", "D", "R", "R", "R", "D", "D", "L", "U"]}]}}),
    ("jam_6x7_plus720", 720, {
        "m": 6, "n": 7, "sol": {"decomposition": "2+1", "chains": [
            {"baseCells": [{"x": 0, "y": 2}, {"x": 1, "y": 2}],
             "foldArrows": ["U", "U", "R", "R", "D", "D", "D", "D", "D", "D", "L", "L", "U"]},
            {"baseCells": [{"x": 2, "y": 2}],
             "foldArrows": ["U", "R", "D", "D", "L", "L", "L", "D", "R", "R", "R", "D", "L"]}]}}),
]


def _chains_with_placements(m, n, sol):
    """Reconstruct the live-engine chain shape (baseCells + replayed placements) from a stored blob."""
    return [{"baseCells": c["baseCells"],
             "placements": twist_jump.replay(c["baseCells"], c["foldArrows"], m, n)}
            for c in sol["chains"]]


def test_shipped_matches_expected():
    """twist_jump's two entry points both == the known Model-B Tw, and agree with each other."""
    for label, want_tw, case in CASES:
        m, n, sol = case["m"], case["n"], case["sol"]

        ship = twist_jump.twist_2plus1_from_sol(sol, m, n)          # re-replay path
        assert round(ship["tw"]) == want_tw, f"{label}: shipped Tw {ship['tw']} != {want_tw}"
        assert ship["pass"] is (want_tw == 0), f"{label}: shipped pass disagrees"

        live = twist_jump.twist_2plus1_from_chains(_chains_with_placements(m, n, sol))  # live path
        assert live["decided"] is True
        assert round(live["tw"]) == want_tw, f"{label}: live Tw {live['tw']} != {want_tw}"
        assert live["pass"] is (want_tw == 0)
        assert len(live["pairs"]) == 1 and round(live["pairs"][0]["tw"]) == want_tw


def test_engine_twist_check_decides_2plus1():
    """search.twist_check now returns decided=True (not the legacy NULL) for a 2+1 pair."""
    import search
    label, want_tw, case = CASES[1]                                # a jam
    m, n, sol = case["m"], case["n"], case["sol"]
    res = search.twist_check(_chains_with_placements(m, n, sol))
    assert res["decided"] is True
    assert res["pass"] is False                                    # Tw != 0 -> jam
    assert round(res["pairs"][0]["tw"]) == want_tw


def test_non_2plus1_is_undecided():
    """A chain set that is NOT a 2-chain + 1-chain pair returns the legacy undecided shape
    (exercises the else branch of twist_2plus1_from_chains -- _split_2plus1 -> None)."""
    chains = [{"baseCells": [{"x": 0, "y": 0}]},                   # 1 + 1, not 2 + 1
              {"baseCells": [{"x": 1, "y": 0}]}]
    res = twist_jump.twist_2plus1_from_chains(chains)
    assert res == {"decided": False, "pass": None, "pairs": [], "tw": None, "idx": None}


def _pl(*cellpairs):
    """Fake placements: each (a, b) becomes a placement whose domino cells idx0=a, idx1=b."""
    return [{"cells": [a, b]} for a, b in cellpairs]


def test_pick_canon_idx_skips_diagonal_seam():
    """idx 0's hub seam is diagonal so it is rejected; idx 1 is clean so it is chosen (return 1)."""
    placements2 = _pl(((0, 0), (0, 0)), ((1, 1), (1, 0)))          # idx0 end (1,1), idx1 end (1,0)
    path1 = [twist_jump.cc((3, 0)), twist_jump.cc((2, 0))]         # end (2,0), start (3,0)
    # idx0 hub: (1,1)->(2,0) is diagonal (reject); idx1 hub: (1,0)->(2,0) unit, close far (accept).
    assert twist_jump.pick_canon_idx(placements2, path1) == 1


def test_pick_canon_idx_both_diagonal_fallback():
    """Both strands present a diagonal hub seam -> the loop exhausts and falls back to idx 0."""
    placements2 = _pl(((0, 0), (4, 4)), ((1, 1), (3, 3)))          # idx0 end (1,1), idx1 end (3,3)
    path1 = [twist_jump.cc((5, 5)), twist_jump.cc((2, 2))]         # end (2,2)
    # idx0 hub (1,1)->(2,2) diagonal; idx1 hub (3,3)->(2,2) diagonal -> neither idx accepted.
    assert twist_jump.pick_canon_idx(placements2, path1) == 0


def test_pick_canon_idx_unequal_lengths_no_indexerror():
    """Regression: the closing seam uses loop[-1] (length-agnostic). A 3-placement 2-chain against a
    1-point 1-chain must not IndexError -- the old loop[2*k-1] indexed off the end."""
    placements2 = _pl(((0, 0), (0, 0)), ((1, 0), (1, 0)), ((2, 0), (2, 0)))
    path1 = [twist_jump.cc((3, 0))]                                # shorter than the 2-chain strand
    assert twist_jump.pick_canon_idx(placements2, path1) == 0
