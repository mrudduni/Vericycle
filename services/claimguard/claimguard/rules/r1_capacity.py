"""R1: claimed processed tonnes must fit the facility's rated capacity.

SOLUTION.md section 6: processed_t <= rated_t_per_hr * hours_per_day *
operating_days_in_period, plus the annual licensed cap. Uses the lowest
sourced capacity if documents disagree (not exercised by the demo facility
data, which has one set of numbers per facility).

The CPCB guideline's own worked example prints 20 h x 4 t/h x 330 d =
46,200 t; the correct product is 26,400 t (problem_statement.md section
"Scope for a four-day build"). This rule always uses the correct
arithmetic, and the card the UI renders from `formula_rendered` shows both
numbers so the erratum is visible, not hidden.
"""

from __future__ import annotations

from ..context import RuleContext
from ..model import Claim, RuleOutcome, RuleResult, Severity

RULE_ID = "R1"
RULE_VERSION = "1.0.0"

ERRATUM_NOTE = (
    "CPCB's own worked example prints 20 h x 4 t/h x 330 d = 46,200 t. "
    "The correct product is 26,400 t; this rule uses the correct arithmetic."
)


def _period_days(claim: Claim) -> float:
    """Days in the period. A period ending 23:59:59 counts as whole days (365, not 364.99999), so limits print as 26,400."""
    days = (claim.period_end - claim.period_start).total_seconds() / 86400.0
    return float(round(days)) if abs(days - round(days)) < 2 / 1440 else days


def evaluate(claim: Claim, ctx: RuleContext) -> RuleResult:
    facility = ctx.facility
    missing = (
        facility is None
        or facility.rated_t_per_hr is None
        or facility.hours_per_day is None
        or facility.operating_days is None
        or claim.processed_t is None
    )
    if missing:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.INSUFFICIENT_EVIDENCE,
            severity=Severity.HARD,
            observed=claim.processed_t,
            limit=None,
            formula_rendered="Missing facility capacity or claimed processed tonnes.",
            source_ids=("cpcb-capacity-guideline",),
            next_action="Request consent-to-operate and production logs for the period.",
        )

    period_days = _period_days(claim)
    operating_days_in_period = facility.operating_days * (period_days / 365.0)
    period_capacity_t = facility.rated_t_per_hr * facility.hours_per_day * operating_days_in_period

    limit_t = period_capacity_t
    limit_source = "period"
    if facility.licensed_t_per_yr is not None:
        annual_prorated = facility.licensed_t_per_yr * (period_days / 365.0)
        if annual_prorated < limit_t:
            limit_t = annual_prorated
            limit_source = "annual licensed cap, prorated"

    formula = (
        f"{claim.processed_t:.3f} t processed <= "
        f"{facility.rated_t_per_hr:g} t/h x {facility.hours_per_day:g} h/day x "
        f"{operating_days_in_period:.1f} operating days = {period_capacity_t:.1f} t "
        f"({limit_source} applies: {limit_t:.1f} t). {ERRATUM_NOTE}"
    )

    if claim.processed_t <= limit_t:
        outcome = RuleOutcome.PASS
    else:
        outcome = RuleOutcome.FLAG

    return RuleResult(
        claim_id=claim.claim_id,
        rule_id=RULE_ID,
        rule_version=RULE_VERSION,
        outcome=outcome,
        severity=Severity.HARD,
        observed=claim.processed_t,
        limit=limit_t,
        formula_rendered=formula,
        source_ids=("cpcb-capacity-guideline",),
        next_action=None if outcome is RuleOutcome.PASS else "Request consent-to-operate and production logs for the period.",
    )
