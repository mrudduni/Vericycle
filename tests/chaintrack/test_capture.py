import json
from datetime import datetime, timedelta

import pytest

pytest.importorskip("cedarpy")
pytest.importorskip("yaml")

from capture.authz import LocalCedarAuthorizer, business_user
from capture.errors import ApiError
from capture.repo import MemoryRepo
from capture.service import CaptureService, Settings
from ledger.signing import LocalSigner
import seed_demo

AUTHZ = LocalCedarAuthorizer()
COL = business_user("COL-118", "COLLECTOR")
COL_P = business_user("COL-207", "COLLECTOR")
AGG = business_user("AGG-01", "AGGREGATOR")
REC = business_user("REC-01", "RECYCLER")
AUD = business_user("AUD-01", "AUDITOR")


class Clock:
    def __init__(self):
        self.t = datetime.fromisoformat("2026-10-10T09:00:00+05:30")
    def __call__(self):
        return self.t.isoformat(timespec="seconds")
    def advance(self, **kw):
        self.t += timedelta(**kw)


RESPONSES = []


@pytest.fixture
def svc():
    repo, signer, clock = MemoryRepo(), LocalSigner(), Clock()
    seed_demo.seed(repo, signer, log=lambda *_: None)
    s = CaptureService(repo, signer, AUTHZ, Settings(web_url="https://capture.test", wa_number="919999999999"), clock=clock)
    s._clock_obj = clock
    orig = {}
    for name in ("create_handover", "add_event", "get_batch", "lineage", "receipt", "confirm_get", "confirm_post", "verify", "presign"):
        f = getattr(s, name)
        def wrap(*a, _f=f, **k):
            r = _f(*a, **k)
            RESPONSES.append(r)
            return r
        setattr(s, name, wrap)
    return s


def status_of(svc, batch_id, principal=AUD):
    return svc.get_batch(principal, batch_id)["view"][0]["confirmation"]["status"]


def chip_of(svc, batch_id):
    return svc.get_batch(AUD, batch_id)["view"][0]["confirmation"]["chip"]["en"]


def handover_body(**kw):
    b = {"material": "BATTERY_LEAD_ACID", "at_device": "2026-10-10T08:59:50+05:30", "device_id": "dev-collector",
         "fields": {"count": 4, "weight_kg": 80, "source_category": "DRIVER"}}
    b.update(kw)
    return b


# --- seeded data matches CONTRACT §8 ----------------------------------------------

@pytest.mark.parametrize("batch,expected", [
    ("B-0041", "HANDLER_CONFIRMED"), ("B-0042", "BUYER_REPORTED"), ("B-0043", "BUYER_REPORTED"),
    ("B-0046", "BOTH_PARTIES_CONFIRMED"), ("P-0101", "BOTH_PARTIES_CONFIRMED"), ("P-0102", "BUYER_REPORTED"),
])
def test_seeded_event_status(svc, batch, expected):
    assert status_of(svc, batch) == expected


def test_same_device_is_labelled_not_independent(svc):
    assert chip_of(svc, "B-0043") == "Confirmed on buyer's phone (not independent)"
    assert chip_of(svc, "B-0042") == "Entered by buyer only"


def test_all_seeded_chains_verify(svc):
    for b in list(seed_demo.BATCHES) + ["B-0046.1", "B-0046.2"]:
        r = svc.verify(b)
        assert r["ok"], (b, r)


def test_lineage_of_split(svc):
    lin = svc.lineage(AUD, "B-0046")
    assert lin["root_batch_id"] == "B-0046"
    assert {n["batch_id"] for n in lin["nodes"]} == {"B-0046", "B-0046.1", "B-0046.2"}
    assert lin["edges"] == [{"from": "B-0046", "to": "B-0046.1", "kind": "SPLIT", "weight_kg": 60},
                            {"from": "B-0046", "to": "B-0046.2", "kind": "SPLIT", "weight_kg": 58}]
    assert all("kms_sig" not in e for n in lin["nodes"] for e in n["events"])


def test_intake_weights_for_c101_coverage(svc):
    kg = [svc.get_batch(AUD, b)["events"][-1]["fields"]["weight_kg"]["value"] for b in ("B-0041", "B-0042", "B-0043")]
    assert sum(kg) == 410


# --- handover and handler confirmation -------------------------------------------------

