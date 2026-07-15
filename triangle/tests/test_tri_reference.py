"""test_tri_reference.py — reference-snapshot tests for the committed triangle-lattice JSONs.

Purpose: lock the committed triangle-lattice (tetrakis, K=12, 45-45-90) result files as a
STRUCTURAL + COUNT reference so later refactors (notably the Session-4 tile/lattice
abstraction) can detect drift. These tests do NOT re-run the tri search — regenerating tri
results is heavy and out of scope. They only assert that the committed JSON snapshots keep
their shape, counts, key sets, and cross-file invariants.

Schema discovered from the committed files (do not assume — derived from the actual data):

  results/tri_K12_hl_all.json      — JSON array of 32 record objects. Each record has the
      key set {chains, footprint, tw, foldable, holefree, sidematch, sideinfo}:
        * chains    : list of 3 chains; each chain is a list of [x, y, dir] segments
                      (dir in {N,S,E,W}). This is the canonical identity of a fold.
        * footprint : list of 3 [x, y, dir] segments.
        * tw        : list of 3 ints (twist values).
        * foldable  : bool.
        * holefree  : bool.
        * sidematch : bool (False for every K=12 record — see commit 45b53f4).
        * sideinfo  : str describing the side-length relationship.

  results/tri_foldable_K12_hl.json — JSON array of 8 record objects (the foldable subset).
      Each record has the SMALLER key set {chains, footprint, holefree}; it does NOT carry
      foldable/tw/sidematch/sideinfo. Foldability is implied by membership. 2 of the 8 are
      holefree == True.

  Cross-file invariant: every record in the foldable file matches (by canonical `chains`) a
  record in the all file whose foldable == True; and there are exactly 8 foldable == True
  records in the all file, so the foldable file is exactly the foldable subset.
"""
import json
import os
from typing import Any

import pytest

# --- Locked baselines (counts captured once from the committed files) -------------------
# These integers pin the record counts of the committed snapshots. A refactor that changes
# how many tri folds are emitted will trip these and must be reviewed deliberately.
EXPECTED_ALL: int = 32  # committed baseline: len(results/tri_K12_hl_all.json)
EXPECTED_FOLDABLE: int = 8  # committed baseline: len(results/tri_foldable_K12_hl.json)

ALL_FILENAME: str = "tri_K12_hl_all.json"
FOLDABLE_FILENAME: str = "tri_foldable_K12_hl.json"

# Full key set every record in each file is expected to carry (derived from the data).
ALL_KEYS: frozenset[str] = frozenset(
    {"chains", "footprint", "tw", "foldable", "holefree", "sidematch", "sideinfo"}
)
FOLDABLE_KEYS: frozenset[str] = frozenset({"chains", "footprint", "holefree"})


