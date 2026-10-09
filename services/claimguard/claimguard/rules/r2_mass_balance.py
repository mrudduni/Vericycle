"""R2: mass balance. SOLUTION.md section 6.

(a) opening stock + inputs - outputs - documented losses - closing stock
    >= -tolerance. Catches output that could not have come from the
    claimed input.
(b) each recovered metal <= input x the sourced maximum recoverable
    fraction for that metal. Catches an implausibly high recovery rate.

Both halves are HARD. Missing opening or closing stock, or a missing
sourced fraction, returns INSUFFICIENT_EVIDENCE rather than guessing.
"""

from __future__ import annotations

from ..context import RuleContext
from ..model import Claim, RuleOutcome, RuleResult, Severity

RULE_ID = "R2"
RULE_VERSION = "1.0.0"
TOLERANCE_T = 0.01

MAX_FRACTION_SOURCE_BY_METAL = {
    "LEAD": "lead-fraction-lead-acid-max",
}


def evaluate(claim: Claim, ctx: RuleContext) -> list[RuleResult]:
    return [_evaluate_a(claim), _evaluate_b(claim, ctx)]


def _evaluate_a(claim: Claim) -> RuleResult:
    missing = (
        claim.input_t is None
        or claim.opening_stock_t is None
        or claim.closing_stock_t is None
        or claim.documented_losses_t is None
        or not claim.output
    )
    if missing:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=f"{RULE_ID}a",
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.INSUFFICIENT_EVIDENCE,
            severity=Severity.HARD,
            observed=None,
            limit=None,
            formula_rendered="Missing opening/closing stock, losses, or output.",
            next_action="Request opening and closing stock records and documented process losses.",
        )

    output_total = sum(claim.output.values())
    balance = (
        claim.opening_stock_t + claim.input_t - output_total - claim.documented_losses_t - claim.closing_stock_t
    )
    formula = (
        f"opening({claim.opening_stock_t:.3f}) + input({claim.input_t:.3f}) - "
        f"output({output_total:.3f}) - losses({claim.documented_losses_t:.3f}) - "
        f"closing({claim.closing_stock_t:.3f}) = {balance:.3f} t "
        f">= -{TOLERANCE_T:.3f} t tolerance"
    )
    outcome = RuleOutcome.PASS if balance >= -TOLERANCE_T else RuleOutcome.FLAG
    return RuleResult(
        claim_id=claim.claim_id,
        rule_id=f"{RULE_ID}a",
        rule_version=RULE_VERSION,
        outcome=outcome,
        severity=Severity.HARD,
        observed=balance,
        limit=-TOLERANCE_T,
        formula_rendered=formula,
        next_action=None if outcome is RuleOutcome.PASS else "Request stock and loss records explaining the gap.",
    )


def _evaluate_b(claim: Claim, ctx: RuleContext) -> RuleResult:
    if claim.input_t is None or not claim.output:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=f"{RULE_ID}b",
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.INSUFFICIENT_EVIDENCE,
            severity=Severity.HARD,
            observed=None,
            limit=None,
            formula_rendered="Missing claimed input or output.",
        )

    worst_outcome = RuleOutcome.PASS
    worst_detail = None
    demo_value = False
    source_ids: list[str] = []
    for metal, out_t in claim.output.items():
        source_id = MAX_FRACTION_SOURCE_BY_METAL.get(metal)
        if source_id is None:
            continue  # no sourced fraction for this metal; not checked by R2b
        try:
            fraction, is_demo = ctx.sources.require_value(source_id)
        except KeyError:
            fraction = None
            is_demo = False
        source_ids.append(source_id)
        if fraction is None:
            if worst_outcome is RuleOutcome.PASS:
                worst_outcome = RuleOutcome.INSUFFICIENT_EVIDENCE
                worst_detail = f"{metal}: no sourced maximum recoverable fraction."
            continue
        demo_value = demo_value or is_demo
        max_out_t = claim.input_t * fraction
        detail = (
            f"{metal} output {out_t:.3f} t <= input {claim.input_t:.3f} t x "
            f"max fraction {fraction:.2f} = {max_out_t:.3f} t"
        )
        if out_t > max_out_t:
            worst_outcome = RuleOutcome.FLAG
            worst_detail = detail
        elif worst_outcome is RuleOutcome.PASS:
            worst_detail = detail

    if worst_detail is None:
        worst_outcome = RuleOutcome.INSUFFICIENT_EVIDENCE
        worst_detail = "No sourced maximum recoverable fraction for any claimed output metal."

    return RuleResult(
        claim_id=claim.claim_id,
        rule_id=f"{RULE_ID}b",
        rule_version=RULE_VERSION,
        outcome=worst_outcome,
        severity=Severity.HARD,
        observed=dict(claim.output),
        limit=None,
        formula_rendered=worst_detail,
        source_ids=tuple(source_ids),
        demo_value=demo_value,
        next_action=None if worst_outcome is RuleOutcome.PASS else "Request a published composition table for the claimed metal.",
    )
