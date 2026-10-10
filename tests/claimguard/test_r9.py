from __future__ import annotations

from datetime import datetime, timezone

from claimguard.context import RuleContext
from claimguard.engine import run_claim
from claimguard.model import Claim, ClaimProduct, Facility, RuleOutcome, Severity
from claimguard.rules import r9_satellite
from claimguard.sources import SourcesRegistry

UTC = timezone.utc
CLAIM = Claim(claim_id="T", recycler_party_id="REC-03", product=ClaimProduct.BATTERY_LEAD_ACID,
              period_start=datetime(2026, 8, 1, tzinfo=UTC), period_end=datetime(2026, 9, 30, tzinfo=UTC), input_t=1, processed_t=1)
FAC = Facility("REC-03", 2, 16, 300, 9600, 28.73, 77.78)


def ctx(obs, fac=FAC):
    return RuleContext(facility=fac, sources=SourcesRegistry.load(), satellite=lambda *a: obs)


def o(site, ring=1000.0):
    return {"date": "2026-09-01", "cloud": 5.0, "site_b12": site, "ring_b12": ring}


def test_thermal_signal_passes_but_never_claims_what_was_processed():
    r = r9_satellite.evaluate(CLAIM, ctx([o(1700), o(1000)]))
    assert r.outcome is RuleOutcome.PASS and "does not show what was processed" in r.formula_rendered


def test_no_signal_is_inconclusive_never_a_flag():
    r = r9_satellite.evaluate(CLAIM, ctx([o(1000), o(1100), o(900)]))
    assert r.outcome is RuleOutcome.INCONCLUSIVE and r.severity is Severity.NONE and "not evidence the plant was idle" in r.formula_rendered


def test_cloud_and_missing_coordinates():
    assert r9_satellite.evaluate(CLAIM, ctx([o(2000)])).outcome is RuleOutcome.INCONCLUSIVE  # one scene is not enough
    assert r9_satellite.evaluate(CLAIM, ctx([], FAC)).outcome is RuleOutcome.INCONCLUSIVE
    no_loc = Facility("REC-01", 4, 20, 330, 26400)
    assert r9_satellite.evaluate(CLAIM, ctx([o(2000)] * 3, no_loc)).outcome is RuleOutcome.INSUFFICIENT_EVIDENCE


def test_only_runs_when_a_provider_is_configured_and_never_changes_the_acceptance_flags():
    assert not any(r.rule_id == "R9" for r in run_claim(CLAIM, RuleContext(facility=FAC, sources=SourcesRegistry.load())))
    res = run_claim(CLAIM, ctx([o(1000), o(1000)]))
    assert any(r.rule_id == "R9" for r in res) and not any(r.outcome is RuleOutcome.FLAG and r.rule_id == "R9" for r in res)
