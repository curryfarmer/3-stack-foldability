"""test_physical_deciders.py — engine prediction vs recorded paper-fold, for the deciders.

For every entry in the tracked findings SNAPSHOT with a recorded physical result (foldable != null),
we MATCH its canonical hash against the engine's own enumerated closing-candidate set (the vet
golden) and assert the engine's foldable tag equals the physical outcome. These are the ground-truth
anchors: a mismatch means the maths disagrees with reality.

Why match-by-hash and not replay: a canonical hash is a dedup key -- the minimal signature over the
sheet's automorphism subgroup (S3; all of D4 before it) -- not a replayable fold path
(transform_arrow is not replay-equivariant with apply_transform), so replaying it can leave the
grid. Matching the engine's own canonical_hash on both sides is exact and safe.

_is_corner_footprint below DOES read a stored rep back as geometry, which is exactly what S3 made
sound: minimizing over all of D4 could pick a rep describing the fold on the TRANSPOSED sheet, so a
non-square rep could sit off-grid and be mis-classified. Reps are now on-grid by construction.

WHY A SNAPSHOT, NOT results/foldfindings.json. The live findings DB is gitignored AND append-written
at runtime (scripts/phystest/logresult.py, via records.py:52). Reading it directly made this module
error at COLLECTION time on a fresh clone (the read was unguarded, at module scope, to build the
parametrize list). fixtures/foldfindings_snapshot.json is therefore a deliberate tracked baseline
with exactly the same contract as a golden: it travels with the corpus, so a fresh clone RUNS these
assertions instead of skipping them, and it is regenerated on purpose, never silently.

Because it is a copy of an append-written master it can go stale, so test_snapshot_matches_live below
fails loudly the moment the live DB gains a record -- drift is a visible failure, not a quiet rot.
"""
import json
import os

import pytest

import enginelib as EL  # noqa: E402  (sys.path set in conftest.py)


def _labels(path: str) -> list[dict]:
    """Load the physical-fold label records from a findings JSON. I/O: (path) -> list of dicts."""
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


def _is_corner_footprint(canonical_hash: str, m: int, n: int) -> bool:
    """Does the (canonical) footprint touch a grid corner? Picks which vet golden would contain this
    decider: vet_{grid}_c (corner / allowNonCorner=False) vs vet_{grid}_nc (off-corner). canonical_hash
    keeps absolute grid position (it is a grid-symmetry quotient, not a translation), so a footprint
    cell coinciding with a grid corner is an exact corner-class test. I/O: (hash, m, n) -> bool."""
    fp = json.loads(canonical_hash)["fp"]
    corners = {(0, 0), (0, n - 1), (m - 1, 0), (m - 1, n - 1)}
    return any((x, y) in corners for x, y in fp)


# Parametrize at import time over the labelled deciders. Both paths are TRACKED and sit next to this
# file, so this module-scope read is safe on a fresh clone (the old code read gitignored results/
# here, which made collection ERROR rather than skip).
_HERE = os.path.dirname(os.path.abspath(__file__))
_SNAPSHOT = os.path.join(_HERE, "fixtures", "foldfindings_snapshot.json")
_GOLDEN = os.path.join(_HERE, "golden")
_DECIDERS = [l for l in _labels(_SNAPSHOT) if l.get("foldable") is not None]

# The live master this snapshot was taken from -- gitignored, absent on a fresh clone.
_LIVE = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "results", "foldfindings.json")


def test_snapshot_matches_live():
    """The tracked snapshot must still equal the live findings DB it was copied from.

    fixtures/foldfindings_snapshot.json is a copy of an APPEND-WRITTEN master (logresult.py adds a
    record every time a fold is physically tested), so it goes stale silently. This fails the moment
    they diverge: refresh with `cp results/foldfindings.json
    square/tests/fixtures/foldfindings_snapshot.json` and re-run, which re-parametrizes the deciders
    above over the new record set. Skips where the live DB is absent (fresh clone) -- there is
    nothing to drift from there."""
    if not os.path.exists(_LIVE):
        pytest.skip("results/foldfindings.json absent (fresh clone) — nothing to compare against")
    live = _labels(_LIVE)
    snap = _labels(_SNAPSHOT)
    live_ids = {(r["grid"], r["id"]) for r in live}
    snap_ids = {(r["grid"], r["id"]) for r in snap}
    assert snap_ids == live_ids, (
        f"findings snapshot is stale: {len(live_ids - snap_ids)} record(s) only in live "
        f"{sorted(live_ids - snap_ids)[:5]}, {len(snap_ids - live_ids)} only in snapshot "
        f"{sorted(snap_ids - live_ids)[:5]} — refresh fixtures/foldfindings_snapshot.json")
    live_by_id = {(r["grid"], r["id"]): r for r in live}
    drifted = [(s["grid"], s["id"]) for s in snap
               if live_by_id[(s["grid"], s["id"])].get("foldable") != s.get("foldable")]
    assert not drifted, (
        f"findings snapshot disagrees with live on foldable for {drifted[:5]} — "
        f"refresh fixtures/foldfindings_snapshot.json")


@pytest.mark.parametrize("label", _DECIDERS, ids=[f"{l['grid']}#{l['id']}" for l in _DECIDERS])
def test_decider_matches_physics(label: dict):
    """Engine's foldable tag for a labelled decider must equal the recorded paper-fold result."""
    physical = bool(label["foldable"])
    target = EL.norm_hash(label["canonicalHash"])
    hash_map = _vet_hash_maps(_GOLDEN)
    if target not in hash_map:
        # A vet run is split by corner-ness (allowNonCorner): vet_{grid}_c covers corner footprints,
        # vet_{grid}_nc covers off-corner ones. Require presence only in the golden that WOULD contain
        # THIS footprint's corner-class: fail if that golden exists (a real hash-changing regression),
        # skip if it was never generated. The off-corner 6x7/8x6/6x8 vet sets are prohibitively slow
        # (~hrs) and not generated — those JAM predictions are pinned instead by test_twist_jump.py.
        m, n = (int(v) for v in label["grid"].split("x"))
        sub = "c" if _is_corner_footprint(label["canonicalHash"], m, n) else "nc"
        need = os.path.join(_GOLDEN, f"vet_{label['grid']}_{sub}.json")
        if os.path.exists(need):
            pytest.fail(f"{label['grid']}#{label['id']}: {os.path.basename(need)} exists but the "
                        f"decider's canonical hash is absent — a hash-changing regression?")
        pytest.skip(f"{label['grid']}#{label['id']}: no {os.path.basename(need)} "
                    f"({'corner' if sub == 'c' else 'off-corner'}) vet golden — "
                    f"run tests/gen_golden.py vetonly")
    engine_foldable = bool(hash_map[target])
    assert engine_foldable == physical, (
        f"{label['grid']}#{label['id']}: engine predicts "
        f"{'FOLD' if engine_foldable else 'JAM'} but physical result was "
        f"{'FOLD' if physical else 'JAM'}")
