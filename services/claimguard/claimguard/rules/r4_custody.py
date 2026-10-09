"""R4: chain of custody. SOLUTION.md section 6.

Produces ONE RuleResult for the claim (the worst finding wins), covering:
  - a batch cited by this claim is also cited by an earlier claim
    (double-claim; HARD, and only against the later claim: CONTRACT.md
    section 1's tie-break rule, so the first honest claim is never
    punished for someone else's later reuse);
  - an INTAKE event that happens before the batch's first HANDOVER
    (impossible order; HARD);
  - a SPLIT whose children's weights do not sum to the parent's within
    tolerance (SOFT; not exercised by the current demo batches, which all
    conserve).

Coverage itself is a metric (scores.py), never a flag outcome: citing no
batches, or batches with low weighed overlap, returns PASS here. Missing
data is not fraud (SOLUTION.md P2).
"""

from __future__ import annotations

from ..context import RuleContext
from ..model import Claim, EventType, RuleOutcome, RuleResult, Severity

RULE_ID = "R4"
RULE_VERSION = "1.0.0"
SPLIT_TOLERANCE_FRACTION = 0.02


def evaluate(claim: Claim, ctx: RuleContext) -> RuleResult:
    if not claim.batch_ids:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.PASS,
            severity=Severity.NONE,
            observed=0,
            limit=None,
            formula_rendered="No batches cited; chain-of-custody checks are vacuous. Coverage is tracked separately as a metric, not a flag.",
        )

    double_claim_detail = _check_double_claim(claim, ctx)
    if double_claim_detail is not None:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.FLAG,
            severity=Severity.HARD,
            observed=double_claim_detail["batch_id"],
            limit=None,
            formula_rendered=double_claim_detail["formula"],
            next_action="Ask the earlier claim's recycler to confirm which claim actually processed this batch.",
        )

    order_detail = _check_impossible_order(claim, ctx)
    if order_detail is not None:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.FLAG,
            severity=Severity.HARD,
            observed=order_detail["batch_id"],
            limit=None,
            formula_rendered=order_detail["formula"],
            next_action="Request the correct event timestamps or a correction event with a reason.",
        )

    split_detail = _check_split_conservation(claim, ctx)
    if split_detail is not None:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.FLAG,
            severity=Severity.SOFT,
            observed=split_detail["batch_id"],
            limit=None,
            formula_rendered=split_detail["formula"],
            next_action="Request the weigh slips for the parent batch and each child.",
        )

    return RuleResult(
        claim_id=claim.claim_id,
        rule_id=RULE_ID,
        rule_version=RULE_VERSION,
        outcome=RuleOutcome.PASS,
        severity=Severity.NONE,
        observed=len(claim.batch_ids),
        limit=None,
        formula_rendered=f"{len(claim.batch_ids)} batch(es) cited; no double-claim, order, or split-conservation issue found.",
    )


def _check_double_claim(claim: Claim, ctx: RuleContext) -> dict | None:
    for batch_id in claim.batch_ids:
        other_claim_ids = [
            c for c in ctx.claims_citing_batch.get(batch_id, []) if c != claim.claim_id
        ]
        if not other_claim_ids:
            continue
        this_t = ctx.claim_submitted_at.get(claim.claim_id)
        for other_id in other_claim_ids:
            other_t = ctx.claim_submitted_at.get(other_id)
            is_earlier = other_t is not None and this_t is not None and other_t < this_t
            is_earlier = is_earlier or (this_t is None and other_t is not None)
            if is_earlier:
                return {
                    "batch_id": batch_id,
                    "formula": (
                        f"batch {batch_id} is also cited by claim {other_id}, "
                        f"submitted before this claim ({other_t} < {this_t})."
                    ),
                }
    return None


def _check_impossible_order(claim: Claim, ctx: RuleContext) -> dict | None:
    if ctx.ledger_reader is None:
        return None
    for batch_id in claim.batch_ids:
        batch = ctx.ledger_reader.get_batch(batch_id)
        if batch is None:
            continue
        handover_times = [e.at_server for e in batch.events if e.type is EventType.HANDOVER]
        intake_times = [e.at_server for e in batch.events if e.type is EventType.INTAKE]
        if not handover_times or not intake_times:
            continue
        first_handover = min(handover_times)
        first_intake = min(intake_times)
        if first_intake < first_handover:
            return {
                "batch_id": batch_id,
                "formula": (
                    f"batch {batch_id}: intake at {first_intake} is before "
                    f"the first handover at {first_handover}."
                ),
            }
    return None


def _check_split_conservation(claim: Claim, ctx: RuleContext) -> dict | None:
    if ctx.ledger_reader is None:
        return None
    for batch_id in claim.batch_ids:
        batch = ctx.ledger_reader.get_batch(batch_id)
        if batch is None:
            continue
        for event in batch.events:
            if event.type is not EventType.SPLIT or not event.child_batch_ids:
                continue
            parent_weight_field = event.fields.get("weight_kg")
            if parent_weight_field is None:
                continue
            child_total = 0.0
            for child_id in event.child_batch_ids:
                child_batch = ctx.ledger_reader.get_batch(child_id)
                if child_batch is None:
                    continue
                for ce in child_batch.events:
                    if ce.type is EventType.SPLIT and "weight_kg" in ce.fields:
                        child_total += ce.fields["weight_kg"].value
            parent_weight = parent_weight_field.value
            if parent_weight and abs(child_total - parent_weight) > parent_weight * SPLIT_TOLERANCE_FRACTION:
                return {
                    "batch_id": batch_id,
                    "formula": (
                        f"batch {batch_id} split: children sum to {child_total:g} kg, "
                        f"parent was {parent_weight:g} kg "
                        f"(tolerance {SPLIT_TOLERANCE_FRACTION:.0%})."
                    ),
                }
    return None
