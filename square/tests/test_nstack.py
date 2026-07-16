"""test_nstack.py — the n-stack engine vs its recorded known-answer oracle.

fixtures/nstack_p4_hunt_results.jsonl is the ONLY oracle for n-stack (N > 3): 35 rows from the
overnight ladder that scratch_examples/hunt_n4n5.py ran, of which 11 completed and 24 timed out. It
is TRACKED precisely because it cannot be cheaply recreated -- the sweep burned an 8h budget and
still never reached panels=5, so every row here is expensive evidence. These tests pin square/nstack.py
(the tracked replacement for that scratch worker) against it.

WHAT IS COMPARED, AND WHY NOT MORE. Only the COUNT columns
(coveredCount/exitPass/parityPass/survivors/fold/jam/bentFoldCount). Never `bentExamples[].hash`:
those are canonicalHash strings recorded BEFORE S3, which narrowed canonicalization from all of D4 to
the sheet's automorphism subgroup and so rewrote every representative on a NON-square sheet -- 5x8,
the only bent row, is exactly such a sheet. The counts are S3-invariant (S3 moved representatives,
not dedup classes: an N-stack fold covers the whole sheet, so a transposed image covers n x m and is
never a legal m x n candidate; for m != n, D4-merge <=> D2-merge), which is why the pre-S3 rows still
reproduce exactly. Asserting on a stored hash would fail for a reason that is not a regression.

TIERING IS BY *SERIAL* COST, NOT THE ORACLE'S `seconds`. Those were recorded at jobs=20; this suite
runs serial (conftest.py sets FOLD_JOBS=1), and the gap is enormous and grows with the grid:
4x5 0.3s->1.1s, 4x6 0.4s->4.7s, 4x7 0.8s->16.5s, 4x8 2.5s->82s. Counts are job-independent
(search.run's parallel path is byte-identical to serial), wall-clock is very much not. So only
4x4/4x5/4x6 stay in the default tier; everything else is `slow` (deselected by pytest.ini's addopts).
"""
import json
import os

import pytest

import generate as Gen  # noqa: E402  (sys.path set in conftest.py)
import nstack as NS     # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
_ORACLE = os.path.join(_HERE, "fixtures", "nstack_p4_hunt_results.jsonl")

# Count columns only -- see the module docstring on why bentExamples is excluded.
_COUNT_COLS = ("coveredCount", "exitPass", "parityPass", "survivors", "fold", "jam", "bentFoldCount")

# Serial cost, measured 2026-07-16. Anything not listed here is `slow`.
_FAST_GRIDS = {(4, 4), (4, 5), (4, 6)}


