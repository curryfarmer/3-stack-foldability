"""reflect.py — the single reflection primitive shared by every lattice.

`reflect_point(p, a, b)` mirrors point `p` across the line through points `a` and `b`. It is
coordinate-agnostic (pure linear algebra, no axis/angle assumptions), so it serves the square
engine (axis-aligned creases), the triangle engines (0/60/120-degree creases), and the 2-stack
reference identically. Moved here verbatim from the former twostack._reflect_point so there is
ONE reflection of record across the whole codebase.
"""


def reflect_point(p, a, b):
    """Reflect point p across the line through points a and b."""
    x0, y0 = p
    x1, y1 = a
    x2, y2 = b
    A = y2 - y1
    B = x1 - x2
    C = -(A * x1 + B * y1)
    denom = A * A + B * B
    if denom == 0:
        raise ValueError("reflect_point needs distinct points a, b (got a coincident pair, "
                         "so the crease line is undefined)")
    xr = x0 - 2 * A * (A * x0 + B * y0 + C) / denom
    yr = y0 - 2 * B * (A * x0 + B * y0 + C) / denom
    return (xr, yr)
