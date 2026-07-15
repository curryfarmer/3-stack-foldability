"""oracle_cache.py — fingerprint cache for the physical-testing acceptance oracle.

The oracle (scripts/phystest/check.py -> scripts/validate_square.py) re-derives a fresh engine
verdict for every physically-folded record. The expensive part is the per-grid engine search
(_search_grid), which dominates the run; the records themselves are cheap to re-check. This module
memoizes ONLY that search, keyed by a fingerprint of everything that can change its result.

WHY THIS IS SAFE (the cache lives inside the only proof the gates are correct):
  * The key is COARSE ON PURPOSE. It covers the whole engine package source, so ANY engine edit
    invalidates every entry — the cache can never mask a regression, only skip re-proving an
    engine that is byte-for-byte the one already proven.
  * Every failure mode degrades to a MISS (recompute), never to a stale hit: corrupt file, truncated
    -name collision, unreadable dir, schema bump.
  * store() is called only AFTER compute() returns, so a failed search is never memoized.
  * A permanently-warm gate is the real risk, so hit/miss is reported per grid (a PASS must state
    whether it came from a search or from disk) and ORACLE_CACHE=0 forces a cold run.

WHAT IS IN THE KEY, AND WHY:
  * engine package source — every *.py, content-addressed (mtime ignored, line endings normalized).
  * opts MINUS `jobs` — `jobs` is behaviour-neutral: search.py replays dedup/id assignment serially
    in the parent, documented byte-identical to serial (search.py:430/517/563). Keying on it would
    make the cache per-core-count, so FOLD_JOBS=4 then FOLD_JOBS=8 would each pay a full cold run.
  * runtime — square/engine/runner.py shells the ENTIRE search to PyPy when FOLD_PY=pypy, which no
    digest of square/*.py would ever see.
  * checkers — validate_square.py owns _norm_hash and the opts literal but is not under square/.

WHAT IS DELIBERATELY *NOT* IN THE KEY:
  * The ground-truth record set. _search_grid(Runner, m, n) never sees a record — records are
    consumed afterwards, in run(), on every run regardless of hit or miss. Keying on them would
    invalidate a multi-hour search on every `phystest log`, i.e. leave the cache cold during exactly
    the curate -> fold -> log -> check loop it exists to serve, while buying no safety. A new grid
    changes opts["m"]/["n"] and misses anyway. The record digest is stored as METADATA, for audit.

LOAD-BEARING ASSUMPTION: the engine search is deterministic for fixed (source, opts, runtime).
Grounded in search.py's own parallel-path docs ("byte-identical to serial"). If that ever stops
being true, this cache would freeze one sample of a nondeterministic search — revisit then.

Stdlib only; imports no engine package and no sibling phystest module (keeping it a leaf keeps it
importable from both `python scripts/phystest` and a bare `import oracle_cache`).
"""
import hashlib
import json
import os
import platform
import sys
import tempfile
import time

SCHEMA = "oracle-cache/1"

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))
CACHE_DIR = os.path.join(_REPO_ROOT, "results", ".oracle_cache")

# opts keys that cannot change the search RESULT, only how fast it is computed.
_NON_SEMANTIC_OPTS = ("jobs",)

# Keep the newest N entries (~5 engine versions x 6 grids). Stale fingerprints are worthless the
# moment the engine changes, so eviction order is all that matters -- there is no TTL.
KEEP = int(os.environ.get("ORACLE_CACHE_KEEP") or 32)


def enabled():
    """False when ORACLE_CACHE=0 -- the kill-switch that forces a cold, from-scratch proof."""
    return os.environ.get("ORACLE_CACHE", "1") != "0"


# ------------------------------------------------------------------ fingerprint ----

def _iter_sources(pkg_dir):
    """(posix_relpath, abspath) for every *.py under pkg_dir, __pycache__ pruned, sorted."""
    for dirpath, dirnames, filenames in os.walk(pkg_dir):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                ap = os.path.join(dirpath, fn)
                yield os.path.relpath(ap, pkg_dir).replace(os.sep, "/"), ap


