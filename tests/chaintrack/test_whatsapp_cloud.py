"""WhatsApp via Meta's Cloud API: webhook handshake, signatures, parsing, Graph transport, voice off."""
import hashlib
import hmac
import io
import json

from ingest.cloud import GraphClient, route, valid_signature
from ingest.whatsapp import parse_webhook

from test_whatsapp import DEALER, button, text, wa  # noqa: F401  (fixture)

SECRET = {"verify_token": "vt-123", "app_secret": "app-secret", "access_token": "tok"}


def body(msgs):
    return {"object": "whatsapp_business_account", "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"phone_number_id": "PNID"}, "messages": msgs}}]}]}


def post(b, secret="app-secret", sig=None):
    raw = json.dumps(b).encode()
    sig = sig or "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return {"requestContext": {"http": {"method": "POST"}}, "headers": {"X-Hub-Signature-256": sig}, "body": raw.decode()}


def test_handshake_echoes_challenge_only_for_the_right_token():
    ok = route({"requestContext": {"http": {"method": "GET"}}, "queryStringParameters":
                {"hub.mode": "subscribe", "hub.verify_token": "vt-123", "hub.challenge": "42"}}, lambda: SECRET, None)
    bad = route({"requestContext": {"http": {"method": "GET"}}, "queryStringParameters":
                 {"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"}}, lambda: SECRET, None)
    assert (ok["statusCode"], ok["body"]) == (200, "42") and bad["statusCode"] == 403


def test_unsigned_or_forged_posts_are_rejected():
    seen = []
    assert route(post(body([text("m1", DEALER, "hi")]), sig="sha256=00"), lambda: SECRET, seen.append)["statusCode"] == 401
    assert route(post(body([text("m1", DEALER, "hi")]), secret="other"), lambda: SECRET, seen.append)["statusCode"] == 401
    assert not seen and not valid_signature(b"x", None, "s")


def test_parse_webhook_reads_cloud_api_bodies_and_ignores_others():
    ms = parse_webhook(body([text("m1", DEALER, "4 battery"), button("m2", DEALER, "ok:D1")]))
    assert [(m.kind, m.phone_number_id) for m in ms] == [("text", "PNID"), ("button", "PNID")]
    assert parse_webhook({"object": "page"}) == []
    assert parse_webhook({"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"statuses": [{}]}}]}]}) == []


def test_text_to_card_to_receipt_over_the_cloud_api(wa):  # noqa: F811
    w, svc, sent, *_ = wa
    r = route(post(body([text("c1", DEALER, "4 e-rickshaw batteries from a driver, about 120 kg")])), lambda: SECRET, w.on_message)
    assert r["statusCode"] == 200 and json.loads(r["body"])["results"] == ["draft"]
    draft = sent[-1]["interactive"]["action"]["buttons"][0]["reply"]["id"]
    route(post(body([button("c2", DEALER, draft)])), lambda: SECRET, w.on_message)
    assert any("Saved" in (p.get("text") or {}).get("body", "") for p in sent)
    assert any(p.get("type") == "image" for p in sent)          # QR codes as images
    again = route(post(body([button("c2", DEALER, draft)])), lambda: SECRET, w.on_message)  # Meta retry
    assert json.loads(again["body"])["results"] == ["duplicate"]


def test_voice_note_gets_a_type_please_reply_when_voice_is_off(wa):  # noqa: F811
    w, svc, sent, fetched, _ = wa
    w.transcriber = None
    msg = {"id": "v1", "from": DEALER, "timestamp": "1", "type": "audio", "audio": {"id": "MEDIA", "mime_type": "audio/ogg"}}
    route(post(body([msg])), lambda: SECRET, w.on_message)
    assert not fetched and "Please type" in sent[-1]["text"]["body"]


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_graph_client_sends_json_and_uploads_multipart_png():
    calls = []

    def opener(req):
        calls.append(req)
        return FakeResp(json.dumps({"id": "MEDIA9", "messages": [{"id": "wamid"}]}).encode())

    g = GraphClient("tok", "PNID", version="v23.0", opener=opener)
    g.send({"messaging_product": "whatsapp", "to": "1", "type": "text", "text": {"body": "hi"}})
    assert g.upload_png(b"\x89PNGdata") == "MEDIA9"
    assert calls[0].full_url == "https://graph.facebook.com/v23.0/PNID/messages"
    assert calls[0].get_header("Authorization") == "Bearer tok" and calls[0].get_header("Content-type") == "application/json"
    assert calls[1].full_url.endswith("/PNID/media") and b"\x89PNGdata" in calls[1].data
    assert calls[1].get_header("Content-type").startswith("multipart/form-data; boundary=")
