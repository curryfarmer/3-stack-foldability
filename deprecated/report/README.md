# Report toolchain

Build a documented report (with real fold-pattern screenshots) from generated results.

## Pipeline

```
py/generate.py  →  results/<m>x<n>_<hash>.json     # search + cache
report/shoot.js →  report/figures/*.png            # Playwright screenshots of the live tool
report/*.md     →  pandoc → report.docx            # → drag into Google Docs / open in Word
```

## Prerequisites (already installed in this environment)

- **Static server** running from the project dir: `python3 -m http.server 8001`
- **Google Chrome** (used headless via `channel:'chrome'`)
- `playwright-core` (in `report/node_modules`), `pandoc`, `matplotlib`

## Screenshots — `shoot.js`

Drives the real browser tool: loads a results JSON, steps to each solution by id, and
screenshots the rendered SVG.

```bash
cd report
node shoot.js --results ../results/6x5_<hash>.json --ids 1,2,3
node shoot.js --results <file> --id 2 --element .svg-wrap --scale 2 --label twisted
```

Options: `--results <file>` (required), `--id N` (repeatable) / `--ids 1,2,3`
(default: all), `--out <dir>` (default `figures/`), `--element <css>` (default `.svg-wrap`;
use `.grid-card` to include the header + H/V/T counters), `--scale` (devicePixelRatio,
default 2), `--label <suffix>`, `--url` (default `http://localhost:8001`).

Selecting "a 6×5 variant that does X": filter the results JSON for the matching solution id
(by decomposition / shape / verdict / foldArrows), then pass that id to `shoot.js`.

## Automation hook

`app.js` exposes `window.App` with `loadResultsData(payload)`, `stepToId(id)`, and
`solutionCount()` — the same code path as the in-page "Load results JSON" picker.

## Report → .docx

```bash
pandoc report.md -o report.docx          # images embed automatically
```

Then drag `report.docx` into Google Docs (clean import) or open in Word. `matplotlib` is
available for summary plots (stats, k-formula curves) if needed alongside the screenshots.
