"""Web chat capture (SHAURYA.md 3.4): message -> draft card -> ✅ -> HANDOVER via the ledger writer.

Drafts live 24 h as ``DRAFT#<id>`` items with TTL. Voice drafts start TRANSCRIBING and become
READY when the Transcribe completion event is processed (``complete_voice_draft``).
"""
from __future__ import annotations

from typing import Callable

from . import ids, materials as M
from .errors import ApiError, bad, forbidden, gone, not_found, unprocessable

DRAFT_TTL = 24 * 3600
RATE_PER_HOUR = 30
SOURCE_LABELS = {
    "DRIVER": ("a driver", "ड्राइवर से"), "HOUSEHOLD": ("a household", "घर से"),
    "TECHNICIAN": ("a technician", "मिस्त्री से"), "RETAIL_EXCHANGE": ("a shop exchange", "दुकान एक्सचेंज से"),
    "INSTITUTION": ("an institution", "संस्था से"), "OTHER": ("someone else", "किसी और से"),
    "UNKNOWN": ("seller not said", "किससे लिया, नहीं बताया"),
}


def _fmt(n) -> str:
    return "?" if n is None else (f"{n:g}" if isinstance(n, float) else str(n))


def readback(x: dict) -> dict:
    """The numbers read back in English and Hindi. The collector must confirm or edit them."""
    if x["material"] == "UNKNOWN":
        return {"en": "I could not tell what was sold. Is it batteries, phones or an AC?",
                "hi": "समझ नहीं आया क्या बेचा गया। बैटरी, फ़ोन या एसी?"}
    m = M.material(x["material"])
    en_src, hi_src = SOURCE_LABELS[x.get("source_category") or "UNKNOWN"]
    basis_en = "weighed" if x.get("weight_basis") == "WEIGHED" else "stated"
    basis_hi = "तौला गया" if x.get("weight_basis") == "WEIGHED" else "बताया गया"
    en = f"{_fmt(x.get('count'))} × {m['label']['en'].lower()}"
    hi = f"{_fmt(x.get('count'))} {m['unit_label']['hi']}"
    if x["material"] == "AC_REFRIGERANT":
        if x.get("gas_type"):
            en += f", gas {x['gas_type']}"
            hi += f", गैस {x['gas_type']}"
        if x.get("charge_kg"):
            en += f", {_fmt(x['charge_kg'])} kg charge"
            hi += f", {_fmt(x['charge_kg'])} किलो गैस"
    elif x.get("weight_kg") is not None:
        en += f", about {_fmt(x['weight_kg'])} kg ({basis_en})"
        hi += f", लगभग {_fmt(x['weight_kg'])} किलो ({basis_hi})"
    else:
        en += ", weight not said"
        hi += ", वज़न नहीं बताया"
    return {"en": f"{en}, from {en_src}. Is this correct?", "hi": f"{hi}, {hi_src}। क्या यह सही है?"}


def card(draft: dict) -> dict:
    x = draft.get("extraction") or {}
    out = {"draft_id": draft["PK"].split("#", 1)[1], "status": draft["status"],
           "transcript": draft.get("transcript"), "expires_at": draft.get("expires_at")}
    if x:
        mat = x.get("material")
        out.update({
            "material": mat,
            "material_label": M.material(mat)["label"] if mat in M.materials() else None,
            "fields": {k: x.get(k) for k in ("count", "weight_kg", "source_category", "gas_type", "charge_kg")},
            "weight_basis": x.get("weight_basis"),
            "uncertain_fields": x.get("uncertain_fields", []),
            "readback": readback(x),
        })
    if draft.get("error"):
        out["error"] = draft["error"]
    return out


def _owner_check(p, draft):
    if p is None or draft.get("party_id") != p.party_id:
        raise forbidden("This draft belongs to someone else.")


