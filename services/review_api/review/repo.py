"""Claims repository: in-memory (local dev, tests) or DynamoDB (CONTRACT.md section 6, claims table)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from claimguard import io as cg_io
from claimguard.model import Claim, Evidence, Facility


class ClaimsRepo(Protocol):
    def list_claims(self) -> list[Claim]: ...
    def get_claim(self, claim_id: str) -> Claim | None: ...
    def put_claim(self, claim: Claim) -> None: ...
    def get_facility(self, party_id: str) -> Facility | None: ...
    def get_evidence(self, ids: list[str]) -> dict[str, Evidence]: ...
    def all_evidence(self) -> dict[str, Evidence]: ...
    def put_evidence(self, e: Evidence) -> None: ...
    def put_run(self, claim_id: str, run: dict) -> None: ...
    def latest_run(self, claim_id: str) -> dict | None: ...
    def append_review(self, claim_id: str, review: dict) -> dict: ...
    def reviews(self, claim_id: str) -> list[dict]: ...


class MemoryRepo:
    def __init__(self, data_dir: Path | None = None):
        d = data_dir or cg_io.DATA_DIR
        self._claims = {c.claim_id: c for c in cg_io.load_claims_dir(d / "claims")}
        self._facilities = cg_io.load_facilities(d / "facilities.json")
        self._evidence = cg_io.load_evidence_index(d / "evidence" / "evidence_index.json")
        self._runs: dict[str, dict] = {}
        self._reviews: dict[str, list[dict]] = {}

    def list_claims(self): return list(self._claims.values())
    def get_claim(self, claim_id): return self._claims.get(claim_id)
    def put_claim(self, claim): self._claims[claim.claim_id] = claim
    def get_facility(self, party_id): return self._facilities.get(party_id)
    def get_evidence(self, ids): return {i: self._evidence[i] for i in ids if i in self._evidence}
    def all_evidence(self): return dict(self._evidence)
    def put_evidence(self, e): self._evidence[e.evidence_id] = e
    def put_run(self, claim_id, run): self._runs[claim_id] = run
    def latest_run(self, claim_id): return self._runs.get(claim_id)

    def append_review(self, claim_id, review):
        lst = self._reviews.setdefault(claim_id, [])
        review = {**review, "seq": len(lst) + 1}
        lst.append(review)
        return review

    def reviews(self, claim_id): return list(self._reviews.get(claim_id, []))


def _dec(v: Any) -> Any:
    if isinstance(v, float):
        return Decimal(str(v))
    if isinstance(v, dict):
        return {k: _dec(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_dec(x) for x in v]
    return v


def _plain(v: Any) -> Any:
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    return v


class DynamoRepo:
    """Claims table (CONTRACT §6): CLAIM#<id>/META, CLAIM#<id>/RUN#<ran_at>, CLAIM#<id>/REVIEW#<seq 6>,
    CLAIM#<id>/BATCH#<id> (+ GSI1 BATCH# -> CLAIM#), FACILITY#<party>/META, EV#<id>/META."""

    def __init__(self, table_name: str, region: str = "ap-southeast-2", table=None):
        if table is None:
            import boto3  # noqa: PLC0415

            table = boto3.resource("dynamodb", region_name=region).Table(table_name)
        self._t = table

    def _query(self, pk: str, sk_prefix: str | None = None, **kw) -> list[dict]:
        from boto3.dynamodb.conditions import Key  # noqa: PLC0415

        cond = Key("PK").eq(pk)
        if sk_prefix:
            cond = cond & Key("SK").begins_with(sk_prefix)
        items, start = [], None
        while True:
            r = self._t.query(KeyConditionExpression=cond, **kw, **({"ExclusiveStartKey": start} if start else {}))
            items += r.get("Items", [])
            start = r.get("LastEvaluatedKey")
            if not start or "Limit" in kw:
                return [_plain(i) for i in items]

    def _scan_prefix(self, prefix: str) -> list[dict]:
        from boto3.dynamodb.conditions import Attr  # noqa: PLC0415

        items, start = [], None
        while True:
            r = self._t.scan(FilterExpression=Attr("PK").begins_with(prefix) & Attr("SK").eq("META"),
                             **({"ExclusiveStartKey": start} if start else {}))
            items += r.get("Items", [])
            start = r.get("LastEvaluatedKey")
            if not start:
                return [_plain(i) for i in items]

    def list_claims(self):
        return [cg_io.claim_from_dict(i["data"]) for i in self._scan_prefix("CLAIM#")]

    def get_claim(self, claim_id):
        r = self._t.get_item(Key={"PK": f"CLAIM#{claim_id}", "SK": "META"}).get("Item")
        return cg_io.claim_from_dict(_plain(r["data"])) if r else None

    def put_claim(self, claim):
        self._t.put_item(Item={"PK": f"CLAIM#{claim.claim_id}", "SK": "META", "data": _dec(cg_io.claim_to_dict(claim))})
        for b in claim.batch_ids:
            self._t.put_item(Item={"PK": f"CLAIM#{claim.claim_id}", "SK": f"BATCH#{b}",
                                   "GSI1PK": f"BATCH#{b}", "GSI1SK": f"CLAIM#{claim.claim_id}"})

    def get_facility(self, party_id):
        r = self._t.get_item(Key={"PK": f"FACILITY#{party_id}", "SK": "META"}).get("Item")
        return cg_io.facility_from_dict(party_id, _plain(r["data"])) if r else None

    def put_facility(self, party_id: str, data: dict):
        self._t.put_item(Item={"PK": f"FACILITY#{party_id}", "SK": "META", "data": _dec(data)})

    def get_evidence(self, ids):
        out = {}
        for i in ids:
            r = self._t.get_item(Key={"PK": f"EV#{i}", "SK": "META"}).get("Item")
            if r:
                out[i] = cg_io.evidence_from_dict(i, _plain(r["data"]))
        return out

    def all_evidence(self):
        return {i["data"]["evidence_id"]: cg_io.evidence_from_dict(i["data"]["evidence_id"], i["data"])
                for i in self._scan_prefix("EV#")}

    def put_evidence(self, e):
        self._t.put_item(Item={"PK": f"EV#{e.evidence_id}", "SK": "META", "data": _dec(cg_io.evidence_to_dict(e))})

    def put_run(self, claim_id, run):
        self._t.put_item(Item={"PK": f"CLAIM#{claim_id}", "SK": f"RUN#{run['ran_at']}", "data": _dec(run)})

    def latest_run(self, claim_id):
        items = self._query(f"CLAIM#{claim_id}", "RUN#", ScanIndexForward=False, Limit=1)
        return items[0]["data"] if items else None

    def append_review(self, claim_id, review):
        seq = len(self._query(f"CLAIM#{claim_id}", "REVIEW#")) + 1
        review = {**review, "seq": seq}
        self._t.put_item(
            Item={"PK": f"CLAIM#{claim_id}", "SK": f"REVIEW#{seq:06d}", "data": _dec(review)},
            ConditionExpression="attribute_not_exists(PK)",
        )
        return review

    def reviews(self, claim_id):
        return [i["data"] for i in self._query(f"CLAIM#{claim_id}", "REVIEW#")]
