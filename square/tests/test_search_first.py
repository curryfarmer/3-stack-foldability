"""test_search_first.py — the square 3-stack find-example (opts["first"]) short-circuit.

`opts["first"]` makes Search.run stop at the FIRST foldable (twist-decided FOLD) solution instead of
enumerating every footprint x decomposition. It piggybacks on the engine's existing ctx["cancelled"]
unwind and forces the serial path. These tests pin: (1) it genuinely short-circuits (far fewer
footprints + nodes than a full run) while still returning a real foldable example, and (2) it always
terminates cleanly whether or not a fold exists (never hangs on the fall-through-to-full case).
"""
import enginelib as EL      # type: ignore  # square/tests on sys.path via conftest
import search as Search     # type: ignore


def _folds(sols):
    return [s for s in sols if s["verdict"]["twist"] is True]


def test_first_finds_a_foldable_and_short_circuits():
    kw = dict(decomps=("2+1",), allow_non_corner=True)     # 6x4 non-corner 2+1 has a known fold
    full_sols, full_ctx, err = Search.run(EL.opts_3stack(6, 4, **kw))
    assert err is None
    assert _folds(full_sols), "precondition: 6x4 non-corner 2+1 must have a foldable"

    first_opts = EL.opts_3stack(6, 4, **kw)
    first_opts["first"] = True
    first_sols, first_ctx, err = Search.run(first_opts)
    assert err is None
    # returned an actual foldable example, and stopped exactly ON it (last admitted solution folds)
    assert _folds(first_sols)
    assert first_sols[-1]["verdict"]["twist"] is True
    # genuinely short-circuited: strictly fewer footprints explored + nodes visited than the full run
    assert first_ctx["footprintsTried"] < full_ctx["footprintsTried"]
    assert first_ctx["nodeCount"] < full_ctx["nodeCount"]


def test_first_always_terminates_cleanly():
    """find-first must return (never hang) whether a fold exists or not; when one is found the search
    stopped on it, and a fold-free grid falls through to a full, terminating enumeration."""
    for (m, n) in [(3, 2), (6, 4)]:
        opts = EL.opts_3stack(m, n, decomps=("2+1",), allow_non_corner=True)
        opts["first"] = True
        sols, _ctx, err = Search.run(opts)
        assert err is None
        if _folds(sols):
            assert sols[-1]["verdict"]["twist"] is True
