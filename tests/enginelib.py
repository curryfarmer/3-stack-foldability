"""enginelib.py — thin, reusable wrappers over the Python engine for the test suite.

All maths lives in py/search.py, py/fold.py, py/twostack.py; this module only adapts their
call shapes for tests and provides the closing-candidate oracle + canonical-hash matching used
by the golden / hard-case / physical-decider tests. Pure compute, no disk I/O.
"""
from __future__ import annotations

import json
from typing import Any

import search as Search      # type: ignore  # provided on sys.path by conftest.py
import twostack as TwoStack  # type: ignore

Opts = dict[str, Any]


# ---------- option builders ----------

def opts_3stack(
    m: int,
    n: int,
    *,
    shapes: tuple[str, ...] = ("L", "Rect"),
    decomps: tuple[str, ...] = ("2+1", "1+1+1"),
    allow_non_corner: bool = False,
    dedup: bool = True,
    jobs: int | None = None,
) -> Opts:
    """Build a 3-stack search opts dict.
    I/O: (m, n, shapes, decomps, allow_non_corner, dedup, jobs) -> opts dict for Search.run.
    jobs=None lets Search.run fall back to env FOLD_JOBS (default serial)."""
    return {
        "m": m, "n": n, "stacks": 3,
        "shapes": {s: (s in shapes) for s in ("L", "Rect")},
        "decomps": {d: (d in decomps) for d in ("2+1", "1+1+1")},
        "allowNonCorner": allow_non_corner,
        "dedup": dedup,
        "jobs": jobs,
    }


# ---------- engine runners ----------

def run_3stack(m: int, n: int, **kw: Any) -> tuple[list[dict], dict]:
    """Run the 3-stack search; raise on engine rejection.
    I/O: (m, n, **opts_3stack kwargs) -> (solutions, ctx_counts)."""
    opts = opts_3stack(m, n, **kw)
    solutions, ctx, err = Search.run(opts)
    if err:
        raise RuntimeError(f"3-stack {m}x{n} rejected: {err}")
    return solutions, ctx


def run_2stack(m: int, n: int, *, dedup: bool = True) -> tuple[list[dict], dict]:
    """Run the RSPA 2-stack Hamiltonian-circuit search; raise on rejection.
    I/O: (m, n, dedup) -> (solutions, ctx_counts)."""
    solutions, ctx, err = TwoStack.run({"m": m, "n": n, "stacks": 2, "dedup": dedup})
    if err:
        raise RuntimeError(f"2-stack {m}x{n} rejected: {err}")
    return solutions, ctx


# ---------- closing-candidate oracle (parametrized vet_enumerate) ----------

def closing_candidates(
    m: int,
    n: int,
    *,
    allow_non_corner: bool = False,
    dedup: bool = True,
) -> tuple[list[dict], int]:
    """All distinct closing 3-stack fold candidates (FOLD + predicted-JAM), gate-tagged.

    Mirrors py/vet_enumerate.enumerate_grid but with allow_non_corner / dedup as params, so
    physical deciders (which are off-corner) are reachable. A candidate 'closes' iff it folds
    back to a footprint-shaped 3-stack (exit_footprint_check); it is predicted FOLD iff
    parity & reflection & (twist undecided or passes).
    I/O: (m, n, allow_non_corner, dedup) -> (list of {shape,decomp,hash,foldable,fails,chains}, K).
    """
    K = m * n // 3
    opts = opts_3stack(m, n, allow_non_corner=allow_non_corner, dedup=dedup)
    seen: dict[str, bool] = {}
    out: list[dict] = []
    for footprint in Search.enumerate_footprints(m, n, opts):
        for decomp in Search.enumerate_decompositions(footprint, opts):
            ctx = {"nodeCount": 0, "candidateCount": 0, "coveredCount": 0, "cancelled": False}

            def on_candidate(chains: list[dict], _fp: dict = footprint, _dc: dict = decomp) -> None:
                if not Search.exit_footprint_check(chains, _fp["shape"]):
                    return
                par = Search.parity_check(chains)
                ref = Search.reflection_check(chains)
                tw = Search.twist_check(chains)
                h = Search.canonical_hash(_fp, chains, m, n)
                if dedup and h in seen:
                    return
                seen[h] = True
                fails: list[str] = []
                if not par:
                    fails.append("parity")
                if not ref:
                    fails.append("refl")
                if tw["decided"] and not tw["pass"]:
                    fails.append("twist")
                out.append({
                    "shape": _fp["shape"], "decomp": _dc["decomp"], "hash": h,
                    "foldable": (par and ref and (not tw["decided"] or tw["pass"])),
                    "fails": fails,
                    "chains": [{"kind": c["kind"],
                                "baseCells": [[b[0], b[1]] for b in c["baseCells"]],
                                "foldArrows": list(c["foldArrows"])} for c in chains],
                })

            Search.search_decomposition(m, n, K, decomp, on_candidate, ctx)
    out.sort(key=lambda r: (not r["foldable"], r["shape"], r["decomp"], r["hash"]))
    return out, K


# ---------- canonical-hash matching (physical-decider lookup) ----------
#
# NOTE: a canonical hash is a D4 *dedup key*, NOT a replayable fold path — `transform_arrow`
# is not replay-equivariant with `apply_transform`, so replaying a canonical hash's (base,
# arrows) can leave the grid (e.g. 6x6 decider #1's arrows exit at the 2nd 'U'). To test a
# physical decider we therefore MATCH its canonical hash against the engine's own enumerated
# closing set (same canonical_hash on both sides), never replay it.

def norm_hash(canonical_hash: str) -> str:
    """Normalize a canonical-hash JSON string (sorted keys, compact) for robust comparison.
    I/O: (hash json str) -> normalized json str."""
    return json.dumps(json.loads(canonical_hash), sort_keys=True, separators=(",", ":"))


def find_closing_by_hash(
    m: int,
    n: int,
    target_hash: str,
    *,
    allow_non_corner: bool = False,
) -> dict | None:
    """Enumerate closing candidates and return the one whose canonical hash matches, else None.
    I/O: (m, n, target_hash, allow_non_corner) -> candidate dict | None."""
    target = norm_hash(target_hash)
    cands, _ = closing_candidates(m, n, allow_non_corner=allow_non_corner)
    for c in cands:
        if norm_hash(c["hash"]) == target:
            return c
    return None


# ---------- stable digests for golden comparison ----------

def solution_digest(solutions: list[dict]) -> dict:
    """Order-independent summary of a 3-stack solution set for golden diffing.
    I/O: (solutions list) -> {count, hashes (sorted), twist0, byDecomp, byShape}."""
    hashes = sorted(s["canonicalHash"] for s in solutions)
    twist0 = sum(1 for s in solutions if s["verdict"]["twist"] is True)
    by_decomp: dict[str, int] = {}
    by_shape: dict[str, int] = {}
    for s in solutions:
        by_decomp[s["decomposition"]] = by_decomp.get(s["decomposition"], 0) + 1
        by_shape[s["footprint"]["shape"]] = by_shape.get(s["footprint"]["shape"], 0) + 1
    return {"count": len(solutions), "hashes": hashes, "twist0": twist0,
            "byDecomp": by_decomp, "byShape": by_shape}
