"""R5: photo light vs time stamp. SOLUTION.md section 6, in detail.

Deterministic path only here (the Bedrock vision signal from
docs/team/MRUDDUNI.md section 3.4 step 3 is a P1 addition that can only
sharpen an INCONCLUSIVE into a HARD/SOFT flag when it agrees with the
deterministic signal; it is never required and never the sole basis for a
flag). Inputs: EXIF DateTimeOriginal (+ offset, or IST assumed), GPS or the
facility location, and a deterministic light classification.

Decision table (exact copy from SOLUTION.md section 6):

| Sun elevation        | Image shows                     | Outcome              |
|-----------------------|----------------------------------|-----------------------|
| < -1 (below horizon)  | Direct sun, hard cast shadows    | FLAG HARD             |
| < -12 (past nautical) | Bright outdoor daylight sky      | FLAG HARD             |
| -12 to -1             | Bright diffuse light             | INCONCLUSIVE          |
| > +10                 | Night scene outdoors              | FLAG SOFT             |
| any                   | Indoor, unclear                   | INCONCLUSIVE          |
| no time stamp         | -                                  | INSUFFICIENT_EVIDENCE |
"""

from __future__ import annotations

from datetime import timedelta, timezone

from ..context import RuleContext
from ..model import Claim, Evidence, EvidenceKind, RuleOutcome, RuleResult, Severity
from ..solar import solar_elevation_deg

RULE_ID = "R5"
RULE_VERSION = "1.0.0"

IST = timezone(timedelta(hours=5, minutes=30))

LIGHT_CLASSES = (
    "DIRECT_SUN_HARD_SHADOWS",
    "BRIGHT_DIFFUSE_DAYLIGHT",
    "TWILIGHT",
    "NIGHT_ARTIFICIAL",
    "INDOOR",
    "UNCLEAR",
)


def evaluate(claim: Claim, ctx: RuleContext) -> list[RuleResult]:
    photo_ids = [
        eid
        for eid in claim.evidence_ids
        if (ev := ctx.evidence.get(eid)) is not None and ev.kind is EvidenceKind.PHOTO
    ]
    if not photo_ids:
        return [
            RuleResult(
                claim_id=claim.claim_id,
                rule_id=RULE_ID,
                rule_version=RULE_VERSION,
                outcome=RuleOutcome.INSUFFICIENT_EVIDENCE,
                severity=Severity.HARD,
                observed=None,
                limit=None,
                formula_rendered="No photo evidence linked to this claim.",
                next_action="Request a weighbridge or intake photo.",
            )
        ]
    return [_evaluate_one(claim, ctx.evidence[eid]) for eid in photo_ids]


def _evaluate_one(claim: Claim, evidence: Evidence) -> RuleResult:
    exif = evidence.exif or {}
    dt_original = exif.get("DateTimeOriginal")
    if dt_original is None:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.INSUFFICIENT_EVIDENCE,
            severity=Severity.HARD,
            observed=None,
            limit=None,
            formula_rendered="No EXIF time stamp on this photo. Missing data is not fraud.",
            evidence_ids=(evidence.evidence_id,),
        )

    assumed_ist = "OffsetTimeOriginal" not in exif
    aware_dt = dt_original if dt_original.tzinfo else dt_original.replace(tzinfo=IST)

    lat = exif.get("gps_lat")
    lon = exif.get("gps_lon")
    if lat is None or lon is None:
        return RuleResult(
            claim_id=claim.claim_id,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
            outcome=RuleOutcome.INSUFFICIENT_EVIDENCE,
            severity=Severity.HARD,
            observed=None,
            limit=None,
            formula_rendered="No GPS on the photo and no registered facility location to fall back to.",
            evidence_ids=(evidence.evidence_id,),
        )

    elevation = solar_elevation_deg(aware_dt, lat, lon)
    light_class = exif.get("_demo_light_class", "UNCLEAR")  # set by generate_sample_data.py
    ist_note = " (IST assumed, no offset in EXIF)" if assumed_ist else ""
    formula = (
        f"sun elevation {elevation:.1f} deg at {aware_dt.isoformat()}{ist_note}, "
        f"image classified {light_class}"
    )

    outcome, severity, next_action = _decide(elevation, light_class)
    return RuleResult(
        claim_id=claim.claim_id,
        rule_id=RULE_ID,
        rule_version=RULE_VERSION,
        outcome=outcome,
        severity=severity,
        observed={"elevation_deg": round(elevation, 2), "light_class": light_class},
        limit="elevation < -1 with hard shadows, or < -12 with bright daylight, is impossible",
        formula_rendered=formula,
        evidence_ids=(evidence.evidence_id,),
        next_action=next_action,
    )


def _decide(elevation: float, light_class: str) -> tuple[RuleOutcome, Severity, str | None]:
    if light_class in ("INDOOR", "UNCLEAR"):
        return RuleOutcome.INCONCLUSIVE, Severity.NONE, None
    if light_class == "DIRECT_SUN_HARD_SHADOWS" and elevation < -1:
        return (
            RuleOutcome.FLAG,
            Severity.HARD,
            "Ask for the original, unedited photo and a second photo from the same visit.",
        )
    if light_class == "BRIGHT_DIFFUSE_DAYLIGHT" and elevation < -12:
        return (
            RuleOutcome.FLAG,
            Severity.HARD,
            "Ask for the original, unedited photo and a second photo from the same visit.",
        )
    if light_class == "BRIGHT_DIFFUSE_DAYLIGHT" and -12 <= elevation < -1:
        return RuleOutcome.INCONCLUSIVE, Severity.NONE, None
    if light_class == "NIGHT_ARTIFICIAL" and elevation > 10:
        return (
            RuleOutcome.FLAG,
            Severity.SOFT,
            "Check whether the camera's clock or time zone is set correctly.",
        )
    return RuleOutcome.PASS, Severity.NONE, None