# --- Helpers ----------------------------------------------------------------------------
def _load_or_skip(results_dir: str, filename: str) -> list[dict[str, Any]]:
    """Load a tri result JSON array, or pytest.skip if absent. I/O: (dir, name) -> list[record]."""
    path = os.path.join(results_dir, filename)
    if not os.path.exists(path):
        pytest.skip(f"reference file missing: {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _canonical(record: dict[str, Any]) -> str:
    """Stable identity string for a fold record from its `chains`. I/O: (record) -> str."""
    return json.dumps(record["chains"], sort_keys=True)


# --- Per-file structural tests ----------------------------------------------------------
def test_all_file_parses_and_nonempty(results_dir: str) -> None:
    """The all-folds file parses as a non-empty list. I/O: (results_dir) -> None."""
    records = _load_or_skip(results_dir, ALL_FILENAME)
    assert isinstance(records, list)
    assert len(records) > 0


def test_all_file_count_locked(results_dir: str) -> None:
    """The all-folds file holds exactly the committed-baseline count. I/O: (results_dir) -> None."""
    records = _load_or_skip(results_dir, ALL_FILENAME)
    assert len(records) == EXPECTED_ALL


def test_all_file_records_share_full_key_set(results_dir: str) -> None:
    """Every all-folds record carries the full expected key set. I/O: (results_dir) -> None."""
    records = _load_or_skip(results_dir, ALL_FILENAME)
    for i, rec in enumerate(records):
        assert set(rec.keys()) == set(ALL_KEYS), f"record {i} key mismatch: {sorted(rec.keys())}"


def test_all_file_tw_is_int_sequence(results_dir: str) -> None:
    """Every all-folds record's `tw` is a list of ints (bools excluded). I/O: (results_dir) -> None."""
    records = _load_or_skip(results_dir, ALL_FILENAME)
    for i, rec in enumerate(records):
        tw = rec["tw"]
        assert isinstance(tw, list), f"record {i} tw not a list: {type(tw).__name__}"
        for v in tw:
            # bool is a subclass of int; the committed tw values are plain ints.
            assert isinstance(v, int) and not isinstance(v, bool), f"record {i} tw element {v!r}"


def test_all_file_foldable_holefree_sidematch_are_bools(results_dir: str) -> None:
    """foldable/holefree/sidematch are booleans on every all-folds record. I/O: (results_dir) -> None."""
    records = _load_or_skip(results_dir, ALL_FILENAME)
    for i, rec in enumerate(records):
        for field in ("foldable", "holefree", "sidematch"):
            assert isinstance(rec[field], bool), f"record {i} {field} not bool: {rec[field]!r}"


def test_all_file_sidematch_all_false(results_dir: str) -> None:
    """Documented finding: no K=12 tetrakis fold passes side-matching. I/O: (results_dir) -> None.

    See commit 45b53f4 — the side-matching filter disqualifies all K=12 tetrakis Tw=0 folds.
    """
    records = _load_or_skip(results_dir, ALL_FILENAME)
    assert all(rec["sidematch"] is False for rec in records)


def test_all_file_foldable_count_matches_subset_baseline(results_dir: str) -> None:
    """Exactly EXPECTED_FOLDABLE records are foldable==True. I/O: (results_dir) -> None."""
    records = _load_or_skip(results_dir, ALL_FILENAME)
    foldable = [rec for rec in records if rec["foldable"] is True]
    assert len(foldable) == EXPECTED_FOLDABLE


def test_foldable_file_parses_and_nonempty(results_dir: str) -> None:
    """The foldable-subset file parses as a non-empty list. I/O: (results_dir) -> None."""
    records = _load_or_skip(results_dir, FOLDABLE_FILENAME)
    assert isinstance(records, list)
    assert len(records) > 0


def test_foldable_file_count_locked(results_dir: str) -> None:
    """The foldable-subset file holds exactly the committed-baseline count. I/O: (results_dir) -> None."""
    records = _load_or_skip(results_dir, FOLDABLE_FILENAME)
    assert len(records) == EXPECTED_FOLDABLE


def test_foldable_file_records_share_key_set(results_dir: str) -> None:
    """Every foldable-subset record carries the (smaller) expected key set. I/O: (results_dir) -> None."""
    records = _load_or_skip(results_dir, FOLDABLE_FILENAME)
    for i, rec in enumerate(records):
        assert set(rec.keys()) == set(FOLDABLE_KEYS), f"record {i} key mismatch: {sorted(rec.keys())}"


def test_foldable_file_holefree_is_bool(results_dir: str) -> None:
    """Every foldable-subset record's `holefree` is a bool. I/O: (results_dir) -> None."""
    records = _load_or_skip(results_dir, FOLDABLE_FILENAME)
    for i, rec in enumerate(records):
        assert isinstance(rec["holefree"], bool), f"record {i} holefree not bool: {rec['holefree']!r}"


# --- Cross-file invariants --------------------------------------------------------------
def test_foldable_is_subset_of_all_by_chains(results_dir: str) -> None:
    """Every foldable record's `chains` identity appears in the all-folds file. I/O: (results_dir) -> None."""
    all_records = _load_or_skip(results_dir, ALL_FILENAME)
    foldable_records = _load_or_skip(results_dir, FOLDABLE_FILENAME)
    all_ids = {_canonical(rec) for rec in all_records}
    for i, rec in enumerate(foldable_records):
        assert _canonical(rec) in all_ids, f"foldable record {i} not found in all-folds file"


def test_foldable_records_are_foldable_in_all_file(results_dir: str) -> None:
    """Each foldable record maps (by `chains`) only to foldable==True all-records. I/O: (results_dir) -> None."""
    all_records = _load_or_skip(results_dir, ALL_FILENAME)
    foldable_records = _load_or_skip(results_dir, FOLDABLE_FILENAME)
    all_by_chain: dict[str, list[dict[str, Any]]] = {}
    for rec in all_records:
        all_by_chain.setdefault(_canonical(rec), []).append(rec)
    for i, rec in enumerate(foldable_records):
        matches = all_by_chain.get(_canonical(rec), [])
        assert matches, f"foldable record {i} has no match in all-folds file"
        assert all(m["foldable"] is True for m in matches), f"foldable record {i} maps to a non-foldable all-record"


def test_foldable_holefree_agrees_with_all_file(results_dir: str) -> None:
    """A foldable record's `holefree` agrees with its all-file counterpart. I/O: (results_dir) -> None."""
    all_records = _load_or_skip(results_dir, ALL_FILENAME)
    foldable_records = _load_or_skip(results_dir, FOLDABLE_FILENAME)
    all_by_chain: dict[str, list[dict[str, Any]]] = {}
    for rec in all_records:
        all_by_chain.setdefault(_canonical(rec), []).append(rec)
    for i, rec in enumerate(foldable_records):
        matches = all_by_chain.get(_canonical(rec), [])
        assert any(m["holefree"] == rec["holefree"] for m in matches), (
            f"foldable record {i} holefree={rec['holefree']!r} has no matching all-record"
        )
