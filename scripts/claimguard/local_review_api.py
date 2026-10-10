"""Run the real Review API handler locally against the demo fixture (no AWS). For dashboard development.

    services/claimguard/.venv/Scripts/python.exe scripts/claimguard/local_review_api.py --port 8788

Auth: X-Dev-Party / X-Dev-Role headers (e.g. AUD-01 / AUDITOR, REC-01 / RECYCLER). Never deploy this.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "services" / "claimguard"), str(ROOT / "services" / "review_api")]
os.environ["AUTH_MODE"] = "dev"

from review.handler import build_service, handler  # noqa: E402

SVC = build_service()
if "--no-precheck" not in sys.argv:
    for c in SVC.repo.list_claims():  # run every demo claim once so the dashboard starts populated
        SVC.check_claim(c.claim_id)


class H(BaseHTTPRequestHandler):
    def _go(self):
        u = urlsplit(self.path)
        n = int(self.headers.get("content-length") or 0)
        ev = {"requestContext": {"http": {"method": self.command}}, "rawPath": u.path,
              "headers": dict(self.headers), "body": self.rfile.read(n).decode() if n else None}
        r = handler(ev, None, service=SVC)
        self.send_response(r["statusCode"])
        for k, v in r["headers"].items():
            self.send_header(k, v)
        self.send_header("access-control-allow-headers", "authorization,content-type,x-dev-party,x-dev-role")
        self.send_header("access-control-allow-methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(r["body"].encode())

    do_GET = do_POST = do_OPTIONS = _go

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8788)
    ap.add_argument("--no-precheck", action="store_true")
    a = ap.parse_args()
    print(f"review API on http://127.0.0.1:{a.port}")
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
