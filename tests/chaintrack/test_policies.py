"""Cedar policy tests (SHAURYA.md 3.8). Run locally with cedarpy; the same files load into Verified Permissions."""
import json
from pathlib import Path

import pytest

cedarpy = pytest.importorskip("cedarpy")

POL = Path(__file__).resolve().parents[2] / "policies"
POLICIES = "\n".join(p.read_text() for p in sorted(POL.glob("*.cedar")))
SCHEMA = (POL / "schema.cedarschema.json").read_text()
DATA = json.loads((POL / "tests" / "cases.json").read_text())


def test_policies_validate_against_schema():
    r = cedarpy.validate_policies(POLICIES, SCHEMA)
    assert r.validation_passed, r.errors


@pytest.mark.parametrize("case", DATA["cases"], ids=[c["name"] for c in DATA["cases"]])
def test_case(case):
    req = {k: case[k] for k in ("principal", "action", "resource", "context")}
    r = cedarpy.is_authorized(req, POLICIES, DATA["entities"], schema=SCHEMA)
    assert not r.diagnostics.errors, r.diagnostics.errors  # a deny must come from policy, not an evaluation error
    assert r.decision.value == case["expect"], (case["name"], r.diagnostics.reasons)
