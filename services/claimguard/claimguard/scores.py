"""Three scores per claim, kept separate. SOLUTION.md P4 and F7.

Never combine these into one number, anywhere: not in this module, not in
an API response, not in the UI. A single "fraud score" is exactly what
SOLUTION.md section 19 rejects ("Why not an ML fraud score?").
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import (
    Event,
    FieldConfirmationStatus,
    RuleOutcome,
    RuleResult,
)

PHYSICAL_RULE_IDS = {"R1", "R2", "R3"}


@dataclass(frozen=True)
class EvidenceQualityCounts:
    handler_confirmed: int = 0
    same_device_confirmed: int = 0
    buyer_reported: int = 0

    @property
    def total(self) -> int:
        return self.handler_confirmed + self.same_device_confirmed + self.buyer_reported


@dataclass(frozen=True)
class ClaimScores:
    physical_consistency: float | None  # 0..1, or None if no physical rules ran
    physical_consistency_capped_by_hard_flag: bool
    traceability_coverage: float  # 0..1, always computable (0 when no batches)
    covered_kg: float
    claimed_kg: float
    evidence_quality: EvidenceQualityCounts
    evidence_quality_rule_outcomes: dict[str, RuleOutcome]  # R5, R6, R7 by rule_id


def physical_consistency_score(rule_results: list[RuleResult]) -> tuple[float | None, bool]:
    """Share of R1-R3 that PASS; capped at 0 if any of them is a HARD flag."""
    relevant = [r for r in rule_results if r.rule_id in PHYSICAL_RULE_IDS]
    decidable = [r for r in relevant if r.outcome in (RuleOutcome.PASS, RuleOutcome.FLAG)]
    if not decidable:
        return None, False
    hard_flag = any(
        r.outcome is RuleOutcome.FLAG and r.severity.value == "HARD" for r in decidable
    )
    if hard_flag:
        return 0.0, True
    passed = sum(1 for r in decidable if r.outcome is RuleOutcome.PASS)
    return passed / len(decidable), False


def traceability_coverage(covered_kg: float, claimed_kg: float) -> float:
    if claimed_kg <= 0:
        return 0.0
    return min(covered_kg, claimed_kg) / claimed_kg


def evidence_quality_counts(
    cited_events: list[Event], asked_fields_by_event: dict[tuple[str, int], tuple[str, ...]]
) -> EvidenceQualityCounts:
    """Counts handovers by their field confirmation status (CONTRACT §3)."""
    handler = same_device = buyer = 0
    for event in cited_events:
        asked = asked_fields_by_event.get((event.batch_id, event.seq), ())
        if not asked:
            continue
        statuses = [event.fields[n].field_status() for n in asked if n in event.fields]
        if not statuses:
            continue
        if any(s is FieldConfirmationStatus.HANDLER_CONFIRMED for s in statuses):
            handler += 1
        elif any(s is FieldConfirmationStatus.SAME_DEVICE_CONFIRMED for s in statuses):
            same_device += 1
        else:
            buyer += 1
    return EvidenceQualityCounts(handler, same_device, buyer)


def compute_scores(
    claim_id: str,
    rule_results: list[RuleResult],
    covered_kg: float,
    claimed_kg: float,
    cited_events: list[Event],
    asked_fields_by_event: dict[tuple[str, int], tuple[str, ...]],
) -> ClaimScores:
    phys, capped = physical_consistency_score(rule_results)
    coverage = traceability_coverage(covered_kg, claimed_kg)
    eq_counts = evidence_quality_counts(cited_events, asked_fields_by_event)
    eq_rules = {
        r.rule_id: r.outcome
        for r in rule_results
        if r.rule_id in ("R5", "R6", "R7") and r.claim_id == claim_id
    }
    return ClaimScores(
        physical_consistency=phys,
        physical_consistency_capped_by_hard_flag=capped,
        traceability_coverage=coverage,
        covered_kg=covered_kg,
        claimed_kg=claimed_kg,
        evidence_quality=eq_counts,
        evidence_quality_rule_outcomes=eq_rules,
    )
