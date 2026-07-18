"""test_store_all.py — Phase-A store-all engine + the non-destructive verdict columns.

Pins the inversion from "gates prune during DFS" to "gates annotate; every covered
candidate is stored": the new vectorParity column (legacy nH-even/nV-odd, distinct from the
orientation-aware parity gate), the unconditional fold-count annotator, the equal-folds
arithmetic criterion, and the invariant that store-all is a strict superset of the legacy
gate-survivor set with byte-identical legacy verdicts.
"""
import search as Search    # noqa: E402  (sys.path set in conftest.py)
from lattice.square import SquareLattice  # noqa: E402


def _opts(store_all, **over):
    o = {"m": 3, "n": 2, "stacks": 3,
         "shapes": {"L": True, "Rect": True},
         "decomps": {"2+1": True, "1+1+1": True},
         "allowNonCorner": True, "dedup": True, "jobs": 1, "storeAll": store_all}
    o.update(over)
    return o


# ---------- vector_parity_check (legacy, orientation-UNaware) ----------

def test_vector_parity_legacy_rule():
    # Every chain needs nH even AND nV odd.
    good = [{"foldArrows": ["L", "R", "U"]},      # nH=2 even, nV=1 odd
            {"foldArrows": ["U", "L", "R"]}]
    assert Search.vector_parity_check(good) is True
    bad_nh = [{"foldArrows": ["L", "U"]}]          # nH=1 odd
    assert Search.vector_parity_check(bad_nh) is False
    bad_nv = [{"foldArrows": ["L", "R"]}]          # nV=0 even (needs odd)
    assert Search.vector_parity_check(bad_nv) is False


def test_vector_parity_differs_from_orientation_aware_parity():
    """The whole point of the new column: on a 2+1 vertical-axis placement the orientation-aware
    parity passes (nV even) while the legacy vector parity fails (it demands nV odd)."""
    chains = [{"baseCells": [(0, 0), (1, 0)], "foldArrows": ["U", "D"]},   # nV=2 even
              {"baseCells": [(0, 1)], "foldArrows": ["U", "U"]}]           # nV=2 even
    assert Search.parity_check(chains) is True          # orientation-aware: nV even -> pass
    assert Search.vector_parity_check(chains) is False  # legacy: nV must be odd -> fail


# ---------- set_fold_counts (unconditional nH/nV) ----------

def test_set_fold_counts_annotates_all_chains_after_early_parity_bail():
    # 1+1+1 legacy rule: chain[0] is nH-odd, so parity_check returns before touching chains 1,2.
    chains = [{"baseCells": [(0, 0)], "foldArrows": ["L", "U"]},          # nH=1 -> parity bails here
              {"baseCells": [(1, 0)], "foldArrows": ["U", "L", "R"]},
              {"baseCells": [(0, 1)], "foldArrows": ["D", "R", "L"]}]
    assert Search.parity_check(chains) is False
    assert "nH" not in chains[2]                         # parity_check bailed early
    SquareLattice.set_fold_counts(chains)
    assert all("nH" in c and "nV" in c for c in chains)  # store-all path needs them on EVERY chain
    assert (chains[1]["nH"], chains[1]["nV"]) == (2, 1)


# ---------- store-all integration ----------

def test_store_all_is_superset_of_legacy_with_real_verdicts():
    legacy, lc, le = Search.run(_opts(False))
    allp, ac, ae = Search.run(_opts(True))
    assert le is None and ae is None
    assert ac["coveredCount"] == lc["coveredCount"]      # same enumeration; only admission differs
    legacy_hashes = {s["canonicalHash"] for s in legacy}
    all_hashes = {s["canonicalHash"] for s in allp}
    assert legacy_hashes <= all_hashes                   # every gate-survivor is present in store-all
    assert len(allp) >= len(legacy)


def test_store_all_verdict_block_has_vector_parity_and_real_values():
    allp, _, _ = Search.run(_opts(True))
    assert allp, "store-all should emit covered candidates"
    for s in allp:
        v = s["verdict"]
        assert set(v) == {"arithmetic", "exitFootprint", "parity",
                          "vectorParity", "reflection", "twist"}
        assert isinstance(v["exitFootprint"], bool)      # real gate value, not hardcoded True
        assert v["arithmetic"] is True                   # equal folds per subchain (structural)
    # at least one stored pattern must FAIL a gate — proof gates no longer prune.
    assert any(s["verdict"]["reflection"] is False or s["verdict"]["parity"] is False
               for s in allp)


def test_legacy_verdict_block_byte_identical_shape():
    legacy, _, _ = Search.run(_opts(False))
    assert legacy, "legacy run should still yield gate-survivors"
    for s in legacy:
        # historic key order preserved (no vectorParity leak into the pruned JSON). The FUNNEL gates
        # (exitFootprint, reflection) are still all-True here — pruned mode emits only exit+reflection
        # survivors — but PARITY was demoted 2026-07-18 to a diagnostic column and now carries its
        # REAL value (a fold may legitimately be emitted with parity False).
        assert list(s["verdict"].keys()) == ["arithmetic", "exitFootprint", "parity",
                                             "reflection", "twist"]
        assert s["verdict"]["exitFootprint"] is True
        assert isinstance(s["verdict"]["parity"], bool)   # real value now, no longer hardcoded True
        assert s["verdict"]["reflection"] is True