def test_handover_then_seller_confirms_on_own_phone(svc):
    r = svc.create_handover(COL, handover_body())
    assert r["batch_id"].startswith("B-") and len(r["batch_id"]) == 10
    assert r["event"]["confirmation"]["status"] == "BUYER_REPORTED"
    assert r["receipt_url"].startswith("https://capture.test/r/")
    assert r["wa_confirm_link"].endswith(f"HAAN%20{r['confirm_code']}")
    ask = svc.confirm_get(r["confirm_token"])
    assert ask["count"] == 4 and ask["approx_weight_kg"] == 80 and set(ask["asks"]) == {"count", "source_category", "weight_kg"}
    out = svc.confirm_post(r["confirm_token"], "yes", device_id="dev-seller")
    assert out["channel"] == "OWN_DEVICE_LINK" and out["status"] == "BOTH_PARTIES_CONFIRMED"
    assert status_of(svc, r["batch_id"]) == "BOTH_PARTIES_CONFIRMED"
    assert svc.verify(r["batch_id"])["ok"]


def test_confirm_on_buyer_device_is_same_device(svc):
    r = svc.create_handover(COL, handover_body())
    out = svc.confirm_post(r["confirm_token"], "yes", device_id="dev-collector")
    assert out["channel"] == "SAME_DEVICE" and out["status"] == "BUYER_REPORTED"


def test_token_single_use(svc):
    r = svc.create_handover(COL, handover_body())
    svc.confirm_post(r["confirm_token"], "yes", device_id="x")
    with pytest.raises(ApiError) as e:
        svc.confirm_post(r["confirm_token"], "yes", device_id="x")
    assert e.value.status == 410 and e.value.code == "TOKEN_USED"


def test_token_expires_after_7_days(svc):
    r = svc.create_handover(COL, handover_body())
    svc._clock_obj.advance(days=7, seconds=1)
    with pytest.raises(ApiError) as e:
        svc.confirm_post(r["confirm_token"], "yes", device_id="x")
    assert e.value.code == "TOKEN_EXPIRED"


def test_rejection_is_a_correction_event(svc):
    r = svc.create_handover(COL, handover_body())
    svc.confirm_post(r["confirm_token"], "no", device_id="x")
    evs = svc.get_batch(AUD, r["batch_id"])["events"]
    assert evs[-1]["type"] == "CORRECTION" and evs[-1]["fields"]["reason"]["value"] == "HANDLER_REJECTED"


def test_buyer_cannot_set_handler_confirmation(svc):
    body = handover_body(fields={"count": {"value": 4, "confirmed_by_roles": ["HANDLER"], "confirmation_channel": "OWN_DEVICE_LINK"},
                                 "weight_kg": 80, "source_category": "DRIVER"})
    with pytest.raises(ApiError) as e:
        svc.create_handover(COL, body)
    assert e.value.status == 403


def test_buyer_cannot_confirm_via_correction(svc):
    body = {"type": "CORRECTION", "fields": {"corrects_seq": 1, "field": "count", "reason": "HANDLER_CONFIRMED",
            "new_value": {"value": {"value": 6, "confirmed_by_roles": ["HANDLER"], "confirmation_channel": "OWN_DEVICE_LINK"}}}}
    with pytest.raises(ApiError) as e:
        svc.add_event(COL, "B-0042", body)
    assert e.value.status == 403


def test_hindi_number_values_are_validated(svc):
    with pytest.raises(ApiError) as e:
        svc.create_handover(COL, handover_body(fields={"count": "chaar", "weight_kg": 80, "source_category": "DRIVER"}))
    assert e.value.status == 422


# --- other event types -------------------------------------------------------------

def test_aggregator_cannot_create_intake(svc):
    with pytest.raises(ApiError) as e:
        svc.add_event(AGG, "B-0042", {"type": "INTAKE", "fields": {"weight_kg": 170, "facility_id": "AGG-01"}})
    assert e.value.status == 403


def test_intake_without_upstream_warns_but_is_accepted(svc):
    r = svc.add_event(REC, "B-9999", {"type": "INTAKE", "material": "BATTERY_LEAD_ACID",
                                      "fields": {"weight_kg": 50, "facility_id": "REC-01"}})
    assert r["warnings"][0]["code"] == "NO_UPSTREAM_EVENT"
    assert "NO_UPSTREAM_EVENT" not in json.dumps(r["events"])  # not a field on the event


