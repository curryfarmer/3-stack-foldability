# explainer/

Labelled, first-principles diagrams of the square-grid **twist criterion** — 2-stack baseline
and the 3-stack **1+1+1** extension. Idealized schematics (not driven by `results/*.json`),
rendered with matplotlib to SVG. Standalone: no import of the fold engine.

## Files

| file | role |
|---|---|
| `lib.py` | shared matplotlib primitives + palette (mirrors `grid.js`). |
| `gen.py` | one function per figure; renders all to `svg/`. |
| `svg/` | generated figures (A1–A12 = 2-stack, B1–B5 = 1+1+1). |
| `EXPLAINER.md` | the walkthrough — embeds the figures in order. |

## Regenerate the figures

```bash
cd "Folding Drawer. "
python3 explainer/gen.py        # writes 17 SVGs to explainer/svg/, prints a manifest
```
Requires `matplotlib` + `numpy` (both already present in this environment).

## Build the document

SVG embeds natively in Markdown viewers (GitHub, VS Code) and in HTML:

```bash
cd explainer
pandoc EXPLAINER.md -o EXPLAINER.html --standalone --mathml
```

PDF via LaTeX needs an SVG rasteriser on PATH (`rsvg-convert` or `cairosvg`), which is **not**
installed here. If you add one:

```bash
pandoc EXPLAINER.md -o EXPLAINER.pdf            # needs rsvg-convert / cairosvg for the SVGs
```

## Editing figures

Each figure is a function in `gen.py` (e.g. `A10_tw_zero_2x4`). Shared drawing helpers and the
colour palette live in `lib.py`. Add a figure by writing a function that returns
`L.save(fig, "name")` and appending it to the `FIGURES` list.
