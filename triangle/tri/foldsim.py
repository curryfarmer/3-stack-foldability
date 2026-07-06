"""foldsim.py — simulate folding the PRINTED 3-stack sheet and report whether it seats flat.

The physical sheet is a set of tiles joined by three kinds of interior edge:
  - CREASE (fold): reflect across it.
  - RIGID  (keep flat / attached): the two tiles stay coplanar — a hub trapezoid seam OR a domino's
    internal edge (a domino is one rigid 2-tile unit — domino21 model).
  - SLIT   (cut): not connected.
Folding = start from an anchor tile (identity frame) and compose one reflection per CREASE edge on
the path out to each tile; RIGID edges contribute the identity (the tiles ride along rigidly).

A valid flat 3-stack onto the START trapezoid {a, mid, b} requires ALL of:
  (i)  on-footprint : every tile's folded polygon coincides with a footprint cell (a / mid / b).
  (ii) uniform cover: each of the 3 cells is covered the same number of times (= K layers).
  (iii) consistent  : every CREASE edge coincides when reached from either side (the closure /
       cycle-consistency condition — this replaces the old, over-folding tree_fold check).

This is exactly what the user does with scissors, so it is the authority for FOLD/JAM *closure*.
The twist (Tw==0) remains the separate FOLD-vs-JAM *label* among folds that close.

Works on any Lattice subclass (equilateral / righttri / scalene / hex) via lat.shared_edge +
lat.vertices_cart + lat.adj, reusing the reflection primitive in lattice/foldwalk.
"""
import os
import sys
from collections import deque, Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lattice import foldwalk as FW          # noqa: E402  _poly_key / _edge_key
from lattice.reflect import reflect_point   # noqa: E402


def _uf_components(region, rigid):
    """Union-find the tiles into maximal RIGID-connected components (each folds as one unit)."""
    parent = {t: t for t in region}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for fs in rigid:
        u, v = tuple(fs)
        if u in parent and v in parent:
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[ru] = rv
    return {t: find(t) for t in region}


def _apply(pts, mirrors):
    """Fold a polygon by reflecting across each mirror in order (mirrors[0] applied first)."""
    for (p1, p2) in mirrors:
        pts = [reflect_point(p, p1, p2) for p in pts]
    return pts


def simulate(lat, region, crease, rigid, anchor=None):
    """Fold the sheet. `crease`/`rigid` are sets of frozenset({tileA, tileB}) interior edges.

    Returns dict:
      landing   : {tile -> world _poly_key}  (folded polygon key of every reached tile)
      reached   : set of tiles reachable from the anchor via crease|rigid edges
      consistent: bool — every crease edge coincides from both sides (closure holds)
      comp      : {tile -> rigid-component root}
    """
    region = [tuple(t) for t in region]
    rset = set(region)
    crease = {frozenset(map(tuple, fs)) for fs in crease}
    rigid = {frozenset(map(tuple, fs)) for fs in rigid}
    comp = _uf_components(region, rigid)

    # component graph: components joined by a crease edge (carry the shared crease geometry)
    cadj = {}
    for fs in crease:
        u, v = tuple(fs)
        if u not in rset or v not in rset or (u, v) not in lat.shared:
            continue                                 # non-edge crease (malformed) -> ignore the join
        cu, cv = comp[u], comp[v]
        e = lat.shared_edge(u, v)
        cadj.setdefault(cu, []).append((cv, e))
        cadj.setdefault(cv, []).append((cu, e))

    roots = list(dict.fromkeys(comp[t] for t in region))
    anchor_comp = comp[tuple(anchor)] if anchor is not None else roots[0]
    # BFS a spanning tree over components; each component gets a mirror list (crease path to anchor)
    cmirror = {anchor_comp: []}
    q = deque([anchor_comp])
    while q:
        c = q.popleft()
        for (d, e) in cadj.get(c, ()):
            if d not in cmirror:
                cmirror[d] = [e] + cmirror[c]     # reflect across e first, then c's path
                q.append(d)

    reached = {t for t in region if comp[t] in cmirror}
    landing = {t: FW._poly_key(_apply(lat.vertices_cart(t), cmirror[comp[t]]))
               for t in reached}

    # (iii) consistency: every crease edge must coincide from both incident component frames.
    consistent = True
    for fs in crease:
        u, v = tuple(fs)
        if u not in reached or v not in reached or (u, v) not in lat.shared:
            consistent = False                       # unreached, or a crease with no real shared edge
            continue
        e = lat.shared_edge(u, v)
        segu = _apply(list(e), cmirror[comp[u]])
        segv = _apply(list(e), cmirror[comp[v]])
        if FW._edge_key(segu) != FW._edge_key(segv):
            consistent = False
    return {"landing": landing, "reached": reached, "consistent": consistent, "comp": comp}


