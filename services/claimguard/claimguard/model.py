"""Data model shared with ChainTrack, per docs/team/CONTRACT.md sections 3, 5, 7.

These are the enums and shapes ClaimGuard reads. They mirror the ledger's
event schema exactly, so a fixture file and a live DynamoDB read produce
identical objects here. Do not add enum members without updating
CONTRACT.md first (section 0 of docs/team/MRUDDUNI.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Material(str, Enum):
    BATTERY_LEAD_ACID = "BATTERY_LEAD_ACID"
    EWASTE_PHONE = "EWASTE_PHONE"
    AC_REFRIGERANT = "AC_REFRIGERANT"


class ClaimProduct(str, Enum):
    """Deliberately has no AC_REFRIGERANT member. See CONTRACT §3 and §7.

    A refrigerant claim cannot be represented. This is requirement 6 of
    problem_statement.md, enforced at the type level, not by a runtime check
    alone (though the API also rejects it explicitly for a clear error).
    """

    BATTERY_LEAD_ACID = "BATTERY_LEAD_ACID"
    EWASTE_PHONE = "EWASTE_PHONE"


class Role(str, Enum):
    HANDLER = "HANDLER"
    COLLECTOR = "COLLECTOR"
    AGGREGATOR = "AGGREGATOR"
    RECYCLER = "RECYCLER"
    AUDITOR = "AUDITOR"
    PRODUCER = "PRODUCER"


class EventType(str, Enum):
    HANDOVER = "HANDOVER"
    TRANSFER = "TRANSFER"
    SPLIT = "SPLIT"
    MERGE = "MERGE"
    INTAKE = "INTAKE"
    PROCESS = "PROCESS"
    OUTPUT = "OUTPUT"
    CORRECTION = "CORRECTION"


class Basis(str, Enum):
    STATED = "STATED"
    WEIGHED = "WEIGHED"
    OCR = "OCR"
    COMPUTED = "COMPUTED"


class ConfirmationChannel(str, Enum):
    OWN_DEVICE_WHATSAPP = "OWN_DEVICE_WHATSAPP"
    OWN_DEVICE_SMS = "OWN_DEVICE_SMS"
    OWN_DEVICE_LINK = "OWN_DEVICE_LINK"
    SAME_DEVICE = "SAME_DEVICE"
    NONE = "NONE"


OWN_DEVICE_CHANNELS = {
    ConfirmationChannel.OWN_DEVICE_WHATSAPP,
    ConfirmationChannel.OWN_DEVICE_SMS,
    ConfirmationChannel.OWN_DEVICE_LINK,
}


class SourceCategory(str, Enum):
    DRIVER = "DRIVER"
    HOUSEHOLD = "HOUSEHOLD"
    TECHNICIAN = "TECHNICIAN"
    RETAIL_EXCHANGE = "RETAIL_EXCHANGE"
    INSTITUTION = "INSTITUTION"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class EvidenceKind(str, Enum):
    PHOTO = "PHOTO"
    WEIGH_SLIP = "WEIGH_SLIP"
    INVOICE = "INVOICE"
    POWER_BILL = "POWER_BILL"
    VOICE_TRANSCRIPT = "VOICE_TRANSCRIPT"


class RuleOutcome(str, Enum):
    PASS = "PASS"
    FLAG = "FLAG"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    INCONCLUSIVE = "INCONCLUSIVE"


class Severity(str, Enum):
    HARD = "HARD"
    SOFT = "SOFT"
    NONE = "NONE"


class ReviewAction(str, Enum):
    ACCEPT = "ACCEPT"
    REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
    ESCALATE = "ESCALATE"
    RECYCLER_RESPONSE = "RECYCLER_RESPONSE"


class FieldConfirmationStatus(str, Enum):
    """Per-field status. Computed, never stored. CONTRACT §3."""

    HANDLER_CONFIRMED = "HANDLER_CONFIRMED"
    SAME_DEVICE_CONFIRMED = "SAME_DEVICE_CONFIRMED"
    BUYER_REPORTED = "BUYER_REPORTED"


class EventConfirmationStatus(str, Enum):
    """Per-event status, over the fields the confirmation token asked about."""

    BOTH_PARTIES_CONFIRMED = "BOTH_PARTIES_CONFIRMED"
    HANDLER_CONFIRMED = "HANDLER_CONFIRMED"
    BUYER_REPORTED = "BUYER_REPORTED"


@dataclass(frozen=True)
class FieldValue:
    value: Any
    asserted_by_role: Role
    confirmed_by_roles: tuple[Role, ...] = ()
    confirmation_channel: ConfirmationChannel = ConfirmationChannel.NONE
    basis: Basis = Basis.STATED
    unit: str | None = None

    def field_status(self) -> FieldConfirmationStatus:
        if Role.HANDLER not in self.confirmed_by_roles:
            return FieldConfirmationStatus.BUYER_REPORTED
        if self.confirmation_channel in OWN_DEVICE_CHANNELS:
            return FieldConfirmationStatus.HANDLER_CONFIRMED
        if self.confirmation_channel is ConfirmationChannel.SAME_DEVICE:
            return FieldConfirmationStatus.SAME_DEVICE_CONFIRMED
        return FieldConfirmationStatus.BUYER_REPORTED


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    kind: EvidenceKind
    s3_key: str
    sha256: str
    received_at_server: datetime
    phash: str | None = None
    exif: dict[str, Any] = field(default_factory=dict)
    extracted: dict[str, Any] = field(default_factory=dict)
    batch_id: str | None = None
    """Which batch this evidence documents, if any. R6 uses this to tell a
    photo attached once to one batch apart from the same file reused on a
    different batch, which is what the rule actually flags."""


@dataclass(frozen=True)
class Event:
    batch_id: str
    seq: int
    type: EventType
    material: Material
    at_device: datetime
    at_server: datetime
    actor_party_id: str
    prev_hash: str
    hash: str
    counterparty_party_id: str | None = None
    parent_batch_ids: tuple[str, ...] = ()
    child_batch_ids: tuple[str, ...] = ()
    fields: dict[str, FieldValue] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    geohash5: str | None = None
    kms_sig: str | None = None

    def event_confirmation_status(
        self, asked_field_names: tuple[str, ...]
    ) -> EventConfirmationStatus:
        """CONTRACT §3: per-event status over the fields a token asked about."""
        asked = [self.fields[n] for n in asked_field_names if n in self.fields]
        if not asked:
            return EventConfirmationStatus.BUYER_REPORTED
        statuses = [f.field_status() for f in asked]
        if all(s is FieldConfirmationStatus.HANDLER_CONFIRMED for s in statuses):
            return EventConfirmationStatus.BOTH_PARTIES_CONFIRMED
        if any(s is FieldConfirmationStatus.HANDLER_CONFIRMED for s in statuses):
            return EventConfirmationStatus.HANDLER_CONFIRMED
        return EventConfirmationStatus.BUYER_REPORTED


@dataclass(frozen=True)
class Batch:
    batch_id: str
    material: Material
    events: tuple[Event, ...]
    parent_ids: tuple[str, ...] = ()
    child_ids: tuple[str, ...] = ()
    status: str = "OPEN"


@dataclass(frozen=True)
class Facility:
    recycler_party_id: str
    rated_t_per_hr: float | None
    hours_per_day: float | None
    operating_days: int | None
    licensed_t_per_yr: float | None
    lat: float | None = None
    lon: float | None = None
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Claim:
    claim_id: str
    recycler_party_id: str
    product: ClaimProduct
    period_start: datetime
    period_end: datetime
    input_t: float | None
    processed_t: float | None
    output: dict[str, float] = field(default_factory=dict)  # metal -> tonnes
    batch_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    opening_stock_t: float | None = None
    closing_stock_t: float | None = None
    documented_losses_t: float | None = None
    electricity_kwh: float | None = None
    diesel_generator_logged: bool = False
    producer_party_ids: tuple[str, ...] = ()
    """Producers (brands) whose products this claim covers; Cedar's producer-read-citing-claim policy reads it."""
    submitted_at: datetime | None = None
    """When this claim was submitted. R4's double-claim check flags whichever
    claim cites a batch *later* than the earliest claim to cite it, so the
    first claim to use a batch is never punished for a later claim's reuse."""


@dataclass(frozen=True)
class RuleResult:
    claim_id: str
    rule_id: str
    rule_version: str
    outcome: RuleOutcome
    severity: Severity
    observed: Any
    limit: Any
    formula_rendered: str
    evidence_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    demo_value: bool = False
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "outcome": self.outcome.value,
            "severity": self.severity.value,
            "observed": self.observed,
            "limit": self.limit,
            "formula_rendered": self.formula_rendered,
            "evidence_ids": list(self.evidence_ids),
            "source_ids": list(self.source_ids),
            "demo_value": self.demo_value,
            "next_action": self.next_action,
        }


class RefrigerantClaimError(ValueError):
    """Raised if anything tries to build a Claim with a refrigerant product.

    ClaimProduct has no AC_REFRIGERANT member, so the common path is a
    ValueError from the enum constructor already. This exception exists so
    API handlers can catch one specific, named thing and return a clear
    422 instead of a bare traceback.
    """
