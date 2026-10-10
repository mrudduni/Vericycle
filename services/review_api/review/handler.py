"""Lambda entry for the Review API (API Gateway HTTP API, payload v2). CONTRACT.md section 7.

Env: AUTH_MODE=dev|jwt, CLAIMS_TABLE, LEDGER_TABLE (omit LEDGER_TABLE to read the demo fixture),
CLAIM_EVIDENCE_BUCKET, ALLOW_ORIGIN.
AUTH_MODE=dev trusts X-Dev-Party / X-Dev-Role headers: synthetic data only, never in prod.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

from claimguard.ledger_reader import FixtureLedgerReader
from claimguard.sources import SourcesRegistry

from .service import ApiError, ReviewService

ROLES = {"COLLECTOR", "AGGREGATOR", "RECYCLER", "AUDITOR", "PRODUCER"}


def can_read_claim(principal: dict, claim) -> bool:
    """One function so tomorrow it can call Verified Permissions IsAuthorized without touching handlers."""
    role = principal.get("role")
    if role in ("AUDITOR", "PRODUCER"):
        return True
    if role == "RECYCLER":
        return principal.get("party_id") == claim.recycler_party_id
    return False


def principal_from_event(event: dict, auth_mode: str) -> dict | None:
    if auth_mode == "dev":
        h = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        role, party = h.get("x-dev-role"), h.get("x-dev-party")
        return {"role": role, "party_id": party} if role in ROLES else None
    claims = (((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt") or {}).get("claims") or {}
    groups = re.findall(r"[A-Z]+", str(claims.get("cognito:groups", "")))
    role = next((g for g in groups if g in ROLES), None)
    return {"role": role, "party_id": claims.get("custom:party_id")} if role else None


def build_service() -> ReviewService:
    from .repo import DynamoRepo, MemoryRepo  # noqa: PLC0415

    sources = SourcesRegistry.load(os.environ.get("SOURCES_PATH") or None)
    claims_table = os.environ.get("CLAIMS_TABLE")
    repo = DynamoRepo(claims_table) if claims_table else MemoryRepo()
    ledger_table = os.environ.get("LEDGER_TABLE")
    if ledger_table:
        from claimguard.dynamo_ledger import DynamoLedgerReader  # noqa: PLC0415

        ledger = DynamoLedgerReader(ledger_table)
    else:
        ledger = FixtureLedgerReader(os.environ.get("LEDGER_FIXTURE") or None)
    return ReviewService(repo, ledger, sources)


_SERVICE: ReviewService | None = None
_LLM = None


def copilot_answer(svc: ReviewService, claim_id: str, question: str) -> dict:
    """Deterministic explanation always; a Bedrock/Strands answer on top when COPILOT_MODEL_ID is set (read-only tools)."""
    global _LLM
    from copilot.agent import answer, make_llm_runner  # noqa: PLC0415

    model_id = os.environ.get("COPILOT_MODEL_ID")
    if model_id and _LLM is None:
        try:
            _LLM = make_llm_runner(svc.get_claim, model_id, os.environ.get("COPILOT_REGION", "ap-south-1"),
                                   os.environ.get("GUARDRAIL_ID") or None, os.environ.get("GUARDRAIL_VERSION") or None)
        except ImportError:
            _LLM = False
    return answer(claim_id, question or "Why was this claim flagged?", svc.get_claim, _LLM or None)


def _resp(status: int, body: Any) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json", "cache-control": "no-store",
                    "access-control-allow-origin": os.environ.get("ALLOW_ORIGIN", "*")},
        "body": json.dumps(body),
    }


def route(svc: ReviewService, method: str, path: str, event: dict, principal: dict | None) -> tuple[int, Any]:
    body = json.loads(event["body"]) if event.get("body") else {}
    m = re.match

    if method == "GET" and path == "/impact":
        return 200, svc.impact()
    if (r := m(r"^/sources/([\w.-]+)$", path)) and method == "GET":
        return 200, svc.get_source(r.group(1))

    if principal is None:
        raise ApiError(401, "UNAUTHENTICATED", "Sign in first.")

    def guard(claim_id: str) -> None:
        claim = svc.repo.get_claim(claim_id)
        if claim is None:
            raise ApiError(404, "CLAIM_NOT_FOUND", f"No claim {claim_id}.")
        if not can_read_claim(principal, claim):
            raise ApiError(403, "FORBIDDEN", "You cannot read this claim.")

    if method == "GET" and path == "/claims":
        rows = svc.list_claims()
        rows["claims"] = [c for c in rows["claims"]
                          if can_read_claim(principal, svc.repo.get_claim(c["claim_id"]))]
        return 200, rows
    if method == "POST" and path == "/claims":
        if principal["role"] != "RECYCLER":
            raise ApiError(403, "FORBIDDEN", "Only a recycler can submit a claim.")
        body["recycler_party_id"] = principal["party_id"]
        return 201, svc.submit_claim(body)
    if (r := m(r"^/claims/([\w-]+)$", path)) and method == "GET":
        guard(r.group(1))
        return 200, svc.get_claim(r.group(1))
    if (r := m(r"^/claims/([\w-]+)/check$", path)) and method == "POST":
        if principal["role"] != "AUDITOR":
            raise ApiError(403, "FORBIDDEN", "Only an auditor can run ClaimGuard.")
        return 200, svc.check_claim(r.group(1))
    if (r := m(r"^/claims/([\w-]+)/runs/([\w:+.-]+)$", path)) and method == "GET":
        guard(r.group(1))
        run = svc.repo.latest_run(r.group(1))
        if not run or run["run_id"] != r.group(2):
            raise ApiError(404, "RUN_NOT_FOUND", "No such run.")
        return 200, run
    if (r := m(r"^/claims/([\w-]+)/reviews$", path)) and method == "POST":
        guard(r.group(1))
        return 201, svc.add_review(r.group(1), body, principal)
    if (r := m(r"^/claims/([\w-]+)/copilot$", path)) and method == "POST":
        guard(r.group(1))
        return 200, copilot_answer(svc, r.group(1), str(body.get("question", ""))[:500])
    if method == "POST" and path == "/claim-evidence/presign":
        raise ApiError(501, "NOT_IMPLEMENTED", "Evidence upload is wired by the evidence stack (see infra/claimguard).")
    raise ApiError(404, "NOT_FOUND", f"{method} {path}")


def handler(event: dict, context: Any = None, service: ReviewService | None = None) -> dict:
    global _SERVICE
    svc = service or _SERVICE or build_service()
    if service is None:
        _SERVICE = svc
    http = (event.get("requestContext") or {}).get("http") or {}
    method, path = http.get("method", event.get("httpMethod", "GET")), event.get("rawPath", event.get("path", "/"))
    if method == "OPTIONS":
        return {"statusCode": 204, "headers": {
            "access-control-allow-origin": os.environ.get("ALLOW_ORIGIN", "*"),
            "access-control-allow-headers": "authorization,content-type,x-dev-party,x-dev-role",
            "access-control-allow-methods": "GET,POST,OPTIONS"}, "body": ""}
    try:
        principal = principal_from_event(event, os.environ.get("AUTH_MODE", "jwt"))
        status, body = route(svc, method, path, event, principal)
        return _resp(status, body)
    except ApiError as e:
        return _resp(e.status, {"error": {"code": e.code, "message": e.message}})
