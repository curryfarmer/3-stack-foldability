"""test_findings_matcher.py — the engine `predicted` block matches the physical deciders (gate-verdict).

The findings matcher projects the engine's whole-candidate verdict (FOLD/JAM + failing gates) for a
finding's canonicalHash; it never uses a fold index. For the three recorded JAM deciders the engine
must agree: matched=True and predicted.foldable == the physical foldable bit (False). A valid finding
whose hash exists in NO enumerated candidate must come back matched=False (schema admits any hash
string; only the engine enumeration decides existence). 6x6/6x7 are heavy enumerations -> slow-marked.

Deciders are embedded here (grid, id, hash, foldable) so this unit stays independent of the findings
DB file (twoplus1_labels.json -> foldfindings.json migration happens in a later step).
"""
import pytest

import findings as F          # noqa: E402  (py/ on sys.path via conftest.py)
from enginelib import predicted_trace, norm_hash   # noqa: E402

# All three are off-corner JAM deciders -> reachable only with allow_non_corner=True at enumeration?
# No: the committed vet golden enumerates allow_non_corner=False and CONTAINS these hashes, so the
# matcher enumerates the same (allow_non_corner=False) set. (Confirmed against tests/golden/vet_*.json.)
DECIDERS = [
    pytest.param(
        "6x5", 1, False,
        '{"fp":[[0,0],[0,1],[1,0]],"chains":[{"kind":"1chain","base":[[0,1]],"arrows":["R","D","L","D","D","R","U","R","R"]},{"kind":"2chain","base":[[0,0],[1,0]],"arrows":["R","R","D","L","D","R","D","D","L"]}]}',
        id="6x5#1",
    ),
    pytest.param(
        "6x6", 1, False,
        '{"fp":[[0,0],[0,1],[1,0]],"chains":[{"kind":"1chain","base":[[0,1]],"arrows":["U","U","U","U","L","D","D","D","D","L","L"]},{"kind":"2chain","base":[[0,0],[1,0]],"arrows":["L","L","U","U","U","U","U","R","D","D","D"]}]}',
        id="6x6#1", marks=pytest.mark.slow,
    ),
    pytest.param(
        "6x7", 8, False,
        '{"fp":[[0,0],[0,1],[1,1]],"chains":[{"kind":"1chain","base":[[1,1]],"arrows":["D","L","L","L","U","R","R","U","R","U","L","L","D"]},{"kind":"2chain","base":[[0,0],[0,1]],"arrows":["U","U","L","L","L","L","L","L","D","D","R","U","R"]}]}',
        id="6x7#8", marks=pytest.mark.slow,
    ),
]


def _grid(g):
    m, n = g.split("x")
    return int(m), int(n)


@pytest.mark.parametrize("grid,fid,foldable,canonical_hash", DECIDERS)
def test_predicted_trace_matches_decider(grid, fid, foldable, canonical_hash):
    m, n = _grid(grid)
    trace = predicted_trace(m, n, canonical_hash)
    assert trace is not None and trace["matched"] is True          # hash exists in the engine set
    assert trace["foldable"] == foldable                           # engine JAM == physical JAM
    assert trace["failingGates"], "a JAM decider must report >=1 failing gate"


@pytest.mark.parametrize("grid,fid,foldable,canonical_hash", DECIDERS)
def test_predict_finding_block_matches_decider(grid, fid, foldable, canonical_hash):
    rec = {"grid": grid, "id": fid, "canonicalHash": canonical_hash,
           "foldable": foldable, "by": "test", "date": "2026-06-15"}
    pred = F.predict_finding(rec)
    F.validate_finding(dict(rec, predicted=pred))                  # the built block is schema-valid
    assert pred["matched"] is True
    assert pred["foldable"] == foldable                            # gate-verdict agrees with physical


def test_schema_hash_must_exist_in_engine():
    # A perfectly valid finding whose hash matches no enumerated candidate -> matched False.
    rec = {"grid": "6x5", "id": 999,
           "canonicalHash": '{"fp":[[0,0]],"chains":[]}',          # well-formed, not a real candidate
           "foldable": None, "by": "test", "date": "2026-06-15"}
    F.validate_finding(rec)                                        # schema accepts it...
    pred = F.predict_finding(rec)
    assert pred == {"matched": False}                              # ...but the engine has no such hash
    assert predicted_trace(6, 5, rec["canonicalHash"]) is None


def test_norm_hash_agrees_across_modules():
    # findings._norm_hash and enginelib.norm_hash must canonicalize identically (shared DB key).
    h = '{"fp":[[0,0],[0,1],[1,0]],"chains":[]}'
    assert F._norm_hash(h) == norm_hash(h)
