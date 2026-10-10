"""Copilot guardrails, offline: deterministic explanation, verdict refusal, citation validation, no-model fallback."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "services" / "copilot"), str(ROOT / "services" / "review_api")]
os.environ["AUTH_MODE"] = "dev"

from copilot.agent import answer, refuse_if_verdict, validate_answer  # noqa: E402
from review.handler import build_service, handler  # noqa: E402


def detail(claim_id="C-102"):
    svc = build_service()
    svc.check_claim(claim_id)
    return svc.get_claim


def test_static_explanation_cites_rules_and_sources_and_matches_engine():
    out = answer("C-102", "Why was C-102 flagged?", detail(), None)
    assert out["answer"] is None and not out["model_used"]
    r1 = next(e for e in out["explanation"] if e["text"].startswith("R1 "))
    assert "inconsistent with the data" in r1["text"] and "46,200" in r1["text"]
    assert "R1" in r1["cites"] and "S:cpcb-capacity-guideline" in r1["cites"]
    assert out["explanation"][-1]["text"].endswith("not certified as genuine.")


def test_verdict_questions_refused_with_rule_outcomes_instead():
    for q in ("Is Recycler X a fraud?", "are they scammers", "Was REC-01 cheating?"):
        assert refuse_if_verdict(q), q
    out = answer("C-102", "Is REC-01 a fraud?", detail(), lambda *_: "REC-01 is a fraud [R1]")
    assert out["answer"] is None and "can't say" in out["refusal"] and out["explanation"]
    assert not refuse_if_verdict("Why was C-105 flagged?")


def test_answer_without_valid_citations_is_discarded():
    gd = detail()
    assert answer("C-102", "why", gd, lambda *_: "It exceeded capacity.")["answer"] is None
    assert answer("C-102", "why", gd, lambda *_: "It exceeded capacity [R9].")["answer"] is None
    ok = answer("C-102", "why", gd, lambda *_: "Processed tonnage exceeds the period capacity [R1] per [S:cpcb-capacity-guideline].")
    assert ok["model_used"] and "[R1]" in ok["answer"]
    assert validate_answer("x [R1]", {"R1"}) and not validate_answer("x", {"R1"})


def test_model_failure_falls_back_to_static():
    def boom(*_):
        raise RuntimeError("throttled")
    out = answer("C-102", "why", detail(), boom)
    assert out["answer"] is None and out["explanation"] and "unavailable" in out["refusal"]


def test_http_route_without_model_and_authz():
    svc = build_service()
    svc.check_claim("C-107")
    call = lambda role, party: handler({"requestContext": {"http": {"method": "POST"}}, "rawPath": "/claims/C-107/copilot",  # noqa: E731
                                        "headers": {"x-dev-role": role, "x-dev-party": party},
                                        "body": json.dumps({"question": "Why was C-107 flagged?"})}, None, service=svc)
    ok = call("AUDITOR", "AUD-01")
    assert ok["statusCode"] == 200 and any(e["text"].startswith("R4 ") for e in json.loads(ok["body"])["explanation"])
    assert call("RECYCLER", "REC-02")["statusCode"] == 403  # not their claim