def _file_digest(path):
    """sha256 of file content with CRLF normalized to LF. Line endings are not semantic in Python,
    and this tree is checked out with autocrlf on Windows -- a re-clone must not burn a cold run."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()


def source_digest(pkg_dir):
    """sha256 over the sorted (posix relpath, content digest) manifest of pkg_dir's *.py.

    Content-addressed: touching a file without editing it is ignored; edits, adds, deletes and
    renames all change the digest (the relpath is hashed alongside the content).
    I/O: (path) -> 64-hex str."""
    manifest = sorted([rel, _file_digest(ap)] for rel, ap in _iter_sources(pkg_dir))
    blob = json.dumps(manifest, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def fingerprint(engine, pkg_dir, opts, extra_files=()):
    """Cache key over every input that can change the search result. See the module docstring for
    what is included and what is deliberately excluded. I/O: (str, path, dict, [path]) -> 64-hex."""
    key = {
        "v": 1,
        "engine": engine,
        "source": source_digest(pkg_dir),
        "checkers": {os.path.basename(p): _file_digest(p) for p in sorted(extra_files)},
        "opts": {k: v for k, v in opts.items() if k not in _NON_SEMANTIC_OPTS},  # m,n live here
        "runtime": {
            "impl": platform.python_implementation(),
            "py": "%d.%d" % sys.version_info[:2],       # patch bumps must not burn a cold run
            "FOLD_PY": os.environ.get("FOLD_PY", "").strip().lower(),
        },
    }
    blob = json.dumps(key, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


# ----------------------------------------------------------------------- store ----

def _path(fp):
    """Filename is the fingerprint's first 16 hex; the full 64 is stored inside and verified on
    load, so a truncation collision degrades to a miss, never to a wrong verdict."""
    return os.path.join(CACHE_DIR, "%s.json" % fp[:16])


def load(fp):
    """Cached payload, or None on miss / corrupt / schema bump / fingerprint mismatch. Never raises:
    a cache that cannot be read is a slow oracle, not a broken one."""
    try:
        with open(_path(fp), encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema") != SCHEMA or payload.get("fingerprint") != fp:
        return None                                     # collision or stale format -> recompute
    if not isinstance(payload.get("map"), dict):
        return None
    return payload


def store(fp, payload):
    """Atomically write payload. Never raises -- the oracle's correctness must not depend on the
    cache being writable (read-only results/, full disk, AV lock all degrade to 'slow')."""
    payload = dict(payload, schema=SCHEMA, fingerprint=fp)
    tmp = None
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=CACHE_DIR, suffix=".tmp")   # same dir => same volume
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(3):                        # an AV scanner / indexer can hold a lock
            try:
                os.replace(tmp, _path(fp))              # atomic on Windows (MoveFileEx)
                tmp = None
                break
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.1 * (attempt + 1))
        _gc()
    except OSError:
        pass
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _gc(keep=None):
    """Prune to the newest `keep` entries, by mtime.

    Scans ONLY results/.oracle_cache, non-recursively, reading names + mtime and never file
    content. results/ itself is ~1.6 GB / 304 files and must never be walked or checksummed."""
    keep = KEEP if keep is None else keep
    try:
        ents = [e for e in os.scandir(CACHE_DIR) if e.is_file() and e.name.endswith(".json")]
    except OSError:
        return
    ents.sort(key=lambda e: e.stat().st_mtime, reverse=True)
    for e in ents[keep:]:
        try:
            os.unlink(e.path)
        except OSError:
            pass            # another interpreter may hold it open; try again on the next write


def get_or_compute(fp, compute, meta=None):
    """Cached map for fp, else compute() and cache it. Returns (map, hit).

    compute() runs only on a miss, and its result is stored only on success -- an exception
    propagates uncached, so a rejected/failed search is never memoized as a verdict.
    I/O: (fp, callable, dict|None) -> (dict, bool)."""
    if enabled():
        payload = load(fp)
        if payload is not None:
            return payload["map"], True
    t0 = time.time()
    result = compute()
    store(fp, dict(meta or {}, map=result, nCandidates=len(result),
                   elapsedSec=round(time.time() - t0, 1),
                   createdAt=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    return result, False


def records_digest(records):
    """Audit-only digest of a grid's ground-truth record set. Stored as METADATA, never in the key
    (see the module docstring). I/O: (list[dict]) -> 64-hex str."""
    blob = json.dumps(sorted(json.dumps(r, sort_keys=True, separators=(",", ":"))
                             for r in records), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
