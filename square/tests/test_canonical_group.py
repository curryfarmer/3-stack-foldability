"""test_canonical_group.py — canonical_hash canonicalizes over the sheet's automorphism subgroup.

S3 narrowed `SquareLattice.canonical_hash` from all 8 of D4 to the subgroup that actually maps the
m x n sheet onto itself (D4 when m == n, D2 otherwise). These pins record both halves of that
change on a REAL candidate set rather than a hand-built one, because both facts are about the
population as a whole:

  * why it was safe   — narrowing the group split no class, so the golden orbit counts did not move
                        and the stored ground truth was never ambiguous;
  * what it bought    — every canonical representative now describes a fold on its own grid.

Unlike test_gates.py (hand-derived, no enumeration) these run the engine. 6x4 is the smallest
non-square grid in the ground truth and takes ~3.5s serially, so they stay in the default tier.
"""
from __future__ import annotations

import json

import enginelib as EL  # noqa: E402  (sys.path set in conftest.py)
from lattice.square import SquareLattice  # noqa: E402

M, N = 6, 4
_D4 = [{"rot": r, "flip": f} for r in range(4) for f in range(2)]


def _geom(sol: dict) -> tuple[dict, list[dict]]:
    """A sol's footprint/chains in the shape canonical_hash wants (sols carry {"x":,"y":} dicts)."""
    fp = {"cells": [(c["x"], c["y"]) for c in sol["footprint"]["cells"]]}
    chains = [{"kind": c["kind"],
               "baseCells": [(b["x"], b["y"]) for b in c["baseCells"]],
               "foldArrows": list(c["foldArrows"])} for c in sol["chains"]]
    return fp, chains


def _candidates() -> list[dict]:
    """Every gate-passing 6x4 candidate, UNdeduped — dedup would hide exactly what we test."""
    solutions, _ctx = EL.run_3stack(M, N, allow_non_corner=True, dedup=False)
    assert solutions, "no 6x4 candidates enumerated — an empty set is not a passing test"
    return solutions


def test_narrowing_to_automorphisms_splits_no_class():
    """Aut induces the SAME partition as all-of-D4 on a non-square grid — only reps move.

    This is what made S3 safe to ship. Minimizing over all 8 never over-merged: a 3-stack fold
    covers the whole m x n sheet (search.search_chains only admits a candidate once its chains
    reserve all m*n cells), so a transposed image covers n x m and can never itself be a legal
    m x n candidate. For m != n the two groups therefore agree on classes.

    If this ever fails, all-of-D4 really was merging physically distinct folds, every affected
    stored record is ambiguous about which fold was tested, and the orbit counts in the goldens
    are wrong. It is the load-bearing claim of the S3 migration, not a style check."""
    classes: dict[str, set[str]] = {}
    for sol in _candidates():
        fp, chains = _geom(sol)
        classes.setdefault(SquareLattice._hash_over(_D4, fp, chains, M, N), set()).add(
            SquareLattice.canonical_hash(fp, chains, M, N))

    split = {k: v for k, v in classes.items() if len(v) > 1}
    assert not split, f"{len(split)} D4 class(es) split under Aut — D4 WAS over-merging"
    # ...and the map is a bijection, so the migration cannot collide two records either.
    assert len({h for v in classes.values() for h in v}) == len(classes)


def test_canonical_representatives_are_on_grid():
    """Every canonical representative describes a fold on the sheet it belongs to.

    The defect S3 fixed: the all-of-D4 minimum could be attained at a transposing element, leaving
    a representative in n x m coordinates that can sit outside the m x n grid entirely (a stored
    9x4 bundle had a footprint cell at y=5 with n=4). Anything reading the hash back as geometry is
    unsound while that is possible — e.g. test_physical_deciders._is_corner_footprint tests fp
    cells against this grid's corners to pick which vet golden should contain a decider."""
    for sol in _candidates():
        fp, chains = _geom(sol)
        h = SquareLattice.canonical_hash(fp, chains, M, N)
        for (x, y) in json.loads(h)["fp"]:
            assert 0 <= x < M and 0 <= y < N, f"canonical rep sits off the {M}x{N} grid: {h[:80]}"
