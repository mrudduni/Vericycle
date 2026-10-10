"""R9 (stretch): site activity from Sentinel-2 (SOLUTION.md section 6). A review signal, never a flag.

For each cloud-free Sentinel-2 L2A scene over the claim period, the provider reports short-wave infrared (B12, 2.2 um)
reflectance in a 3x3-pixel window at the plant and the median of a surrounding ring. Active furnaces and hot slag raise SWIR at
the site relative to the ring. At 20 m a pixel is 400 m2, small plants may be invisible, and monsoon cloud removes most scenes, so:

- site brighter than its surroundings in at least one clear scene -> PASS ("thermal signal present"; consistent with activity);
- no such signal -> INCONCLUSIVE, never FLAG: absence at this resolution is not evidence the plant was idle;
- no coordinates -> INSUFFICIENT_EVIDENCE; fewer than 2 clear scenes -> INCONCLUSIVE.

Observation dict: {"date": "YYYY-MM-DD", "cloud": float %, "site_b12": float, "ring_b12": float}.
"""

from __future__ import annotations

from ..context import RuleContext
from ..model import Claim, RuleOutcome, RuleResult, Severity

RULE_ID = "R9"
RULE_VERSION = "1.0.0"
HOT_RATIO = 1.5  # site SWIR / ring SWIR; DEMO VALUE, uncalibrated on real plants
MIN_CLEAR_SCENES = 2
SOURCE = "sentinel-2-l2a-aws-open-data"


def _result(claim, outcome, text, observed=None, next_action=None):
    return RuleResult(
        claim_id=claim.claim_id, rule_id=RULE_ID, rule_version=RULE_VERSION, outcome=outcome, severity=Severity.NONE,
        observed=observed, limit=f"site/ring B12 ratio >= {HOT_RATIO}", formula_rendered=text,
        source_ids=(SOURCE,), demo_value=True, next_action=next_action)


def evaluate(claim: Claim, ctx: RuleContext) -> RuleResult:
    f = ctx.facility
    if f is None or f.lat is None or f.lon is None:
        return _result(claim, RuleOutcome.INSUFFICIENT_EVIDENCE, "No plant coordinates on file, so no satellite check was possible.",
                       next_action="Add the plant's registered coordinates.")
    obs = [o for o in ctx.satellite(f.lat, f.lon, claim.period_start.date(), claim.period_end.date())
           if o.get("ring_b12") and o.get("site_b12") is not None]
    if len(obs) < MIN_CLEAR_SCENES:
        return _result(claim, RuleOutcome.INCONCLUSIVE,
                       f"Only {len(obs)} usable cloud-free Sentinel-2 scene(s) in the period (need {MIN_CLEAR_SCENES}). Monsoon cloud is a common cause.",
                       observed=len(obs))
    ratios = [o["site_b12"] / o["ring_b12"] for o in obs]
    hot = sum(r >= HOT_RATIO for r in ratios)
    detail = f"{hot} of {len(obs)} clear scenes show site SWIR >= {HOT_RATIO}x its surroundings (max {max(ratios):.2f}x)."
    if hot:
        return _result(claim, RuleOutcome.PASS, detail + " A thermal signal is consistent with activity; it does not show what was processed.",
                       observed={"hot": hot, "clear": len(obs), "max_ratio": round(max(ratios), 2)})
    return _result(claim, RuleOutcome.INCONCLUSIVE,
                   detail + " Absence of a signal at 20 m resolution is not evidence the plant was idle (small site, short heating cycles).",
                   observed={"hot": 0, "clear": len(obs), "max_ratio": round(max(ratios), 2)})
