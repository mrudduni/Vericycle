"""Authorisation through Cedar (SHAURYA.md 3.8).

``LocalCedarAuthorizer`` evaluates policies/ with cedarpy (tests, offline).
``AvpAuthorizer`` calls Verified Permissions IsAuthorized with the same entities (Lambda).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

NS = "OAE"


@dataclass
class Principal:
    kind: str                      # BusinessUser | HandlerToken | Copilot
    id: str
    attrs: dict = field(default_factory=dict)

    @property
    def role(self) -> str | None:
        return self.attrs.get("role")

    @property
    def party_id(self) -> str | None:
        return self.attrs.get("party_id")


def business_user(party_id: str, role: str) -> Principal:
    return Principal("BusinessUser", party_id, {"role": role, "party_id": party_id})


def handler_token(token_id: str, batch_id: str, seq: int, field_names: list[str]) -> Principal:
    return Principal("HandlerToken", token_id, {"batch_id": batch_id, "seq": seq, "field_names": list(field_names)})


def _uid(kind: str, id_: str) -> dict:
    return {"type": f"{NS}::{kind}", "id": id_}


def _entity(kind: str, id_: str, attrs: dict, parents: list | None = None) -> dict:
    return {"uid": _uid(kind, id_), "attrs": attrs, "parents": parents or []}


def build_request(principal: Principal, action: str, resource: tuple[str, str, dict], context: dict):
    rkind, rid, rattrs = resource
    entities = [_entity(principal.kind, principal.id, principal.attrs)]
    if rkind == "Event":
        entities.append(_entity("Batch", rattrs["batch_id"], {"material": rattrs.get("material", "")}))
        entities.append(_entity("Event", rid, {k: rattrs[k] for k in ("batch_id", "seq", "type")},
                                [_uid("Batch", rattrs["batch_id"])]))
    else:
        entities.append(_entity(rkind, rid, rattrs))
    return principal, action, (rkind, rid), context, entities


class LocalCedarAuthorizer:
    def __init__(self, policy_dir: Path | None = None):
        import cedarpy  # noqa: PLC0415

        self._cedar = cedarpy
        d = policy_dir or Path(__file__).resolve().parents[3] / "policies"
        if not d.exists():  # packaged Lambda layout
            d = Path(__file__).resolve().parent.parent / "policies"
        self.policies = "\n".join(p.read_text() for p in sorted(d.glob("*.cedar")))
        self.schema = (d / "schema.cedarschema.json").read_text()

    def is_authorized(self, principal: Principal, action: str, resource: tuple[str, str, dict], context: dict) -> bool:
        p, a, (rk, rid), ctx, ents = build_request(principal, action, resource, context)
        req = {
            "principal": f'{NS}::{p.kind}::{json.dumps(p.id)}',
            "action": f'{NS}::Action::{json.dumps(a)}',
            "resource": f'{NS}::{rk}::{json.dumps(rid)}',
            "context": ctx,
        }
        r = self._cedar.is_authorized(req, self.policies, ents, schema=self.schema)
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
    if isinstance(v, dict):
        return {"record": {k: _avp_value(x) for k, x in v.items()}}
    raise TypeError(type(v))


class AvpAuthorizer:
    def __init__(self, policy_store_id: str, region: str | None = None):
        import boto3  # noqa: PLC0415

        self.store_id = policy_store_id
        from ledger.aws import DEFAULT_REGION  # noqa: PLC0415
        self.client = boto3.client("verifiedpermissions", region_name=region or DEFAULT_REGION)

    def is_authorized(self, principal, action, resource, context) -> bool:
        p, a, (rk, rid), ctx, ents = build_request(principal, action, resource, context)
        r = self.client.is_authorized(
            policyStoreId=self.store_id,
            principal={"entityType": f"{NS}::{p.kind}", "entityId": p.id},
            action={"actionType": f"{NS}::Action", "actionId": a},
            resource={"entityType": f"{NS}::{rk}", "entityId": rid},
            context={"contextMap": {k: _avp_value(v) for k, v in ctx.items()}},
            entities={"entityList": [
                {"identifier": {"entityType": e["uid"]["type"], "entityId": e["uid"]["id"]},
                 "attributes": {k: _avp_value(v) for k, v in e["attrs"].items()},
                 "parents": [{"entityType": x["type"], "entityId": x["id"]} for x in e["parents"]]}
                for e in ents
            ]},
        )
        return r["decision"] == "ALLOW"
