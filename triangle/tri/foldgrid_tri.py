"""foldgrid_tri.py — arbitrary drawn-REGION ingest for the triangle 3-stack / 1+1+1 engine.

The shipped finder (find_example.find_first) builds a deliberately OVERSIZED ambient lattice and
lets the folded region emerge (region = union of the three chains); it does not fold a FIXED region.
This module does the opposite: given an exact drawn region S (an arbitrary connected set of a tiling's
base cells), it builds the lattice from EXACTLY those cells and enumerates every closing 1+1+1 fold
that covers S. This is the triangle analog of the square engine's opts["sheet"] ingest (session S6).

  region S  ->  build_lattice(tiling, S)  ->  enumerate_folds(lat, tiling)  ->  [closing fold record]

DESIGN (see docs/S6 handoff + docs/SESSIONS.md "S6"):

  * We reuse the legacy enumerator's GENERIC primitives only -- lat.all_trapezoids() (base.Lattice)
    and trisearch.grow_walks() -- to enumerate the exact 3-cover of S from every trapezoid hub in S.
    trisearch.search_111 itself is NOT called: its `foldable` verdict is the wrong (non-closing)
    exit_ok gate, and its twist uses the bipartite TL.sigma default, which is only defined on
    equilateral U/D ids (it fails / reads garbage on righttri N/E/S/W, scalene 5-tuple, hex (q,r) ids)
    and reads a spurious Tw=0 on the spliced pairwise loop even on equilateral. trisearch.py stays
    byte-frozen (it is XVAL-oracle-compared; gate at the consumer -- see memory tri-closure-gate).

  * The verdict is the PHYSICAL CLOSURE gate foldclose.reflection_closes_111 -- each chain's end tile
    folds exactly onto its start tile. This is the sole filter (exit_ok is NOT applied: it tests the
    end tiles' mutual adjacency in the UNFOLDED lattice, which closure does not imply, so it can drop
    valid closing folds).

  * Twist is a LABEL, never a filter (matching the shipped authority find_example.gen_111). It is
    scored with the LOOP-INDEX sigma (find_example.pairwise(chains, cent, "path")), the only correct
    sigma on a spliced pairwise loop and on non-bipartite hex. Records mirror gen_111's yield shape so
    the rest of the triangle pipeline (gen_testset.fold_uid / _fold_record, render_fold) consumes them
    unchanged.

Triangle 2+1 is NOT generalized (rhombus-index bound); this module is 1+1+1 / 3-stack only.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foldclose as FC        # noqa: E402  reflection_closes_111 (physical closure = the gate)
import find_example as FE     # noqa: E402  GEN table (LatClass/cent) + pairwise (loop-index twist)
import trisearch as TS        # noqa: E402  grow_walks (generic DFS walk primitive) -- byte-frozen

TILINGS = ("equilateral", "righttri", "scalene", "hex")


# --------------------------------------------------------------------------- lattice construction
def build_lattice(tiling, cells):
    """Build the triangle lattice on EXACTLY the region `cells` (an arbitrary connected set of base
    tiles), dispatching to the tiling's constructor via its uniform `cells=` path.

    `cells` are native tile ids as JSON lists or tuples (equilateral [i,j,o]; righttri [i,j,o] with
    o in N/E/S/W; scalene [i,j,o,vid,oid]; hex [q,r]). Raises ValueError on a malformed region --
    NEVER returns an empty/degenerate lattice silently (an empty enumeration is indistinguishable
    from "unfoldable" downstream, so bad input must be loud)."""
    if tiling not in FE.GEN:
        raise ValueError("unknown tiling %r (expected one of %s)" % (tiling, ", ".join(TILINGS)))
    ids = [tuple(c) for c in cells]
    if not ids:
        raise ValueError("empty region: `cells` must be non-empty")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate cells in region")
    if len(ids) % 3 != 0:
        raise ValueError("region size %d is not divisible by 3 (1+1+1 needs len(cells) %% 3 == 0)"
                         % len(ids))
    lat = FE.GEN[tiling]["LatClass"](cells=ids)
    if not _edge_connected(lat):
        raise ValueError("region is not edge-connected over the dual (face-adjacency) graph")
    return lat


def _edge_connected(lat):
    """True iff the region's dual graph (lat.adj, full-edge sharing) is connected -- a BFS from any
    tile must reach every tile. Vertex-only touching does NOT count (base.Lattice.adj is edge-share)."""
    tiles = lat.tris
    if not tiles:
        return False
    seen, stack = {tiles[0]}, [tiles[0]]
    while stack:
        t = stack.pop()
        for nb in lat.adj[t]:
            if nb not in seen:
                seen.add(nb)
                stack.append(nb)
    return len(seen) == len(tiles)


# --------------------------------------------------------------------------- enumeration
def _canon(chains):
    """Order-independent identity of a 1+1+1 fold on its region: (mid-chain, {arm chains}). Collapses
    the arm A<->C swap the same trapezoid hub emits twice. Matches gen_testset._dedup_key's 111 key."""
    arm0, mid, arm2 = chains
    tt = lambda w: tuple(tuple(t) for t in w)   # noqa: E731
    return ("111", tt(mid), frozenset({tt(arm0), tt(arm2)}))


