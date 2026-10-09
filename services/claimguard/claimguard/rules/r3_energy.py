"""R3: energy consistency. SOLUTION.md section 6. SOFT only, never HARD.

kWh per tonne of claimed processed output, checked against a configured
band per process. A logged diesel generator run can explain an apparent
gap, so this never escalates past SOFT: there are too many innocent
explanations (outages, outsourced smelting, a DG set) for a HARD flag to
be fair. Missing electricity data returns INSUFFICIENT_EVIDENCE.
"""

from __future__ import annotations

from ..context import RuleContext
from ..model import Claim, RuleOutcome, RuleResult, Severity

RULE_ID = "R3"
RULE_VERSION = "1.0.0"

# facility recycler_party_id -> energy band source id. REC-02 here stands in
# for a dismantling-only process (no smelting), used by the Hapur-style case.
ENERGY_SOURCE_BY_RECYCLER = {
    "REC-01": "energy-band-lead-smelting-kwh-per-t",
    "REC-03": "energy-band-ewaste-dismantling-kwh-per-t",
}
DEFAULT_ENERGY_SOURCE = "energy-band-lead-smelting-kwh-per-t"


def evaluate(claim: Claim, ctx: RuleContext) -> RuleResult:
    if claim.electricity_kwh is None or not claim.processed_t:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.INSUFFICIENT_EVIDENCE,
            severity=Severity.SOFT,
            observed=claim.electricity_kwh,
            limit=None,
            formula_rendered="No electricity bill linked to this claim.",
            next_action="Request the electricity bill for the claim period.",
        )

    source_id = ENERGY_SOURCE_BY_RECYCLER.get(claim.recycler_party_id, DEFAULT_ENERGY_SOURCE)
    try:
        band, is_demo = ctx.sources.require_value(source_id)
    except KeyError:
        band, is_demo = None, False

    if band is None:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.INSUFFICIENT_EVIDENCE,
            severity=Severity.SOFT,
            observed=claim.electricity_kwh,
            limit=None,
            formula_rendered="No sourced energy band configured for this process.",
            source_ids=(source_id,),
        )

    observed_kwh_per_t = claim.electricity_kwh / claim.processed_t
    low, high = band
    formula = (
        f"{claim.electricity_kwh:g} kWh / {claim.processed_t:.3f} t = "
        f"{observed_kwh_per_t:.1f} kWh/t, band [{low:g}, {high:g}] kWh/t"
    )

    if claim.diesel_generator_logged:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.INCONCLUSIVE,
            severity=Severity.SOFT,
            observed=observed_kwh_per_t,
            limit=band,
            formula_rendered=formula + " (diesel generator logs explain any gap)",
            source_ids=(source_id,),
            demo_value=is_demo,
        )

    in_band = low <= observed_kwh_per_t <= high
    outcome = RuleOutcome.PASS if in_band else RuleOutcome.FLAG
    return RuleResult(
        claim_id=claim.claim_id,
        rule_id=RULE_ID,
        rule_version=RULE_VERSION,
        outcome=outcome,
        severity=Severity.SOFT,
        observed=observed_kwh_per_t,
        limit=band,
        formula_rendered=formula,
        source_ids=(source_id,),
        demo_value=is_demo,
        next_action=None if outcome is RuleOutcome.PASS else "Request diesel generator logs or outsourced-smelting invoices.",
    )
