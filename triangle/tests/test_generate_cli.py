"""test_generate_cli.py — the `tri-generate` command line, end to end.

WHY THIS EXISTS. `triangle/tri/generate.py` is the front door the console script `tri-generate`
points at (pyproject.toml: `tri-generate = "triangle.tri.generate:main"`), and until now NOTHING in
any suite exercised it. That is how its central bug survived: `find_first` called `gen_21` with no
`hubs` argument, silently taking the single-example default of ONE start hub, so the CLI printed
"no closing example found" at righttri 2+1 K=6 and K=8 -- where folds demonstrably exist -- and the
published figures disagreed with the programme that was supposed to produce them. A second instance
(equilateral 2+1 dispatching on tiling before decomp, landing in `gen_eq`, whose signature has no
`hubs` at all) was invisible for the same reason.

So the tests below are organised around the properties that would have caught it:
  * the two false negatives themselves, and that --hubs 1 still reproduces them (regression pins);
  * that --hubs actually reaches every 2+1 path, equilateral included (the dispatch-order bug);
  * that --all and the default find-first mode agree about what exists (they share
    find_example.iter_candidates precisely so they cannot drift);
  * that widening the sweep only ever ADDS placements, never changes the answer set underneath;
  * that a "none found" message never claims to be an obstruction.

Every case is chosen to run in well under a second or two -- the whole module is a few seconds --
so it belongs in the default gate rather than behind @slow. `main(argv)` is driven in process; no
subprocess, no console-script resolution.

TRIANGLE-ONLY: modules imported exactly as the engine imports them (via conftest.py's tri/ path);
NO square.* here -- square/ ships a colliding bare `generate` and `lattice`.
"""
import json
import os

import pytest

import congruence as CG        # noqa: E402
import find_example as FE      # noqa: E402
import generate                # noqa: E402  triangle/tri/generate.py (square/generate.py is NOT on this path)


# (tiling, decomp, K) that are known to close, and are cheap. Counts come from the engine itself --
# see the per-test pins below for the ones that are asserted exactly.
MATRIX = [
    ("righttri", "2plus1", 4),
    ("righttri", "1plus1plus1", 14),
    ("equilateral", "2plus1", 6),
    ("equilateral", "1plus1plus1", 12),
    ("scalene", "2plus1", 4),
    ("scalene", "1plus1plus1", 14),
    ("hex", "2plus1", 3),
    ("hex", "1plus1plus1", 3),
]


def run(tmp_path, *argv):
    """Drive generate.main with --out pointed at tmp_path. Returns the exit code."""
    return generate.main(["--out", str(tmp_path)] + [str(a) for a in argv])


def uids(tmp_path):
    """The uid directories a run wrote."""
    return sorted(p for p in os.listdir(tmp_path) if os.path.isdir(os.path.join(tmp_path, p)))


def cands(tiling, decomp, K, hubs=None, hub=None):
    """The raw candidate list the CLI would search, straight off the shared iterator."""
    _, gen = FE.iter_candidates(tiling, decomp, K, hub=hub, hubs=hubs, budget=180.0)
    return list(gen)


def regions(cs):
    """Candidates as comparable tile sets (a fold's identity, independent of dict ordering)."""
    return {frozenset(CG.region_of(c)) for c in cs}


# --------------------------------------------------------------------------- 1. the matrix
@pytest.mark.parametrize("tiling,decomp,K", MATRIX)
def test_every_tiling_and_decomp_finds_and_writes(tmp_path, tiling, decomp, K):
    """All 8 (tiling, decomp) combinations search, succeed, and write a readable record."""
    assert run(tmp_path, "--tiling", tiling, "--decomp", decomp, "--K", K) == 0
    written = uids(tmp_path)
    assert len(written) == 1, "expected exactly one fold record, got %s" % written
    uid = written[0]
    with open(os.path.join(tmp_path, uid, "%s.json" % uid)) as fh:
        rec = json.load(fh)
    assert rec["uid"] == uid
    assert rec["tiling"] == tiling and rec["decomp"] == decomp and rec["K"] == K
    assert rec["chains"], "record carries no chains"


