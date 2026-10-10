"""Review API through the real Lambda handler, fixture-backed, no AWS."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "review_api"))
os.environ["AUTH_MODE"] = "dev"

from review.handler import build_service, handler  # noqa: E402


@pytest.fixture()
def svc():
    return build_service()


def call(svc, method, path, role="AUDITOR", party="AUD-01", body=None):
    ev = {"requestContext": {"http": {"method": method}}, "rawPath": path,
          "headers": {"x-dev-role": role, "x-dev-party": party} if role else {},
          "body": json.dumps(body) if body is not None else None}
    r = handler(ev, None, service=svc)
    return r["statusCode"], json.loads(r["body"]) if r["body"] else None


def test_requires_auth(svc):
    assert call(svc, "GET", "/claims", role=None)[0] == 401


def test_check_and_read_claim_c102_flags_with_source(svc):
    assert call(svc, "POST", "/claims/C-102/check")[0] == 200
    s, d = call(svc, "GET", "/claims/C-102")
    assert s == 200
    r1 = next(r for r in d["run"]["rule_results"] if r["rule_id"] == "R1")
    assert r1["outcome"] == "FLAG" and r1["severity"] == "HARD"
    assert "cpcb-capacity-guideline" in d["sources"]


def test_list_shows_flag_counts_after_run(svc):
    call(svc, "POST", "/claims/C-107/check")
    _, d = call(svc, "GET", "/claims")
    row = next(c for c in d["claims"] if c["claim_id"] == "C-107")
    assert row["flags"]["hard"] >= 1


def test_c101_coverage_and_lineage(svc):
    call(svc, "POST", "/claims/C-101/check")
    _, d = call(svc, "GET", "/claims/C-101")
    assert round(d["run"]["scores"]["traceability_coverage"] * 100) == 82
    assert {n["batch_id"] for n in d["lineage"]["nodes"]} == {"B-0041", "B-0042", "B-0043"}
    b41 = next(n for n in d["lineage"]["nodes"] if n["batch_id"] == "B-0041")
    assert b41["events"][0]["confirmation"] == "HANDLER_CONFIRMED"  # count+source confirmed, weight only stated
    b42 = next(n for n in d["lineage"]["nodes"] if n["batch_id"] == "B-0042")
    assert b42["events"][0]["confirmation"] == "BUYER_REPORTED"
    b43 = next(n for n in d["lineage"]["nodes"] if n["batch_id"] == "B-0043")
    assert b43["events"][0]["confirmation"] == "BUYER_REPORTED"  # SAME_DEVICE never counts as witnessed


def test_recycler_cannot_read_other_recyclers_claim(svc):
    assert call(svc, "GET", "/claims/C-106", role="RECYCLER", party="REC-01")[0] == 403
    assert call(svc, "GET", "/claims/C-101", role="RECYCLER", party="REC-01")[0] == 200


def test_recycler_cannot_run_check_or_review_actions(svc):
    assert call(svc, "POST", "/claims/C-101/check", role="RECYCLER", party="REC-01")[0] == 403
    assert call(svc, "POST", "/claims/C-101/reviews", role="RECYCLER", party="REC-01",
                body={"action": "ACCEPT"})[0] == 403


def test_review_trail_is_append_only_and_recycler_can_respond(svc):
    assert call(svc, "POST", "/claims/C-102/reviews", body={"action": "REQUEST_EVIDENCE", "note": "DG logs"})[0] == 201
    assert call(svc, "POST", "/claims/C-102/reviews", role="RECYCLER", party="REC-01",
                body={"action": "RECYCLER_RESPONSE", "note": "logs attached"})[0] == 201
    _, d = call(svc, "GET", "/claims/C-102")
    assert [r["seq"] for r in d["reviews"]] == [1, 2]


def test_refrigerant_claim_rejected(svc):
    s, d = call(svc, "POST", "/claims", role="RECYCLER", party="REC-01",
                body={"claim_id": "C-201", "product": "AC_REFRIGERANT"})
    assert s == 422 and d["error"]["code"] == "REFRIGERANT_CLAIM_NOT_ALLOWED"


def test_submit_then_check_new_claim(svc):
    body = {"claim_id": "C-201", "product": "BATTERY_LEAD_ACID", "period_start": "2026-10-01T00:00:00+05:30",
            "period_end": "2026-10-31T23:59:59+05:30", "input_t": 1.0, "processed_t": 1.0, "output": {"LEAD": 0.5},
            "opening_stock_t": 0, "closing_stock_t": 0, "documented_losses_t": 0, "electricity_kwh": 200}
    assert call(svc, "POST", "/claims", role="RECYCLER", party="REC-01", body=body)[0] == 201
    s, run = call(svc, "POST", "/claims/C-201/check")
    assert s == 200 and any(r["rule_id"] == "R1" and r["outcome"] == "PASS" for r in run["rule_results"])


def test_impact_numbers_have_sources_and_no_invented_refrigerant_claim(svc):
    s, d = call(svc, "GET", "/impact", role=None)
    assert s == 200
    ids = {m["id"]: m for m in d["metrics"]}
    assert ids["lead_traced_kg"]["value"] > 0 and ids["lead_traced_kg"]["source_ids"]
    assert ids["refrigerant_uncounted_t_co2e"]["value"] > 0
    assert "no claim can be made" in ids["refrigerant_uncounted_t_co2e"]["note"]
    for m in d["metrics"]:
        for sid in m["source_ids"]:
            assert call(svc, "GET", f"/sources/{sid}", role=None)[0] == 200


def test_handler_confirmation_correction_is_applied():
    from claimguard.ledger_reader import effective_events, parse_event

    base = {"material": "BATTERY_LEAD_ACID", "at_device": "2026-10-02T09:00:00+05:30",
            "at_server": "2026-10-02T09:00:00+05:30", "actor_party_id": "COL-1"}
    fv = {"value": 4, "asserted_by_role": "COLLECTOR", "confirmed_by_roles": [], "confirmation_channel": "NONE", "basis": "STATED"}
    ho = parse_event("B-1", {**base, "seq": 1, "type": "HANDOVER", "fields": {"count": fv}})
    new = dict(fv, confirmed_by_roles=["HANDLER"], confirmation_channel="OWN_DEVICE_LINK")
    h = lambda v: {"value": v, "asserted_by_role": "HANDLER", "confirmed_by_roles": [], "confirmation_channel": "NONE", "basis": "STATED"}  # noqa: E731
    corr = parse_event("B-1", {**base, "seq": 2, "type": "CORRECTION", "actor_party_id": "HND-1", "fields": {
        "corrects_seq": h(1), "field": h("count"), "new_value": h(new), "reason": h("HANDLER_CONFIRMED")}})
    eff = effective_events((ho, corr))
    assert eff[0].fields["count"].field_status().value == "HANDLER_CONFIRMED"
    assert ho.fields["count"].field_status().value == "BUYER_REPORTED"  # original untouched
