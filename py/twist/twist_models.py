"""twist_models.py — the registry of candidate 2+1 twist hypotheses (the single source of truth).

The 2+1 "twist" gate is undecided in the shipped engine (search.twist_check returns NULL for any
chain longer than one cell). Several competing reductions predict whether a 2+1 fold closes flat;
this module names them, wires each to its (experimental) computation, and exposes:

  MODELS            ordered {key: {"desc", "fn"}} — ADD A HYPOTHESIS = add one entry here.
  compute_all(sol, m, n)   -> {key: {"pass", "tw", "class"}}  for one stored solution blob.
  model_version(key)       -> short source-hash; changes whenever that model's math (or the shared
                              geometry it rides on) changes, so a re-run can stamp/diff predictions.

The math lives in experimental/ (kept out of the production engine on purpose); this is the thin,
DB-facing adapter the backfill (compute_twist_models.py) drives. The compute fns all share one
signature — twist_2plus1(two, one, m, n, ctx) -> {"pass": bool, "tw": float, "class"?: str} — so a
new hypothesis only has to match that to slot in.
"""
import hashlib
import inspect
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))   # py/twist/ -> py/ -> repo root
_EXP = os.path.join(_ROOT, "experimental")
if _EXP not in sys.path:                         # experimental/ holds common + the per-model engines
    sys.path.insert(0, _EXP)

import common                                     # noqa: E402  (shared replay/loop-twist geometry)
from partial_decomp import twist as _partial      # noqa: E402  Model A (variable-width, atan(1/2) seam)
from jump_decomp import twist as _jump            # noqa: E402  Model B (canonical strand; validated)
from no_decomp import twist as _no                # noqa: E402  Model C (whole-domino centroid; 936 artifact)

# key -> hypothesis. Order is display order. The key drives the tag names <key>_pred / <key>_actual.
MODELS = {
    "modelA": {"desc": "partial-decomp: variable-width 1/2-unit; atan(1/2) overhang signature "
                       "(pass = flat or overhang)", "fn": _partial.twist_2plus1},
    "modelB": {"desc": "jump-decomp: canonical kept strand, short folds = 3-jumps; pass = Tw==0 "
                       "(the validated reduction)", "fn": _jump.twist_2plus1},
    "modelC": {"desc": "no-decomp: whole-domino centroid per placement (936 artifact); pass = Tw==0",
               "fn": _no.twist_2plus1},
}


def compute_all(sol, m, n):
    """Run every registered model on one stored solution blob (the patterns.detail_json `sol` shape:
    chains with baseCells/foldArrows). Shares one replayed ctx across models. Returns
    {key: {"pass": bool, "tw": float|None, "class": str|None}}. Raises (ValueError) if a chain
    replays off-grid — the caller decides whether to skip. I/O: (sol, m, n) -> dict."""
    two, one = common.split_chains(sol)
    ctx = common.prepare(two, one, m, n)             # replay both chains + pick the canonical strand once
    out = {}
    for key, spec in MODELS.items():
        r = spec["fn"](two, one, m, n, ctx=ctx)
        out[key] = {"pass": bool(r["pass"]), "tw": r.get("tw"), "class": r.get("class")}
    return out


def model_version(key):
    """Short source-hash of one model: its compute fn PLUS the shared geometry (common) it rides on.
    Editing the model's math — or the common primitives — changes this, so backfilled predictions can
    be stamped and a stale re-run detected. I/O: (key) -> 8-hex str."""
    h = hashlib.sha1()
    h.update(inspect.getsource(MODELS[key]["fn"]).encode())
    h.update(inspect.getsource(common).encode())
    return h.hexdigest()[:8]