# --------------------------------------------------------------------------- 2. the regressions
@pytest.mark.parametrize("K", [6, 8])
def test_righttri_2plus1_k6_k8_found_by_default_missed_at_one_hub(tmp_path, K):
    """THE bug. At the default sweep both K close; at --hubs 1 both report nothing.

    The second half is not redundant -- it pins that the failure was the sweep width and not some
    unrelated change, so a future default that silently drops below saturation fails here."""
    assert run(tmp_path, "--tiling", "righttri", "--decomp", "2plus1", "--K", K) == 0
    assert len(uids(tmp_path)) == 1, "K=%d should close at the default hub sweep" % K

    narrow = tmp_path / "narrow"
    narrow.mkdir()
    assert run(narrow, "--tiling", "righttri", "--decomp", "2plus1", "--K", K, "--hubs", 1) == 0
    assert uids(narrow) == [], "K=%d at 1 hub is the historical false negative" % K


def test_equilateral_2plus1_honours_hubs():
    """The dispatch-order bug: equilateral 2+1 must route to gen_21 (which takes `hubs`), not to
    gen_eq (which has no such parameter and would pin the search to a single hub whatever is asked).
    If it regresses, widening the sweep stops changing anything and these counts collapse to equal."""
    one = cands("equilateral", "2plus1", 6, hubs=1)
    many = cands("equilateral", "2plus1", 6, hubs=20)
    assert len(one) < len(many), "hubs had no effect on equilateral 2+1 -- dispatched to gen_eq?"
    assert regions(one) < regions(many)


# --------------------------------------------------------------------------- 3. find-one vs find-all
def test_all_is_a_superset_of_find_first(tmp_path, capsys):
    """--all must contain the fold the default mode returns. Both consume iter_candidates, so a
    disagreement means the shared dispatch has been bypassed on one of the two paths."""
    assert run(tmp_path, "--tiling", "righttri", "--decomp", "2plus1", "--K", 8) == 0
    single = uids(tmp_path)[0]

    every = tmp_path / "all"
    every.mkdir()
    assert run(every, "--tiling", "righttri", "--decomp", "2plus1", "--K", 8, "--all") == 0
    assert single in uids(every)
    assert "8 closing fold(s)" in capsys.readouterr().out


def test_all_reports_exact_counts(tmp_path, capsys):
    """righttri 2+1 K=7 closes 18 times at the default sweep and none of them are flat."""
    assert run(tmp_path, "--tiling", "righttri", "--decomp", "2plus1", "--K", 7,
               "--all", "--limit", 0) == 0
    out = capsys.readouterr().out
    assert "18 closing fold(s), 0 predicted foldable" in out


# --------------------------------------------------------------------------- 4. sweep width
@pytest.mark.parametrize("K,expect", [(4, {1: 1, 4: 2, 20: 12}), (7, {1: 2, 4: 4, 20: 18})])
def test_widening_the_sweep_only_adds_placements(K, expect):
    """Placements grow with --hubs, and the narrower answer set is always contained in the wider one.
    central_hubs takes the n most central trapezoids, so a smaller hub list is a prefix of a larger
    one -- if this containment ever breaks, the sweep is not nested and no count is comparable."""
    seen = {}
    for h in sorted(expect):
        cs = cands("righttri", "2plus1", K, hubs=h)
        assert len(cs) == expect[h], "K=%d hubs=%d" % (K, h)
        seen[h] = regions(cs)
    hs = sorted(expect)
    for lo, hi in zip(hs, hs[1:]):
        assert seen[lo] <= seen[hi], "hubs=%d found folds hubs=%d did not" % (lo, hi)