def test_split_must_sum_within_2_percent(svc):
    r = svc.create_handover(COL, handover_body())
    b = r["batch_id"]
    svc.add_event(COL, b, {"type": "TRANSFER", "counterparty_party_id": "AGG-01", "fields": {"weight_kg": 100}})
    with pytest.raises(ApiError) as e:
        svc.add_event(AGG, b, {"type": "SPLIT", "fields": {"child_weights_kg": [50, 47]}})
    assert e.value.status == 422 and e.value.code == "SPLIT_WEIGHT_MISMATCH"
    ok = svc.add_event(AGG, b, {"type": "SPLIT", "fields": {"child_weights_kg": [50, 49]}})
    assert [e["batch_id"] for e in ok["events"]] == [b, f"{b}.1", f"{b}.2"]
    assert svc.verify(f"{b}.1")["ok"]


def test_merge(svc):
    a = svc.create_handover(COL, handover_body())["batch_id"]
    b = svc.create_handover(COL, handover_body())["batch_id"]
    for x in (a, b):
        svc.add_event(COL, x, {"type": "TRANSFER", "counterparty_party_id": "AGG-01", "fields": {"weight_kg": 80}})
    r = svc.add_event(AGG, a, {"type": "MERGE", "parent_batch_ids": [b], "fields": {"weight_kg": 159}})
    new = r["batch_id"]
    assert svc.get_batch(AUD, a)["status"] == "MERGED"
    lin = svc.lineage(AUD, new)
    assert {e["from"] for e in lin["edges"]} == {a, b}


def test_closed_batch_rejects_new_events(svc):
    with pytest.raises(ApiError) as e:
        svc.add_event(COL, "B-0046", {"type": "TRANSFER", "fields": {"weight_kg": 10}})
    assert e.value.code == "BATCH_CLOSED"


# --- products -----------------------------------------------------------------------

def test_phone_batch_uses_same_flow(svc):
    r = svc.create_handover(COL_P, {"material": "EWASTE_PHONE",
                                    "fields": {"count": 12, "weight_kg": 2.1, "source_category": "RETAIL_EXCHANGE"}})
    assert r["batch_id"].startswith("P-")
    assert svc.confirm_post(r["confirm_token"], "yes", device_id="d2")["status"] == "BOTH_PARTIES_CONFIRMED"


def test_ac_record_has_no_claim_path_and_harm_note(svc):
    r = svc.create_handover(business_user("COL-330", "COLLECTOR"),
                            {"material": "AC_REFRIGERANT",
                             "fields": {"count": 1, "source_category": "TECHNICIAN", "gas_type": "R-32", "charge_kg": 0.9}})
    assert r["batch_id"].startswith("A-")
    assert "no recycling certificate" in r["receipt_note"]["en"]
    assert "confirm_token" not in r


# --- receipts, privacy ------------------------------------------------------------------

def test_receipt_is_public_and_nameless(svc):
    tok = svc.get_batch(AUD, "B-0042")["receipt_token"]
    rec = svc.receipt(tok)
    assert rec["count"] == 6 and rec["approx_weight_kg"] == 180 and rec["chain"]["ok"]
    dumped = json.dumps(rec)
    for party in ("COL-118", "AGG-01", "REC-01", "HND-2b81d0"):
        assert party not in dumped


def test_presign(svc):
    r = svc.presign(REC, {"kind": "WEIGH_SLIP", "content_type": "image/jpeg", "size_bytes": 1000,
                          "sha256": "ab" * 32, "batch_id": "B-0042"})
    assert r["evidence_id"].startswith("EV-") and len(r["evidence_id"]) == 29
    assert "x-amz-checksum-sha256" in r["headers"]


def test_no_response_contains_phone_or_names(svc):
    # run a broad flow so RESPONSES has every route's output
    r = svc.create_handover(COL, handover_body())
    svc.confirm_get(r["confirm_token"])
    svc.confirm_post(r["confirm_token"], "yes", device_id="s")
    svc.receipt(r["receipt_token"])
    svc.lineage(AUD, "B-0046")
    svc.get_batch(AUD, r["batch_id"])
    blob = json.dumps(RESPONSES, ensure_ascii=False)
    for bad in ("phone_hmac", "phone_e164", "display_name", "creator_device_id", "Demo battery dealer", "Demo aggregator"):
        assert bad not in blob, bad