def coverage(sim, footprint, lat):
    """Bucket every reached tile's landing onto the footprint cells; returns (Counter, off_count)."""
    a, mid, b = [tuple(t) for t in footprint]
    fk = {"a": FW._poly_key(lat.vertices_cart(a)),
          "mid": FW._poly_key(lat.vertices_cart(mid)),
          "b": FW._poly_key(lat.vertices_cart(b))}
    # the three footprint cells must be geometrically distinct, else `inv` would collapse two cells
    # and silently under-count coverage (a false JAM). A real trapezoid always has 3 distinct cells.
    if len(set(fk.values())) != 3:
        raise ValueError("degenerate footprint: cells not distinct (a/mid/b=%s)" % (footprint,))
    inv = {v: k for k, v in fk.items()}
    cov = Counter()
    off = 0
    for t, key in sim["landing"].items():
        cell = inv.get(key)
        if cell is None:
            off += 1
        else:
            cov[cell] += 1
    return cov, off


def valid_flat_fold(lat, region, crease, rigid, footprint, end_footprint=None):
    """PASS iff the printed sheet folds to a flat 3-stack on the START trapezoid {a,mid,b}.

    Frames propagate from the START-hub anchor `mid` via creases + `rigid` (which must be the
    domino-internal + START-hub seams ONLY — NOT the end hub; each chain folds independently and the
    end hub is a *landing* check, not a frame coupler). Requires:
      - every tile reached and landing on a footprint cell (off == 0),
      - uniform K-coverage of a / mid / b,
      - END-footprint correspondence: end_footprint[i] lands on footprint[i]'s cell
        (strand/chainA end -> a, mid/partner end -> mid, one/chainC end -> b).
    Returns (ok, diagnostics)."""
    region = [tuple(t) for t in region]
    a, mid, b = [tuple(t) for t in footprint]
    sim = simulate(lat, region, crease, rigid, anchor=mid)
    cov, off = coverage(sim, footprint, lat)
    all_reached = len(sim["reached"]) == len(region)
    counts = [cov.get("a", 0), cov.get("mid", 0), cov.get("b", 0)]
    uniform = counts[0] == counts[1] == counts[2] > 0

    # closes-flat GATE: folds onto the trapezoid with uniform K layers, single-valued.
    closes = all_reached and off == 0 and uniform and sim["consistent"]

    # correspondence LABEL: does the END footprint land on the START cells in-order (strand/chainA
    # end -> a, partner/mid end -> mid, one/chainC end -> b)? Correspondence-preserving = the rigid
    # domino / chains return UN-twisted => predicted FOLDABLE. Broken (flipped/permuted) => the piece
    # returns twisted => predicted JAM. (A physical predictor, unlike the unreliable triangle twist.)
    corr = None
    corr_detail = None
    if end_footprint is not None:
        fk = {"a": FW._poly_key(lat.vertices_cart(a)),
              "mid": FW._poly_key(lat.vertices_cart(mid)),
              "b": FW._poly_key(lat.vertices_cart(b))}
        want = ["a", "mid", "b"]
        got = [next((nm for nm, kk in fk.items() if kk == sim["landing"].get(tuple(t))), "OFF")
               for t in end_footprint]
        corr = (got == want)
        corr_detail = "%s->%s" % (want, got)

    foldable = bool(closes and corr)
    diag = {"reached": len(sim["reached"]), "n": len(region), "off": off, "cover": dict(cov),
            "uniform": uniform, "consistent": sim["consistent"], "closes": closes,
            "corr": corr, "corr_detail": corr_detail, "foldable": foldable, "ok": closes}
    return closes, diag


