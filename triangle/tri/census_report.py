"""Turn the store-all census (results/census/) into the density tables and the per-gate funnel.

Two questions this answers, both of which the old aggregate-only census could not:

  1. DENSITY -- closing candidates and flat folds per (tiling, decomp, K), with truncation flagged.
     A truncated cell is a lower bound, never an exhaustive count; the published tables drifted from
     the on-disk ones precisely because that distinction was dropped.

  2. RARITY -- WHERE 2+1 candidates die relative to 1+1+1. Surviving counts alone cannot distinguish
     "2+1 rarely closes" from "2+1 closes but rarely untwists"; the funnel can. The two ladders are
     not identical (1+1+1 fuses exit+parity into its enumerator, 2+1 tests exit_ok on a materialised
     triple), so the shared tail -- closure -> twist -- is what gets compared directly.

Usage:
    python -m triangle.tri.census_report
    python -m triangle.tri.census_report --md > docs/research/census_2026-07.md
"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CENSUS = os.path.join(REPO, "results", "census")

TILINGS = ["equilateral", "righttri", "scalene", "hex"]
DECOMPS = ["1plus1plus1", "2plus1"]


def load():
    with open(os.path.join(CENSUS, "index.json")) as fh:
        return json.load(fh)["cells"]


def density(cells, md=False):
    out = []
    bar = "|" if md else " "
    for d in DECOMPS:
        out.append("\n### %s — closing / flat (Tw=0)\n" % d)
        ks = sorted({c["K"] for c in cells if c["decomp"] == d})
        if not ks:
            continue
        out.append("| tiling | " + " | ".join("K=%d" % k for k in ks) + " |")
        out.append("|" + "---|" * (len(ks) + 1))
        for t in TILINGS:
            row = ["**%s**" % t]
            for k in ks:
                c = next((x for x in cells
                          if x["tiling"] == t and x["decomp"] == d and x["K"] == k), None)
                if c is None:
                    row.append("–")
                    continue
                cell = "%d / **%d**" % (c["closing"], c["tw0"]) if c["tw0"] else \
                       "%d / 0" % c["closing"]
                if c["truncated"]:
                    cell += " ⚠"          # lower bound: cell hit the wall-clock cap
                row.append(cell)
            out.append("| " + " | ".join(row) + " |")
    out.append("\n⚠ = truncated (wall-clock cap hit) — the count is a LOWER BOUND, not a census.\n")
    return "\n".join(out)


def funnel(cells):
    """Per (tiling, decomp): the gate ladder, and the survival rate of the shared closure->twist tail."""
    out = ["\n### Gate funnel — where candidates die\n"]
    out.append("| tiling | decomp | enumerated | closes | Tw=0 | closure rate | twist rate |")
    out.append("|---|---|---|---|---|---|---|")
    for t in TILINGS:
        for d in DECOMPS:
            cs = [c for c in cells if c["tiling"] == t and c["decomp"] == d]
            if not cs:
                continue
            f = {}
            for c in cs:
                for k, v in c["funnel"].items():
                    f[k] = f.get(k, 0) + v
            # "enumerated" = raw candidates offered to the closure gate. 1+1+1 counts them as
            # `routed` (triples the enumerator built, already past exit+parity); 2+1 as `tried`
            # (one_chain candidates), narrowed by exit_ok to `topology_pass`.
            enum = f.get("routed", 0) if d == "1plus1plus1" else f.get("topology_pass", 0)
            closes = sum(c["closing"] for c in cs)
            tw0 = sum(c["tw0"] for c in cs)
            crate = ("%.4f%%" % (100.0 * closes / enum)) if enum else "–"
            trate = ("%.1f%%" % (100.0 * tw0 / closes)) if closes else "–"
            out.append("| %s | %s | %d | %d | %d | %s | %s |"
                       % (t, d, enum, closes, tw0, crate, trate))
    out.append("\n`closure rate` = closes / enumerated (the geometric gate — does the sheet come "
               "back onto its own footprint).\n`twist rate` = Tw=0 / closes (the topological gate — "
               "given that it closes, does it close *untwisted*).\n")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="census density tables + gate funnel")
    ap.add_argument("--md", action="store_true", help="markdown only (no header chatter)")
    args = ap.parse_args()

    cells = load()
    trunc = [c for c in cells if c["truncated"]]
    if not args.md:
        print("census: %d cells, %d truncated" % (len(cells), len(trunc)))
    print("# Non-square census\n")
    print(density(cells))
    print(funnel(cells))
    if trunc:
        print("\n### Truncated cells (lower bounds)\n")
        for c in sorted(trunc, key=lambda c: (c["tiling"], c["decomp"], c["K"])):
            print("- %s %s K=%d — %d closing after %.0fs"
                  % (c["tiling"], c["decomp"], c["K"], c["closing"], c["dt"]))


if __name__ == "__main__":
    main()
