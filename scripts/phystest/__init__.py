"""phystest — the physical-testing suite for the fold engines.

Physical folding is the ONLY ground truth in this project: the reflection/twist/parity gates are
proven for canonical sheets but are heuristics on hand-drawn ones, so a gate verdict is a
*prediction* until a human prints the foldsheet and folds it. This package makes that loop
first-class and tracked:

    curate  ->  print + fold by hand  ->  log  ->  check

  * check   — the acceptance ORACLE. Re-derives a fresh engine verdict for every physically-folded
              record and confirms it still agrees with what was physically observed. Wraps the two
              existing regression proofs (scripts/validate_square.py, scripts/validate_triangle.py)
              via subprocess, so the square and triangle packages are never imported into one
              interpreter (they each put a bare `lattice` on sys.path — co-import races). Returns
              structured data; nonzero exit only on a real disagreement.
  * curate  — the to-test BATCH generator. Runs the engine on target grids, selects the candidates
              worth folding by hand (predicted-fold / predicted-jam / undecided, minus already
              tested), and writes a batch: the printable foldsheet PNGs + a manifest of blank
              physical-test records to fill in.
  * log     — records a physical FOLD/JAM outcome for a batch item back into the findings DB, in
              the exact schema scripts/validate_square.py already reads.
  * status  — summarizes the queue: pending vs tested, per-grid agreement rate.

Run as a directory tool (mirrors the repo's other CLIs):

    python scripts/phystest check
    python scripts/phystest curate --square --m 6 --n 6 --decomps 2+1 --out out/batch_6x6
    python scripts/phystest log --batch out/batch_6x6 --uid 12c638f3261d --folded yes --by john
    python scripts/phystest status

Design constraints honored:
  * NEVER imports an engine package (square/ or triangle/) — every engine call is a subprocess.
  * Skips gracefully when the gitignored ground-truth data (results/, report/tri/) is absent, so a
    fresh clone still passes the tracked pytest.
"""

RECORD_SCHEMA = "physical-test/1"
BATCH_SCHEMA = "phystest-batch/1"
CHECK_SCHEMA = "phystest-check/1"
