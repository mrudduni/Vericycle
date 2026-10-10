"""append_event(): the only way an event enters the ledger.

Steps (SHAURYA.md 3.2):
1. Read the batch head (``last_seq``, ``last_hash``).
2. ``seq = last_seq + 1``, ``prev_hash = last_hash``, ``at_server`` = server clock now.
3. Compute ``hash`` (CONTRACT §5) and sign it.
4. One transaction: put the event with ``attribute_not_exists(PK)`` and update the head on
   condition ``last_seq = :expected``. On a condition failure, retry from step 1 (max 3).

Event items are never updated or deleted. Corrections are CORRECTION events.
"""
from __future__ import annotations

import copy
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Protocol

from .canonical import GENESIS_HASH, compute_hash, normalize
from .signing import Signer

IST = timezone(timedelta(hours=5, minutes=30))
MAX_ATTEMPTS = 3

# Set by the writer; a caller can never supply them.
_SERVER_OWNED = ("seq", "prev_hash", "hash", "kms_sig")


def now_ist() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


class ConflictError(Exception):
    """The head moved between read and write (another writer won)."""


class LedgerBusyError(Exception):
    """Gave up after MAX_ATTEMPTS conflicts."""


@dataclass
class Head:
    last_seq: int = 0
    last_hash: str = GENESIS_HASH
    exists: bool = False
    attrs: dict = field(default_factory=dict)


class Store(Protocol):
    def get_head(self, batch_id: str) -> Head: ...
    def append(self, event: dict, expected_last_seq: int, head_updates: Mapping[str, Any]) -> None:
        """Atomically put the event and advance the head. Raise ConflictError if last_seq moved."""


def build_event(
    batch_id: str,
    body: Mapping[str, Any],
    head: Head,
    signer: Signer,
    at_server: str,
) -> dict:
    event = copy.deepcopy(dict(body))
    for k in _SERVER_OWNED:
        event.pop(k, None)
    event.setdefault("parent_batch_ids", [])
    event.setdefault("child_batch_ids", [])
    event.setdefault("evidence_ids", [])
    event.setdefault("geohash5", None)
    event.setdefault("counterparty_party_id", None)
    event["batch_id"] = batch_id
    event["seq"] = head.last_seq + 1
    event["at_server"] = at_server
    event["prev_hash"] = head.last_hash
    event = normalize(event)
    event["hash"] = compute_hash(event["prev_hash"], event)
    event["kms_sig"] = signer.sign(event["hash"])
    return event


def append_event(
    store: Store,
    signer: Signer,
    batch_id: str,
    body: Mapping[str, Any],
    *,
    head_updates: Mapping[str, Any] | None = None,
    clock: Callable[[], str] = now_ist,
    at_server: str | None = None,
) -> dict:
    """Append one event to ``batch_id`` and return the stored event.

    ``at_server`` may be fixed only by trusted seed scripts; the API always uses ``clock``.
    ``head_updates`` are extra batch-head attributes (status, material, lineage, receipt_token).
    """
    for attempt in range(MAX_ATTEMPTS):
        head = store.get_head(batch_id)
        event = build_event(batch_id, body, head, signer, at_server or clock())
        updates = dict(head_updates or {})
        updates.setdefault("material", event.get("material"))
        try:
            store.append(event, expected_last_seq=head.last_seq, head_updates=updates)
            return event
        except ConflictError:
            time.sleep(random.uniform(0.005, 0.03) * (attempt + 1))  # jitter so racing writers spread out
            continue
    raise LedgerBusyError(f"{batch_id}: head kept moving after {MAX_ATTEMPTS} attempts")


class MemoryStore:
    """Thread-safe in-memory Store with the same conditional semantics as DynamoDB. For tests."""

    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()
        self.events: dict[str, dict[int, dict]] = {}
        self.heads: dict[str, dict] = {}

    def get_head(self, batch_id: str) -> Head:
        with self._lock:
            h = self.heads.get(batch_id)
            if not h:
                return Head()
            return Head(h["last_seq"], h["last_hash"], True, dict(h))

    def append(self, event: dict, expected_last_seq: int, head_updates: Mapping[str, Any]) -> None:
        with self._lock:
            b = event["batch_id"]
            current = self.heads.get(b, {}).get("last_seq", 0)
            if current != expected_last_seq or event["seq"] in self.events.get(b, {}):
                raise ConflictError(b)
            self.events.setdefault(b, {})[event["seq"]] = copy.deepcopy(event)
            head = self.heads.setdefault(b, {"status": "OPEN", "parent_batch_ids": [], "child_batch_ids": []})
            head.update({k: v for k, v in head_updates.items() if v is not None})
            head["last_seq"] = event["seq"]
            head["last_hash"] = event["hash"]

    def list_events(self, batch_id: str) -> list[dict]:
        with self._lock:
            return [copy.deepcopy(e) for _, e in sorted(self.events.get(batch_id, {}).items())]
