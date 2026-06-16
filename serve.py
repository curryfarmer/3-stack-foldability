"""serve.py — static frontend server + one POST route for in-page FoldFinding capture.

`python serve.py` replaces `python -m http.server 8000` for capture sessions:
  * GET/HEAD serve the repo's static frontend BYTE-IDENTICALLY (index.html / app.js / results load
    exactly as today), and
  * POST /api/findings hands the JSON body to the pure findings.submit_record() pipeline
    (validate -> upsert DB -> append LAB_LOG) and returns the persisted record (200) or the
    validation error (400).
Same origin (:8000) => no CORS, no Flask, no extra dependency. The CLI `python py/findings.py submit
<file>` and the UI "Download JSON" button remain the offline fallback; all three wrap one pure
submit path. Engine prediction enumerates closing candidates on submit, so large grids (6x7) can take
a while — that is the same cost the matcher pays.
"""
from __future__ import annotations

import functools
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
# findings lives in py/; enginelib (lazy-imported by predict) in tests/. Put both on the path.
sys.path.insert(0, os.path.join(ROOT, "py"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from http.server import HTTPServer, SimpleHTTPRequestHandler  # noqa: E402

from jsonschema import ValidationError  # noqa: E402

import findings as F  # noqa: E402

ENDPOINT = "/api/findings"


class FindingHandler(SimpleHTTPRequestHandler):
    """Static GET/HEAD (unchanged from stdlib); POST /api/findings -> findings.submit_record()."""

    def do_POST(self) -> None:  # noqa: N802 (stdlib naming)
        if self.path.rstrip("/") != ENDPOINT:
            self.send_error(404, "no such endpoint (only POST /api/findings)")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"ok": False, "error": f"bad JSON body: {exc}"})
            return
        try:
            rec = F.submit_record(payload)              # validate FIRST -> upsert -> LAB_LOG
        except ValidationError as exc:
            self._json(400, {"ok": False, "error": f"schema: {exc.message}"})
            return
        except Exception as exc:                        # noqa: BLE001 (report any engine/IO failure)
            self._json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            return
        self._json(200, {"ok": True, "record": rec})

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:     # quieter than the stdlib default
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main(argv: list[str] | None = None) -> int:
    """Serve the frontend + findings POST route. I/O: (argv) -> exit code. `serve.py [port]` (8000)."""
    args = list(sys.argv[1:] if argv is None else argv)
    port = int(args[0]) if args else 8000
    handler = functools.partial(FindingHandler, directory=ROOT)
    httpd = HTTPServer(("127.0.0.1", port), handler)
    print(f"serving {ROOT} at http://127.0.0.1:{port}/  "
          f"(POST {ENDPOINT} -> {F.DB_PATH})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
