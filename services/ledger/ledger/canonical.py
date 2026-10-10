"""Canonical JSON and hash chain, exactly as CONTRACT.md section 5.

1. Remove ``hash`` and ``kms_sig`` from the event.
2. ``json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`` as UTF-8.
   Integers as integers; non-integers as decimals with no trailing zeros
   (DynamoDB ``Decimal`` is converted back to ``int`` or ``float`` first).
3. ``hash = sha256(bytes.fromhex(prev_hash) + canonical).hexdigest()``.
4. ``prev_hash`` of seq 1 is 64 zeros.

Interpretation (flagged to Shaurya): a float with an integral value (``120.0``) is
written as the integer ``120``, so a value read back from DynamoDB as ``Decimal("120")``
hashes the same as the ``120.0`` the client sent.
"""
from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from typing import Any, Mapping

GENESIS_HASH = "0" * 64

# Every top-level attribute of an event (CONTRACT §5). Anything else on a stored
# item (PK, SK, GSI2PK, GSI2SK) is storage plumbing and is not hashed.
EVENT_KEYS = (
    "batch_id", "seq", "type", "material", "at_device", "at_server",
    "actor_party_id", "counterparty_party_id", "parent_batch_ids", "child_batch_ids",
    "fields", "evidence_ids", "geohash5", "prev_hash", "hash", "kms_sig",
)
_EXCLUDED_FROM_HASH = ("hash", "kms_sig")


def _number(value: Decimal | float) -> int | float:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("NaN and infinity are not allowed in events")
        integral = value == value.to_integral_value()
    else:
        if not math.isfinite(value):
            raise ValueError("NaN and infinity are not allowed in events")
        integral = value.is_integer()
    return int(value) if integral else float(value)


def normalize(obj: Any) -> Any:
    """Return a JSON-ready copy: Decimals and integral floats become ints, sets become sorted lists."""
    if isinstance(obj, bool) or obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, (Decimal, float)):
        return _number(obj)
    if isinstance(obj, Mapping):
        return {str(k): normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [normalize(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(normalize(v) for v in obj)
    raise TypeError(f"Unsupported type in event: {type(obj).__name__}")


def event_from_item(item: Mapping[str, Any]) -> dict:
    """Strip storage keys from a DynamoDB event item and normalise numbers."""
    return normalize({k: item[k] for k in EVENT_KEYS if k in item})


def canonical_bytes(event: Mapping[str, Any]) -> bytes:
    body = {k: v for k, v in event.items() if k not in _EXCLUDED_FROM_HASH}
    return json.dumps(normalize(body), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_hash(prev_hash: str, event: Mapping[str, Any]) -> str:
    if len(prev_hash) != 64:
        raise ValueError("prev_hash must be 64 hex characters")
    return hashlib.sha256(bytes.fromhex(prev_hash) + canonical_bytes(event)).hexdigest()
