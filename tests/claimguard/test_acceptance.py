"""The main acceptance test: docs/team/CONTRACT.md section 8's table.

Every claim must produce exactly its expected outcome. This is the test
that matters most; everything else in tests/claimguard is a supporting
detail check.
"""

from __future__ import annotations

from claimguard import io
from claimguard.engine import run_claim_set
from claimguard.ledger_reader import FixtureLedgerReader
from claimguard.model import RuleOutcome, Severity
from claimguard.sources import SourcesRegistry


def _load():
    claims = io.load_claims_dir()
    facilities = io.load_facilities()
    evidence = io.load_evidence_index()
    sources = SourcesRegistry.load()
    ledger = FixtureLedgerReader()
    return run_claim_set(claims, facilities, sources, evidence, ledger)


def _outcomes(run, rule_id):
    return [r for r in run.rule_results if r.rule_id == rule_id]


def test_c101_all_pass_and_coverage_82_percent():
    runs = _load()
    run = runs["C-101"]
    decidable = [
        r for r in run.rule_results
        if r.outcome in (RuleOutcome.PASS, RuleOutcome.FLAG)
    ]
    flagged = [r for r in decidable if r.outcome is RuleOutcome.FLAG]
    assert not flagged, f"C-101 should have no flags, got: {flagged}"
    assert decidable, "C-101 should have at least some decidable rule results"
    assert round(run.scores.traceability_coverage * 100) == 82


def test_c102_capacity_flag_hard_with_erratum():
    runs = _load()
    r1 = _outcomes(runs["C-102"], "R1")[0]
    assert r1.outcome is RuleOutcome.FLAG
    assert r1.severity is Severity.HARD
    assert "46,200" in r1.formula_rendered and "26,400" in r1.formula_rendered


def test_c103_mass_balance_flag_hard():
    runs = _load()
    r2b = _outcomes(runs["C-103"], "R2b")[0]
    assert r2b.outcome is RuleOutcome.FLAG
    assert r2b.severity is Severity.HARD


def test_c104_energy_flag_soft_with_next_action():
    runs = _load()
    r3 = _outcomes(runs["C-104"], "R3")[0]
    assert r3.outcome is RuleOutcome.FLAG
    assert r3.severity is Severity.SOFT
    assert r3.next_action and "generator" in r3.next_action.lower()


def test_c105_photo_flag_hard():
    runs = _load()
    r5 = _outcomes(runs["C-105"], "R5")[0]
    assert r5.outcome is RuleOutcome.FLAG
    assert r5.severity is Severity.HARD


def test_c105b_photo_inconclusive_twilight_safeguard():
    runs = _load()
    r5 = _outcomes(runs["C-105b"], "R5")[0]
    assert r5.outcome is RuleOutcome.INCONCLUSIVE


def test_c106_duplicate_photo_flag_soft():
    runs = _load()
    r6 = _outcomes(runs["C-106"], "R6")[0]
    assert r6.outcome is RuleOutcome.FLAG
    assert r6.severity is Severity.SOFT


def test_c107_double_claim_flag_hard():
    runs = _load()
    r4 = _outcomes(runs["C-107"], "R4")[0]
    assert r4.outcome is RuleOutcome.FLAG
    assert r4.severity is Severity.HARD
    assert r4.observed == "B-0042"


def test_c101_not_flagged_for_the_double_claim_c107_causes():
    """CONTRACT.md's tie-break rule: the earlier claim is never punished
    for a later claim's reuse of the same batch."""
    runs = _load()
    r4 = _outcomes(runs["C-101"], "R4")[0]
    assert r4.outcome is RuleOutcome.PASS


def test_c108_insufficient_not_flagged():
    runs = _load()
    run = runs["C-108"]
    r3 = _outcomes(run, "R3")[0]
    r5 = _outcomes(run, "R5")[0]
    assert r3.outcome is RuleOutcome.INSUFFICIENT_EVIDENCE
    assert r5.outcome is RuleOutcome.INSUFFICIENT_EVIDENCE
    flagged = [r for r in run.rule_results if r.outcome is RuleOutcome.FLAG]
    assert not flagged, f"C-108 must never be flagged for missing data, got: {flagged}"
    assert run.scores.traceability_coverage == 0.0
