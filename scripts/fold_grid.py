"""scripts/fold_grid.py — the single entry point that folds ONE drawn sheet (a fold-grid/1 file)
across BOTH engines and writes one aggregate `out/<gridUid>/bundle.json`.

WHY SUBPROCESS-ONLY (imports NO engine). `square/` and `triangle/` each put a bare-named `lattice`
package on `sys.path` (their `_bootstrap.py`). Importing both into ONE interpreter races whichever
bootstrap ran second — a later `import lattice` silently resolves to the wrong package. So this
orchestrator, like `scripts/validate.py`, NEVER imports either engine; it only `Popen`s their
`generate.py` CLIs. It also copies the FILE-not-PIPE + `_killtree` reaping from `scripts/run_tests.py`:
a `--jobs` pool filling a PIPE while a killed child lingers is the Windows orphan trap.

Dispatch by tiling:
  * square      -> square/generate.py  --grid-file PATH --stacks N --out <workdir>   (one call per N)
  * equilateral | righttri | scalene | hex
                -> triangle/tri/generate.py --grid-file PATH --render --out <workdir> (one call, 1+1+1)

Exit-code policy (multi-stack aware — a per-N rejection must NOT kill the other N's solutions):
  * square exit 0 -> collect that N's records (0 records = searched, none foldable — a valid outcome)
  * square exit 1 -> `rejected: <reason>` (empty / not-4-connected / cell count not divisible by N):
                     record a per-config rejection and KEEP GOING (a len-8 sheet folds at 2 but 3
                     rejects, 8 % 3 != 0; one N must not abort the other)
  * square exit 2 -> usage / malformed grid-file: hard error, abort (no bundle)
  * triangle exit 0 -> collect ("no closing fold" is exit 0, a valid obstruction)
  * triangle exit != 0 -> bad region: hard error, abort
Never read exit 0 as "found something" — the record set is scanned off disk.

`proven` (a BOOLEAN, never string-sniffed downstream — S9's "unproven" badge reads it) marks whether
the verdict METHOD is validated, not that this shape was oracle-proven: square (any stack count) is
method-proven (RSPA reflection+twist are theorems over any grid-graph Hamiltonian circuit; the 3/n-stack
footprint engine is oracle-gated); triangle equilateral 1+1+1 is the validated solver; every other
triangle family is a model/closure prediction -> false.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPTS_DIR)
_SQUARE_GEN = os.path.join(_REPO_ROOT, "square", "generate.py")
_TRIANGLE_GEN = os.path.join(_REPO_ROOT, "triangle", "tri", "generate.py")

BUNDLE_SCHEMA = "fold-bundle/1"
GRID_SCHEMA = "fold-grid/1"
SQUARE_TILING = "square"
TRIANGLE_TILINGS = ("equilateral", "righttri", "scalene", "hex")
ALL_TILINGS = (SQUARE_TILING,) + TRIANGLE_TILINGS
_POLL_SECONDS = 0.5


# --------------------------------------------------------------------------- process reaping
def _killtree(pid):
    """Kill pid AND its whole descendant tree. A plain proc.kill() orphans multiprocessing
    grandchildren (a --jobs pool spawns N of them); on Windows taskkill /T is the only reliable reap.
    Byte-identical to scripts/run_tests.py:_killtree."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, text=True)
    else:
        subprocess.run(["pkill", "-9", "-P", str(pid)], capture_output=True, text=True)
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def _run_worker(argv, log_prefix, timeout):
    """Run one engine CLI to completion, orphan-free, tailing its output live. Returns
    (returncode, combined_output). stdout+stderr go to a FILE (never a PIPE) so no --jobs grandchild
    can hold a pipe open and wedge the reap. `timeout` is seconds or None (unbounded). On timeout OR
    KeyboardInterrupt the whole process tree is killtree-reaped before we return / re-raise."""
    import tempfile
    fd, out_path = tempfile.mkstemp(prefix="fold_grid_%s_" % log_prefix, suffix=".out")
    os.close(fd)
    t0 = time.time()
    timed_out = False
    try:
        with open(out_path, "w", encoding="utf-8") as fw:
            proc = subprocess.Popen([sys.executable, "-u", *argv],
                                    cwd=_REPO_ROOT, stdout=fw, stderr=subprocess.STDOUT)
            with open(out_path, "r", encoding="utf-8", errors="replace") as fr:
                try:
                    while True:
                        chunk = fr.read()
                        if chunk:
                            sys.stdout.write(chunk)
                            sys.stdout.flush()
                        if proc.poll() is not None:
                            tail = fr.read()
                            if tail:
                                sys.stdout.write(tail)
                                sys.stdout.flush()
                            break
                        if timeout is not None and time.time() - t0 > timeout:
                            timed_out = True
                            _killtree(proc.pid)
                            try:
                                proc.wait(timeout=30)
                            except subprocess.TimeoutExpired:
                                pass
                            break
                        time.sleep(_POLL_SECONDS)
                except KeyboardInterrupt:
                    _killtree(proc.pid)
                    try:
                        proc.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        pass
                    raise
        with open(out_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()          # a killed worker can truncate a multi-byte tail -> replace
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass
    rc = -1 if timed_out else proc.returncode
    return rc, content


# --------------------------------------------------------------------------- grid-file + identity
def _load_grid(path):
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    if not isinstance(spec, dict):
        raise ValueError("fold-grid: top level must be a JSON object")
    if spec.get("schema") != GRID_SCHEMA:
        raise ValueError("fold-grid: schema must be %r, got %r" % (GRID_SCHEMA, spec.get("schema")))
    tiling = spec.get("tiling")
    if tiling not in ALL_TILINGS:
        raise ValueError("fold-grid: tiling must be one of %s, got %r"
                         % (", ".join(ALL_TILINGS), tiling))
    cells = spec.get("cells")
    if not isinstance(cells, list) or not cells:
        raise ValueError("fold-grid: 'cells' must be a non-empty array")
    return spec, tiling, cells


def _canonical_json(obj):
    """Deterministic JSON: sorted keys, no whitespace. Same bytes -> same sha1 across runs/machines."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _grid_uid(tiling, cells, stacks):
    """12-hex sha1 of (schema, tiling, sorted cells, resolved stacks) — mirrors gen_testset.fold_uid's
    sha1[:12] convention. The same drawn sheet + same resolved stack set -> the same out/<gridUid>/."""
    sorted_cells = sorted([list(c) for c in cells])
    payload = _canonical_json([GRID_SCHEMA, tiling, sorted_cells, sorted(stacks)])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _sheet_cells(tiling, cells):
    """The drawn cells in the SAME frame the engine's renderer used, so an S10 mask lines up: the
    square engine origin-normalizes (gridfile.parse_grid shifts the bbox min corner to (0,0)); the
    triangle engine folds the native ids untouched. Returned sorted, for determinism."""
    if tiling == SQUARE_TILING:
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        mnx, mny = min(xs), min(ys)
        return sorted([x - mnx, y - mny] for (x, y) in cells)
    return sorted([list(c) for c in cells])


def _resolve_stacks(tiling, override, hint):
    """Which stack counts to search. Triangle is 1+1+1 / 3-stack ONLY (the worker guards it), so always
    [3]. Square: CLI --stacks override wins, else the file's `stacks` hint (a list), else [3] (covers
    "auto" / missing). 2 is a valid square stack count now (2-stack drawn-sheet ingest is baked in)."""
    if tiling in TRIANGLE_TILINGS:
        return [3]
    if override is not None:
        vals = override
    elif isinstance(hint, list) and hint:
        vals = hint
    else:                                       # "auto", a string, or missing
        vals = [3]
    out = sorted({int(v) for v in vals})
    if any(v < 2 for v in out):
        raise ValueError("square stacks must all be >= 2, got %s" % out)
    return out


# --------------------------------------------------------------------------- aggregation
def _record_stacks(rec):
    """The stack count a written record self-reports (square stamps `stacks`; triangle is always 3)."""
    if "stacks" in rec:
        return int(rec["stacks"])
    return 3


def _record_proven(rec):
    """proven = the verdict METHOD is validated. Square (any) -> True. Triangle: equilateral 1+1+1 ->
    True (the validated solver); every other triangle family -> False (model/closure prediction)."""
    lattice = rec.get("lattice", "")
    if lattice in ("square", "square2stack") or "circuit" in rec or "canonicalHash" in rec:
        return True                             # square 2-stack (circuit) or 3/n-stack (canonicalHash)
    tiling = rec.get("tiling")
    decomp = rec.get("decomp")
    return tiling == "equilateral" and decomp == "1plus1plus1"


def _record_foldable(rec):
    """Tri-state foldability read off a record: True / False / None (undecided). 2-stack stores
    verdict.foldable; 3/n-stack stores verdict.twist (None = twist undecided); triangle stores a
    top-level `foldable` bool."""
    v = rec.get("verdict")
    if isinstance(v, dict):
        if "foldable" in v:
            return v["foldable"]
        if "twist" in v:
            return v["twist"]
    if "foldable" in rec:
        return rec["foldable"]
    return None


def _collect_records(workdir):
    """Every out/<uid>/<uid>.json under workdir, as (uid, rec, files) — files lists the bundle's
    on-disk artifacts (json + any PNGs) relative to <uid>/."""
    found = []
    for uid in sorted(os.listdir(workdir)):
        sub = os.path.join(workdir, uid)
        rec_path = os.path.join(sub, "%s.json" % uid)
        if not os.path.isfile(rec_path):
            continue                            # skip bundle.json itself + stray dirs
        with open(rec_path, encoding="utf-8") as f:
            rec = json.load(f)
        files = {}
        for fn in sorted(os.listdir(sub)):
            full = os.path.join(sub, fn)
            if not os.path.isfile(full):
                continue
            if fn.endswith(".json"):
                files["json"] = fn
            else:
                stem = fn.split("_", 1)[0]      # foldsheet_/overlay_/twist_/reflect_ -> key
                files[stem] = fn
        found.append((uid, rec, files))
    return found


# --------------------------------------------------------------------------- orchestration
def _dispatch_square(grid_file, workdir, resolved, jobs, timeout):
    """One square subprocess per resolved N. Returns the `configs` list (per-N status/reason). Raises
    RuntimeError on a square exit 2 (usage / malformed grid-file) -> the caller aborts."""
    configs = []
    for n in resolved:
        argv = [_SQUARE_GEN, "--grid-file", grid_file, "--stacks", str(n), "--out", workdir]
        if jobs is not None:
            argv += ["--jobs", str(jobs)]
        print("\n=== square --stacks %d ===" % n, flush=True)
        rc, out = _run_worker(argv, "sq%d" % n, timeout)
        if rc == 0:
            configs.append({"stacks": n, "status": "ok", "reason": None})
        elif rc == 1:
            configs.append({"stacks": n, "status": "rejected", "reason": _reject_reason(out)})
        else:
            raise RuntimeError("square --stacks %d failed hard (exit %s); aborting bundle" % (n, rc))
    return configs


def _dispatch_triangle(grid_file, tiling, workdir, timeout):
    """One triangle subprocess (1+1+1, --render). Returns a one-entry `configs` list. Raises
    RuntimeError on any non-zero exit (a bad region traceback) -> the caller aborts."""
    argv = [_TRIANGLE_GEN, "--grid-file", grid_file, "--render", "--out", workdir]
    print("\n=== triangle %s (1+1+1) ===" % tiling, flush=True)
    rc, _out = _run_worker(argv, "tri", timeout)
    if rc != 0:
        raise RuntimeError("triangle %s failed hard (exit %s); aborting bundle" % (tiling, rc))
    return [{"stacks": 3, "status": "ok", "reason": None}]


def _reject_reason(out):
    """Pull the `rejected: <reason>` line the engine prints to stderr (merged into `out`)."""
    for line in out.splitlines():
        s = line.strip()
        if s.lower().startswith("rejected:"):
            return s.split(":", 1)[1].strip()
    return "rejected (no reason line captured)"


def _build_bundle(grid_uid, tiling, sheet_cells, resolved, configs, workdir):
    """Scan the workdir's records and assemble bundle.json. `proven` per record + the roll-up
    `gateValidityUnproven` (True iff ANY record is unproven). configs' nRecords is filled from the
    records each N actually produced (grouped by the record's self-reported stack count)."""
    records = []
    for uid, rec, files in _collect_records(workdir):
        records.append({
            "uid": uid,
            "stacks": _record_stacks(rec),
            "proven": _record_proven(rec),
            "foldable": _record_foldable(rec),
            "verdict": rec.get("verdict"),
            "dir": uid,
            "files": files,
        })
    counts = {}
    for r in records:
        counts[r["stacks"]] = counts.get(r["stacks"], 0) + 1
    for cfg in configs:
        cfg["nRecords"] = counts.get(cfg["stacks"], 0)
    return {
        "schema": BUNDLE_SCHEMA,
        "gridUid": grid_uid,
        "tiling": tiling,
        "sheetCells": sheet_cells,
        "stacks": resolved,
        "configs": configs,
        "gateValidityUnproven": any(not r["proven"] for r in records),
        "records": records,
    }


def _parse_stacks_arg(s):
    if s is None:
        return None
    try:
        return [int(x) for x in s.split(",") if x.strip() != ""]
    except ValueError:
        raise argparse.ArgumentTypeError("--stacks must be a comma list of ints, e.g. 2,3")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="fold one drawn sheet (a fold-grid/1 file) across both engines into "
                    "out/<gridUid>/bundle.json")
    ap.add_argument("grid_file", help="path to a fold-grid/1 JSON file")
    ap.add_argument("--stacks", type=_parse_stacks_arg, default=None,
                    help="comma list of square stack counts to search (e.g. 2,3); overrides the file's "
                         "`stacks` hint. Ignored for triangle tilings (1+1+1 / 3-stack only).")
    ap.add_argument("--out", default="out", help="output root (bundle lands in <out>/<gridUid>/)")
    ap.add_argument("--jobs", type=int, default=None,
                    help="parallel worker processes forwarded to the square engine (3/n-stack search)")
    ap.add_argument("--timeout", type=float, default=None,
                    help="per-engine-subprocess wall-clock budget in seconds (default: unbounded). On "
                         "timeout the whole process tree is killtree-reaped.")
    args = ap.parse_args(argv)

    try:
        spec, tiling, cells = _load_grid(args.grid_file)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    try:
        resolved = _resolve_stacks(tiling, args.stacks, spec.get("stacks"))
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    grid_uid = _grid_uid(tiling, cells, resolved)
    workdir = os.path.abspath(os.path.join(args.out, grid_uid))
    os.makedirs(workdir, exist_ok=True)
    sheet_cells = _sheet_cells(tiling, cells)
    print("fold-grid: tiling=%s |cells|=%d gridUid=%s stacks=%s -> %s"
          % (tiling, len(cells), grid_uid, resolved, workdir), flush=True)

    grid_abs = os.path.abspath(args.grid_file)
    try:
        if tiling == SQUARE_TILING:
            configs = _dispatch_square(grid_abs, workdir, resolved, args.jobs, args.timeout)
        else:
            configs = _dispatch_triangle(grid_abs, tiling, workdir, args.timeout)
    except RuntimeError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1

    bundle = _build_bundle(grid_uid, tiling, sheet_cells, resolved, configs, workdir)
    bundle_path = os.path.join(workdir, "bundle.json")
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=1)

    n_unproven = sum(1 for r in bundle["records"] if not r["proven"])
    print("\nbundle: %d record(s) (%d unproven) -> %s"
          % (len(bundle["records"]), n_unproven, bundle_path), flush=True)
    for cfg in configs:
        tag = cfg["status"] if cfg["status"] == "ok" else "REJECTED (%s)" % cfg["reason"]
        print("  stacks=%d  %s  %d record(s)" % (cfg["stacks"], tag, cfg["nRecords"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
