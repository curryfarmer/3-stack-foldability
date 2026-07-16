"""test_grid_ingest_2stack.py — S7 arbitrary-sheet ingest for the RSPA 2-stack engine.

The 2-stack engine (twostack.run) historically folded a full m x n rectangle only; S7 threads a drawn
sheet (opts["sheet"]) through it so the S7 orchestrator can fan a drawn polyomino out over [2, 3]. This
is the ONLY coverage the 2-stack sheet path gets — the square 61/61 physical oracle is 3-stack only and
never runs twostack.py. The engine is driven in-process via twostack.run(opts), mirroring test_golden.py.

Two distinct invariants live here, do NOT conflate them:
  * The historic **no-sheet** rectangle path is byte-frozen by test_golden.py::test_2stack_golden (the
    sheet=None branch is unchanged). That is the "byte-identical" guarantee.
  * A **rectangle-as-sheet** run reproduces the same FOLD SET (uid identities + verdicts + ctx counts),
    but NOT byte-identically: the sheet path indexes nodes by sorted(cells) where the rectangle path uses
    row-major y*m+x, so a circuit can be emitted in the reverse orientation (same undirected cycle, same
    canonical id, mirrored `circuit`/`cutEdge` list). The fold identity is what must match, and does.
"""
import pytest

import twostack as TwoStack   # type: ignore  # on sys.path via conftest.py
import enginelib as EL        # type: ignore


# ---------- helpers ----------

def _rect(m, n):
    return [[x, y] for y in range(n) for x in range(m)]


def _run_sheet(sheet, *, dedup=True):
    """twostack.run over a drawn sheet. m,n are placeholders — run re-derives the tight bbox from the
    sheet — but the key must be present (run reads opts["m"]/["n"] before the sheet overrides them)."""
    xs = [c[0] for c in sheet] or [0]
    ys = [c[1] for c in sheet] or [0]
    opts = {"m": max(xs) + 1, "n": max(ys) + 1, "stacks": 2, "dedup": dedup, "sheet": sheet}
    return TwoStack.run(opts)


def _by_uid(sols):
    """The fold set as {uid: verdict} — the orientation-invariant identity of a 2-stack solution set."""
    return {s["uid"]: s["verdict"] for s in sols}


def _assert_covers_sheet(sols, sheet):
    """Every solution's circuit is a Hamiltonian circuit of the sheet: it visits each sheet cell once
    and never a cell outside the sheet."""
    S = set(map(tuple, sheet))
    for s in sols:
        circ = [tuple(c) for c in s["circuit"]]
        assert set(circ) == S, "circuit does not cover exactly the sheet"
        assert len(circ) == len(S), "circuit revisits a cell (not a simple Hamiltonian circuit)"


# ---------- fixtures (drawn sheets) ----------

# 8-cell ring: a 3x3 with the centre removed. Exactly one Hamiltonian circuit (the ring). Even, 4-conn.
RING8 = [[0, 0], [1, 0], [2, 0], [0, 1], [2, 1], [0, 2], [1, 2], [2, 2]]

# 14-cell asymmetric sheet: a 4x4 square with the two cells (2,0),(3,0) removed. Its bounding box is a
# 4x4 SQUARE (bbox symmetry group = all 8 of D4), but the shape itself is fully asymmetric (Aut(S) = the
# identity alone). It has exactly two distinct Hamiltonian circuits — the case that proves dedup under
# the true stabilizer does not merge (hide) genuinely-distinct folds.
ASYM14 = [[0, 0], [0, 1], [0, 2], [0, 3], [1, 0], [1, 1], [1, 2], [1, 3],
          [2, 1], [2, 2], [2, 3], [3, 1], [3, 2], [3, 3]]


# ---------- rectangle-equivalence (the compatibility invariant) ----------

