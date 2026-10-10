import pytest

pytest.importorskip("cedarpy")

from capture.authz import LocalCedarAuthorizer, business_user
from capture.repo import MemoryRepo
from capture.service import CaptureService, Settings
from ledger.signing import LocalSigner
from test_capture import Clock, handover_body

COL, AUD = business_user("COL-118", "COLLECTOR"), business_user("AUD-01", "AUDITOR")


@pytest.fixture
def svc():
    clock = Clock()
    s = CaptureService(MemoryRepo(), LocalSigner(), LocalCedarAuthorizer(), Settings(), clock=clock)
    s.clock_obj = clock
    return s


def codes(svc, b):
    return [f["code"] for f in svc.get_batch(AUD, b)["anomalies"]]


def test_slow_confirmation_has_no_flag(svc):
    r = svc.create_handover(COL, handover_body())
    svc.clock_obj.advance(minutes=5)
    svc.confirm_post(r["confirm_token"], "yes", device_id="seller-1")
    assert codes(svc, r["batch_id"]) == []


def test_confirmation_seconds_after_creation_is_flagged(svc):
    r = svc.create_handover(COL, handover_body())
    svc.clock_obj.advance(seconds=8)
    svc.confirm_post(r["confirm_token"], "yes", device_id="seller-1")
    flags = svc.get_batch(AUD, r["batch_id"])["anomalies"]
    assert flags[0]["code"] == "FAST_CONFIRM" and flags[0]["seconds"] == 8
    # status is untouched: flags are review signals only
    assert svc.get_batch(AUD, r["batch_id"])["view"][0]["confirmation"]["status"] == "BOTH_PARTIES_CONFIRMED"


def test_one_phone_confirming_for_many_sellers_is_flagged(svc):
    batches = []
    for _ in range(3):
        r = svc.create_handover(COL, handover_body())
        svc.clock_obj.advance(minutes=10)
        svc.confirm_post(r["confirm_token"], "yes", device_id="same-phone")
        batches.append(r["batch_id"])
    assert codes(svc, batches[0]) == [] and codes(svc, batches[1]) == []
    assert codes(svc, batches[2]) == ["DEVICE_FANOUT"]
    other = svc.create_handover(COL, handover_body())
    svc.clock_obj.advance(minutes=10)
    svc.confirm_post(other["confirm_token"], "yes", device_id="different-phone")
    assert codes(svc, other["batch_id"]) == []


def test_rejection_does_not_count_towards_fanout(svc):
    for _ in range(3):
        r = svc.create_handover(COL, handover_body())
        svc.clock_obj.advance(minutes=10)
        svc.confirm_post(r["confirm_token"], "no", device_id="p")
    assert codes(svc, r["batch_id"]) == []