@pytest.mark.parametrize("hubs", [4, 20])
def test_distinct_count_is_invariant_above_saturation(tmp_path, capsys, hubs):
    """The property the figures rest on: placements move with the sweep width, SHAPES do not.
    righttri 2+1 K=7 is 4 placements at 4 hubs and 18 at 20 -- both are the same 2 shapes."""
    assert run(tmp_path, "--tiling", "righttri", "--decomp", "2plus1", "--K", 7,
               "--all", "--distinct", "--limit", 0, "--hubs", hubs) == 0
    assert "distinct: 2 closing shape(s), 0 flat shape(s)" in capsys.readouterr().out


def test_hub_variant_changes_the_result_set():
    """--hub selects an ambient VARIANT (a different lattice), not a count. righttri's LL and HL are
    inequivalent, so a variant never searched is folds never found -- which is what the census was
    doing before it swept both."""
    ll = cands("righttri", "1plus1plus1", 14, hub="LL")
    hl = cands("righttri", "1plus1plus1", 14, hub="HL")
    assert len(ll) != len(hl)
    assert regions(ll) != regions(hl)


# --------------------------------------------------------------------------- 5. output discipline
def test_limit_caps_records_without_changing_counts(tmp_path, capsys):
    """--limit bounds what lands on disk; the reported counts stay exact. A cell can hold 500k folds
    and one directory each is not something a CLI should do silently."""
    assert run(tmp_path, "--tiling", "righttri", "--decomp", "2plus1", "--K", 7,
               "--all", "--limit", 3) == 0
    out = capsys.readouterr().out
    assert "18 closing fold(s)" in out          # count is of the search, not of the writing
    assert "(--limit 3 of 18)" in out
    assert len(uids(tmp_path)) == 3


def test_uid_is_deterministic(tmp_path):
    """The same search twice yields the same uid -- records are content-addressed."""
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    run(a, "--tiling", "scalene", "--decomp", "2plus1", "--K", 4)
    run(b, "--tiling", "scalene", "--decomp", "2plus1", "--K", 4)
    assert uids(a) == uids(b) != []


# --------------------------------------------------------------------------- 6. honesty of failure
def test_a_search_that_finds_nothing_writes_nothing_and_still_succeeds(tmp_path, capsys):
    """Finding no fold is a result, not an error: exit 0, no record on disk, and the funnel counters
    still printed so the caller can see how much was actually searched. `--hubs 1` is the historical
    false negative (righttri 2+1 K=6 closes at four hubs), so it is the right probe here."""
    assert run(tmp_path, "--tiling", "righttri", "--decomp", "2plus1", "--K", 6, "--hubs", 1) == 0
    out = capsys.readouterr().out
    assert "candidate(s) tried" in out                      # the funnel, i.e. what was searched
    assert "closure" in out
    assert uids(tmp_path) == []                             # and nothing was written


# --------------------------------------------------------------------------- 7. argument validation
def test_grid_file_is_exclusive_with_the_search_arguments(tmp_path):
    spec = tmp_path / "g.json"
    spec.write_text(json.dumps({"schema": "fold-grid/1", "tiling": "righttri", "cells": []}))
    with pytest.raises(SystemExit):
        run(tmp_path, "--grid-file", str(spec), "--tiling", "righttri")


@pytest.mark.parametrize("argv", [
    ["--tiling", "righttri", "--decomp", "2plus1"],          # no --K
    ["--tiling", "righttri", "--K", "4"],                    # no --decomp
    ["--decomp", "2plus1", "--K", "4"],                      # no --tiling
])
def test_missing_required_search_arguments_error(tmp_path, argv):
    with pytest.raises(SystemExit):
        run(tmp_path, *argv)


def test_unknown_tiling_rejected(tmp_path):
    with pytest.raises(SystemExit):
        run(tmp_path, "--tiling", "octagon", "--decomp", "2plus1", "--K", 4)
