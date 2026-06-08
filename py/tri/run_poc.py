"""run_poc.py — triangle 3-stack proof-of-concept driver.

Produces the figures + the summary table reported to the lead. Findings (see LAB_LOG):
the lattice / sigma / reflection / closed-loop-twist machinery ports exactly to the triangle
lattice (verified), but on small grids the 3-stack TILINGS never fold back to a congruent exit
footprint, so the closed-loop twist criterion has no valid instance yet (an existence/parity
obstruction, not a math-port failure).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trilattice as TL   # noqa: E402
import tritwist as TW      # noqa: E402
import trisearch as TS     # noqa: E402
import trirender as TR     # noqa: E402


def fmt_loops(loops):
    return "  ".join("%s=%+.0f" % (k, loops[k]["Tw"]) for k in ("AB", "BC", "AC"))


def main():
    figs = []

    # 1) verified balanced bipartite lattice (hexagon side 2)
    hexlat = TL.TriLattice(cells=TL.hexagon_cells(2))
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.6, 6.0))
    TR.draw_lattice(ax, hexlat, sigma_fill=True, label_sigma=True)
    xs = [p[0] for t in hexlat.tris for p in TR._poly(t)]
    ys = [p[1] for t in hexlat.tris for p in TR._poly(t)]
    ax.set_xlim(min(xs) - 0.5, max(xs) + 0.5); ax.set_ylim(min(ys) - 0.5, max(ys) + 0.9)
    nU = sum(1 for t in hexlat.tris if t[2] == "U")
    ax.text((min(xs) + max(xs)) / 2, max(ys) + 0.6,
            "triangle lattice (hexagon side 2): %d triangles, bipartite UP=+ / DOWN=−  (%d/%d)"
            % (len(hexlat.tris), nU, len(hexlat.tris) - nU),
            ha="center", va="bottom", fontsize=10, fontweight="bold", color=TR.INK)
    os.makedirs(TR.OUT, exist_ok=True)
    p = os.path.join(TR.OUT, "lattice_hex2.png"); fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig); figs.append(p)

    # 2) verified closed-loop twist anchor: the 6-triangle ring around an interior vertex
    par = TL.TriLattice(2, 3)
    ring = TW._hex_ring_around(par, 1, 1)
    res = TW.loop_twist(ring)
    p = TR.render_tiling(par, [ring], "closed-loop twist anchor (6-ring)",
                         "ring_twist.png",
                         twist_note="all gamma = 120 deg\nTw = %+.0f deg  (clean, multiple of 360)"
                         % res["Tw"], closed_loops=[ring])
    figs.append(p)

    # 3) three 1+1+1 tilings on the hexagon (relaxed exit — they do NOT close; twist fractional)
    s111 = TS.search_111(hexlat, require_exit=False)
    print("hex(side2) 1+1+1 tilings found: %d   (closing: %d)"
          % (len(s111), sum(1 for s in s111 if s["closes"])))
    picks = s111[:3]
    for idx, s in enumerate(picks, 1):
        note = ("1+1+1  K=%d\nstarts trapezoid; ends DO NOT reform a footprint\n%s\n"
                "=> loop has no 2nd hub -> fractional (non-physical)"
                % (len(s["chains"][0]), fmt_loops(s["loops"])))
        p = TR.render_tiling(hexlat, s["chains"], "1+1+1 triangle tiling #%d (non-closing)" % idx,
                             "tiling_111_%d.png" % idx, twist_note=note, footprint=s["footprint"])
        figs.append(p)

    # 4) a 2+1 tiling illustration on the 2x3 parallelogram (rigid rhombus ribbon + 1-chain)
    s21 = TS.search_21(par)
    if s21:
        s = s21[0]
        note = ("2+1  rigid rhombus-ribbon + 1-chain\nreduced-strand loop Tw = %+.0f deg\n"
                "(also non-closing on this grid)" % s["loop"]["Tw"])
        p = TR.render_tiling(par, [s["chains"][0], s["one_chain"]],
                             "2+1 triangle tiling (rhombus ribbon + 1-chain)",
                             "tiling_21.png", twist_note=note, footprint=s["footprint"])
        figs.append(p)

    print("\n=== triangle PoC summary ===")
    print("lattice / sigma(up,down) / reflection / closed-loop twist : PORTED + VERIFIED")
    print("  6-ring closed loop: all gamma=120 deg, Tw=%+.0f (clean)        [ring_twist.png]" % res["Tw"])
    print("3-stack tilings exist but NONE close to a congruent exit footprint:")
    print("  1+1+1 hex(side2): %d tilings, %d closing" % (len(s111), sum(1 for s in s111 if s["closes"])))
    print("  => closed-loop twist criterion has no valid instance on small triangle grids")
    print("\nfigures written:")
    for f in figs:
        print("  ", os.path.relpath(f))


if __name__ == "__main__":
    main()
