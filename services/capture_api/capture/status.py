"""Confirmation status, derived and never stored (CONTRACT §3).

Live confirmations arrive after the HANDOVER is written. Events are immutable (P8), so a
confirmation is a CORRECTION event (actor = handler) whose ``new_value`` is the updated
FieldValue; ``effective_events`` applies corrections in seq order before deriving status.
(PROPOSED contract addition: pending Shaurya/Mrudduni agreement.)
"""
from __future__ import annotations

import copy
from typing import Iterable

OWN_DEVICE = {"OWN_DEVICE_WHATSAPP", "OWN_DEVICE_SMS", "OWN_DEVICE_LINK"}
CONFIRM_REASONS = {"HANDLER_CONFIRMED"}
REJECT_REASON = "HANDLER_REJECTED"


def field_status(fv: dict) -> str:
    if "HANDLER" in (fv.get("confirmed_by_roles") or []):
        if fv.get("confirmation_channel") in OWN_DEVICE:
            return "HANDLER_CONFIRMED"
        if fv.get("confirmation_channel") == "SAME_DEVICE":
            return "SAME_DEVICE_CONFIRMED"
    return "BUYER_REPORTED"


def event_status(event: dict, asked_fields: Iterable[str]) -> str:
    asked = [f for f in asked_fields if f in event.get("fields", {})]
    statuses = [field_status(event["fields"][f]) for f in asked]
    confirmed = sum(s == "HANDLER_CONFIRMED" for s in statuses)
    if asked and confirmed == len(asked):
        return "BOTH_PARTIES_CONFIRMED"
    if confirmed:
        return "HANDLER_CONFIRMED"
    return "BUYER_REPORTED"


def evidence_badge(event: dict) -> str:
    return "EVIDENCE_ATTACHED" if event.get("evidence_ids") else "EVIDENCE_MISSING"


def _val(fv):
    return fv.get("value") if isinstance(fv, dict) else fv


def effective_events(events: list[dict]) -> list[dict]:
    """Events with CORRECTIONs applied to the event they correct (originals untouched)."""
    out = [copy.deepcopy(e) for e in sorted(events, key=lambda e: e["seq"])]
    by_seq = {e["seq"]: e for e in out}
    for e in out:
        if e["type"] != "CORRECTION":
            continue
        f = e["fields"]
        target = by_seq.get(_val(f.get("corrects_seq")))
        if not target:
            continue
        name, reason = _val(f.get("field")), _val(f.get("reason"))
        if reason == REJECT_REASON:
            target["handler_rejected"] = True
        elif name in target.get("fields", {}) and isinstance(_val(f.get("new_value")), dict):
            target["fields"][name] = _val(f.get("new_value"))
    return out


def asked_fields(event: dict, material_cfg: dict) -> list[str]:
    """For a HANDOVER: count, source_category and, if stated, weight_kg (CONTRACT §3)."""
    names = []
    for n in material_cfg["handover"]["confirm_fields"]:
        fv = event.get("fields", {}).get(n)
        if fv is None:
            continue
        if n == "weight_kg" and fv.get("basis") != "STATED":
            continue
        names.append(n)
    return names


CHIP_TEXT = {
    "HANDLER_CONFIRMED": {"en": "Seller confirmed on own phone", "hi": "विक्रेता ने अपने फ़ोन से पुष्टि की"},
    "BOTH_PARTIES_CONFIRMED": {"en": "Seller confirmed on own phone", "hi": "विक्रेता ने अपने फ़ोन से पुष्टि की"},
    "SAME_DEVICE_CONFIRMED": {"en": "Confirmed on buyer's phone (not independent)", "hi": "ख़रीदार के फ़ोन पर पुष्टि (स्वतंत्र नहीं)"},
    "BUYER_REPORTED": {"en": "Entered by buyer only", "hi": "सिर्फ़ ख़रीदार ने दर्ज किया"},
}
