"""foldclose.py — the physical CLOSURE gate for triangle/general 3-stack folds.

Ports the square engine's reflection check (py/engine/fold.py reflection_verdict: seed a shared
crease, reflect it through each side's folds, require the images to COINCIDE) to the triangle /
righttri / scalene / hex lattices via the lattice-agnostic fold geometry in lattice/foldwalk.py.

This is the check the triangle pipeline never had: trisearch.exit_ok tests only the dual-GRAPH
degree pattern of the three end tiles (do they form a trapezoid abstractly), NOT whether the fold
physically closes them into one stack. exit_ok therefore admits non-closing folds (the user's two
bugs). reflection_closes_* is the geometric authority that replaces "trust the (unreliable) twist".

1+1+1: each of the three chains must accordion its END tile back onto its START tile; then the three
ends coincide with the start trapezoid (the closed 3-stack). Verified == the equilateral oracle
(2/2 closing at K=10, 94/94 at K=12).

2+1: the rigid 2-chain folds as a rigid body (tree); the 1-chain as a walk; they are bound at the
start crease (mid<->b). In a 3-STACK the 1-chain layer stacks directly on top of the binding tile,
so b and mid are the SAME footprint cell (different layers) — the two frames are identified WITHOUT
the start-crease reflection. The fold closes iff (i) the 1-chain accordions home onto b AND (ii) the
END binding crease (end 2-chain tile <-> end 1-chain tile) coincides when the 2-chain side (rigid
body, rooted at the binding tile) and the 1-chain side (its own anchor) are both folded down.

Because each end folds back onto the start, the closed footprint IS the start trapezoid — so that is
what the renderer highlights (a real landing, with start-footprint adjacencies preserved).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lattice import foldwalk as FW  # noqa: E402


def reflection_closes_111(lat, chains):
    """chains = [pa, pm, pc]. PASS iff every chain folds its end tile exactly onto its start tile."""
    for w in chains:
        if len(w) < 1:
            return False
        if len(w) == 1:
            continue
        M = FW.fold_transform(lat, w)
        if FW._poly_key(FW.folded_polygon(lat, M, w[-1])) != FW._poly_key(lat.vertices_cart(w[0])):
            return False
    return True


# NB (2026-06-30): there is deliberately NO separate edges_match_111 / edge-type gate for 1+1+1.
# Two independent adversarial audits confirmed reflection_closes_111 ALREADY implies the YYR
# position+direction (edge-type) condition on every reflection tiling: each chain's END folds onto
# its START as an exact congruent copy, and _poly_key set-equality forces an orientation-CONSISTENT
# landing (a scalene 30-60-90 tile has no symmetry, so the only isometry fixing its vertex set is the
# identity; righttri's only self-map is the harmless leg-swap). The apparent START-vs-END "long<->short
# seam swap" on righttri/scalene is HARMLESS: the inter-chain hub seams are rigid trapezoid joins
# (kept flat), and the END hub folds onto the START hub as a unit — no end-seam ever re-binds, so its
# length is irrelevant. A crease-coincidence gate of that form is NOT a no-op on equilateral (it folds
# each chain's end-seam back to a DIFFERENT world anchor a0 vs m0 and so wrongly drops 72/94 closing
# folds at K=12). The only legitimate edge-type assertion would be "end->start landing == identity
# vertex permutation up to the tile's symmetry group", which reflection_closes_111 already guarantees.

# NB (2026-07-17): the former reflection_closes_21 + _root_of lived here but had ZERO live callers and
# were wrong post-refactor — the 2+1 closure authority is now foldsim.valid_21 (simulate the printed
# sheet: land on {a,mid,b}, uniform K layers, single-valued), which superseded them (see domino21.py).
# They were deleted rather than kept as dead code.


# NB: a closing fold returns each chain's end onto its start, so the closed 3-stack lands on the
# START trapezoid. The renderers therefore highlight the start footprint tiles (real landing, with
# the start-footprint adjacencies preserved by construction) — no separate folded-polygon needed.
