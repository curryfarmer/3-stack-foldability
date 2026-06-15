# deprecated/ — retired tooling (not maintained)

Archived during the ss2 debloat. These scripts and artifacts are **not part of the live engine,
frontend, or test suite** and are not guaranteed to run against the current code. Kept only for
reference / possible salvage; safe to delete wholesale.

- `py/` — square-grid analysis + rendering tooling: `analyze_*` (twist / loop-seams / 2+1-reduction
  / reflection / wrap), `sweep_minsize`, `vet_enumerate` (the live oracle is reimplemented in
  `tests/enginelib.closing_candidates`), `foldpattern`, `render_*`, `make_foldsheets`.
- `report/` — generated square fold-sheets, theta diagrams, and the Playwright screenshot toolchain
  (`shoot.js`, `package*.json`).

The live triangle-lattice renderers stay under `py/tri/`; live ground-truth fixtures stay under
`results/`.
