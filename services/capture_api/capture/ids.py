"""Identifiers (CONTRACT §4)."""
from __future__ import annotations

import os
import secrets
import time

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _b32(n: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(CROCKFORD[n & 31])
        n >>= 5
    return "".join(reversed(out))


def ulid() -> str:
    return _b32(int(time.time() * 1000), 10) + _b32(int.from_bytes(os.urandom(10), "big"), 16)


def batch_id(prefix: str) -> str:
    return f"{prefix}-{_b32(secrets.randbits(40), 8)}"


def evidence_id() -> str:
    return f"EV-{ulid()}"


def token() -> str:
    """22-char URL-safe random (CONTRACT §4)."""
    return secrets.token_urlsafe(16)[:22]


def handler_id(phone_hmac: str | None = None) -> str:
    return f"HND-{(phone_hmac or secrets.token_hex(3))[:6].lower()}"


def short_code() -> str:
    """6-char code for the wa.me 'HAAN <code>' confirmation (no 0/O/1/I confusion)."""
    alphabet = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    return "".join(secrets.choice(alphabet) for _ in range(6))