def _rows():
    """Every oracle row. I/O: () -> list of dicts."""
    with open(_ORACLE, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


_COMPLETED = [r for r in _rows() if r.get("err") is None]
_TIMEOUTS = [r for r in _rows() if r.get("err") is not None]


def _case(row):
    """pytest param for one oracle row, marked slow unless it is in the cheap serial set."""
    grid = (row["m"], row["n"])
    marks = () if grid in _FAST_GRIDS else (pytest.mark.slow,)
    return pytest.param(row, marks=marks, id="%dx%d_p%d" % (row["m"], row["n"], row["panels"]))


def test_oracle_corpus_is_intact():
    """The tracked oracle must keep its shape: lose a row and the tests below silently cover less.

    Pinned because this file is a rescued copy of untracked scratch output (the sweep that made it is
    gone), so there is nothing to regenerate it from."""
    rows = _rows()
    assert len(rows) == 35, f"oracle should hold 35 rows, found {len(rows)}"
    assert len(_COMPLETED) == 11, f"oracle should hold 11 completed rows, found {len(_COMPLETED)}"
    assert {r["panels"] for r in rows} == {4}, "oracle is panels=4 only (the sweep never reached 5)"


def test_timeout_rows_carry_no_gate_fields():
    """The 24 timeout rows are {m, n, panels, err, seconds} and nothing else.

    They are useless as an oracle and must never be mistaken for evidence: a timeout row with a
    `fold` key would mean the sweep recorded a verdict it never actually computed."""
    for row in _TIMEOUTS:
        leaked = [c for c in _COUNT_COLS if c in row]
        assert not leaked, f"{row['m']}x{row['n']} timed out but carries gate fields {leaked}"


def test_no_completed_row_jams():
    """`jam` is 0 on every completed row -- so it discriminates nothing at panels=4.

    Pinned as a fact, not an aspiration: if a jam ever appears, the n-stack gate story changed and
    the tests that lean on fold-vs-survivors need revisiting."""
    assert [r["jam"] for r in _COMPLETED] == [0] * len(_COMPLETED)


@pytest.mark.parametrize("row", [_case(r) for r in _COMPLETED])
def test_oracle_row_reproduces(row):
    """Re-run one oracle grid and require every gate COUNT to match the recorded row.

    jobs=None (not 1) so the run honours FOLD_JOBS, which conftest setdefault's to 1: serial and safe
    by default, but `FOLD_JOBS=20 pytest -m slow` becomes tractable. That matters at the top of the
    ladder -- 4x12 took 726s at jobs=20, and serial cost grows ~33x by 4x8, so the big rows are
    hours-to-days serially. Counts are job-independent, so this cannot change the verdict."""
    got = NS.run_grid(row["m"], row["n"], row["panels"], jobs=None)
    assert got["err"] is None, f"engine rejected {row['m']}x{row['n']}: {got['err']}"
    actual = {c: got[c] for c in _COUNT_COLS}
    expected = {c: row[c] for c in _COUNT_COLS}
    assert actual == expected


@pytest.mark.slow
def test_bent_fold_is_found_on_5x8():
    """5x8 is the ONLY oracle row with a bent fold (fold=2, bentFoldCount=2) -- the single most
    valuable case in the corpus, and the only evidence n-stack finds non-accordion folds.

    Checks the bend STRUCTURALLY (a chain whose arrows are not all equal), never by hash: the stored
    hashes are pre-S3 and 5x8 is non-square, so they no longer match (module docstring)."""
    got = NS.run_grid(5, 8, 4, jobs=None)   # honours FOLD_JOBS -- see test_oracle_row_reproduces
    assert got["fold"] == 2 and got["bentFoldCount"] == 2
    assert got["bentExamples"], "bentFoldCount is 2 but no examples were emitted"
    for ex in got["bentExamples"]:
        assert any(len(set(arrows)) > 1 for arrows in ex["arrows"]), \
            f"example reported as bent but every chain is straight: {ex['arrows']}"


# ---------- the opts/CLI contract ----------

def test_all_singleton_decomp_key():
    """'1+1+1' at 3, '1+1+1+1' at 4, ... -- the key naming the all-singleton decomposition."""
    assert NS.all_singleton_decomp_key(3) == "1+1+1"
    assert NS.all_singleton_decomp_key(4) == "1+1+1+1"
    assert NS.all_singleton_decomp_key(5) == "1+1+1+1+1"


def test_build_opts_selects_only_the_all_singleton_decomp():
    """2+1 is a 3-panel-only concept; an n-stack search must not switch it on."""
    opts = NS.build_opts(4, 8, 4)
    assert opts["panels"] == 4
    assert opts["decomps"] == {"2+1": False, "1+1+1+1": True}
    assert opts["allowNonCorner"] is True, "the oracle rows were swept non-corner"
    assert "storeAll" not in opts, "the oracle is gate-PRUNED; storeAll would change `survivors`"


def test_build_opts_rejects_under_three_panels():
    with pytest.raises(ValueError):
        NS.build_opts(4, 4, 2)


@pytest.mark.parametrize("stacks,panels,want", [
    (None, None, 3),      # neither given -> the historical default
    (None, 4, 4),         # --panels alone must keep working (back-compat)
    (4, None, 4),         # --stacks N is the new one knob (was capped at choices=(2, 3))
    (4, 4, 4),            # both, agreeing
    (2, None, 2),         # the RSPA 2-stack engine
])
def test_resolve_stacks(stacks, panels, want):
    assert Gen.resolve_stacks(stacks, panels) == want


@pytest.mark.parametrize("stacks,panels", [
    (3, 4),               # contradiction: refuse rather than silently pick one
    (2, 4),               # --panels is meaningless for the 2-stack engine
    (None, 2),            # `--panels 2` is not the 2-stack engine
    (1, None),
])
def test_resolve_stacks_rejects(stacks, panels):
    with pytest.raises(ValueError):
        Gen.resolve_stacks(stacks, panels)
