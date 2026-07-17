"""gridfile.py — ingest a fold-grid/1 file into the sheet form the square engine consumes.

A fold-grid/1 file describes an arbitrary drawn grid (a connected polyomino) rather than an m x n
rectangle. See docs/schema/fold-grid-1.md. This loader is the single place that:
  * parses + validates the JSON envelope (schema tag, tiling),
  * reconstitutes native square tile ids [x, y] to (x, y) tuples (the same idiom triangle's
    render_fold.py uses: [tuple(t) for t in ...]),
  * normalizes the cells so the bounding box's min corner is (0, 0) — the engine's reflection math
    (apply_transform / make_fold) and the renderer both assume a 0-based bbox,
  * returns opts["sheet"] as a LIST (not a frozenset) so it survives the pickle boundary into
    ProcessPoolExecutor workers AND json.dumps into the PyPy subprocess (a frozenset crashes json).

Square-only (tiling == "square"); the triangle tilings are S6. Raises ValueError on any malformed input.
"""
import json

SCHEMA = "fold-grid/1"
TILING = "square"


def parse_grid(spec):
    """Validate a fold-grid/1 dict and return {"sheet": [[x,y]...], "m": M, "n": N, "stacks": <raw>}.

    sheet is origin-normalized and deduplicated; m,n are the tight bounding box. stacks is the raw
    schema field (hint), passed through untouched for the caller to resolve against --stacks."""
    if not isinstance(spec, dict):
        raise ValueError("fold-grid: top level must be a JSON object")
    if spec.get("schema") != SCHEMA:
        raise ValueError(f"fold-grid: schema must be {SCHEMA!r}, got {spec.get('schema')!r}")
    tiling = spec.get("tiling")
    if tiling != TILING:
        raise ValueError(f"fold-grid: square engine ingests tiling {TILING!r}, got {tiling!r} "
                         f"(triangle tilings are handled by the triangle engine)")
    raw = spec.get("cells")
    if not isinstance(raw, list) or not raw:
        raise ValueError("fold-grid: 'cells' must be a non-empty array")

    cells = []
    for c in raw:
        if (not isinstance(c, (list, tuple)) or len(c) != 2
                or not all(isinstance(v, int) for v in c)):
            raise ValueError(f"fold-grid: square cell id must be [x, y] of ints, got {c!r}")
        cells.append((int(c[0]), int(c[1])))
    uniq = set(cells)
    if len(uniq) != len(cells):
        raise ValueError("fold-grid: duplicate cells")

    min_x = min(x for x, _ in uniq)
    min_y = min(y for _, y in uniq)
    norm = sorted((x - min_x, y - min_y) for (x, y) in uniq)   # sorted => stable, deterministic
    m = max(x for x, _ in norm) + 1
    n = max(y for _, y in norm) + 1

    bbox = spec.get("bbox")
    if bbox is not None:
        if not isinstance(bbox, dict):
            raise ValueError("fold-grid: bbox must be an object with m,n")
        bm, bn = bbox.get("m"), bbox.get("n")
        if (bm, bn) != (m, n):
            raise ValueError(f"fold-grid: bbox {{{bm},{bn}}} disagrees with the cells' extent "
                             f"{{{m},{n}}} (after origin-normalization)")

    return {"sheet": [[x, y] for (x, y) in norm], "m": m, "n": n, "stacks": spec.get("stacks", "auto")}


def load_grid(path):
    """Read a fold-grid/1 file from disk and parse_grid it."""
    with open(path, encoding="utf-8") as f:
        return parse_grid(json.load(f))
