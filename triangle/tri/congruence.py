"""congruence.py — collapse folds into CONGRUENCE CLASSES (distinct shapes, not placements).

Why this exists. Every search here counts PLACEMENTS: each candidate each start hub yields is a
separate result, and nothing dedups congruent regions sitting at different positions or orientations
(gen_testset's frozenset(region) key compares tile IDs, so it separates them). A reported fold COUNT
is therefore partly a fact about the tiling and partly a fact about how wide the sweep was --
righttri 2+1 K=7 goes from 4 folds at 4 hubs to 18 at 20 hubs while the number of distinct shapes
stays at 2. Distinct counts are stable where raw counts are not, so anything that plots or publishes
a count has to dedup first.

Flat module on purpose: `census_distinct.py` is package-relative (`from . import find_example`) while
`generate.py` uses the flat tri/ imports, and both need this. Keeping the canonicaliser here lets
each import it in its own style without either adopting the other's.

TRIANGLE ONLY -- never co-imported with square/ (both packages ship a bare top-level `lattice`).
"""
import hashlib
import math

# Point group to canonicalise against, per tiling. Getting this wrong in the safe direction only
# UNDER-merges (two congruent regions counted twice); over-merging is impossible, because every op
# listed is an actual symmetry of the tiling and so maps folds to folds. righttri is built on the
# tetrakis square lattice (4-fold); the others are triangular or hexagonal (6-fold).
NFOLD = {"righttri": 4, "equilateral": 6, "scalene": 6, "hex": 6}


def ops(n):
    """The 2n elements of the dihedral group of order 2n, as (a, b, c, d) 2x2 matrices."""
    out = []
    for k in range(n):
        th = 2.0 * math.pi * k / n
        c, s = math.cos(th), math.sin(th)
        out.append((c, -s, s, c))                    # rotation by 2*pi*k/n
        out.append((c, s, s, -c))                    # the same, composed with a reflection
    return out


def canon(pts, group):
    """Congruence-class key for a set of points: the lexicographically smallest form over `group`,
    with translation normalised away by subtracting the componentwise minimum.

    Returned as a 16-byte digest rather than the tuple: a large census cell holds millions of these
    at once and the key's only use is set membership. 128 bits makes an accidental collision far less
    likely than a bug in everything else here."""
    best = None
    for (a, b, c, d) in group:
        q = [(a * x + b * y, c * x + d * y) for (x, y) in pts]
        mx = min(p[0] for p in q)
        my = min(p[1] for p in q)
        # 4dp: lattice coordinates are O(K) ~ 20 with float error ~1e-13, so this rounds off noise
        # without merging distinct tiles (nearest centroids are ~0.2 apart on the finest tiling).
        form = tuple(sorted((round(x - mx, 4), round(y - my, 4)) for (x, y) in q))
        if best is None or form < best:
            best = form
    return hashlib.blake2b(repr(best).encode(), digest_size=16).digest()


def region_of(rec):
    """The fold's tile set, from any of the record shapes in play.

    The two decompositions are stored differently and neither is negotiable here: 1+1+1 writes its
    three chains under `chains`, while 2+1 deliberately keeps `strand`/`partners`/`one_chain` apart
    (so the dual-decomposition question stays answerable offline) and carries no `chains` key at all.
    Assuming `chains` reads as correct against every 2+1 cell whose count is zero and KeyErrors on
    the first one that is not -- which is exactly how it shipped, and how it was caught."""
    if "region" in rec:                              # live candidate dicts from gen_111 / gen_21
        return {tuple(t) for t in rec["region"]}
    if "chains" in rec:                              # 1+1+1 census record
        return {tuple(t) for ch in rec["chains"] for t in ch}
    if "two_tris" in rec and "one_chain" in rec:     # 2+1 census record
        return {tuple(t) for t in rec["two_tris"]} | {tuple(t) for t in rec["one_chain"]}
    raise KeyError("record has none of `region`, `chains`, `two_tris`+`one_chain`: %s" % sorted(rec))


def classifier(tiling, cent):
    """-> key(rec) mapping a fold record to its congruence-class key on `tiling`.

    `cent` is the tiling's tile-id -> (x, y) centroid function (find_example.GEN[tiling]["cent"]);
    it is passed in rather than imported so this module stays free of the engine import graph.
    """
    group = ops(NFOLD[tiling])

    def key(rec):
        return canon([cent(t) for t in region_of(rec)], group)

    return key


def count_distinct(records, tiling, cent, flat_key="foldable"):
    """(n, distinct, distinct_flat) over an iterable of fold records. Streams -- `records` may be a
    generator over a census cell too large to hold."""
    key = classifier(tiling, cent)
    seen, seen_flat, n = set(), set(), 0
    for rec in records:
        n += 1
        k = key(rec)
        seen.add(k)
        if rec.get(flat_key):
            seen_flat.add(k)
    return n, len(seen), len(seen_flat)
