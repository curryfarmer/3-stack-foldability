"""test_style_parity.py — the two render-style single-sources-of-truth agree on their shared palette.

square/render/figstyle.py (square track) and triangle/tri/tristyle.py (triangle track) are SEPARATE,
independent packages that never import each other (each ships a bare-named `lattice` that collides in
one interpreter — see the conftest rationale). They agree on a handful of shared hexes only by hand.
This test enforces that agreement WITHOUT importing either module: it reads both files by path and
parses their module-level constant assignments with `ast`. So it is safe to run in the neutral
smoketest interpreter, and it fails loudly (not skips) if a shared colour drifts or tristyle.py is
missing.

Contract spec'd in docs/guides/STYLE_SPEC.md §2.
"""
import ast
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGSTYLE = os.path.join(ROOT, "square", "render", "figstyle.py")
TRISTYLE = os.path.join(ROOT, "triangle", "tri", "tristyle.py")

# Shared constants that MUST be byte-identical across the two tracks. Widened: the START footprint
# (FOOTPRINT_EDGE, purple) + the parity/sigma tile tint (PARITY_RED/BLUE) are now unified across
# tracks, and the verdict/label/grid/dpi/muted values that were duplicated by hand are now enforced.
SHARED_SCALAR = ["CUT", "INK", "VLY", "MNT", "FOOTPRINT_EDGE", "MUTED", "GRID_EDGE", "DPI",
                 "POS", "NEG", "FOLD_BADGE", "JAM_BADGE", "PARITY_RED", "PARITY_BLUE"]
# Legitimately triangle-only: the parity gate must NOT require these to match figstyle, only exist.
# START_FILL (faint purple hub fill — square start footprint carries no fill) and TINT (per-chain fill
# list — square uses CHAIN+alpha, no literal) have no square counterpart.
TRIANGLE_ONLY = ["CHIR_COLOR", "CHIR_TAG", "START_FILL", "RIGID", "TINT"]


def _constants(path):
    """{name: literal} for every module-level `NAME = <literal>` assignment (single Name target whose
    value is a constant/list/dict/tuple literal). Non-literal RHS (e.g. `TINT_UP = TINT[0]`) is skipped
    — it can't drift a hex by itself. No import: pure source parse."""
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        tgt = node.targets[0]
        if not isinstance(tgt, ast.Name):
            continue
        try:
            out[tgt.id] = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            continue                          # non-literal RHS -> not a palette constant
    return out


def test_style_files_exist():
    assert os.path.isfile(FIGSTYLE), "square/render/figstyle.py missing (the square reference)"
    assert os.path.isfile(TRISTYLE), "triangle/tri/tristyle.py missing (the triangle reference)"


def test_shared_scalars_match():
    sq = _constants(FIGSTYLE)
    tri = _constants(TRISTYLE)
    for name in SHARED_SCALAR:
        assert name in sq, f"figstyle missing shared constant {name}"
        assert name in tri, f"tristyle missing shared constant {name}"
        assert tri[name] == sq[name], (
            f"{name} drifted between the tracks: figstyle={sq[name]!r} tristyle={tri[name]!r}")
    assert sq["CUT"] == "#2a8f6f", f"figstyle.CUT unexpected: {sq['CUT']!r}"
    assert tri["CUT"] == "#2a8f6f", f"tristyle.CUT unexpected: {tri['CUT']!r}"


def test_chain_triple_matches():
    sq = _constants(FIGSTYLE)
    tri = _constants(TRISTYLE)
    assert tri["CHAIN"] == sq["CHAIN"][:3], (
        f"chain A/B/C drifted: figstyle={sq['CHAIN'][:3]!r} tristyle={tri['CHAIN']!r}")


def test_triangle_only_constants_exist_and_are_unconstrained():
    tri = _constants(TRISTYLE)
    for name in TRIANGLE_ONLY:
        assert name in tri, f"tristyle missing its triangle-only constant {name}"
    # These are deliberately NOT required to equal any figstyle value — that's the point of the split.
