"""foldfilter.py — filter a bundle's parsed rows by stack count, decomposition, and the per-gate
foldability vector. Pure (no tkinter, no engine), so the GUI results table AND the headless CLI apply
the SAME predicates off one body of record (and it unit-tests with no display).

A "row" is a dict as produced by gui.results.parse_bundle: it carries `stacks` (int), `decomp`
(normalized "2+1"/"1+1+1"/None), `vector` (a per-gate dict / None), `foldable` (tri-state), `proven`.
The decomp/vector keys are the ones fold_grid._build_bundle stamps; a bundle written before that
enrichment simply has them absent (treated as None) and only the stacks/foldable/proven predicates bite.
"""

# The engines spell the decomposition two ways; normalize to one vocabulary the filters key on. Kept
# byte-identical to scripts/fold_grid.py:_DECOMP_NORMAL (the two never co-import, so it lives in both).
_DECOMP_NORMAL = {"2+1": "2+1", "1+1+1": "1+1+1", "2plus1": "2+1", "1plus1plus1": "1+1+1"}


def normalize_decomp(raw):
    """Fold either engine's decomposition spelling to "2+1"/"1+1+1" (unknown n-stack keys pass
    through); None stays None. I/O: (str | None) -> str | None."""
    if raw is None:
        return None
    return _DECOMP_NORMAL.get(raw, raw)


def _vector_ok(row_vector, require_vector):
    """True iff `row_vector` (a per-gate dict, or None) satisfies every component demanded by
    `require_vector` ({component: bool}). A row with no vector fails any active demand. I/O:
    (dict | None, dict) -> bool."""
    if not require_vector:
        return True
    if not isinstance(row_vector, dict):
        return False
    for comp, want in require_vector.items():
        if row_vector.get(comp) != want:
            return False
    return True


def apply(rows, *, stacks=None, decomps=None, require_vector=None, foldable=None, proven=None):
    """Return the subset of `rows` matching EVERY active predicate (a None/empty predicate is
    inactive). I/O:
      stacks         iterable[int]  keep rows whose `stacks` is in the set
      decomps        iterable[str]  keep rows whose normalized `decomp` is in the set
      require_vector dict{str:bool} keep rows whose `vector` has each component == the wanted value
                                    (rows with vector None are dropped when this is non-empty)
      foldable       bool           keep rows whose `foldable` is exactly this
      proven         bool           keep rows whose `proven` is exactly this
    -> list[dict]. Order is preserved; input rows are not mutated."""
    stack_set = set(stacks) if stacks else None
    decomp_set = {normalize_decomp(d) for d in decomps} if decomps else None
    out = []
    for r in rows:
        if stack_set is not None and r.get("stacks") not in stack_set:
            continue
        if decomp_set is not None and normalize_decomp(r.get("decomp")) not in decomp_set:
            continue
        if not _vector_ok(r.get("vector"), require_vector):
            continue
        if foldable is not None and r.get("foldable") is not foldable:
            continue
        if proven is not None and r.get("proven") is not proven:
            continue
        out.append(r)
    return out


def vector_summary(row_vector):
    """A compact one-line read of a per-gate vector for a table cell, e.g. "exit✓ par✓ refl✓ tw✓",
    or "" when there is no structured vector. Only the components present are shown. I/O:
    (dict | None) -> str."""
    if not isinstance(row_vector, dict):
        return ""
    labels = [("exitFootprint", "exit"), ("parity", "par"), ("reflection", "refl"), ("twist", "tw")]
    parts = []
    for key, short in labels:
        if key in row_vector:
            v = row_vector[key]
            mark = "✓" if v is True else ("✗" if v is False else "·")
            parts.append("%s%s" % (short, mark))
    return " ".join(parts)
