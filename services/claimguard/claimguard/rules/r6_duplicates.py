"""R6: duplicate or near-duplicate photo. SOLUTION.md section 6. SOFT.

Exact SHA-256 match, or perceptual-hash Hamming distance below a
threshold, between two photos used in DIFFERENT batches or claims. The
same yard photographed twice on different days must not flag: the
"different batch or claim" condition is what keeps this from punishing an
honest recycler who photographs the same weighbridge every day.
"""

from __future__ import annotations

from ..context import RuleContext
from ..model import Claim, EvidenceKind, RuleOutcome, RuleResult, Severity

RULE_ID = "R6"
RULE_VERSION = "1.0.0"
PHASH_HAMMING_THRESHOLD = 6  # out of 64 bits for a typical 8x8 perceptual hash


def _hamming(a: str, b: str) -> int:
    ai, bi = int(a, 16), int(b, 16)
    return bin(ai ^ bi).count("1")


def evaluate(claim: Claim, ctx: RuleContext) -> RuleResult:
    photo_ids = [
        eid
        for eid in claim.evidence_ids
        if (ev := ctx.evidence.get(eid)) is not None and ev.kind is EvidenceKind.PHOTO
    ]
    if not photo_ids:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.INSUFFICIENT_EVIDENCE,
            severity=Severity.SOFT,
            observed=None,
            limit=None,
            formula_rendered="No photo evidence linked to this claim.",
        )

    matches: list[str] = []
    for eid in photo_ids:
        ev = ctx.evidence[eid]
        for other_id, other_ev in ctx.evidence.items():
            if other_id == eid or other_ev.kind is not EvidenceKind.PHOTO:
                continue
            same_batch = (
                ev.batch_id is not None and ev.batch_id == other_ev.batch_id
            )
            if same_batch:
                continue  # the rule flags reuse across DIFFERENT batches or claims, not one photo filed once against its own batch
            exact = ev.sha256 and ev.sha256 == other_ev.sha256
            near = (
                ev.phash
                and other_ev.phash
                and _hamming(ev.phash, other_ev.phash) <= PHASH_HAMMING_THRESHOLD
            )
            if exact or near:
                kind = "exact SHA-256 match" if exact else "near-duplicate (pHash)"
                pair = tuple(sorted((eid, other_id)))
                note = f"{pair[0]} and {pair[1]} ({ev.batch_id or '?'} vs {other_ev.batch_id or '?'}): {kind}"
                if note not in matches:
                    matches.append(note)

    if matches:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.FLAG,
            severity=Severity.SOFT,
            observed=matches,
            limit=f"pHash Hamming distance <= {PHASH_HAMMING_THRESHOLD}",
            formula_rendered="; ".join(matches),
            evidence_ids=tuple(photo_ids),
            next_action="Ask for the original camera files, or a fresh photo from this visit.",
        )

    return RuleResult(
        claim_id=claim.claim_id,
        rule_id=RULE_ID,
        rule_version=RULE_VERSION,
        outcome=RuleOutcome.PASS,
        severity=Severity.NONE,
        observed=len(photo_ids),
        limit=None,
        formula_rendered=f"No duplicate or near-duplicate photo found across other batches or claims, among {len(photo_ids)} photo(s).",
    )
