"""RuleContext: everything a rule needs besides the Claim itself.

Built once per claim run by engine.py, passed to every rule's evaluate().
Rules never reach into AWS, a file, or a database directly; they only read
from this object, which is why they stay unit-testable offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import Evidence, Facility
from .sources import SourcesRegistry


@dataclass
class RuleContext:
    facility: Facility | None
    sources: SourcesRegistry
    evidence: dict[str, Evidence] = field(default_factory=dict)
    # batch_id -> claim_ids that cite it, across the whole claim set this run
    # knows about (fixture: passed in explicitly; live: read from the claims
    # table's GSI1). Used by R4's double-claim check.
    claims_citing_batch: dict[str, list[str]] = field(default_factory=dict)
    # claim_id -> submitted_at, for the same check's tie-break rule.
    claim_submitted_at: dict[str, object] = field(default_factory=dict)
    ledger_reader: object = None
    # R9 only: callable (lat, lon, start_date, end_date) -> list[dict] of clear-sky observations (see rules/r9_satellite.py).
    satellite: object = None
