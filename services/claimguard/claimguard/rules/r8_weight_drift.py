"""R8: weight drift along the chain. SOLUTION.md section 6. SOFT.

Compares weighed kg at each hop in a cited batch's ledger history to the
previous hop. A drop is allowed up to a configurable fraction (electrolyte
draining from a battery, moisture loss, is a legitimate reason a battery
weighs less at the recycler than at the first handover). A gain above
tolerance is flagged; there is no legitimate reason a batch gains weight
on its way to the recycler.

Only hops with a WEIGHED basis are compared; if every weight along a
batch's history is STATED (never actually weighed), the result is
INCONCLUSIVE, not a flag: a difference between two unverified numbers
proves nothing.
"""

from __future__ import annotations

from ..context import RuleContext
from ..model import Basis, Claim, RuleOutcome, RuleResult, Severity

RULE_ID = "R8"
RULE_VERSION = "1.0.0"
MAX_ALLOWED_DROP_FRACTION = 0.08
MAX_ALLOWED_GAIN_FRACTION = 0.01


def evaluate(claim: Claim, ctx: RuleContext) -> RuleResult:
    if not claim.batch_ids or ctx.ledger_reader is None:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.INSUFFICIENT_EVIDENCE,
            severity=Severity.SOFT,
            observed=None,
            limit=None,
            formula_rendered="No cited batches to check weight drift on.",
        )

    findings: list[str] = []
    any_weighed_pair = False
    for batch_id in claim.batch_ids:
        batch = ctx.ledger_reader.get_batch(batch_id)
        if batch is None:
            continue
        hops = [
            (e.seq, e.fields["weight_kg"])
            for e in batch.events
            if "weight_kg" in e.fields
        ]
        for (seq_a, field_a), (seq_b, field_b) in zip(hops, hops[1:]):
            if field_a.basis is not Basis.WEIGHED or field_b.basis is not Basis.WEIGHED:
                continue
            any_weighed_pair = True
            a, b = field_a.value, field_b.value
            if a <= 0:
                continue
            change = (b - a) / a
            if change < -MAX_ALLOWED_DROP_FRACTION:
                findings.append(
                    f"{batch_id} seq {seq_a}->{seq_b}: {a:g} kg -> {b:g} kg "
                    f"({change:.1%}, over the {MAX_ALLOWED_DROP_FRACTION:.0%} allowed drop)."
                )
            elif change > MAX_ALLOWED_GAIN_FRACTION:
                findings.append(
                    f"{batch_id} seq {seq_a}->{seq_b}: {a:g} kg -> {b:g} kg "
                    f"({change:+.1%}, a gain over the {MAX_ALLOWED_GAIN_FRACTION:.0%} tolerance)."
                )

    if not any_weighed_pair:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.INCONCLUSIVE,
            severity=Severity.NONE,
            observed=None,
            limit=None,
            formula_rendered="Only stated (unweighed) weights are available along the chain; a difference between them proves nothing.",
        )

    if findings:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.FLAG,
            severity=Severity.SOFT,
            observed=findings,
            limit=f"drop <= {MAX_ALLOWED_DROP_FRACTION:.0%}, gain <= {MAX_ALLOWED_GAIN_FRACTION:.0%}",
            formula_rendered="; ".join(findings),
            next_action="Ask for the weigh slips at each hop.",
        )

    return RuleResult(
        claim_id=claim.claim_id,
        rule_id=RULE_ID,
        rule_version=RULE_VERSION,
        outcome=RuleOutcome.PASS,
        severity=Severity.NONE,
        observed=None,
        limit=f"drop <= {MAX_ALLOWED_DROP_FRACTION:.0%}, gain <= {MAX_ALLOWED_GAIN_FRACTION:.0%}",
        formula_rendered="Weight at each weighed hop is consistent with the previous hop.",
    )