def chat_message(svc, p, body: dict, *, extractor: Callable[[str], dict], transcriber=None) -> dict:
    if p is None:
        raise ApiError(401, "UNAUTHENTICATED", "Please sign in.")
    if p.role != "COLLECTOR":
        raise forbidden("Only collectors record handovers in the chat.")
    now = svc._epoch()
    if svc.repo.increment(f"RATE#{p.party_id}", f"H#{now // 3600}", "n", now + 7200) > RATE_PER_HOUR:
        raise ApiError(429, "RATE_LIMITED", "Too many messages this hour. Please wait a little.")
    text, evid = body.get("text"), body.get("evidence_id")
    draft_id = ids.ulid()
    item = {"PK": f"DRAFT#{draft_id}", "SK": "META", "party_id": p.party_id, "device_id": body.get("device_id"),
            "expires_at": now + DRAFT_TTL, "created_at": svc.clock()}
    if isinstance(text, str) and text.strip():
        if len(text) > 2000:
            raise bad("TOO_LONG", "Please keep the message under 2000 characters.")
        item.update(status="READY", transcript=text.strip(), extraction=extractor(text.strip()))
    elif isinstance(evid, str):
        ev = svc.repo.get(f"EV#{evid}")
        if not ev or ev.get("kind") != "AUDIO" or ev.get("uploaded_by_party_id") != p.party_id:
            raise not_found("Voice note not found.")
        if transcriber is None:
            raise ApiError(503, "VOICE_UNAVAILABLE", "Voice notes are not available right now. Please type the message.")
        item.update(status="TRANSCRIBING", audio_evidence_id=evid)
        svc.repo.put_new(item)
        transcriber(draft_id, ev["s3_bucket"], ev["s3_key"])
        return card(item)
    else:
        raise bad("EMPTY_MESSAGE", "Send text or a voice note.")
    svc.repo.put_new(item)
    return card(item)


def get_draft(svc, p, draft_id: str) -> dict:
    d = svc.repo.get(f"DRAFT#{draft_id}")
    if not d or int(d.get("expires_at", 0)) <= svc._epoch():
        raise not_found("Draft not found or expired.")
    _owner_check(p, d)
    return card(d)


def complete_voice_draft(svc, draft_id: str, transcript: str, extractor: Callable[[str], dict],
                         transcript_key: str | None = None, error: str | None = None) -> None:
    d = svc.repo.get(f"DRAFT#{draft_id}")
    if not d or d.get("status") != "TRANSCRIBING":
        return
    if error or not transcript:
        d.update(status="FAILED", error=error or "No speech found. Please try again or type the message.")
    else:
        d.update(status="READY", transcript=transcript, extraction=extractor(transcript))
        if transcript_key:
            evid = ids.evidence_id()
            svc.repo.put_new({"PK": f"EV#{evid}", "SK": "META", "kind": "VOICE_TRANSCRIPT",
                              "s3_bucket": svc.settings.evidence_bucket, "s3_key": transcript_key, "sha256": None,
                              "received_at_server": svc.clock(), "batch_id": None,
                              "uploaded_by_party_id": d["party_id"]})
            d["transcript_evidence_id"] = evid
    svc.repo.put(d)


def confirm_draft(svc, p, draft_id: str, body: dict) -> dict:
    d = svc.repo.get(f"DRAFT#{draft_id}")
    if not d:
        raise not_found("Draft not found or expired.")
    _owner_check(p, d)
    if d.get("status") != "READY":
        raise unprocessable("DRAFT_NOT_READY", "This draft is not ready yet.")
    x = dict(d["extraction"])
    edits = body.get("fields") or {}
    for k in ("count", "weight_kg", "source_category", "gas_type", "charge_kg"):
        if k in edits:
            x[k] = edits[k]
    if body.get("material"):
        x["material"] = body["material"]
    if body.get("weight_basis"):
        x["weight_basis"] = body["weight_basis"]
    if x.get("material") not in M.materials():
        raise unprocessable("MISSING_FIELD", "Please choose what was sold.")
    allowed = set(M.material(x["material"])["handover"]["required"]) | set(M.material(x["material"])["handover"].get("optional", []))
    fields = {k: x.get(k) for k in allowed if x.get(k) is not None}
    if not svc.repo.claim_token(f"DRAFT#{draft_id}", svc.clock(), svc._epoch()):
        raise gone("DRAFT_USED", "This draft was already confirmed or has expired.")
    resp = svc.create_handover(p, {
        "material": x["material"], "fields": fields, "weight_basis": x.get("weight_basis", "STATED"),
        "device_id": body.get("device_id") or d.get("device_id"), "at_device": body.get("at_device"),
        "evidence_ids": [d["transcript_evidence_id"]] if d.get("transcript_evidence_id") else [],
    })
    return resp
