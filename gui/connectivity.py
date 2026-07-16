"""connectivity.py — is a drawn selection a single connected sheet?

The GUI shows this before enabling "fold": a valid sheet is a non-empty, edge-connected set of tiles.
It mirrors each engine's own connectivity guard (square 4-connectivity, triangle dual-edge
connectivity), but runs on the DUMPED adjacency (i<j index pairs), so it is tiling-agnostic -- one
BFS for all five geometries, no per-tiling adjacency re-derivation.
"""


def is_connected(selected_indices, adj):
    """True iff `selected_indices` is a non-empty set that is edge-connected over `adj` (the dump's
    undirected index-pair adjacency). Empty selection -> False; a single cell -> True. I/O:
    (iterable[int], list[[i, j]]) -> bool."""
    sel = set(selected_indices)
    if not sel:
        return False
    nbrs = {i: set() for i in sel}
    for a, b in adj:
        if a in sel and b in sel:
            nbrs[a].add(b)
            nbrs[b].add(a)
    start = next(iter(sel))
    seen = {start}
    stack = [start]
    while stack:
        node = stack.pop()
        for other in nbrs[node]:
            if other not in seen:
                seen.add(other)
                stack.append(other)
    return seen == sel
