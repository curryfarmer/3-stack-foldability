# fold3stack

Two independent, code-only Python engines that search for and verify **3-stack folds**
(compact-stack tessellated-plate folding, after Yang–You–Rosen, see [`reference/`](reference/)):

- **`square/`** — folds on a square grid: footprint + 2-chain/1-chain (or 1+1+1) decomposition,
  reflection-closure + twist gates. Also supports the paper's original 2-stack (Hamiltonian-circuit)
  mode.
- **`triangle/`** — folds on non-square tilings: equilateral, 45-45-90 right-isosceles, 30-60-90
  scalene, and regular hexagon. Same closure/twist idea, ported to each tiling's own geometry.

The two packages are **fully independent** — no cross-imports. Each has its own `lattice`
subpackage, its own `_bootstrap.py`, and its own pair of CLIs. They happen to both use a bare
module name `lattice` internally, so **never import both packages in the same Python process** —
run them in separate processes (every script in this repo already does this).

Two ways to drive the engines: the raw per-package CLIs below (`sq-generate` / `tri-generate`), or
the higher-level [`gui/`](gui/) front-ends — an interactive **draw-and-fold window** and a matching
**headless CLI** — that let you fold a hand-drawn sheet with example-vs-full search and result
filtering ([jump to that section](#draw-and-fold--the-gui-front-ends)).

## Install

Never used Python from a terminal before? Follow this start to finish and you will have a working
copy in about five minutes. Every step is a line you paste into a terminal.

### 1. Install Python

You need **Python 3.10 or newer**. Check whether you already have it:

```bash
python --version
```

If that prints `Python 3.10` or higher, skip ahead. If it shows an error, or a version below 3.10,
install Python from [python.org/downloads](https://www.python.org/downloads/). **On Windows, tick
"Add python.exe to PATH" on the first screen of the installer** — without it your terminal will not
find the `python` command. Then close your terminal, open a new one, and check the version again.

> On some computers the command is `python3` rather than `python`. If `python --version` does not
> work, try `python3 --version`, and use `python3` in place of `python` everywhere below.

### 2. Get the code

**Option A — with git.** Recommended, because later on `git pull` updates your copy instead of you
downloading it all again. First check whether you already have git:

```bash
git --version
```

If that prints a version number, you have it. If it says the command was not found, install git from
[git-scm.com/downloads](https://git-scm.com/downloads) — accept the installer's defaults — then close
your terminal and open a new one. Now download the code:

```bash
git clone https://github.com/curryfarmer/3-stack-foldability.git
cd 3-stack-foldability
```

**Option B — without git.** Open
[the repository](https://github.com/curryfarmer/3-stack-foldability), click the green **Code**
button, choose **Download ZIP**, and unpack it. The unpacked folder is called
`3-stack-foldability-main`, so move into it with:

```bash
cd 3-stack-foldability-main
```

Everything below assumes you are **inside that folder**. If a command says it cannot find
`pyproject.toml`, you are in the wrong folder.

### 3. Create and activate a virtual environment

A virtual environment keeps this project's packages out of your system Python. Create it once:

```bash
python -m venv .venv
```

Then **activate** it. This is the step people miss, and you have to repeat it every time you open a
new terminal. You will know it worked because your prompt gains a `(.venv)` prefix.

| your system | command |
|---|---|
| Windows — PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows — Command Prompt (cmd) | `.venv\Scripts\activate.bat` |
| Windows — Git Bash | `source .venv/Scripts/activate` |
| macOS / Linux | `source .venv/bin/activate` |

> **PowerShell refuses with "running scripts is disabled on this system"?** That is Windows blocking
> script execution, not a problem with this project. Allow it for your user account once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then run the activate line again.

### 4. Install the project

With `(.venv)` showing in your prompt:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

Takes a minute or two. Use `python -m pip`, not bare `pip` — bare `pip` may belong to a different
Python than the one you activated.

<details>
<summary>Install failed? — the message usually names the cause</summary>

<br>

| what it says | what to do |
|---|---|
| `ERROR: ... requires a different Python: 3.9.x not in '>=3.10'` | your Python is too old — redo step 1, and check `python --version` in the *activated* environment |
| `has a 'pyproject.toml' and its build backend is missing the 'build_editable' hook` | pip is too old for editable installs — run the `--upgrade pip` line above first, then retry |
| `zsh: no matches found: .[test]` | the quotes were dropped — `".[test]"` must be quoted, brackets are shell wildcards |
| `'pip' is not recognized` / `command not found: pip` | you used bare `pip`; use `python -m pip` as above |
| `error: externally-managed-environment` | you are installing into the system Python, not the venv — the venv is not activated, redo step 3 |
| Windows: `Program 'pip.exe' failed to run: An Application Control policy has blocked this file` | a managed-Windows policy blocks the `pip.exe` launcher, not pip itself — `python -m pip` runs the same code without launching that file, so use it and carry on |
| `SSLError` / `CERTIFICATE_VERIFY_FAILED` while downloading | a corporate proxy is inspecting TLS. Ask IT for the proxy's root certificate and point pip at it: `python -m pip install --cert C:\path\to\corp-root.crt -e ".[test]"` |
| `does not appear to be a Python project: neither 'setup.py' nor 'pyproject.toml' found` | wrong folder. `ls` (or `dir`) should list `pyproject.toml`; if you downloaded the ZIP the folder is `3-stack-foldability-main` and it may contain *another* folder of the same name — `cd` until you see `pyproject.toml` |

</details>

### 5. Check it worked

```bash
sq-generate --m 6 --n 4
```

Takes a few seconds and should report **6 solutions**, leaving six folders in `out/`. If you get
`command not found`, the environment is not activated — go back to step 3.

You are set up. The rest of this page is what the tools can do.

---

The install puts four console scripts on your PATH:

| command        | package  | search scope                                    | does                                                        |
|-----------------|----------|-------------------------------------------------|--------------------------------------------------------------|
| `sq-generate`   | square   | full — all footprints × decomps on the `m×n` grid | search for folds on an `m×n` grid, write `out/<uid>/` bundles |
| `sq-render`     | square   | none — redraws a saved record                    | re-render an existing `out/<uid>/<uid>.json` record           |
| `tri-generate`  | triangle | first hit only — one (tiling, decomp, K) per invocation | search one tiling/decomposition/K for a closing fold          |
| `tri-render`    | triangle | none — redraws a saved record                    | re-render an existing triangle record                          |

**Find one vs. find all.** `sq-generate` enumerates everything by default; `--first` short-circuits
it at the first foldable example. `tri-generate` is the other way round — in `--tiling/--decomp/--K`
mode it is **always** find-first and cannot be made to enumerate (its `--first` flag applies only to
`--grid-file` mode, where it stops the exact-region enumeration early). The exhaustive triangle
search is a separate tool:

```bash
python -m triangle.tri.census --tiling righttri --decomp 2plus1 --kmin 3 --kmax 8
python -m triangle.tri.census --all --jobs 12        # every (tiling, decomp, K) cell
```

It drives the same generators `tri-generate` does, but drains them instead of stopping at the first
hit, and writes per-cell `.jsonl.gz` (every closing candidate) + `.summary.json` (counts, gate
funnel, twist spectrum, provenance) under `results/census/`. A cell that hits its wall-clock, memory
or record cap is recorded `truncated: true` rather than passed off as a smaller exhaustive count.

<details>
<summary><b>Search width, and why a "none found" may not mean anything</b> — only matters if you are
counting folds or reporting a zero</summary>

<br>

Neither tool enumerates *every* start configuration by default:

| flag | applies to | meaning |
|------|-----------|---------|
| `--hubs N` | 2+1 | sweep the `N` most central START trapezoids (default 20) |
| `--hub V` | 1+1+1 | ambient lattice variant — righttri `LL`/`HL`, scalene `omitVM`/`omitMG`/`omitVG` |

These are unrelated knobs with confusingly similar names. Both bound the search, so **"no closing
example found" rules out only what was searched** — it is not a proof of obstruction. Narrow sweeps
produce outright false zeros (righttri 2+1 reports none at K=6 and K=8 below 4 hubs, where folds
exist); see `find_example.DEFAULT_HUBS_21` for the measured saturation table. For a proven negative
use `triangle.tri.prove_obstruction`.

Because the sweep width is a free parameter, a raw fold **count** is partly an artifact of it — the
census stores placements, and congruent folds at different positions are counted separately. Collapse
them before reporting or plotting:

```bash
python -m triangle.tri.census_distinct results/census --jobs 8   # adds distinct/distinct_tw0
```

</details>

## Output format

Both engines write the same on-disk contract: one self-contained folder per fold, named after a
12-hex content hash (`uid`, `sha1(lattice \| MxN \| canonical-geometry)`):

```
out/<uid>/
  <uid>.json              full record: chains, footprint, verdict, geometry
  schematic_<uid>.png      folding schematic: footprint + base cells + foldpath
  twist_<uid>.png          twist-enumeration diagram (jump-strand for 2+1, pairwise loops for
                           1+1+1, turn-angle analysis for 2-stack)
  <uid>_analysis.json     triangle only: per-loop twist enumeration + seam/reflection verdict
                           (subsumes the retired reflect_ / overlay_ images)
```

Both tracks now emit the same standardised **two-image** bundle (schematic + twist); the triangle
track adds a small `<uid>_analysis.json` in place of its old reflection/overlay PNGs.

`*-render` re-derives the same image bundle from a saved `.json` with zero search — regenerating
a record and re-rendering it are the same code path, so the two are always byte-consistent.

## Examples

```bash
sq-generate --m 6 --n 6                            # 3-stack, both decomps, corner footprints
sq-generate --m 6 --n 5 --decomps 2+1 --allow-non-corner
sq-generate --stacks 2 --m 6 --n 5                 # RSPA 2-stack (Hamiltonian circuits)
sq-generate --stacks 4 --m 4 --n 8                 # n-stack: all-singleton 1+1+1+1
sq-generate --list                                  # summarize out/'s bundles
sq-render out/<uid>/<uid>.json --out somewhere/

tri-generate --tiling righttri --decomp 1plus1plus1 --K 16
tri-generate --tiling righttri --decomp 1plus1plus1 --K 16 --hub LL   # the other ambient variant
tri-generate --tiling scalene --decomp 2plus1 --K 4
tri-generate --tiling righttri --decomp 2plus1 --K 8 --hubs 40        # widen a "none found"
tri-render out/<uid>/<uid>.json

python -m triangle.tri.census --tiling righttri --decomp 2plus1 --kmin 3 --kmax 8   # count, don't stop
python -m triangle.tri.census_distinct results/census --jobs 8                      # placements -> shapes
```

## Draw-and-fold — the `gui/` front-ends

Beyond the raw engine CLIs there is a small **tkinter app** that lets you *draw* a sheet on any tiling
and fold it, plus a **headless twin** that does the same from a script. Both drive the engines only
through the `scripts/fold_grid.py` orchestrator (subprocess-only — `gui/` imports no engine, keeping
the never-co-import invariant), so they fold and filter identically; one renders to a window, the
other to stdout.

`gui/` is **not** an installed console script — run it from the repo root:

```bash
python -m gui.app                 # the interactive window
python -m gui.app --out mydir     # bundles go to mydir/ (default: ./out)
python -m gui.app --help          # works with no display (argparse exits before Tk)
```

The GUI needs **Tk** — bundled with the python.org and Windows builds; on some Linux distros install
`python3-tk`.

### Using the window

1. **Pick a tiling** (`square`, `equilateral`, `righttri`, `scalene`, `hex`) and an `m×n` size, then
   **New grid** to lay down that ambient block to draw on. *New grid only draws an empty grid — it
   never loads a past result.*
2. **Draw the sheet.** Click a tile to toggle it; **drag to paint** several at once — a drag that
   starts on an empty tile *adds*, one that starts on a filled tile (or any right-drag) *erases*. The
   sheet must be **connected** before **Fold** lights up.
3. **Shape the search** (second row — narrower = faster): which **stacks** to try (2 / 3 — how many
   plate layers the sheet collapses into; 2-stack is the paper's Hamiltonian-circuit case, 3-stack
   adds the footprint decomposition + closure/twist gates), which **decomp** (2+1 / 1+1+1 — leave
   both checked to search both, check exactly one to restrict), and **find: all | example**.
4. **Fold.** Results fill the table on the right; **Cancel** kills a run in flight.
5. **Filter + view.** The filter bar narrows the rows live; click a row to preview its fold image
   (choose which image with the kind buttons, or read a "no image for this record" note).

### Where results are stored

A successful fold writes a bundle to `<out>/<gridUid>/bundle.json`, plus a per-record
`<out>/<uid>/<uid>.json` with its `schematic_<uid>.png` / `twist_<uid>.png` images (triangle also
adds `<uid>_analysis.json`). In the window a **Save results** checkbox controls persistence: when it
is OFF (the default) the fold is written to a temporary directory and discarded once you have viewed
it; when ON, results are written to the folder shown next to it (default `./out`, changeable via
**Browse…**). The headless `gui.cli --out` and the launch-time `gui.app --out DIR` set the location
directly.

### Single example vs. every fold

**find: all** enumerates *every* footprint × decomposition — the complete answer (all folds, exact
counts), but slow on big grids (the square engine can weigh 100k+ candidates). **find: example
(fast)** stops at the **first** foldable it finds and returns just that one:

- square 3-stack — the first twist-decided FOLD,
- square 2-stack — the first foldable Hamiltonian circuit (the circuit *enumeration* still runs in
  full — the RSPA engine's fixed cost — so `example` saves less here than for 3-stack / triangle),
- triangle — the first closing 1+1+1 fold.

Use **example** to answer *"does any fold exist?"* cheaply; use **all** when you need to enumerate or
count them. Restricting stacks/decomps speeds up *both* modes. Under the hood this is the engines'
`--first` flag, threaded GUI → `fold_grid.py` → each engine.

### Filtering

Filters act on the **computed** rows: the foldability vector can't be known without folding, so
filtering is always *post-search* — it narrows what is shown, it does not change what is computed (the
search-shaping row above does that). Filter by:

- **stacks** — 2 or 3;
- **decomp** — 2+1 or 1+1+1 (either engine's spelling is accepted — `2plus1` → `2+1`);
- **foldable** — keep only folds;
- **foldability vector** — per-gate pass/fail: **exit** footprint, **parity**, **reflection**,
  **twist**.

Triangle records carry a single verdict *string* (no structured per-gate vector), so any vector
filter drops them.

<details>
<summary><b>Headless folding — <code>python -m gui.cli</code></b> — the same folding from a script or
CI, and the <code>fold-grid/1</code> region format</summary>

<br>

The same core with no window — for scripts and CI. It reads a drawn region and prints the filtered
verdict table:

```bash
python -m gui.cli --grid-file region.json                          # fold + full table
python -m gui.cli --grid-file region.json --first --only-foldable  # "any fold?" fast
python -m gui.cli --grid-file region.json --stacks 2,3 --decomp 2+1 --require reflection,twist
python -m gui.cli --grid-file region.json --json                   # machine-readable rows
```

The **region** is a `fold-grid/1` file — an arbitrary connected polyomino / tiling region, not just a
rectangle. Write one by hand:

```json
{
  "schema": "fold-grid/1",
  "tiling": "square",              // square | equilateral | righttri | scalene | hex
  "cells": [[0, 0], [1, 0], [0, 1]] // native tile ids: square => [x, y] integer pairs
}
```

…or just fold once in the GUI: it leaves the drawn region at `out/_grid.json`, itself a valid
`fold-grid/1`. (The full per-tiling id spec is in `docs/schema/fold-grid-1.md`, part of the
maintainer's local-only `docs/` tree — not present on a fresh clone.)

| flag                        | kind   | does                                                        |
|-----------------------------|--------|-------------------------------------------------------------|
| `--grid-file PATH`          | in     | the `fold-grid/1` region to fold (**required**)             |
| `--out DIR`                 | in     | bundle output root (default `./out`)                        |
| `--stacks 2,3`              | search | which square stack counts to search                          |
| `--decomps 2+1`             | search | restrict the square decompositions searched                  |
| `--first`                   | search | stop at the first foldable example (fast)                    |
| `--timeout SEC`             | search | per-engine wall-clock budget                                 |
| `--decomp 2+1,1+1+1`        | filter | show only these decompositions                               |
| `--require reflection,twist`| filter | show only rows PASSING these gates (`exit,parity,reflection,twist`) |
| `--only-foldable`           | filter | show only foldable rows                                      |
| `--json`                    | out    | emit the filtered rows as JSON instead of a table            |

Note the singular/plural split: `--decomps` (plural) *shapes the search*; `--decomp` (singular)
*filters the output*. Exit codes: **0** ok, **1** no bundle produced (a schema-valid region the
engine hard-failed on — a crash or internal error), **2** bad arguments or an unreadable /
wrong-schema grid file (a schema-bad grid is caught here, before any engine runs).

</details>

<details>
<summary><b>Validating against physical ground truth</b> — the acceptance oracle; needs the
maintainer's local research data, so it no-ops on a fresh clone</summary>

<br>

The engines make falsifiable claims about paper: every fold on record was physically folded by hand,
and the engine's verdict must still match that outcome. Both tools below **re-derive** a fresh
verdict by re-running the search — never by re-reading a stored boolean — and need the gitignored
local research data (`results/`), skipping gracefully per engine when it is absent (a fresh clone):

```bash
python scripts/validate.py       # both engines' regression proofs
python scripts/phystest check    # the acceptance oracle (see the caveat below)
```

Neither imports both engines in one process; both subprocess-dispatch the per-engine checkers.

**`phystest check` is expensive and its result is not a simple pass/fail.** It re-enumerates every
recorded grid from scratch, which is hours on the big ones (6x8 alone measured 2.6h), so results are
cached per `(engine-source fingerprint, grid)` under `results/.oracle_cache/` — edit anything under
`square/{engine,lattice,twist}` and every square entry is invalidated by design. It distinguishes
`FAIL` (a record genuinely disagrees — a real regression) from `ERROR` (the harness timed out or
broke, so **nothing was proven either way**); conflating those two is what made an earlier version of
this oracle untrustworthy. Note its 4h default timeout is smaller than a fully-cold square run, so
from a cold cache it takes **two invocations** — the per-grid cache survives a kill, so just re-run.

</details>

<details>
<summary><b>Tests</b></summary>

<br>

```bash
python scripts/run_tests.py     # all three suites (smoketest/, square/tests/, triangle/tests/)
```

About a minute. Each suite runs in its own interpreter — `square/` and `triangle/` both put a
bare-named `lattice` on `sys.path`, so they can never share a process. Expensive sweeps are marked
`slow` and deselected by default; run them with `pytest -m slow`.

</details>

## Repository layout

```
triangle/        installable package: the non-square-tiling engine + tri-render/tri-generate
square/          installable package: the square-grid engine + sq-render/sq-generate
  tests/         the square suite (golden baselines + fixtures live here, tracked)
gui/             the draw-and-fold front-ends (run from repo root, NOT installed): `python -m gui.app`
                 (window) + `python -m gui.cli` (headless); subprocess-only, imports no engine
scripts/         run_tests.py (the gate) + fold_grid.py (the GUI's orchestrator) + validate*.py +
                 phystest/ (the acceptance oracle)
smoketest/       tracked pytest suite (packaging/import/CLI smoke only — incl. gui/ contract)
reference/       external source material (the paper + the authors' own reference implementation)
```

`docs/`, `report/`, `results/` are local-only (gitignored) research history: lab logs, generated
figures, and the physical-fold findings DB. They exist on the maintainer's machine but are not part
of the tracked tree — everything needed to run the suites is tracked.