@pytest.mark.parametrize("m,n", [(2, 4), (4, 2), (3, 4), (2, 6)])
def test_rectangle_sheet_matches_parameterized(m, n):
    """A grid whose cells are exactly the m x n rectangle, ingested as a sheet, reproduces the historic
    parameterized run's FOLD SET (uid->verdict) and ctx counters. (Not byte-identical: see module docstring
    — orientation of the emitted circuit can differ; the canonical fold identity does not.)"""
    old, octx = EL.run_2stack(m, n)
    new, nctx, err = _run_sheet(_rect(m, n))
    assert err is None
    assert nctx == octx, f"{m}x{n}: ctx diverged {nctx} != {octx}"
    assert _by_uid(new) == _by_uid(old), f"{m}x{n}: fold set (uid->verdict) diverged"
    _assert_covers_sheet(new, _rect(m, n))


# ---------- non-rectangular sheets enumerate + cover ----------

def test_ring8_folds_enumerate():
    """A non-rectangular even sheet folds without crashing: the 8-cell ring has exactly one Hamiltonian
    circuit, and that solution covers exactly the sheet."""
    sols, ctx, err = _run_sheet(RING8)
    assert err is None
    assert ctx["hcCount"] == 1 and len(sols) == 1
    _assert_covers_sheet(sols, RING8)


# ---------- guards: reject the wrong shapes (never raise; return an error string) ----------

@pytest.mark.parametrize("bad,frag", [
    ([[0, 0], [1, 0], [2, 0]], "even"),                     # odd cell count (3)
    ([[0, 0], [1, 0], [3, 0], [4, 0]], "4-connected"),      # even but two components (gap at (2,0))
    ([[1, 1], [2, 1]], "origin"),                           # not normalized to the origin
])
def test_bad_sheets_rejected(bad, frag):
    _sols, _ctx, err = _run_sheet(bad)
    assert err is not None, f"expected rejection ({frag})"
    assert frag in err, f"error {err!r} does not mention {frag!r}"


def test_empty_sheet_rejected():
    """An empty sheet is rejected (never silently folds). An empty list is falsy, so run() treats it as
    the no-sheet rectangle path and the 1x1 bbox trips the balanced-HC guard — same convention as the
    3-stack engine (test_grid_ingest.py), which only requires that SOME error is returned."""
    _sols, _ctx, err = _run_sheet([])
    assert err is not None


# ---------- dedup: the stabilizer subgroup, not the bounding box's group ----------

def test_dedup_stabilizer_does_not_undercount():
    """On an asymmetric sheet dedup must merge nothing beyond the cyclic/reversal duplicates the
    enumerator already collapses — so it can never hide a genuinely-distinct fold. dedup on/off agree."""
    deduped, _c1, e1 = _run_sheet(ASYM14, dedup=True)
    raw, _c2, e2 = _run_sheet(ASYM14, dedup=False)
    assert e1 is None and e2 is None
    assert len(deduped) == len(raw) == 2, "asymmetric sheet: dedup dropped a distinct fold (under-count)"
    _assert_covers_sheet(deduped, ASYM14)


def test_stabilizer_is_proper_subgroup_of_bbox_group():
    """The fix: canonicalize under Aut(sheet), NOT the bounding box's group. ASYM14 sits in a 4x4 SQUARE
    bbox (whose group is all 8 of D4), yet its own symmetry group is trivial. Minimizing a dedup key over
    the full D4 would take images off-sheet and could merge distinct folds; the engine narrows 8 -> 1."""
    fs = frozenset(map(tuple, ASYM14))
    full = TwoStack._sym_transforms(4, 4)
    stab = [f for f in full if frozenset(f(x, y) for (x, y) in fs) == fs]
    assert len(full) == 8, "a 4x4 square bbox should present all 8 of D4"
    assert len(stab) == 1, "ASYM14 is asymmetric — its stabilizer is the identity alone"


def test_sheet_none_is_a_noop():
    """Passing sheet=None explicitly is identical to omitting the key (the compat-invariant floor)."""
    a, actx, ae = TwoStack.run({"m": 4, "n": 4, "stacks": 2, "dedup": True})
    b, bctx, be = TwoStack.run({"m": 4, "n": 4, "stacks": 2, "dedup": True, "sheet": None})
    assert ae is None and be is None
    assert a == b and actx == bctx
