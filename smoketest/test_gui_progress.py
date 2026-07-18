"""test_gui_progress.py — the bottom-left activity bar + post-run search-effort summary.

Three tiers, matching the surrounding gui smoketests: a pure text-parse unit test for gui.runsummary
(no Tk, no engine), a Tk widget-shape test (the indeterminate progressbar exists + the summary starts
empty), and a fast first-example end-to-end that folds a tiny square and asserts the summary reflects
the run's foldable count. gui only -- the engine runs in a subprocess (never co-imported here).
"""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from gui import runsummary            # noqa: E402
from gui.app import App               # noqa: E402  (Tk lazy-imported inside App)

# A representative square 3-stack run (fold_grid banner + engine `search:` line + bundle footer), so
# the parser is pinned to the real emitted text, not an invented format.
_SQUARE3 = ("fold-grid: tiling=square |cells|=6 gridUid=abc123 stacks=[3] -> /out/abc123\n"
            "=== square --stacks 3 ===\n"
            "search: 4/6 footprint(s), 12 decomposition(s) explored, 20 candidate(s) tried -> "
            "exit 5, parity 3, reflection 2, after-dedup 2, twist-FOLD 1\n"
            "bundle: 2 record(s) (0 unproven) -> /out/abc123/bundle.json\n")


# --- pure parser (no display) ---
def test_parse_square3():
    assert runsummary.parse(_SQUARE3) == {"explored": 12, "attempted": 20, "foldable": 1, "runs": 1}
    # "attempted" (coveredCount = folds attempted) shows because it differs from explored
    assert runsummary.summarize(_SQUARE3) == "explored: 12 · attempted: 20 · foldable: 1"
    # the bundle's authoritative foldable count overrides the parsed one
    assert runsummary.summarize(_SQUARE3, foldable=0) == "explored: 12 · attempted: 20 · foldable: 0"


def test_parse_multi_engine_sums():
    out = ("search: 40 Hamiltonian circuit(s) -> reflection 3, twist 2, foldable 2\n"
           "search: 7 candidate(s) tried, 3 passed the physical closure (reflection) gate\n")
    p = runsummary.parse(out)
    assert p["runs"] == 2
    assert p["explored"] == 47          # 40 circuits + 7 candidates
    assert p["attempted"] == 47         # 2-stack/triangle print no covering count -> attempted==explored
    assert p["foldable"] == 5           # 2 (2-stack foldable) + 3 (triangle closure)


def test_parse_no_search_line():
    assert runsummary.parse("nothing to see here") == {"explored": 0, "attempted": 0,
                                                       "foldable": 0, "runs": 0}
    assert runsummary.summarize("nothing to see here") == ""
    assert runsummary.summarize("nothing to see here", foldable=0) == "foldable: 0"


# --- Tk widget shape ---
def test_progress_widget_exists(tk_root, tmp_path):
    app = App(tk_root, out_dir=str(tmp_path / "out"))
    assert app._progress is not None
    assert str(app._progress.cget("mode")) == "indeterminate"
    assert app._summary_var.get() == ""          # nothing folded yet


# --- fast first-example end-to-end (mirrors test_gui_verdict_tracking's fast tier) ---
def test_summary_after_fold(tk_root, tmp_path):
    app = App(tk_root, out_dir=str(tmp_path / "out"))
    app.pick("square", 3, 3)
    conn = [k for k, c in enumerate(app.geometry.ids) if c[0] in (0, 1)]   # connected 2x3
    app.select(conn)
    app._find_mode.set("example")                # first-example -> fast
    assert app.fold_enabled
    app.fold(timeout=180, wait=True)
    summary = app._summary_var.get()
    assert "foldable:" in summary, summary
    n_fold = sum(1 for r in app.results.rows() if r.get("foldable") is True)
    assert ("foldable: %d" % n_fold) in summary, summary
    app._cleanup_temp_dirs()                     # discard the unsaved scratch dir (fixture owns root)
