"""Claim-read authorization through Cedar, using ChainTrack's policies (policies/*.cedar, CONTRACT §2 policy store).

`AvpAuthorizer` calls Amazon Verified Permissions IsAuthorized with the policy store ChainTrack deployed.
`LocalCedarAuthorizer` evaluates the same .cedar files with cedarpy (tests and local dev).
`DevAuthorizer` is the plain-Python mirror used on solo stages with no policy store; a test proves all three agree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

NS = "OAE"
POLICY_DIR = Path(__file__).resolve().parents[3] / "policies"


class Authorizer(Protocol):
    def can_read_claim(self, principal: dict, claim) -> bool: ...


def _entities(principal: dict, claim) -> list[dict]:
    return [
        {"uid": {"type": f"{NS}::BusinessUser", "id": principal.get("party_id") or "anonymous"},
         "attrs": {"role": principal.get("role") or "", "party_id": principal.get("party_id") or ""}, "parents": []},
        {"uid": {"type": f"{NS}::Claim", "id": claim.claim_id},
         "attrs": {"recycler_party_id": claim.recycler_party_id, "producer_party_ids": list(claim.producer_party_ids)}, "parents": []},
    ]


class DevAuthorizer:
    def can_read_claim(self, principal: dict, claim) -> bool:
        role = principal.get("role")
        if role == "AUDITOR":
            return True
        if role == "RECYCLER":
            return principal.get("party_id") == claim.recycler_party_id
        if role == "PRODUCER":
            return principal.get("party_id") in claim.producer_party_ids
        return False


class LocalCedarAuthorizer:
    def __init__(self, policy_dir: Path | None = None):
        import cedarpy  # noqa: PLC0415

        d = policy_dir or POLICY_DIR
        if not d.exists():  # packaged Lambda layout: policies/ next to the package
            d = Path(__file__).resolve().parent.parent / "policies"
        self._cedar = cedarpy
        self.policies = "\n".join(p.read_text(encoding="utf-8") for p in sorted(d.glob("*.cedar")))
        self.schema = (d / "schema.cedarschema.json").read_text(encoding="utf-8")

    def can_read_claim(self, principal: dict, claim) -> bool:
        if not principal.get("role"):
            return False
        req = {
            "principal": f'{NS}::BusinessUser::{json.dumps(principal.get("party_id") or "anonymous")}',
            "action": f'{NS}::Action::"ReadClaim"',
            "resource": f"{NS}::Claim::{json.dumps(claim.claim_id)}",
            "context": {},
        }
        r = self._cedar.is_authorized(req, self.policies, _entities(principal, claim), schema=self.schema)
        return r.decision.value == "Allow" and not r.diagnostics.errors


def _avp_value(v: Any) -> dict:
    if isinstance(v, bool):
        return {"boolean": v}
    if isinstance(v, int):
        return {"long": v}
    if isinstance(v, str):
        return {"string": v}
    if isinstance(v, (list, set, tuple)):
        return {"set": [_avp_value(x) for x in v]}
    raise TypeError(type(v))


class AvpAuthorizer:
    def __init__(self, policy_store_id: str, region: str = "ap-south-1", client=None):
        if client is None:
            import boto3  # noqa: PLC0415

            client = boto3.client("verifiedpermissions", region_name=region)
        self.store_id = policy_store_id
        self.client = client

    def can_read_claim(self, principal: dict, claim) -> bool:
        if not principal.get("role"):
            return False
        ents = _entities(principal, claim)
        r = self.client.is_authorized(
            policyStoreId=self.store_id,
            principal={"entityType": f"{NS}::BusinessUser", "entityId": principal.get("party_id") or "anonymous"},
            action={"actionType": f"{NS}::Action", "actionId": "ReadClaim"},
            resource={"entityType": f"{NS}::Claim", "entityId": claim.claim_id},
            context={"contextMap": {}},
            entities={"entityList": [
                {"identifier": {"entityType": e["uid"]["type"], "entityId": e["uid"]["id"]},
                 "attributes": {k: _avp_value(v) for k, v in e["attrs"].items()}, "parents": []} for e in ents]},
        )
        return r["decision"] == "ALLOW"
