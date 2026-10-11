"""WhatsApp intake via AWS End User Messaging Social (SHAURYA.md 3.4).

EUMS publishes each inbound webhook to SNS; the Lambda (``handler``) parses ``whatsAppWebhookEntry``
and calls ``WhatsAppIngest.on_message`` once per WhatsApp message ID (Meta retries are deduplicated by
Powertools idempotency in the handler, and again here by a conditional put on the message ID).

Privacy (P6): the sender's number is turned into an HMAC at once. The only copy kept is a KMS-encrypted
reply address on the 24-hour draft, needed to answer after transcription finishes.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

HAAN = re.compile(r"^\s*(?:haan|haa|han|ha|हाँ|हां|yes)\s+([A-Za-z0-9]{6})\s*$", re.IGNORECASE)
RATE_PER_HOUR = 30
WA_API = "v20.0"


@dataclass
class Inbound:
    message_id: str
    sender: str            # E.164 without '+', as Meta sends it; never stored
    kind: str              # text | audio | button | other
    text: str | None = None
    media_id: str | None = None
    mime: str | None = None
    button_id: str | None = None
    phone_number_id: str | None = None   # EUMS originationPhoneNumberId ARN/ID to reply from


def parse_sns(record_message: str) -> list[Inbound]:
    """SNS Message body from EUMS -> inbound WhatsApp messages (status updates are ignored)."""
    body = json.loads(record_message)
    entry = body.get("whatsAppWebhookEntry")
    entry = json.loads(entry) if isinstance(entry, str) else (entry or {})
    ctx_ids = [p.get("arn") or p.get("metaPhoneNumberId") for p in body.get("context", {}).get("MetaPhoneNumberIds", [])]
    out: list[Inbound] = []
    for ch in entry.get("changes", []):
        v = ch.get("value", {})
        origin = ctx_ids[0] if ctx_ids else v.get("metadata", {}).get("phone_number_id")
        for m in v.get("messages", []) or []:
            t = m.get("type")
            base = dict(message_id=m["id"], sender=m["from"], phone_number_id=origin)
            if t == "text":
                out.append(Inbound(kind="text", text=m["text"]["body"], **base))
            elif t == "audio":
                out.append(Inbound(kind="audio", media_id=m["audio"]["id"], mime=m["audio"].get("mime_type"), **base))
            elif t == "interactive" and m["interactive"].get("type") == "button_reply":
                out.append(Inbound(kind="button", button_id=m["interactive"]["button_reply"]["id"], **base))
            elif t == "button":  # quick-reply button on a template
                out.append(Inbound(kind="button", button_id=m["button"].get("payload"), **base))
            else:
                out.append(Inbound(kind="other", **base))
    return out


def qr_png(url: str) -> bytes:
    """QR codes only ever encode a URL (CONTRACT §4)."""
    import io
    import segno
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="png", scale=8, border=3)
    return buf.getvalue()


def image_msg(to: str, media_id: str, caption: str) -> dict:
    return {"messaging_product": "whatsapp", "to": to, "type": "image", "image": {"id": media_id, "caption": caption[:1024]}}


def text_msg(to: str, body: str) -> dict:
    return {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body, "preview_url": True}}


def buttons_msg(to: str, body: str, buttons: list[tuple[str, str]]) -> dict:
    return {"messaging_product": "whatsapp", "to": to, "type": "interactive", "interactive": {
        "type": "button", "body": {"text": body[:1024]},
        "action": {"buttons": [{"type": "reply", "reply": {"id": i[:256], "title": tt[:20]}} for i, tt in buttons]}}}


class WhatsAppIngest:
    """All side effects are injected so this runs offline in tests."""

    def __init__(self, svc, *, hmac: Callable[[str], str], send: Callable[[str, dict], None],
                 fetch_media: Callable[[str, str, str], None], encrypt: Callable[[str], str],
                 decrypt: Callable[[str], str], extractor, transcriber,
                 upload_image: Callable[[str, bytes], str] | None = None):
        self.svc, self.hmac, self.send = svc, hmac, send
        self.fetch_media, self.encrypt, self.decrypt = fetch_media, encrypt, decrypt
        self.extractor, self.transcriber = extractor, transcriber
        self.upload_image = upload_image   # (origin, png) -> WhatsApp media id; None = links only

    # -- helpers -------------------------------------------------------------------------------
    def _reply(self, m: Inbound, payload: dict):
        self.send(m.phone_number_id, payload)

    def _collector(self, phone_hmac: str):
        from capture.authz import business_user
        link = self.svc.repo.get(f"PHONE#{phone_hmac}")
        if not link:
            return None
        party = self.svc.repo.get(f"PARTY#{link['party_id']}")
        return business_user(link["party_id"], party["role"]) if party and party.get("role") == "COLLECTOR" else None

    def _first_time(self, message_id: str) -> bool:
        return self.svc.repo.put_new({"PK": f"WAMSG#{message_id}", "SK": "META",
                                      "expires_at": self.svc._epoch() + 7 * 86400})

    # -- entry point -----------------------------------------------------------------------------
    def on_message(self, m: Inbound) -> str:
        if not self._first_time(m.message_id):
            return "duplicate"
        sender_hmac = self.hmac(m.sender)
        now = self.svc._epoch()
        if self.svc.repo.increment(f"RATE#WA#{sender_hmac}", f"H#{now // 3600}", "n", now + 7200) > RATE_PER_HOUR:
            return "rate_limited"

        # 1. Handler confirmation: "HAAN <code>" from the seller's own phone (customer-initiated, no template).
        if m.kind == "text" and (hm := HAAN.match(m.text or "")):
            return self._handler_confirm(m, hm.group(1).upper(), sender_hmac)

        collector = self._collector(sender_hmac)
        if collector is None:
            self._reply(m, text_msg(m.sender,
                "नमस्ते! यह नंबर अभी Vericycle में कलेक्टर के रूप में दर्ज नहीं है। जुड़ने के लिए अपने एग्रीगेटर से बात करें।\n"
                "Hello! This number is not registered as a collector on Vericycle yet. Please ask your aggregator to register you."))
            return "unregistered"

        if m.kind == "button":
            return self._button(m, collector)
        if m.kind == "text":
            from capture import chat
            card = chat.chat_message(self.svc, collector, {"text": m.text, "device_id": f"wa:{sender_hmac[:12]}"},
                                     extractor=self.extractor)
            self._send_card(m.phone_number_id, m.sender, card)
            return "draft"
        if m.kind == "audio":
            return self._audio(m, collector, sender_hmac)
        self._reply(m, text_msg(m.sender, "कृपया वॉइस नोट या टेक्स्ट भेजें। Please send a voice note or text."))
        return "unsupported"

    def _audio(self, m: Inbound, collector, sender_hmac: str) -> str:
        from capture import chat, ids
        evid = ids.evidence_id()
        key = f"audio/{evid}.ogg"
        self.fetch_media(m.media_id, m.phone_number_id, key)
        self.svc.repo.put_new({"PK": f"EV#{evid}", "SK": "META", "kind": "AUDIO",
                               "s3_bucket": self.svc.settings.evidence_bucket, "s3_key": key, "sha256": None,
                               "received_at_server": self.svc.clock(), "batch_id": None,
                               "uploaded_by_party_id": collector.party_id})
        card = chat.chat_message(self.svc, collector, {"evidence_id": evid, "device_id": f"wa:{sender_hmac[:12]}"},
                                 extractor=self.extractor, transcriber=self.transcriber)
        d = self.svc.repo.get(f"DRAFT#{card['draft_id']}")
        d.update(channel="WHATSAPP", wa_reply_enc=self.encrypt(m.sender), wa_origin=m.phone_number_id)
        self.svc.repo.put(d)
        self._reply(m, text_msg(m.sender, "🎧 सुन रहे हैं… Listening…"))
        return "transcribing"

    def notify_draft_ready(self, draft_id: str) -> bool:
        """Called after transcription completes: send the card to the collector on WhatsApp."""
        from capture import chat
        d = self.svc.repo.get(f"DRAFT#{draft_id}")
        if not d or d.get("channel") != "WHATSAPP" or not d.get("wa_reply_enc"):
            return False
        to = self.decrypt(d["wa_reply_enc"])
        if d.get("status") == "FAILED":
            self.send(d["wa_origin"], text_msg(to, d.get("error") or "Please try again."))
        else:
            self._send_card(d["wa_origin"], to, chat.card(d))
        return True

    def _send_card(self, origin: str, to: str, card: dict) -> None:
        rb = card.get("readback") or {}
        body = f"{rb.get('hi', '')}\n{rb.get('en', '')}"
        if card.get("uncertain_fields"):
            body += "\n\n⚠ जाँचें / check: " + ", ".join(card["uncertain_fields"])
        self.send(origin, buttons_msg(to, body, [(f"ok:{card['draft_id']}", "✅ सही / Yes"),
                                                 (f"edit:{card['draft_id']}", "✏️ बदलें / Edit")]))

    def _button(self, m: Inbound, collector) -> str:
        from capture import chat
        action, _, draft_id = (m.button_id or "").partition(":")
        if action == "edit":
            self._reply(m, text_msg(m.sender, "सही संख्या लिखकर भेजें, जैसे: \"5 battery 150 kilo driver se\"\n"
                                              "Type the correct details, e.g. \"5 batteries 150 kg from a driver\"."))
            return "edit"
        if action != "ok":
            return "ignored"
        r = chat.confirm_draft(self.svc, collector, draft_id, {"device_id": f"wa:{self.hmac(m.sender)[:12]}"})
        lines = [f"✅ दर्ज हो गया / Saved: {r['batch_id']}", f"🧾 {r['receipt_url']}"]
        if r.get("wa_confirm_link"):
            lines.append("बेचने वाले से कहें कि अपने फ़ोन से यह लिंक खोलकर भेजें / Ask the seller to open this on THEIR phone and send:\n"
                         + r["wa_confirm_link"])
        elif r.get("confirm_url"):
            lines.append("बेचने वाले के फ़ोन के लिए / For the seller's phone: " + r["confirm_url"])
        if r.get("receipt_note"):
            lines.append(r["receipt_note"]["hi"] + "\n" + r["receipt_note"]["en"])
        self._reply(m, text_msg(m.sender, "\n".join(lines)))
        if self.upload_image:
            qrs = [(r["receipt_url"], "① अगला ख़रीदार यह स्कैन करे / Next buyer scans this")]
            if r.get("wa_confirm_link") or r.get("confirm_url"):
                qrs.append((r.get("wa_confirm_link") or r["confirm_url"],
                            "② बेचने वाला अपने फ़ोन से स्कैन करे / Seller scans this with THEIR phone"))
            for url, caption in qrs:
                media_id = self.upload_image(m.phone_number_id, qr_png(url))
                self._reply(m, image_msg(m.sender, media_id, caption))
        return "confirmed"

    def _handler_confirm(self, m: Inbound, code: str, sender_hmac: str) -> str:
        token = self.svc.token_for_code(code)
        if not token:
            self._reply(m, text_msg(m.sender, "यह कोड सही नहीं है या पुराना हो गया। This code is not valid or has expired."))
            return "bad_code"
        t = self.svc.repo.get(f"CONFIRM#{token}")
        ev = next((e for e in self.svc._events(t["batch_id"]) if e["seq"] == int(t["seq"])), None)
        collector_link = self.svc.repo.get(f"PARTY#{ev['actor_party_id']}") if ev else None
        same = bool(collector_link and collector_link.get("phone_hmac") == sender_hmac)
        channel = "SAME_DEVICE" if same else "OWN_DEVICE_WHATSAPP"
        try:
            out = self.svc.confirm_post(token, "yes", channel=channel, sender_hmac=sender_hmac)
        except Exception as e:  # noqa: BLE001  (used / expired tokens become a polite reply)
            self._reply(m, text_msg(m.sender, getattr(e, "message", "Could not record this. Please try again.")))
            return "error"
        self._reply(m, text_msg(m.sender, "धन्यवाद! आपकी पुष्टि दर्ज हो गई। आपका नाम कहीं दर्ज नहीं होता।\n"
                                          "Thank you! Your confirmation is recorded. Your name is never stored."))
        return f"handler_{out['channel']}"


def register_collector_phone(repo, phone_hmac: str, party_id: str) -> None:
    """Admin/seed helper: link a collector's phone HMAC to its party. Erasure = delete PHONE#<hmac>."""
    repo.put({"PK": f"PHONE#{phone_hmac}", "SK": "META", "party_id": party_id})
    party = repo.get(f"PARTY#{party_id}") or {"PK": f"PARTY#{party_id}", "SK": "META", "role": "COLLECTOR"}
    party["phone_hmac"] = phone_hmac
    repo.put(party)
