"""Reads batches and events, from a fixture file today or DynamoDB tomorrow.

CONTRACT.md section 2: on 10 October, Mrudduni's app runs in fixture mode.
On 11 October, `-c ledgerStage=<stage>` switches rules to read Shaurya's
live ledger table. Both readers implement the same `LedgerReader` protocol,
so no rule code changes between the two days.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Protocol

from .model import (
    Basis,
    Batch,
    ConfirmationChannel,
    Event,
    EventType,
    FieldValue,
    Material,
    Role,
)

DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "fixtures" / "ledger_events.json"
)


class LedgerReader(Protocol):
    def get_batch(self, batch_id: str) -> Batch | None: ...

    def all_batches(self) -> list[Batch]: ...

    def batches_citing_lead(self) -> dict[str, list[str]]:
        """batch_id -> list of claim_ids that cite it. Used by R4's double-claim check.

        A real implementation reads this from the claims table's GSI1, not
        the ledger. The fixture version takes it as an explicit argument
        instead, since a fixture has no claims table to query.
        """
        ...


def parse_field(fv: dict) -> FieldValue:
    return FieldValue(
        value=fv["value"],
        unit=fv.get("unit"),
        asserted_by_role=Role(fv["asserted_by_role"]),
        confirmed_by_roles=tuple(Role(r) for r in fv.get("confirmed_by_roles", [])),
        confirmation_channel=ConfirmationChannel(fv.get("confirmation_channel") or "NONE"),
        basis=Basis(fv.get("basis", "STATED")),
    )


def parse_event(batch_id: str, raw: dict) -> Event:
    return Event(
        batch_id=batch_id,
        seq=raw["seq"],
        type=EventType(raw["type"]),
        material=Material(raw["material"]),
        at_device=_parse_dt(raw["at_device"]),
        at_server=_parse_dt(raw["at_server"]),
        actor_party_id=raw["actor_party_id"],
        counterparty_party_id=raw.get("counterparty_party_id"),
        parent_batch_ids=tuple(raw.get("parent_batch_ids", [])),
        child_batch_ids=tuple(raw.get("child_batch_ids", [])),
        fields={name: parse_field(fv) for name, fv in raw.get("fields", {}).items()},
        evidence_ids=tuple(raw.get("evidence_ids", [])),
        geohash5=raw.get("geohash5"),
        prev_hash=raw.get("prev_hash", ""),
        hash=raw.get("hash", ""),
        kms_sig=raw.get("kms_sig"),
    )


def effective_events(events: tuple[Event, ...]) -> tuple[Event, ...]:
    """Apply handler CORRECTION events (Shaurya's proposed contract addition, status.py): a
    HANDLER_CONFIRMED correction replaces one field of the event it corrects, with the full
    updated FieldValue. A HANDLER_REJECTED correction is ignored here (shown by the capture UI).
    Originals are never mutated; CORRECTION events stay in the list."""
    by_seq = {e.seq: e for e in events}
    for e in sorted(events, key=lambda e: e.seq):
        if e.type is not EventType.CORRECTION:
            continue
        f = e.fields
        reason = f["reason"].value if "reason" in f else None
        if reason != "HANDLER_CONFIRMED":
            continue
        target = by_seq.get(f["corrects_seq"].value)
        name, new = f["field"].value, f["new_value"].value
        if target is None or name not in target.fields or not isinstance(new, dict):
            continue
        by_seq[target.seq] = replace(target, fields={**target.fields, name: parse_field(new)})
    return tuple(by_seq[e.seq] for e in events)


def _parse_dt(s: str):
    from datetime import datetime

    return datetime.fromisoformat(s)


class FixtureLedgerReader:
    """Reads docs/team/CONTRACT.md section 8's demo batches from a JSON file.

    File shape: {"batches": {"<batch_id>": {"material": "...",
    "events": [ <event dict, CONTRACT §5 shape> , ... ]}}}
    """

    def __init__(self, path: Path | str | None = None):
        p = Path(path) if path else DEFAULT_FIXTURE_PATH
        raw = json.loads(p.read_text(encoding="utf-8"))
        self._batches: dict[str, Batch] = {}
        for batch_id, b in raw.get("batches", {}).items():
            events = tuple(
                parse_event(batch_id, e) for e in sorted(b["events"], key=lambda e: e["seq"])
            )
            self._batches[batch_id] = Batch(
                batch_id=batch_id,
                material=Material(b["material"]),
                events=events,
                parent_ids=tuple(b.get("parent_ids", [])),
                child_ids=tuple(b.get("child_ids", [])),
                status=b.get("status", "OPEN"),
            )

    def get_batch(self, batch_id: str) -> Batch | None:
        return self._batches.get(batch_id)

    def all_batches(self) -> list[Batch]:
        return list(self._batches.values())

    def batches_citing_lead(self) -> dict[str, list[str]]:
        # The fixture has no claims table; engine.py supplies this
        # separately when running the full claim set (see run_claim_set).
        return {}
