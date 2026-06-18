"""build_to_test_store.py — assemble the INDEPENDENT, self-contained physical to-test fold store.

Snapshots the 13-case physical to-test queue into ONE portable file `results/to_test_folds.json`,
decoupled from the findings DB (`results/foldfindings.json`), ahead of the database revamp. Each
record is fully self-contained and re-importable:

  - grid-fitting, REPLAYABLE coords (footprint + both chains' base cells + fold-arrow order). A
    canonicalHash is a D4 *dedup key*, NOT a replayable path (`transform_arrow` is not
    replay-equivariant with `apply_transform`), so the literal hash coords can leave the grid. We
    therefore take grid coords from the engine's own enumerated closing candidate, matched by
    normalized canonicalHash (the same trick the physical-decider tests use).
  - the engine gate verdict (predicted FOLD/JAM + which gates fail),
  - all 4 candidate-engine 2+1 twist verdicts (`run_2plus1_testing.tag_solution` schema),
  - the current physical label, joined from `results/foldfindings.json`.

Membership = `results/twoplus1_labels.json` (the 13 make-sheets). Regenerate:
    python experimental/build_to_test_store.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))            # .../experimental
ROOT = os.path.dirname(HERE)
for _p in (HERE, os.path.join(ROOT, "py"), os.path.join(ROOT, "py", "tri"), os.path.join(ROOT, "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import search as Search          # noqa: E402
import findings                  # noqa: E402  (py/findings._norm_hash — the dedup key)
import enginelib                 # noqa: E402  (test helper: opts builder)
import run_2plus1_testing as R   # noqa: E402  (tag_solution -> the 4-engine twist block)
import common as C               # noqa: E402  (replay, for the in-grid self-check)

QUEUE = os.path.join(ROOT, "results", "twoplus1_labels.json")
LABELS_DB = os.path.join(ROOT, "results", "foldfindings.json")
OUT = os.path.join(ROOT, "results", "to_test_folds.json")


class _Done(Exception):
    """Raised from on_candidate to stop a grid's enumeration once all its targets are found."""


def enum_grid_2plus1(m, n, targets):
    """Enumerate 2+1 closing candidates on m x n (both shapes, non-corner) until every normalized
    hash in `targets` is found, then stop. Returns {norm_hash: candidate}. Each candidate carries
    grid-fitting coords + the per-gate verdict.
    I/O: (m, n, set[norm_hash]) -> dict[norm_hash, {shape,decomp,footprintCells,hash,foldable,failingGates,chains}]."""
    K = m * n // 3
    opts = enginelib.opts_3stack(m, n, decomps=("2+1",), allow_non_corner=True, dedup=True)
    seen = {}
    found = {}

    for footprint in Search.enumerate_footprints(m, n, opts):
        for decomp in Search.enumerate_decompositions(footprint, opts):
            ctx = {"nodeCount": 0, "candidateCount": 0, "coveredCount": 0, "cancelled": False}

            def on_candidate(chains, _fp=footprint, _dc=decomp):
                if not Search.exit_footprint_check(chains, _fp["shape"]):
                    return
                h = Search.canonical_hash(_fp, chains, m, n)
                nh = findings._norm_hash(h)
                if nh in seen:
                    return
                seen[nh] = True
                if nh not in targets:
                    return
                par = Search.parity_check(chains)
                ref = Search.reflection_check(chains)
                tw = Search.twist_check(chains)
                fails = []
                if not par:
                    fails.append("parity")
                if not ref:
                    fails.append("refl")          # engine/findings GATE_ENUM token (NOT "reflection")
                if tw["decided"] and not tw["pass"]:
                    fails.append("twist")
                found[nh] = {
                    "shape": _fp["shape"],
                    "decomp": _dc["decomp"],
                    "footprintCells": [[c[0], c[1]] for c in _fp["cells"]],
                    "hash": h,
                    "foldable": bool(par and ref and (not tw["decided"] or tw["pass"])),
                    "failingGates": fails,
                    "twistDecided": tw["decided"],
                    "chains": [{"kind": c["kind"],
                                "baseCells": [[b[0], b[1]] for b in c["baseCells"]],
                                "foldArrows": list(c["foldArrows"])} for c in chains],
                }
                if len(found) == len(targets):
                    raise _Done

            try:
                Search.search_decomposition(m, n, K, decomp, on_candidate, ctx)
            except _Done:
                return found
    return found


