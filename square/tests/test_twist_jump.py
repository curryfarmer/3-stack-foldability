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
