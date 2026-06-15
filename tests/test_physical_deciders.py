"""test_physical_deciders.py — engine prediction vs recorded paper-fold, for the deciders.

For every entry in results/twoplus1_labels.json with a recorded physical result (foldable
!= null), we MATCH its canonical hash against the engine's own enumerated closing-candidate
set (the vet golden) and assert the engine's foldable tag equals the physical outcome. These
are the ground-truth anchors: a mismatch means the maths disagrees with reality.

Why match-by-hash and not replay: a canonical hash is a D4 dedup key, not a replayable fold
path (transform_arrow is not replay-equivariant with apply_transform), so replaying it can
leave the grid. Matching the engine's own canonical_hash on both sides is exact and safe.
"""
import glob
import json
import os

import pytest

import enginelib as EL  # noqa: E402  (sys.path set in conftest.py)


def _labels(results_dir: str) -> list[dict]:
    """Load the physical-fold label records. I/O: (results_dir) -> list of label dicts."""
    path = os.path.join(results_dir, "twoplus1_labels.json")
    with open(path) as f:
        return json.load(f)


def _vet_hash_maps(golden_dir: str) -> dict[str, bool]:
    """Merge all vet_*.json golden into one {normalized hash -> foldable}.
    I/O: (golden_dir) -> dict mapping normalized canonical hash to the engine's foldable tag."""
    merged: dict[str, bool] = {}
    if not os.path.isdir(golden_dir):
        return merged
    for fn in os.listdir(golden_dir):
        if fn.startswith("vet_"):
            with open(os.path.join(golden_dir, fn)) as f:
                d = json.load(f)
            for c in d["candidates"]:
                merged[EL.norm_hash(c["hash"])] = c["foldable"]
    return merged


def _decider_ids(results_dir: str) -> list[str]:
    """Param ids for every labelled decider (foldable != null). I/O: (results_dir) -> [id str]."""
    here = os.path.dirname(os.path.abspath(__file__))
    rd = results_dir if os.path.isdir(results_dir) else os.path.join(os.path.dirname(here), "results")
    return [f"{l['grid']}#{l['id']}" for l in _labels(rd) if l.get("foldable") is not None]


# Parametrize at import time over the labelled deciders (resolve results/ relative to this file).
_HERE = os.path.dirname(os.path.abspath(__file__))
_RESULTS = os.path.join(os.path.dirname(_HERE), "results")
_GOLDEN = os.path.join(_HERE, "golden")
_DECIDERS = [l for l in _labels(_RESULTS) if l.get("foldable") is not None]


@pytest.mark.parametrize("label", _DECIDERS, ids=[f"{l['grid']}#{l['id']}" for l in _DECIDERS])
def test_decider_matches_physics(label: dict):
    """Engine's foldable tag for a labelled decider must equal the recorded paper-fold result."""
    physical = bool(label["foldable"])
    target = EL.norm_hash(label["canonicalHash"])
    hash_map = _vet_hash_maps(_GOLDEN)
    if target not in hash_map:
        # If this grid HAS a vet golden, the decider's hash must be in it — its absence means a
        # hash-changing regression, which must FAIL (not silently skip). Skip only when the grid
        # was never vetted.
        if glob.glob(os.path.join(_GOLDEN, f"vet_{label['grid']}_*.json")):
            pytest.fail(f"{label['grid']}#{label['id']}: vet golden for {label['grid']} exists but "
                        f"the decider's canonical hash is absent — a hash-changing regression?")
        pytest.skip(f"{label['grid']}#{label['id']}: no vet golden for {label['grid']} "
                    f"(run tests/gen_golden.py vetonly)")
    engine_foldable = bool(hash_map[target])
    assert engine_foldable == physical, (
        f"{label['grid']}#{label['id']}: engine predicts "
        f"{'FOLD' if engine_foldable else 'JAM'} but physical result was "
        f"{'FOLD' if physical else 'JAM'}")