# --------------------------------------------------------------------- high-level validity wrappers
def valid_21(lat, strand, partners, one_chain, footprint, end_footprint=None):
    """(closes, diag) for a 2+1 fold — the AUTHORITY for whether the printed sheet seats as a flat
    3-stack. diag['foldable'] is the correspondence-based FOLD/JAM prediction."""
    crease, rigid = edges_21(lat, strand, partners, one_chain, footprint)
    region = {tuple(t) for t in strand} | {tuple(t) for t in partners} | {tuple(t) for t in one_chain}
    return valid_flat_fold(lat, region, crease, rigid, footprint, end_footprint)


def valid_111(lat, chains, footprint, end_footprint=None):
    """(closes, diag) for a 1+1+1 fold, via the same printed-sheet simulation."""
    crease, rigid = edges_111(lat, chains, footprint)
    region = {tuple(t) for w in chains for t in w}
    return valid_flat_fold(lat, region, crease, rigid, footprint, end_footprint)


# --------------------------------------------------------------------- crease / rigid builders
def edges_111(lat, chains, footprint):
    """(crease, rigid) for a 1+1+1 fold. Crease = consecutive same-chain tiles. Rigid (frame-
    propagating) = the START-hub trapezoid seams ONLY; the END hub is verified by correspondence."""
    crease = set()
    for w in chains:
        for k in range(len(w) - 1):
            crease.add(frozenset((tuple(w[k]), tuple(w[k + 1]))))
    return crease, _hub_rigid(lat, (footprint,))


def edges_21(lat, strand, partners, one_chain, footprint):
    """(crease, rigid) for a 2+1 fold. Crease = ribbon hinges (between consecutive dominoes) +
    1-chain creases. RIGID (frame-propagating) = each domino's internal edge (rigid 2-tile unit) +
    the START-hub trapezoid seams. The domino-internal edge is deliberately RIGID, not a crease
    (it is the rigid 2-stack unit); the END hub is verified by correspondence, not propagation."""
    strand = [tuple(t) for t in strand]
    partners = [tuple(t) for t in partners]
    one_chain = [tuple(t) for t in one_chain]
    crease, rigid = set(), set()
    dom = [(strand[k], partners[k]) for k in range(len(strand))]
    for (s, p) in dom:
        if p in lat.adj.get(s, ()):
            rigid.add(frozenset((s, p)))                       # domino internal = RIGID
    for k in range(len(dom) - 1):
        for u in dom[k]:
            for v in dom[k + 1]:
                if v in lat.adj.get(u, ()):
                    crease.add(frozenset((u, v)))              # ribbon hinge = fold
    for k in range(len(one_chain) - 1):
        crease.add(frozenset((one_chain[k], one_chain[k + 1])))  # 1-chain crease = fold
    rigid |= _hub_rigid(lat, (footprint,))
    return crease, rigid


def _hub_rigid(lat, fps):
    rigid = set()
    for fp in fps:
        if not fp:
            continue
        fpt = [tuple(t) for t in fp]
        for i in range(len(fpt)):
            for j in range(i + 1, len(fpt)):
                t, u = fpt[i], fpt[j]
                if u in lat.adj.get(t, ()):
                    rigid.add(frozenset((t, u)))
    return rigid


if __name__ == "__main__":
    # smoke: fold the validated equilateral 1+1+1 K=12 closing folds -> must land {12,12,12}
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import prove_obstruction as PO
    import solve_foldable as SF
    import foldclose as FC
    lat, S, back = PO.build_ambient(12)
    n = 0
    for (pa, pm, pc) in SF.enum_111(lat, S, back, 12):
        chains = [list(pa), list(pm), list(pc)]
        if not FC.reflection_closes_111(lat, chains):
            continue
        fp = [pa[0], pm[0], pc[0]]
        efp = [pa[-1], pm[-1], pc[-1]]
        crease, rigid = edges_111(lat, chains, fp)
        ok, diag = valid_flat_fold(lat, set(pa) | set(pm) | set(pc), crease, rigid, fp, efp)
        print("1+1+1 eq K=12:", ok, diag)
        n += 1
        if n >= 3:
            break
