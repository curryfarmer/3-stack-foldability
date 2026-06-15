"""gen_golden.py — generate the committed golden baselines from the CURRENT engine.

Run once to lock the present behaviour, then again after any refactor; the test suite
diffs new engine output against these files. Output -> tests/golden/*.json + INDEX.json.

Usage:
  python tests/gen_golden.py            # generate everything, print timing
  python tests/gen_golden.py probe      # just probe physical deciders, write nothing
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (os.path.join(ROOT, "py"), os.path.join(ROOT, "py", "tri")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.path.insert(0, HERE)

import enginelib as EL  # noqa: E402

GOLDEN = os.path.join(HERE, "golden")

# Matrix rationale: every committed results/*.json uses allowNonCorner=False, so that IS the
# canonical baseline (and its counts cross-check the committed manifest: 6x4->2, 6x5->3, 6x6->12,
# 6x7->33, 9x4->19, 8x6->310, 12x4->90). allowNonCorner=True explodes combinatorially (6x6 nc=True
# alone runs >10 min), so it is kept only for the two grids where it is fast, as an extra lock on
# the off-corner code path.
#
# (m, n, allow_non_corner)
THREE_CORE = [               # nc=False, fast — generated every run
    (6, 4, False), (6, 5, False), (6, 6, False), (6, 7, False), (9, 4, False),
    (6, 4, True), (6, 5, True),  # off-corner path, still fast
]
THREE_HEAVY = [              # nc=False but K=16 / 310 sols — opt-in (`heavy`)
    (8, 6, False), (12, 4, False),
]
TWO_STACK = [(6, 4), (6, 5)]
# vet sets double as the physical-decider oracle (match decider canonical hash -> foldable tag).
# 6x7 is included so decider 6x7#8 is covered; it is slow (~minutes) like the 6x7 search.
VET = [(6, 4, False), (6, 5, False), (6, 6, False), (6, 7, False)]


def _write(name: str, payload: dict) -> None:
    os.makedirs(GOLDEN, exist_ok=True)
    with open(os.path.join(GOLDEN, name), "w") as f:
        json.dump(payload, f, separators=(",", ":"), sort_keys=True)


def _tag(nc: bool) -> str:
    return "nc" if nc else "c"


def gen_three_stack(index: dict, matrix: list) -> None:
    for (m, n, nc) in matrix:
        t0 = time.time()
        sols, ctx = EL.run_3stack(m, n, allow_non_corner=nc)
        dt = time.time() - t0
        counts = {k: v for k, v in ctx.items() if isinstance(v, int) and not isinstance(v, bool)}
        name = f"3stack_{m}x{n}_{_tag(nc)}.json"
        _write(name, {"kind": "3stack", "m": m, "n": n, "allowNonCorner": nc,
                      "ctxCounts": counts, "solutions": sols})
        dig = EL.solution_digest(sols)
        index[name] = {"kind": "3stack", "m": m, "n": n, "allowNonCorner": nc,
                       "count": dig["count"], "twist0": dig["twist0"],
                       "byDecomp": dig["byDecomp"], "byShape": dig["byShape"]}
        print(f"  3stack {m}x{n} nc={nc}: {dig['count']:>4} sols "
              f"(Tw0={dig['twist0']})  {dt:5.1f}s")


def gen_two_stack(index: dict) -> None:
    for (m, n) in TWO_STACK:
        t0 = time.time()
        sols, ctx = EL.run_2stack(m, n)
        dt = time.time() - t0
        foldable = sum(1 for s in sols if s["verdict"]["foldable"])
        name = f"2stack_{m}x{n}.json"
        _write(name, {"kind": "2stack", "m": m, "n": n, "ctx": ctx, "solutions": sols})
        index[name] = {"kind": "2stack", "m": m, "n": n,
                       "count": len(sols), "foldable": foldable, "ctx": ctx}
        print(f"  2stack {m}x{n}: {len(sols):>4} HC patterns (foldable={foldable})  {dt:5.1f}s")


def gen_vet(index: dict) -> None:
    for (m, n, nc) in VET:
        t0 = time.time()
        cands, K = EL.closing_candidates(m, n, allow_non_corner=nc)
        dt = time.time() - t0
        nfold = sum(c["foldable"] for c in cands)
        name = f"vet_{m}x{n}_{_tag(nc)}.json"
        _write(name, {"kind": "vet", "m": m, "n": n, "allowNonCorner": nc, "K": K,
                      "candidates": cands})
        index[name] = {"kind": "vet", "m": m, "n": n, "allowNonCorner": nc, "K": K,
                       "closing": len(cands), "fold": nfold, "jam": len(cands) - nfold}
        print(f"  vet    {m}x{n} nc={nc}: {len(cands):>4} closing "
              f"(FOLD={nfold} JAM={len(cands) - nfold})  {dt:5.1f}s")


def _vet_hash_maps() -> dict[str, dict]:
    """Build {goldenfile: {normhash: foldable}} from every vet_*.json golden file.
    I/O: () -> dict keyed by filename of {normalized canonical hash -> bool}."""
    maps: dict[str, dict] = {}
    if not os.path.isdir(GOLDEN):
        return maps
    for fn in os.listdir(GOLDEN):
        if fn.startswith("vet_"):
            with open(os.path.join(GOLDEN, fn)) as f:
                d = json.load(f)
            maps[fn] = {EL.norm_hash(c["hash"]): c["foldable"] for c in d["candidates"]}
    return maps


def probe_deciders() -> list[dict]:
    """Match each physical-labelled decider's canonical hash in the vet golden sets and compare
    the engine's foldable tag to the recorded physics. I/O: () -> [{grid,id,physical,...}]."""
    with open(os.path.join(ROOT, "results", "twoplus1_labels.json")) as f:
        labels = json.load(f)
    maps = _vet_hash_maps()
    rows = []
    for lab in labels:
        if lab.get("foldable") is None:
            continue
        physical = bool(lab["foldable"])
        h = EL.norm_hash(lab["canonicalHash"])
        hit = next(((fn, m[h]) for fn, m in maps.items() if h in m), None)
        if hit is None:
            print(f"  decider {lab['grid']}#{lab['id']}: physical={'FOLD' if physical else 'JAM'} "
                  f"-> not in any vet golden set (generate vet_{lab['grid']})")
            rows.append({"grid": lab["grid"], "id": lab["id"], "physical": physical,
                         "predicted": None, "agree": None})
            continue
        fn, predicted = hit
        agree = bool(predicted) == physical
        print(f"  decider {lab['grid']}#{lab['id']}: physical={'FOLD' if physical else 'JAM'} "
              f"engine={'FOLD' if predicted else 'JAM'} ({fn})  "
              f"[{'OK' if agree else 'MISMATCH'}]")
        rows.append({"grid": lab["grid"], "id": lab["id"], "physical": physical,
                     "predicted": bool(predicted), "agree": agree})
    return rows


