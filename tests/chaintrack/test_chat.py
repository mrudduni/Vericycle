import pytest

pytest.importorskip("cedarpy")

from capture import chat
from capture.authz import LocalCedarAuthorizer, business_user
from capture.errors import ApiError
from capture.repo import MemoryRepo
from capture.service import CaptureService, Settings
from extract.bedrock_extract import extract_offline
from ledger.signing import LocalSigner

COL = business_user("COL-118", "COLLECTOR")


@pytest.fixture
def svc():
    return CaptureService(MemoryRepo(), LocalSigner(), LocalCedarAuthorizer(), Settings(web_url="https://c.test"))


def test_text_message_to_handover(svc):
    c = chat.chat_message(svc, COL, {"text": "chaar e-rickshaw battery driver se, lagbhag assi kilo", "device_id": "d1"},
                          extractor=extract_offline)
    assert c["status"] == "READY" and c["fields"]["count"] == 4 and c["fields"]["weight_kg"] == 80
    assert "4" in c["readback"]["hi"] and "किलो" in c["readback"]["hi"]
    r = chat.confirm_draft(svc, COL, c["draft_id"], {"fields": {"count": 5}})
    assert r["event"]["fields"]["count"]["value"] == 5   # collector's edit wins over the model
    with pytest.raises(ApiError) as e:
        chat.confirm_draft(svc, COL, c["draft_id"], {})
    assert e.value.code == "DRAFT_USED"


def test_other_collector_cannot_confirm_my_draft(svc):
    c = chat.chat_message(svc, COL, {"text": "do battery driver se 60 kilo"}, extractor=extract_offline)
    with pytest.raises(ApiError) as e:
        chat.confirm_draft(svc, business_user("COL-207", "COLLECTOR"), c["draft_id"], {})
    assert e.value.status == 403


def test_voice_draft_lifecycle(svc):
    svc.repo.put_new({"PK": "EV#EV-1", "SK": "META", "kind": "AUDIO", "s3_bucket": "b", "s3_key": "audio/EV-1.webm",
                      "uploaded_by_party_id": "COL-118"})
    started = []
    c = chat.chat_message(svc, COL, {"evidence_id": "EV-1"}, extractor=extract_offline,
                          transcriber=lambda d, b, k: started.append((d, k)))
    assert c["status"] == "TRANSCRIBING" and started == [(c["draft_id"], "audio/EV-1.webm")]
    chat.complete_voice_draft(svc, c["draft_id"], "teen battery driver se", extract_offline, transcript_key="transcripts/x.json")
    d = chat.get_draft(svc, COL, c["draft_id"])
    assert d["status"] == "READY" and d["fields"]["count"] == 3
    r = chat.confirm_draft(svc, COL, c["draft_id"], {"fields": {"weight_kg": 90}})
    assert r["event"]["evidence_ids"] and r["event"]["evidence_badge"] == "EVIDENCE_ATTACHED"


def test_rate_limit(svc):
    for _ in range(chat.RATE_PER_HOUR):
        chat.chat_message(svc, COL, {"text": "ek battery"}, extractor=extract_offline)
    with pytest.raises(ApiError) as e:
        chat.chat_message(svc, COL, {"text": "ek battery"}, extractor=extract_offline)
    assert e.value.status == 429


def test_non_collector_cannot_chat(svc):
    with pytest.raises(ApiError) as e:
        chat.chat_message(svc, business_user("AGG-01", "AGGREGATOR"), {"text": "x"}, extractor=extract_offline)
    assert e.value.status == 403
