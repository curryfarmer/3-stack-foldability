#!/usr/bin/env python3
"""sweep_minsize.py — exhaustive min-grid-size probe for L vs Rect footprints.

For every grid (m cols, n rows) with mn%6==0 and n>=4 up to a bound, run the
3-stack search restricted to one shape at a time and report how many valid
solutions exist (total, and split by decomposition + twist verdict).

"Valid" = passes exitFootprint + parity + reflection (a real solution row).
twist is non-filtering: we additionally tally twist-decided-pass (Tw=0).
"""
import sys, time
import search as Search


def run_shape(m, n, shape, decomps):
    opts = {
        "m": m, "n": n, "stacks": 3,
        "shapes": {"L": shape == "L", "Rect": shape == "Rect"},
        "decomps": {"2+1": "2+1" in decomps, "1+1+1": "1+1+1" in decomps},
        "allowNonCorner": False,
        "dedup": True,
    }
    sols, ctx, err = Search.run(opts)
    if err:
        return None, err
    agg = {"total": len(sols)}
    for d in ("2+1", "1+1+1"):
        ds = [s for s in sols if s["decomposition"] == d]
        tw0 = sum(1 for s in ds if s["verdict"]["twist"] is True)
        twN = sum(1 for s in ds if s["verdict"]["twist"] is None)
        agg[d] = {"n": len(ds), "tw0": tw0, "twNone": twN}
    return agg, None


def main():
    max_dim = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    max_area = int(sys.argv[2]) if len(sys.argv) > 2 else 60

    grids = []
    for n in range(1, max_dim + 1):        # rows
        for m in range(1, max_dim + 1):    # cols
            if (m * n) % 3 == 0 and m * n <= max_area:
                grids.append((m, n))
    grids.sort(key=lambda g: (g[0] * g[1], g[1], g[0]))

    print(f"sweep: dims<= {max_dim}, area<= {max_area}  ({len(grids)} grids pass mn%3==0)")
    print(f"{'grid':>7} {'area':>4} | {'L tot':>6} {'L 2+1(tw0)':>12} {'L 111(tw0)':>12} | "
          f"{'R tot':>6} {'R 2+1(tw0)':>12} {'R 111(tw0)':>12} | gate")
    first_L = first_R = None
    first_L_tw = first_R_tw = None
    for (m, n) in grids:
        t0 = time.time()
        L, errL = run_shape(m, n, "L", ("2+1", "1+1+1"))
        R, errR = run_shape(m, n, "Rect", ("2+1", "1+1+1"))
        dt = time.time() - t0
        gate = errL or errR or "ok"
        if L is None:
            print(f"{m}x{n:>2} {m*n:>4} | rejected: {gate}")
            continue

        def fmt(agg, d):
            a = agg[d]
            return f"{a['n']}({a['tw0']})"
        Ltot, Rtot = L["total"], R["total"]
        print(f"{m}x{n:<2} {m*n:>4} | {Ltot:>6} {fmt(L,'2+1'):>12} {fmt(L,'1+1+1'):>12} | "
              f"{Rtot:>6} {fmt(R,'2+1'):>12} {fmt(R,'1+1+1'):>12} | {dt:.1f}s")
        if Ltot > 0 and first_L is None:
            first_L = (m, n)
        if Rtot > 0 and first_R is None:
            first_R = (m, n)
        if first_L_tw is None and (L['2+1']['tw0'] + L['1+1+1']['tw0']) > 0:
            first_L_tw = (m, n)
        if first_R_tw is None and (R['2+1']['tw0'] + R['1+1+1']['tw0']) > 0:
            first_R_tw = (m, n)

    print()
    print(f"first grid w/ ANY valid L solution    : {first_L}")
    print(f"first grid w/ ANY valid Rect solution : {first_R}")
    print(f"first grid w/ Tw=0-decided L solution : {first_L_tw}")
    print(f"first grid w/ Tw=0-decided Rect sol.  : {first_R_tw}")


if __name__ == "__main__":
    main()
