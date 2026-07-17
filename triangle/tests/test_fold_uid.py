"""test_fold_uid.py — gen_testset.fold_uid is a STABLE content-id contract.

fold_uid(tiling, decomp, cand) = sha1("tri|<tiling>|<decomp>|<canon dedup identity>")[:12]. It keys
every folds/<uid>.json; census / export / ground-truth all cross-reference by it, so a silent re-keying
(payload format, sha1, truncation, or the _dedup_key / _canon_key identity) must fail CI, not pass it.

What the identity guarantees (read from gen_testset._dedup_key / _canon_key):
  1+1+1 : ("111", mid-path, {armA, armC})  -> the two ARMS are a set, sorted in the canonical form,
          so swapping chains[0] <-> chains[2] is INVARIANT. The mid path keeps its direction.
  2+1   : ("21", frozenset(region))        -> the region is a set, sorted in the canonical form, so
          the order (and any duplicate) of the region cell list is INVARIANT.

The pinned hexes below were captured from the shipped code; they detect any future re-keying.

sys.path is set by triangle/tests/conftest.py -- never co-import square/.
Run: python -m pytest triangle/tests/test_fold_uid.py -q
"""
import random

import gen_testset as GT   # noqa: E402  (sys.path set in conftest.py)


# Fixed records (tile ids shaped like real tri ids: [col, row, "U"/"D"]). fold_uid needs only
# decomp + chains (1+1+1) or decomp + region (2+1); no lattice.
CAND_111 = {
    "decomp": "1plus1plus1",
    "chains": [
        [[0, 0, "U"], [0, 1, "U"], [1, 0, "D"]],   # arm A  (chains[0])
        [[1, 1, "U"], [1, 2, "D"], [2, 1, "U"]],   # mid    (chains[1])
        [[2, 2, "D"], [3, 0, "U"], [3, 1, "D"]],   # arm C  (chains[2])
    ],
}
CAND_21 = {
    "decomp": "2plus1",
    "region": [[0, 0, "U"], [1, 0, "D"], [1, 1, "U"], [2, 0, "D"]],
}

# Pins captured from the shipped fold_uid (freeze the content-id; any re-keying moves these).
UID_111 = "6ef31ded33b1"
UID_21 = "91562680521f"


def test_fold_uid_is_stable_111():
    """A fixed 1+1+1 fold hashes to its pinned 12-hex content id."""
    assert GT.fold_uid("scalene", "1plus1plus1", CAND_111) == UID_111


def test_fold_uid_is_stable_21():
    """A fixed 2+1 fold hashes to its pinned 12-hex content id."""
    assert GT.fold_uid("righttri", "2plus1", CAND_21) == UID_21


def test_fold_uid_is_12_lower_hex():
    """The id is exactly 12 lowercase hex chars (sha1[:12]) -- the folds/<uid>.json filename shape."""
    for uid in (UID_111, UID_21):
        assert len(uid) == 12 and all(c in "0123456789abcdef" for c in uid)


def test_fold_uid_invariant_under_arm_swap():
    """1+1+1 arms are a set: swapping chains[0] <-> chains[2] is the same physical fold, same id."""
    swapped = {"decomp": "1plus1plus1",
               "chains": [CAND_111["chains"][2], CAND_111["chains"][1], CAND_111["chains"][0]]}
    assert GT.fold_uid("scalene", "1plus1plus1", swapped) == UID_111


def test_fold_uid_invariant_under_region_cell_order():
    """2+1 region is a set: reordering the region cell list does not change the id."""
    shuffled = list(CAND_21["region"])
    random.Random(1).shuffle(shuffled)
    assert shuffled != CAND_21["region"], "shuffle must actually reorder for the invariance to bite"
    assert GT.fold_uid("righttri", "2plus1", {"decomp": "2plus1", "region": shuffled}) == UID_21


def test_fold_uid_depends_on_tiling_and_decomp():
    """The id folds tiling + decomp into the payload -- different family -> different id (no collision)."""
    assert GT.fold_uid("hex", "1plus1plus1", CAND_111) != UID_111        # tiling participates
    assert UID_111 != UID_21                                             # different family entirely


def test_fold_uid_mid_direction_is_identity():
    """The 1+1+1 mid path keeps its direction: reversing it is a DIFFERENT fold -> a different id
    (the arms collapse, the mid does not)."""
    midrev = {"decomp": "1plus1plus1",
              "chains": [CAND_111["chains"][0], list(reversed(CAND_111["chains"][1])),
                         CAND_111["chains"][2]]}
    assert GT.fold_uid("scalene", "1plus1plus1", midrev) != UID_111
