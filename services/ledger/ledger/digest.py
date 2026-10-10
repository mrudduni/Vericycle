"""Daily Merkle digest of ledger events (SHAURYA.md 3.2).

Leaves: the ``hash`` of every event whose ``at_server`` falls on the IST date, ordered by
``(at_server, batch_id, seq)``. Parent = SHA-256(left || right) over raw 32-byte values;
when a level has an odd count the last node is duplicated. Root of zero events = 64 zeros.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from .canonical import GENESIS_HASH, event_from_item

IST = timezone(timedelta(hours=5, minutes=30))


def merkle_root(leaf_hashes: list[str]) -> str:
    if not leaf_hashes:
        return GENESIS_HASH
    level = [bytes.fromhex(h) for h in leaf_hashes]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0].hex()


def ist_date(at_server: str) -> date:
    return datetime.fromisoformat(at_server).astimezone(IST).date()


def events_for_day(events: Iterable[Mapping[str, Any]], day: date) -> list[dict]:
    evs = [event_from_item(e) for e in events]
    evs = [e for e in evs if ist_date(e["at_server"]) == day]
    evs.sort(key=lambda e: (datetime.fromisoformat(e["at_server"]), e["batch_id"], e["seq"]))
    return evs


def build_digest(events: Iterable[Mapping[str, Any]], day: date, signer=None) -> dict:
    evs = events_for_day(events, day)
    root = merkle_root([e["hash"] for e in evs])
    ref = lambda e: {"batch_id": e["batch_id"], "seq": e["seq"], "hash": e["hash"]}  # noqa: E731
    doc = {
        "date": day.isoformat(),
        "root": root,
        "count": len(evs),
        "first": ref(evs[0]) if evs else None,
        "last": ref(evs[-1]) if evs else None,
        "algorithm": "sha256-merkle, duplicate-last-leaf; signature ECDSA_SHA_256 over root as digest",
    }
    doc["signature"] = signer.sign(root) if signer else None
    return doc
