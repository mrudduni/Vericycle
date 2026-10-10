"""Step Functions workflow logic offline: parallel families joined == one synchronous run."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "review_api"))
os.environ["AUTH_MODE"] = "dev"

from claimguard.engine import FAMILIES  # noqa: E402
from review.handler import build_service, handler  # noqa: E402
from review.workflow import finalize_handler, rules_handler  # noqa: E402


def strip(run):
    return {k: v for k, v in run.items() if k not in ("run_id", "ran_at")}


def test_branches_joined_equal_synchronous_run_for_every_claim():
    svc = build_service()
    for c in svc.repo.list_claims():
        sync = strip(svc.check_claim(c.claim_id))
        branches = [rules_handler({"claim_id": c.claim_id, "family": f}, service=svc) for f in FAMILIES]
        done = finalize_handler({"claim_id": c.claim_id, "results": branches}, service=svc)
        joined = strip(svc.repo.latest_run(c.claim_id))
        assert joined == sync, c.claim_id
        assert done["flags"] == sum(1 for r in sync["rule_results"] if r["outcome"] == "FLAG")


def test_every_rule_runs_in_exactly_one_family():
    svc = build_service()
    ids = [r["rule_id"] for f in FAMILIES for r in rules_handler({"claim_id": "C-101", "family": f}, service=svc)]
    assert len(ids) == len(set(ids)) and {"R1", "R2a", "R2b", "R3", "R4", "R5", "R6", "R7", "R8"} <= set(ids)


class FakeSfn:
    def __init__(self):
        self.calls = []

    def start_execution(self, **kw):
        self.calls.append(kw)
        return {"executionArn": "arn:aws:states:ap-south-1:1:execution:m:" + kw["name"]}


def test_check_route_starts_workflow_when_configured():
    svc, sfn = build_service(), FakeSfn()
    os.environ["STATE_MACHINE_ARN"] = "arn:aws:states:ap-south-1:1:stateMachine:m"
    try:
        r = handler({"requestContext": {"http": {"method": "POST"}}, "rawPath": "/claims/C-102/check",
                     "headers": {"x-dev-role": "AUDITOR", "x-dev-party": "AUD-01"}}, None, service=svc, sfn_client=sfn)
    finally:
        del os.environ["STATE_MACHINE_ARN"]
    assert r["statusCode"] == 202 and json.loads(r["body"])["status"] == "RUNNING"
    assert json.loads(sfn.calls[0]["input"]) == {"claim_id": "C-102"}
