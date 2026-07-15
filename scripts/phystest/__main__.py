"""__main__.py — phystest subcommand dispatcher.

Run as a directory tool (mirrors the repo's other scripts; no install required):

    python scripts/phystest check   [--json]
    python scripts/phystest curate  --m 6 --n 6 --decomps 2+1 [--policy fold] [--out DIR]
    python scripts/phystest log      --batch DIR --uid UID --folded yes|no --by NAME
    python scripts/phystest status  [--batch DIR]

Never imports an engine package in-process — `check` subprocess-dispatches the per-engine checkers,
`curate` subprocess-dispatches the generator.
"""
import os
import sys

# Make sibling modules importable by bare name whether launched as `python scripts/phystest` or
# `python -m ...` (mirrors the engine _bootstrap sys.path convention).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_USAGE = ("usage: python scripts/phystest <check|curate|log|status> [args]\n"
          "  check   re-derive engine verdicts for every physically-folded record and confirm\n"
          "          they still agree with what was observed (the acceptance oracle)\n"
          "  curate  generate a to-test batch: foldsheets + a manifest of blank records\n"
          "  log     record a physical FOLD/JAM outcome for a batch item\n"
          "  status  summarize what's tested / pending and per-grid engine agreement\n")


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(_USAGE)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "check":
        import check
        return check.main(rest)
    if cmd == "curate":
        import curate
        return curate.main(rest)
    if cmd == "log":
        import logresult
        return logresult.main(rest)
    if cmd == "status":
        import status
        return status.main(rest)
    sys.stderr.write("phystest: unknown command %r\n%s" % (cmd, _USAGE))
    return 2


if __name__ == "__main__":
    sys.exit(main())
