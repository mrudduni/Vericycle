"""Drive the Lambda router with real API Gateway HTTP API (v2) events."""
import json
import os

import pytest

pytest.importorskip("aws_lambda_powertools")
pytest.importorskip("cedarpy")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("IDEMPOTENCY_TABLE", "test")
os.environ.setdefault("POWERTOOLS_TRACE_DISABLED", "1")

from aws_lambda_powertools.utilities.idempotency.exceptions import IdempotencyItemAlreadyExistsError, IdempotencyItemNotFoundError

from capture.authz import LocalCedarAuthorizer
from capture.handlers import api
from capture.repo import MemoryRepo
from capture.service import CaptureService, Settings
from extract.bedrock_extract import extract_offline
from ledger.signing import LocalSigner
import seed_demo


class Ctx:
    function_name = "capture-api"
    memory_limit_in_mb = 512
    invoked_function_arn = "arn:aws:lambda:ap-south-1:000000000000:function:capture-api"
    aws_request_id = "req-1"
    def get_remaining_time_in_millis(self):
        return 30000


@pytest.fixture
def client(monkeypatch):
    repo = MemoryRepo()
    signer = LocalSigner()
    seed_demo.seed(repo, signer, log=lambda *_: None)
    svc = CaptureService(repo, signer, LocalCedarAuthorizer(), Settings(web_url="https://c.test"))
    monkeypatch.setattr(api, "service", lambda: svc)
    monkeypatch.setattr(api, "extractor", lambda: extract_offline)
    monkeypatch.setattr(api, "transcriber", lambda: None)
    store = {}
    p = api.persistence
    def get(idempotency_key=None, **_):
        if idempotency_key not in store: raise IdempotencyItemNotFoundError
        return store[idempotency_key]
    def put(data_record=None, **_):
        if data_record.idempotency_key in store:
            raise IdempotencyItemAlreadyExistsError(old_data_record=store[data_record.idempotency_key])
        store[data_record.idempotency_key] = data_record
    monkeypatch.setattr(p, "_get_record", get)
    monkeypatch.setattr(p, "_put_record", put)
    monkeypatch.setattr(p, "_update_record", lambda data_record=None, **_: store.__setitem__(data_record.idempotency_key, data_record))
    monkeypatch.setattr(p, "_delete_record", lambda data_record=None, **_: store.pop(data_record.idempotency_key, None))

    def call(method, path, body=None, groups=None, party=None, key=None):
        headers = {"content-type": "application/json"}
        if key:
            headers["idempotency-key"] = key
        rc = {"http": {"method": method, "path": path, "sourceIp": "1.1.1.1", "userAgent": "t"},
              "requestId": "r", "routeKey": "$default", "stage": "$default"}
        if groups:
            rc["authorizer"] = {"jwt": {"claims": {"cognito:groups": f"[{' '.join(groups)}]", "custom:party_id": party}, "scopes": None}}
        ev = {"version": "2.0", "routeKey": "$default", "rawPath": path, "rawQueryString": "", "headers": headers,
              "requestContext": rc, "body": json.dumps(body) if body is not None else None, "isBase64Encoded": False}
        r = api.handler(ev, Ctx())
        return r["statusCode"], json.loads(r["body"]) if r.get("body") else None
    return call, svc


def test_public_verify_and_receipt(client):
    call, svc = client
    code, body = call("GET", "/verify/B-0042")
    assert code == 200 and body["ok"] and body["checked"] == 3 and "BEGIN PUBLIC KEY" in body["public_key_pem"]
    tok = svc.get_batch(__import__("capture.authz", fromlist=["x"]).business_user("AUD-01", "AUDITOR"), "B-0042")["receipt_token"]
    code, body = call("GET", f"/r/{tok}")
    assert code == 200 and body["count"] == 6


def test_lineage_requires_sign_in(client):
    call, _ = client
    assert call("GET", "/batches/B-0046/lineage")[0] == 401
    code, body = call("GET", "/batches/B-0046/lineage", groups=["AUDITOR"], party="AUD-01")
    assert code == 200 and len(body["edges"]) == 2


def test_post_needs_idempotency_key(client):
    call, _ = client
    code, body = call("POST", "/handovers", {"material": "BATTERY_LEAD_ACID"}, ["COLLECTOR"], "COL-118")
    assert code == 400 and body["error"]["code"] == "MISSING_IDEMPOTENCY_KEY"


def test_same_idempotency_key_gives_one_event(client):
    call, svc = client
    body = {"material": "BATTERY_LEAD_ACID", "fields": {"count": 2, "weight_kg": 60, "source_category": "DRIVER"}}
    c1, r1 = call("POST", "/handovers", body, ["COLLECTOR"], "COL-118", key="01JA0000000000000000000001")
    c2, r2 = call("POST", "/handovers", body, ["COLLECTOR"], "COL-118", key="01JA0000000000000000000001")
    assert c1 == c2 == 200 and r1["batch_id"] == r2["batch_id"]
    assert len(svc.repo.store.list_events(r1["batch_id"])) == 1


def test_buyer_handler_confirmation_is_403_through_api(client):
    call, _ = client
    body = {"material": "BATTERY_LEAD_ACID", "fields": {
        "count": {"value": 2, "confirmed_by_roles": ["HANDLER"], "confirmation_channel": "OWN_DEVICE_LINK"},
        "weight_kg": 60, "source_category": "DRIVER"}}
    code, b = call("POST", "/handovers", body, ["COLLECTOR"], "COL-118", key="k-403")
    assert code == 403 and b["error"]["code"] == "FORBIDDEN"


def test_chat_flow_through_api(client):
    call, _ = client
    code, card = call("POST", "/chat/messages", {"text": "chaar battery driver se lagbhag assi kilo"}, ["COLLECTOR"], "COL-118", key="k-c1")
    assert code == 200 and card["fields"]["count"] == 4
    code, r = call("POST", f"/chat/drafts/{card['draft_id']}/confirm", {"device_id": "d1"}, ["COLLECTOR"], "COL-118", key="k-c2")
    assert code == 200 and r["confirm_url"].startswith("https://c.test/c/")
    tok = r["confirm_token"]
    code, ask = call("GET", f"/confirm/{tok}")
    assert code == 200 and ask["count"] == 4
    code, done = call("POST", f"/confirm/{tok}", {"answer": "yes", "device_id": "d2"}, key="k-c3")
    assert code == 200 and done["status"] == "BOTH_PARTIES_CONFIRMED"


def test_no_api_response_leaks_private_fields(client):
    call, _ = client
    blobs = [call("GET", "/batches/B-0041", groups=["AUDITOR"], party="AUD-01")[1],
             call("GET", "/batches/B-0046/lineage", groups=["AUDITOR"], party="AUD-01")[1],
             call("GET", "/verify/B-0041")[1]]
    s = json.dumps(blobs)
    for k in ("phone_hmac", "display_name", "creator_device_id"):
        assert k not in s
