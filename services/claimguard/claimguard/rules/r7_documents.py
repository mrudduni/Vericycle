"""R7: document consistency. SOLUTION.md section 6.

- Invoice totals vs claimed tonnage (SOFT: a mismatch has innocent
  explanations, like a part-batch invoice).
- Invoice dates inside the claim period (SOFT).
- The same invoice number reused across different evidence records (HARD:
  there is no innocent explanation for a real invoice number appearing
  twice as if it were two different purchases).
- GSTIN format and check digit valid (SOFT). "Format valid" means exactly
  that: the number parses to a real check digit. It does not mean the
  GSTIN is registered or the party behind it is real.

Returns one RuleResult; the worst finding wins, same pattern as R4.
"""

from __future__ import annotations

from ..context import RuleContext
from ..model import Claim, EvidenceKind, RuleOutcome, RuleResult, Severity

RULE_ID = "R7"
RULE_VERSION = "1.0.0"
TOTAL_TOLERANCE_FRACTION = 0.10

GSTIN_CHECK_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_check_digit_valid(gstin: str) -> bool:
    """The published GSTIN check-digit algorithm (15 characters, mod 36).

    This validates FORMAT only: a syntactically valid check digit. It says
    nothing about whether the GSTIN is actually registered.
    """
    if len(gstin) != 15:
        return False
    body, given_check = gstin[:14], gstin[14]
    factor = 2
    total = 0
    for ch in reversed(body):
        idx = GSTIN_CHECK_ALPHABET.find(ch)
        if idx == -1:
            return False
        product = idx * factor
        total += product // 36 + product % 36
        factor = 1 if factor == 2 else 2
    check_idx = (36 - (total % 36)) % 36
    return GSTIN_CHECK_ALPHABET[check_idx] == given_check


def evaluate(claim: Claim, ctx: RuleContext) -> RuleResult:
    invoice_ids = [
        eid
        for eid in claim.evidence_ids
        if (ev := ctx.evidence.get(eid)) is not None and ev.kind is EvidenceKind.INVOICE
    ]
    if not invoice_ids:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.INSUFFICIENT_EVIDENCE,
            severity=Severity.SOFT,
            observed=None,
            limit=None,
            formula_rendered="No invoice evidence linked to this claim.",
            next_action="Request the purchase or sale invoices for this period.",
        )

    seen_numbers: dict[str, str] = {}
    for eid in invoice_ids:
        number = ctx.evidence[eid].extracted.get("invoice_number")
        if number is None:
            continue
        if number in seen_numbers and seen_numbers[number] != eid:
            return RuleResult(
                claim_id=claim.claim_id,
                rule_id=RULE_ID,
                rule_version=RULE_VERSION,
                outcome=RuleOutcome.FLAG,
                severity=Severity.HARD,
                observed=number,
                limit=None,
                formula_rendered=f"Invoice number {number} appears on both {eid} and {seen_numbers[number]}.",
                evidence_ids=(eid, seen_numbers[number]),
                next_action="Request the original invoices from both parties.",
            )
        seen_numbers[number] = eid

    soft_findings: list[str] = []
    for eid in invoice_ids:
        extracted = ctx.evidence[eid].extracted
        total_t = extracted.get("total_weight_t")
        date = extracted.get("date")
        gstin = extracted.get("gstin")

        if total_t is not None and claim.processed_t:
            diff = abs(total_t - claim.processed_t) / claim.processed_t
            if diff > TOTAL_TOLERANCE_FRACTION:
                soft_findings.append(
                    f"{eid}: invoice total {total_t:.3f} t differs from claimed "
                    f"{claim.processed_t:.3f} t by {diff:.0%}, over the {TOTAL_TOLERANCE_FRACTION:.0%} tolerance."
                )
        if date is not None and not (claim.period_start.date() <= date <= claim.period_end.date()):
            soft_findings.append(f"{eid}: invoice dated {date} is outside the claim period.")
        if gstin is not None and not gstin_check_digit_valid(gstin):
            soft_findings.append(f"{eid}: GSTIN {gstin} fails the published check-digit format.")

    if soft_findings:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.FLAG,
            severity=Severity.SOFT,
            observed=soft_findings,
            limit=None,
            formula_rendered="; ".join(soft_findings),
            evidence_ids=tuple(invoice_ids),
            next_action="Request corrected or original documents for the flagged item(s).",
        )

    return RuleResult(
        claim_id=claim.claim_id,
        rule_id=RULE_ID,
        rule_version=RULE_VERSION,
        outcome=RuleOutcome.PASS,
        severity=Severity.NONE,
        observed=len(invoice_ids),
        limit=None,
        formula_rendered=f"{len(invoice_ids)} invoice(s) checked: totals, dates and GSTIN format all consistent. GSTIN format validity is not proof of registration.",
        evidence_ids=tuple(invoice_ids),
    )