def _load_index() -> dict:
    p = os.path.join(GOLDEN, "INDEX.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}


def main(argv: list[str]) -> int:
    mode = argv[0] if argv else "core"
    if mode == "probe":
        probe_deciders()
        return 0

    if mode == "heavy":
        index = _load_index()  # extend, don't clobber the core index
        print("== 3-stack golden (HEAVY: 8x6, 12x4) ==")
        gen_three_stack(index, THREE_HEAVY)
        _write("INDEX.json", index)
        print(f"\nheavy golden written -> {os.path.relpath(GOLDEN, ROOT)}/")
        return 0

    if mode == "vetonly":
        index = _load_index()
        print("== vet hard-case golden (incl. 6x7) ==")
        gen_vet(index)
        _write("INDEX.json", index)
        print("== physical deciders (probe) ==")
        probe_deciders()
        print(f"\nvet golden written -> {os.path.relpath(GOLDEN, ROOT)}/")
        return 0

    # mode == "core" (default) or "all"
    index = _load_index() if mode == "all" else {}
    print("== 3-stack golden (CORE) ==")
    gen_three_stack(index, THREE_CORE)
    print("== 2-stack golden ==")
    gen_two_stack(index)
    print("== vet hard-case golden ==")
    gen_vet(index)
    if mode == "all":
        print("== 3-stack golden (HEAVY) ==")
        gen_three_stack(index, THREE_HEAVY)
    _write("INDEX.json", index)
    print("== physical deciders (probe) ==")
    probe_deciders()
    print(f"\ngolden written -> {os.path.relpath(GOLDEN, ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
