"""Run the real capture API Lambda handler locally (no AWS): in-memory ledger, local P-256 signer,
local Cedar, offline extractor, CONTRACT §8 seed data. For PWA development and UI tests only.

    services/ledger/.venv/bin/python scripts/chaintrack/local_api.py --port 8787

Auth: send X-Dev-Party and X-Dev-Role headers (e.g. COL-118 / COLLECTOR); they become JWT claims.
Never deploy this; it trusts those headers.
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
sys.path[:0] = [str(ROOT / p) for p in ("services/ledger", "services/capture_api", "services/extract", "scripts/chaintrack")]
os.environ.setdefault("POWERTOOLS_TRACE_DISABLED", "1")
os.environ.setdefault("POWERTOOLS_IDEMPOTENCY_DISABLED", "1")
os.environ.setdefault("IDEMPOTENCY_TABLE", "local")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")

from capture.authz import LocalCedarAuthorizer  # noqa: E402
from capture.handlers import api  # noqa: E402
from capture.repo import MemoryRepo  # noqa: E402
from capture.service import CaptureService, Settings  # noqa: E402
from extract.bedrock_extract import extract_offline  # noqa: E402
from ledger.signing import LocalSigner  # noqa: E402
import seed_demo  # noqa: E402


class Ctx:
    function_name = "local"
    memory_limit_in_mb = 512
    invoked_function_arn = "arn:aws:lambda:ap-south-1:000000000000:function:local"
    aws_request_id = "local"

    def get_remaining_time_in_millis(self):
        return 30000


class Uploads:
    """Accepts PUTs to memory:// presigned URLs rewritten as /_upload/<key>."""
    def __init__(self):
        self.objects = {}


def build(web_url: str):
    repo, signer = MemoryRepo(), LocalSigner()
    seed_demo.seed(repo, signer, log=lambda *_: None)
    uploads = Uploads()
    svc = CaptureService(repo, signer, LocalCedarAuthorizer(), Settings(web_url=web_url, wa_number="910000000000"),
                         presigner=lambda key, ct, size, sha: f"/_upload/{key}")

    class Digests:
        def latest(self):
            from datetime import date
            from ledger.digest import build_digest
            evs = [e for b in list(repo.store.events) for e in repo.store.list_events(b)]
            d = build_digest(evs, date(2026, 10, 6), signer)
            d["note"] = "local dev digest for 2026-10-06"
            return d

        def for_date(self, d):
            return None

    svc.digest_reader = Digests()
    api.service = lambda: svc
    api.extractor = lambda: extract_offline
    api.transcriber = lambda: None
    return svc, uploads


def make_handler(svc, uploads, origin):
    class H(BaseHTTPRequestHandler):
        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers", "authorization, content-type, idempotency-key, x-dev-party, x-dev-role, x-amz-checksum-sha256")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_PUT(self):
            n = int(self.headers.get("content-length") or 0)
            body = self.rfile.read(n)
            uploads.objects[urlsplit(self.path).path] = body
            self.send_response(200)
            self._cors()
            self.end_headers()

        def _lambda(self, method):
            u = urlsplit(self.path)
            n = int(self.headers.get("content-length") or 0)
            body = self.rfile.read(n).decode() if n else None
            headers = {k.lower(): v for k, v in self.headers.items()}
            rc = {"http": {"method": method, "path": u.path, "sourceIp": "127.0.0.1", "userAgent": "local"},
                  "requestId": "local", "routeKey": "$default", "stage": "$default"}
            if headers.get("x-dev-party") and headers.get("x-dev-role"):
                rc["authorizer"] = {"jwt": {"claims": {"cognito:groups": f"[{headers['x-dev-role']}]",
                                                       "custom:party_id": headers["x-dev-party"]}, "scopes": None}}
            ev = {"version": "2.0", "routeKey": "$default", "rawPath": u.path, "rawQueryString": u.query or "",
                  "headers": headers, "requestContext": rc, "body": body, "isBase64Encoded": False}
            r = api.handler(ev, Ctx())
            self.send_response(r["statusCode"])
            self._cors()
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write((r.get("body") or "").encode())

        def do_GET(self):
            self._lambda("GET")

        def do_POST(self):
            self._lambda("POST")

        def log_message(self, fmt, *args):
            sys.stderr.write("local-api " + fmt % args + "\n")
    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--web", default="http://localhost:5173")
    a = ap.parse_args()
    svc, uploads = build(a.web)
    print(f"local capture API on http://localhost:{a.port} (seeded CONTRACT §8 data)")
    ThreadingHTTPServer(("0.0.0.0", a.port), make_handler(svc, uploads, a.web)).serve_forever()


if __name__ == "__main__":
    main()
