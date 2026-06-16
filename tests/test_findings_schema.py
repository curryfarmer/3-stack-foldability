"""test_findings_schema.py — FoldFinding JSON-schema validation (accept valid, reject malformed).

Pins the schema contract so the findings pipeline can never persist a malformed finding: every
required field is enforced, every typed/enum field rejects bad values, and unknown keys are
refused (additionalProperties:false). Pure — no disk I/O.
"""
import copy

import pytest
from jsonschema import ValidationError

import findings as F  # noqa: E402  (py/ on sys.path via conftest.py)


# A fully-populated, valid finding (every optional block present).
VALID_FULL = {
    "grid": "6x5",
    "id": 1,
    "canonicalHash": '{"fp":[[0,0],[0,1],[1,0]],"chains":[]}',
    "foldable": False,
    "jam": {"atFold": 7, "crease": [[3, 5], [4, 5]], "reason": "reflection"},
    "foldOrder": ["R", "D", "L", "U"],
    "predicted": {"foldable": False, "failingGates": ["refl"], "matched": True},
    "observed": {"shape": "L", "orient": "H", "K": 10},
    "by": "john",
    "date": "2026-06-08",
    "notes": "physical JAM",
}

# The minimal shape a migrated twoplus1_labels record produces (only required keys + notes).
MINIMAL_MIGRATED = {
    "grid": "6x4",
    "id": 2,
    "canonicalHash": '{"fp":[[0,0]],"chains":[]}',
    "foldable": None,
    "by": "(migrated)",
    "date": "2026-06-15",
    "notes": "",
}


def test_accepts_valid_full():
    F.validate_finding(VALID_FULL)  # must not raise


def test_accepts_minimal_migrated():
    F.validate_finding(MINIMAL_MIGRATED)  # only required keys + notes


@pytest.mark.parametrize("foldable", [True, False, None])
def test_accepts_each_foldable_value(foldable):
    rec = copy.deepcopy(MINIMAL_MIGRATED)
    rec["foldable"] = foldable
    F.validate_finding(rec)


@pytest.mark.parametrize("missing", ["grid", "id", "canonicalHash", "foldable", "by", "date"])
def test_rejects_missing_required(missing):
    rec = copy.deepcopy(VALID_FULL)
    del rec[missing]
    with pytest.raises(ValidationError):
        F.validate_finding(rec)


@pytest.mark.parametrize("patch", [
    {"foldable": "yes"},                       # string, not bool/null
    {"id": "1"},                               # string, not int
    {"grid": 65},                              # int, not string
    {"canonicalHash": {"fp": []}},             # object, not the JSON string
    {"by": 5},                                 # int, not string
    {"foldOrder": ["X"]},                      # not an L/R/U/D arrow
    {"observed": []},                          # array, not object
    {"bogus": 1},                              # unknown top-level key (additionalProperties:false)
])
def test_rejects_bad_top_level(patch):
    rec = copy.deepcopy(VALID_FULL)
    rec.update(patch)
    with pytest.raises(ValidationError):
        F.validate_finding(rec)


@pytest.mark.parametrize("jam", [
    {"reason": "banana"},                      # outside REASON_ENUM
    {"crease": [[1, 2, 3], [4, 5]]},           # inner pair wrong arity
    {"crease": [[1, 2]]},                      # outer wrong arity (needs exactly 2 points)
    {"atFold": "3"},                           # string, not int/null
    {"surprise": 1},                           # unknown jam key (additionalProperties:false)
])
def test_rejects_bad_jam(jam):
    rec = copy.deepcopy(VALID_FULL)
    rec["jam"] = jam
    with pytest.raises(ValidationError):
        F.validate_finding(rec)


def test_rejects_bad_predicted_gate():
    rec = copy.deepcopy(VALID_FULL)
    rec["predicted"]["failingGates"] = ["parity", "banana"]  # "banana" not a gate name
    with pytest.raises(ValidationError):
        F.validate_finding(rec)


def test_norm_finding_normalizes_hash_without_mutating_input():
    rec = {"grid": "6x5", "id": 1, "canonicalHash": '{"b":2,"a":1}',
           "foldable": None, "by": "x", "date": "2026-06-15"}
    out = F.norm_finding(rec)
    assert out["canonicalHash"] == '{"a":1,"b":2}'      # sorted keys, compact
    assert rec["canonicalHash"] == '{"b":2,"a":1}'      # input untouched
