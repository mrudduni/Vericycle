"""Claim-read authorization: Cedar (ChainTrack's real policies), the dev mirror, and the AVP adapter must agree."""

from __future__ import annotations

import itertools
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "review_api"))
os.environ["AUTH_MODE"] = "dev"

from claimguard import io as cg_io  # noqa: E402
from review.authz import AvpAuthorizer, DevAuthorizer, LocalCedarAuthorizer  # noqa: E402

CLAIMS = {c.claim_id: c for c in cg_io.load_claims_dir()}
PRINCIPALS = [
    {"role": "AUDITOR", "party_id": "AUD-01"},
    {"role": "RECYCLER", "party_id": "REC-01"},
    {"role": "RECYCLER", "party_id": "REC-02"},
    {"role": "PRODUCER", "party_id": "PRD-01"},
    {"role": "PRODUCER", "party_id": "PRD-99"},
    {"role": "COLLECTOR", "party_id": "COL-118"},
    {"role": None, "party_id": None},
]


def test_cedar_and_dev_mirror_agree_on_every_role_and_claim():
    cedar, dev = LocalCedarAuthorizer(), DevAuthorizer()
    for p, c in itertools.product(PRINCIPALS, CLAIMS.values()):
        assert cedar.can_read_claim(p, c) == dev.can_read_claim(p, c), (p, c.claim_id)


def test_the_cases_ChainTrack_specified():
    cedar = LocalCedarAuthorizer()
    assert not cedar.can_read_claim({"role": "RECYCLER", "party_id": "REC-01"}, CLAIMS["C-106"])  # another recycler's claim
    assert cedar.can_read_claim({"role": "RECYCLER", "party_id": "REC-02"}, CLAIMS["C-106"])
    assert cedar.can_read_claim({"role": "PRODUCER", "party_id": "PRD-01"}, CLAIMS["C-101"])      # claim covers its product
    assert not cedar.can_read_claim({"role": "PRODUCER", "party_id": "PRD-01"}, CLAIMS["C-106"])  # phone claim, not its product
    assert not cedar.can_read_claim({"role": "COLLECTOR", "party_id": "COL-118"}, CLAIMS["C-101"])


class FakeAvp:
    def __init__(self, decision):
        self.decision, self.calls = decision, []

    def is_authorized(self, **kw):
        self.calls.append(kw)
        return {"decision": self.decision}


def test_avp_adapter_sends_cedar_entities_and_honours_decision():
    fake = FakeAvp("ALLOW")
    a = AvpAuthorizer("store-1", client=fake)
    assert a.can_read_claim({"role": "PRODUCER", "party_id": "PRD-01"}, CLAIMS["C-101"])
    call = fake.calls[0]
    assert call["policyStoreId"] == "store-1" and call["action"] == {"actionType": "OAE::Action", "actionId": "ReadClaim"}
    claim_ent = next(e for e in call["entities"]["entityList"] if e["identifier"]["entityType"] == "OAE::Claim")
    assert claim_ent["attributes"]["producer_party_ids"] == {"set": [{"string": "PRD-01"}]}
    assert not AvpAuthorizer("s", client=FakeAvp("DENY")).can_read_claim({"role": "AUDITOR", "party_id": "A"}, CLAIMS["C-101"])
    assert not AvpAuthorizer("s", client=FakeAvp("ALLOW")).can_read_claim({"role": None}, CLAIMS["C-101"])  # no role: never asks AVP
