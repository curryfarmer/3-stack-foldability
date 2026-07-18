"""runsummary.py — condense a fold_grid run's captured stdout into a one-line search-effort summary.

The GUI folds by subprocessing scripts/fold_grid.py, which itself subprocesses each engine's
generate.py and echoes their stdout back (gui.dispatch captures the lot as DispatchResult.output).
Neither the aggregate out/<uid>/bundle.json nor the DispatchResult carries the engine `ctx` counters,
so the only search-effort numbers that reach the GUI are the ones each engine prints on its `search:`
line. This module reads those back -- pure text, no engine import (the never-co-import invariant holds).

Two effort numbers reach the GUI on each engine's `search:` line, and this module reads both back
(pure text, no engine import -- the never-co-import invariant holds):

  * "explored"  -- (footprint, decomposition) configs the search enumerated (coarse).
  * "attempted" -- candidate coverings the search actually formed and gate-tested. For square 3/n-stack
    this is ctx["coveredCount"] (every full-sheet covering the DFS completed) -- the human-scale answer
    to "how many folds attempted". (ctx["candidateCount"], every individual fold *move* the DFS made
    e.g. 20332, is a finer internal metric still not printed; coveredCount is the one users mean.)
    2-stack / triangle print no separate covering count, so there attempted == explored.

  square 3/n-stack : "search: A/B footprint(s), C decomposition(s) explored, V candidate(s) tried -> ... , twist-FOLD H"
  square 2-stack   : "search: A Hamiltonian circuit(s) -> ... , foldable D"
  triangle 1+1+1   : "search: A candidate(s) tried[, ...], C passed the physical closure ... gate[, ...]"

parse() sums explored + attempted + foldable across however many `search:` lines a (multi-N /
multi-engine) run emitted. Pure str -> dict, so it unit-tests with no display and no subprocess.
"""
import re

# Per engine's `search:` line. SQUARE3: g1 explored (decompCount), g2 attempted (coveredCount),
# g3 foldable (twistPass). SQUARE2: g1 circuits (both explored & attempted), g2 foldable.
_SQUARE3 = re.compile(r"(\d+) decomposition\(s\) explored, (\d+) candidate\(s\) tried.*?twist-FOLD (\d+)")
_SQUARE2 = re.compile(r"(\d+) Hamiltonian circuit\(s\).*?foldable (\d+)")
_TRI_TRIED = re.compile(r"(\d+) candidate\(s\) tried")
_TRI_FOLD = re.compile(r"(\d+) passed the physical closure")


def parse(output):
    """Sum the explored + attempted + foldable counts across every engine `search:` line in `output`.
    I/O: (str|None) -> {"explored": int, "attempted": int, "foldable": int, "runs": int}. `runs` is how
    many `search:` lines were recognised (0 -> nothing to summarise). SQUARE3 is tried before TRI_TRIED
    so a square line's own "candidate(s) tried" is never double-counted as a triangle run."""
    explored = attempted = foldable = runs = 0
    for line in (output or "").splitlines():
        if "search:" not in line:
            continue
        m = _SQUARE3.search(line)
        if m:
            explored += int(m.group(1)); attempted += int(m.group(2))
            foldable += int(m.group(3)); runs += 1; continue
        m = _SQUARE2.search(line)
        if m:
            explored += int(m.group(1)); attempted += int(m.group(1))
            foldable += int(m.group(2)); runs += 1; continue
        m = _TRI_TRIED.search(line)
        if m:
            explored += int(m.group(1)); attempted += int(m.group(1)); runs += 1
            mf = _TRI_FOLD.search(line)
            if mf:
                foldable += int(mf.group(1))
    return {"explored": explored, "attempted": attempted, "foldable": foldable, "runs": runs}


def summarize(output, foldable=None):
    """A compact status-bar line, or "" when there is nothing to show. Shows `attempted` (the
    folds-attempted count the user asked for) whenever it differs from `explored`, else just
    `explored`. `foldable`, when given (the bundle's authoritative foldable-record count), overrides
    the parsed per-engine foldable tally. I/O: (str|None, int|None) -> str."""
    p = parse(output)
    fold = p["foldable"] if foldable is None else foldable
    if not p["runs"] and foldable is None:
        return ""
    parts = []
    if p["runs"]:
        parts.append("explored: %d" % p["explored"])
        if p["attempted"] != p["explored"]:
            parts.append("attempted: %d" % p["attempted"])
    parts.append("foldable: %d" % fold)
    return " · ".join(parts)
