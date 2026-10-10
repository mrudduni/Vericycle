"""Pure rule engine: Claim + RuleContext -> list[RuleResult], plus scores.

No AWS imports anywhere in this module or the rules it calls. Lambda
handlers (../handlers/) call `run_claim` or `run_claim_set` and are the
only place boto3 appears.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import scores as scores_mod
from .context import RuleContext
from .model import Claim, EventType, RuleResult

from .rules import (
    r1_capacity,
    r2_mass_balance,
    r3_energy,
    r4_custody,
    r5_photo_light,
    r6_duplicates,
    r7_documents,
    r8_weight_drift,
)


def run_claim(claim: Claim, ctx: RuleContext) -> list[RuleResult]:
    """Runs every rule against one claim. Order does not affect results."""
    results: list[RuleResult] = []
    results.append(r1_capacity.evaluate(claim, ctx))
    results.extend(r2_mass_balance.evaluate(claim, ctx))
    results.append(r3_energy.evaluate(claim, ctx))
    results.append(r4_custody.evaluate(claim, ctx))
    results.extend(r5_photo_light.evaluate(claim, ctx))
    results.append(r6_duplicates.evaluate(claim, ctx))
    results.append(r7_documents.evaluate(claim, ctx))
    results.append(r8_weight_drift.evaluate(claim, ctx))
    return results


@dataclass(frozen=True)
class ClaimRun:
    claim: Claim
    rule_results: list[RuleResult]
    scores: "scores_mod.ClaimScores"


def build_claims_citing_batch(claims: list[Claim]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for claim in claims:
        for batch_id in claim.batch_ids:
            index.setdefault(batch_id, []).append(claim.claim_id)
    return index


def coverage_inputs(claim: Claim, ctx: RuleContext) -> tuple[float, float]:
    """(covered_kg, claimed_kg). Covered = weighed intake at this claim's
    recycler, across the claim's cited batches. Claimed = claim.input_t in kg.
    """
    claimed_kg = (claim.input_t or 0.0) * 1000.0
    covered_kg = 0.0
    if ctx.ledger_reader is None:
        return covered_kg, claimed_kg
    for batch_id in claim.batch_ids:
        batch = ctx.ledger_reader.get_batch(batch_id)
        if batch is None:
            continue
        intake_weights = [
            e.fields["weight_kg"].value
            for e in batch.events
            if e.type is EventType.INTAKE
            and e.actor_party_id == claim.recycler_party_id
            and "weight_kg" in e.fields
        ]
        if intake_weights:
            covered_kg += max(intake_weights)  # latest/most-reliable weighed intake
    return covered_kg, claimed_kg


def cited_handover_events(claim: Claim, ctx: RuleContext) -> list:
    if ctx.ledger_reader is None:
        return []
    events = []
    for batch_id in claim.batch_ids:
        batch = ctx.ledger_reader.get_batch(batch_id)
        if batch is None:
            continue
        events.extend(e for e in batch.events if e.type is EventType.HANDOVER)
    return events


def run_claim_set(
    claims: list[Claim],
    facilities_by_recycler: dict[str, object],
    sources,
    evidence: dict[str, object],
    ledger_reader,
    handover_asked_fields: dict[tuple[str, int], tuple[str, ...]] | None = None,
) -> dict[str, ClaimRun]:
    """Runs every claim in one set, so R4's double-claim check can see the
    whole set (as a real run would, via the claims table's GSI1)."""
    claims_citing_batch = build_claims_citing_batch(claims)
    submitted_at = {c.claim_id: c.submitted_at for c in claims}
    handover_asked_fields = handover_asked_fields or {}

    runs: dict[str, ClaimRun] = {}
    for claim in claims:
        ctx = RuleContext(
            facility=facilities_by_recycler.get(claim.recycler_party_id),
            sources=sources,
            evidence=evidence,
            claims_citing_batch=claims_citing_batch,
            claim_submitted_at=submitted_at,
            ledger_reader=ledger_reader,
        )
        results = run_claim(claim, ctx)
        covered_kg, claimed_kg = coverage_inputs(claim, ctx)
        events = cited_handover_events(claim, ctx)
        claim_scores = scores_mod.compute_scores(
            claim.claim_id, results, covered_kg, claimed_kg, events, handover_asked_fields
        )
        runs[claim.claim_id] = ClaimRun(claim=claim, rule_results=results, scores=claim_scores)
    return runs