def _as_dict_cells(base_cells):
    return [{"x": b[0], "y": b[1]} for b in base_cells]


def twist_block(cand, m, n):
    """The 4-engine twist verdicts via the established run_2plus1_testing.tag_solution schema."""
    sol = {
        "footprint": {"shape": cand["shape"]},
        "chains": [{"kind": c["kind"],
                    "baseCells": _as_dict_cells(c["baseCells"]),
                    "foldArrows": c["foldArrows"]} for c in cand["chains"]],
    }
    return R.tag_solution(sol, m, n)


def replay_ok(cand, m, n):
    """True iff both grid-fitting chains replay in-grid (the self-check that coords are physical)."""
    try:
        for c in cand["chains"]:
            C.replay(_as_dict_cells(c["baseCells"]), c["foldArrows"], m, n)
        return True
    except Exception:
        return False


def main():
    queue = json.load(open(QUEUE))
    db = json.load(open(LABELS_DB))
    db_by_hash = {findings._norm_hash(r["canonicalHash"]): r for r in db}

    # group targets by grid
    by_grid = {}
    for rec in queue:
        by_grid.setdefault(rec["grid"], []).append(rec)

    folds = []
    problems = []
    for grid in sorted(by_grid):
        m, n = map(int, grid.split("x"))
        recs = by_grid[grid]
        targets = {findings._norm_hash(r["canonicalHash"]) for r in recs}
        print("enumerating %s (m=%d n=%d) for %d target(s)..." % (grid, m, n, len(targets)), flush=True)
        found = enum_grid_2plus1(m, n, targets)
        print("  found %d/%d" % (len(found), len(targets)), flush=True)

        for r in recs:
            nh = findings._norm_hash(r["canonicalHash"])
            cand = found.get(nh)
            if cand is None:
                problems.append("%s#%d: no engine candidate matched its canonicalHash" % (grid, r["id"]))
                continue
            # fidelity self-checks
            rep = replay_ok(cand, m, n)
            recomputed = findings._norm_hash(Search.canonical_hash(
                {"cells": [tuple(c) for c in cand["footprintCells"]]},
                [{"kind": c["kind"],
                  "baseCells": [tuple(b) for b in c["baseCells"]],
                  "foldArrows": c["foldArrows"]} for c in cand["chains"]], m, n))
            if recomputed != nh:
                problems.append("%s#%d: grid-coord hash != queue hash" % (grid, r["id"]))
            if not rep:
                problems.append("%s#%d: grid coords do not replay in-grid" % (grid, r["id"]))
            if cand["shape"] != r["shape"]:
                problems.append("%s#%d: shape mismatch (queue %s / engine %s)" % (grid, r["id"], r["shape"], cand["shape"]))

            # physical label, joined from the live DB. Always emit a `jam` slot (null when absent)
            # and a `tags` slot so the revamp has the full findings shape to re-import into.
            dbr = db_by_hash.get(nh)
            physical = None
            if dbr is not None:
                physical = {
                    "foldable": dbr.get("foldable"),    # true=FOLD, false=JAM, null=untested
                    "by": dbr.get("by"),
                    "date": dbr.get("date"),
                    "notes": dbr.get("notes", ""),
                    "observed": dbr.get("observed"),
                    "jam": dbr.get("jam"),              # {atFold,crease,reason} | null (findings.py shape)
                    "tags": dbr.get("tags"),            # custom per-finding tri-state tags | null
                }

            # orientation DERIVED from the stored (engine) coords, so it describes THESE coords; the
            # make-sheet's as-issued orient may be a different D4 image and is kept under provenance.
            two = next(c for c in cand["chains"] if c["kind"] == "2chain")
            (bx0, by0), (bx1, by1) = two["baseCells"]
            domino_orient = "H" if by0 == by1 else "V"
            fold_order = [a for c in cand["chains"] for a in c["foldArrows"]]   # provenance; never matched

            folds.append({
                "grid": grid, "id": r["id"], "sheet": "%s_%d" % (grid, r["id"]),
                "m": m, "n": n, "K": m * n // 3,
                "shape": cand["shape"], "decomp": cand["decomp"],
                "dominoOrient": domino_orient,          # derived from the stored coords below
                "canonicalHash": r["canonicalHash"],
                "canonicalHashNorm": nh,
                "footprint": {"shape": cand["shape"], "cells": cand["footprintCells"]},
                "chains": cand["chains"],
                "foldOrder": fold_order,
                "replayValidated": rep,
                "enginePredicted": {
                    "foldable": cand["foldable"],
                    "failingGates": cand["failingGates"],
                    # twist is STRUCTURALLY undecided for 2+1 (search.twist_check stubs decided=False),
                    # so it can never appear in failingGates here; the per-strand twist verdict lives in
                    # twistEngines. Do NOT read failingGates as the complete rejection reason.
                    "twistDecided": cand["twistDecided"],
                    "twistGateApplicable": False,
                    "matched": True,
                },
                "twistEngines": twist_block(cand, m, n),
                "physical": physical,
                "provenance": {"coordsFrom": "closing_candidates(allow_non_corner,2+1)",
                               "labelFrom": "foldfindings.json" if dbr is not None else None,
                               "membershipFrom": "twoplus1_labels.json",
                               "asIssuedShape": r.get("shape"),
                               "asIssuedOrient": r.get("orient")},
            })

    labeled = sum(1 for f in folds if f["physical"] and f["physical"]["foldable"] is not None)
    doc = {
        "schema": "to_test_folds/v1",
        "generated_by": "experimental/build_to_test_store.py",
        "generated_note": ("Independent, self-contained snapshot of the physical to-test fold queue, "
                           "decoupled from the findings DB (foldfindings.json) ahead of the database "
                           "revamp. Each record carries grid-fitting REPLAYABLE coords + the engine "
                           "gate verdict + all 4-engine 2+1 twist verdicts + the current physical "
                           "label. Re-importable as the seed of the revamped DB."),
        "membership_source": "results/twoplus1_labels.json (13-case make-sheet queue)",
        "label_source": "results/foldfindings.json",
        "coords_source": ("engine closing-candidate enumeration (allow_non_corner, 2+1); a "
                          "canonicalHash is a D4 dedup key, NOT a replayable path, so grid-fitting "
                          "coords are matched in by normalized hash"),
        "related_not_included": ("Newer deciders 8x6#202, 6x6#19, 6x6#5 live in "
                                 "'results/2+1 testing/to_fold/' and are NOT part of this 13-case "
                                 "template. NOTE 6x6#19/#5 sit on the 6x6 grid already represented "
                                 "here, so this file is NOT the complete 6x6 2+1 to-test set."),
        "record_key": ("key on `canonicalHashNorm` (the D4 dedup key). `(grid,id)` is the human "
                       "label and is per-grid (6x4#1, 6x5#1, 6x6#1 all exist) -> do NOT key on it."),
        "coordinate_convention": "grid integer cells, origin top-left, y-DOWN (screen coords, matching the JS tool); cell (x,y) center = (x+0.5, y+0.5)",
        "units": "cells",
        "arrows": "L/R/U/D = fold that grid edge over; foldArrows are per-chain, foldOrder is the concatenation (provenance, never matched)",
        "foldable_semantics": "physical.foldable: true = FOLD (closes flat), false = JAM (self-blocks), null = untested",
        "twist_note": ("enginePredicted.failingGates can only contain parity/refl for 2+1 because "
                       "search.twist_check is structurally undecided for any 2-chain "
                       "(twistGateApplicable=false). The 4 candidate-engine twist verdicts (incl. the "
                       "Model B strand criterion) are in each record's `twistEngines`."),
        "count": len(folds),
        "labeled": labeled,
        "engines": R.MODEL_DOC,
        "folds": folds,
    }
    with open(OUT, "w") as fh:
        json.dump(doc, fh, indent=2)

    print("\nwrote %d/%d folds -> %s" % (len(folds), len(queue), os.path.relpath(OUT, ROOT)))
    print("labeled (physical FOLD/JAM recorded): %d" % labeled)
    if problems:
        print("\nPROBLEMS (%d):" % len(problems))
        for p in problems:
            print("  ! " + p)
    else:
        print("self-checks: all grid coords replay in-grid AND re-canonicalize to the queue hash; shapes agree.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
