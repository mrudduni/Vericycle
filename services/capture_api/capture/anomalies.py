"""Confirmation anomaly checks (SHAURYA.md block 9, P2).

These are review signals only. They never change a confirmation status or a ClaimGuard outcome;
the dashboard shows them next to the record so a reviewer can look closer.

- FAST_CONFIRM: the seller's confirmation arrived less than FAST_SECONDS after the record was created.
  A real seller usually needs a minute to receive the link, open it and read it.
- DEVICE_FANOUT: the same phone (browser device id, or WhatsApp number HMAC) has confirmed for at
  least FANOUT_LIMIT different sellers. One person confirming "as the seller" for many sellers is the
  pattern a dishonest buyer would produce.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

FAST_SECONDS = 60
FANOUT_LIMIT = 3

TEXT = {
    "FAST_CONFIRM": {"en": "Seller confirmed {s} s after the record was made. Please check.",
                     "hi": "रिकॉर्ड बनने के {s} सेकंड बाद पुष्टि हुई। कृपया जाँचें।"},
    "DEVICE_FANOUT": {"en": "The phone that confirmed this has confirmed for {n} different sellers. Please check.",
                      "hi": "इस पुष्टि वाले फ़ोन ने {n} अलग-अलग विक्रेताओं के लिए पुष्टि की है। कृपया जाँचें।"},
}


def device_key(device_id: str | None, sender_hmac: str | None) -> str | None:
    raw = f"wa:{sender_hmac}" if sender_hmac else (f"dev:{device_id}" if device_id else None)
    return hashlib.sha256(raw.encode()).hexdigest()[:32] if raw else None


def record_confirmation(repo, *, batch_id: str, seq: int, handler_id: str, key: str | None) -> dict | None:
    """Remember which handlers this device confirmed for; return a DEVICE_FANOUT flag if over the limit."""
    if not key:
        return None
    n = repo.add_to_set(f"CONFDEV#{key}", "handlers", handler_id)
    if n < FANOUT_LIMIT:
        return None
    flag = {"code": "DEVICE_FANOUT", "seq": seq, "n": n, "text": {k: v.format(n=n) for k, v in TEXT["DEVICE_FANOUT"].items()}}
    item = repo.get(f"ANOMALY#{batch_id}") or {"PK": f"ANOMALY#{batch_id}", "SK": "META", "flags": []}
    item["flags"] = [f for f in item["flags"] if not (f["code"] == "DEVICE_FANOUT" and f["seq"] == seq)] + [flag]
    repo.put(item)
    return flag


def fast_confirm_flags(events: list[dict]) -> list[dict]:
    """Derived from the ledger alone, so anyone re-reading the chain gets the same answer."""
    created = {e["seq"]: datetime.fromisoformat(e["at_server"]) for e in events if e["type"] == "HANDOVER"}
    out, seen = [], set()
    for e in events:
        f = e.get("fields", {})
        if e["type"] != "CORRECTION" or (f.get("reason") or {}).get("value") != "HANDLER_CONFIRMED":
            continue
        seq = (f.get("corrects_seq") or {}).get("value")
        if seq not in created or seq in seen:
            continue
        secs = int((datetime.fromisoformat(e["at_server"]) - created[seq]).total_seconds())
        if secs < FAST_SECONDS:
            seen.add(seq)
            out.append({"code": "FAST_CONFIRM", "seq": seq, "seconds": secs,
                        "text": {k: v.format(s=secs) for k, v in TEXT["FAST_CONFIRM"].items()}})
    return out


def flags_for(repo, batch_id: str, events: list[dict]) -> list[dict]:
    stored = (repo.get(f"ANOMALY#{batch_id}") or {}).get("flags", [])
    return fast_confirm_flags(events) + list(stored)