def _record(tiling, chains):
    """A gen_111-shaped fold record (find_example.py:177). Twist scored LAST, as a loop-index label;
    `foldable` is all(tw == 0) over an ALREADY-closing fold (the closure gate ran before this)."""
    cent = FE.GEN[tiling]["cent"]
    L = FE.pairwise(chains, cent, "path")
    tw = [int(round(L[nm]["Tw"])) for nm in ("AB", "BC", "AC")]
    region = sorted({t for w in chains for t in w})
    return {"decomp": "1plus1plus1", "chains": [list(w) for w in chains],
            "footprint": [w[0] for w in chains], "end_footprint": [w[-1] for w in chains],
            "region": region, "tw": tw, "foldable": all(v == 0 for v in tw),
            # A region-built lattice IS its own ambient (lat.tris == region), so there are no enclosed
            # empty tiles to detect -- holes is definitionally 0. Carry it explicitly: gen_testset.
            # _fold_record reads cand.get("holes") and the renderer formats it with %d (None crashes).
            "holes": 0,
            "tw_desc": "Tw AB=%+d BC=%+d AC=%+d" % (tw[0], tw[1], tw[2])}


def enumerate_folds(lat, tiling, first=False):
    """Every closing 1+1+1 fold that covers EXACTLY `lat`'s tiles, as gen_111-shaped records.

    Enumerate three vertex-disjoint K-cell triangle walks (K = |tiles| / 3) from each trapezoid hub in
    the region, forcing an exact 3-cover, then keep only those passing the physical closure gate. With
    `first=True`, return as soon as the first closing fold is found (a witness that the region admits a
    3-stack closure), instead of enumerating the whole set."""
    allset = set(lat.tris)
    K = len(allset) // 3
    seen, out = set(), []
    for fp in lat.all_trapezoids():
        A, B, C = fp
        for wa in TS.grow_walks(lat, A, K, allset):
            freeb = allset - set(wa)
            for wb in TS.grow_walks(lat, B, K, freeb):
                freec = freeb - set(wb)
                for wc in TS.grow_walks(lat, C, K, freec):
                    if set(wc) != freec:            # exact cover of S (NO exit_ok pre-filter)
                        continue
                    chains = [wa, wb, wc]
                    key = _canon(chains)
                    if key in seen:
                        continue
                    seen.add(key)
                    if not FC.reflection_closes_111(lat, chains):   # physical closure = the filter
                        continue
                    out.append(_record(tiling, chains))
                    if first:
                        return out
    return out


def run(tiling, cells, first=False):
    """Convenience: build_lattice(tiling, cells) then enumerate_folds. Returns the fold records."""
    return enumerate_folds(build_lattice(tiling, cells), tiling, first=first)
