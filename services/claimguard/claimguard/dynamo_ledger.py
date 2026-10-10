"""Reads Shaurya's ledger table (CONTRACT.md section 6). The only module besides handlers that imports boto3.

Ledger items: PK `BATCH#<id>`, SK `EVT#<seq>` (events) or `META` (batch head). Every other PK
prefix in the table (ANOMALY#, CONFDEV#, PHONE#, DRAFT#, ...) is ignored.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .ledger_reader import effective_events, parse_event
from .model import Batch, Material


def _plain(v: Any) -> Any:
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if isinstance(v, set):
        return [_plain(x) for x in v]
    return v


class DynamoLedgerReader:
    def __init__(self, table_name: str, region: str = "ap-south-1", table=None):
        if table is None:
            import boto3  # noqa: PLC0415

            table = boto3.resource("dynamodb", region_name=region).Table(table_name)
        self._table = table
        self._cache: dict[str, Batch | None] = {}

    def _query_all(self, **kw) -> list[dict]:
        items, start = [], None
        while True:
            resp = self._table.query(**kw, **({"ExclusiveStartKey": start} if start else {}))
            items.extend(resp.get("Items", []))
            start = resp.get("LastEvaluatedKey")
            if not start:
                return items

    def get_batch(self, batch_id: str) -> Batch | None:
        if batch_id in self._cache:
            return self._cache[batch_id]
        from boto3.dynamodb.conditions import Key  # noqa: PLC0415

        items = [_plain(i) for i in self._query_all(KeyConditionExpression=Key("PK").eq(f"BATCH#{batch_id}"))]
        meta = next((i for i in items if i["SK"] == "META"), None)
        events = [i for i in items if i["SK"].startswith("EVT#")]
        if meta is None or not events:
            self._cache[batch_id] = None
            return None
        parsed = effective_events(tuple(parse_event(batch_id, e) for e in sorted(events, key=lambda e: e["seq"])))
        batch = Batch(
            batch_id=batch_id,
            material=Material(meta["material"]),
            events=parsed,
            parent_ids=tuple(meta.get("parent_batch_ids", [])),
            child_ids=tuple(meta.get("child_batch_ids", [])),
            status=meta.get("status", "OPEN"),
        )
        self._cache[batch_id] = batch
        return batch

    def all_batches(self) -> list[Batch]:
        from boto3.dynamodb.attributes import TypeDeserializer  # noqa: F401, PLC0415
        from boto3.dynamodb.conditions import Attr  # noqa: PLC0415

        ids, start = [], None
        while True:
            resp = self._table.scan(
                FilterExpression=Attr("SK").eq("META") & Attr("PK").begins_with("BATCH#"),
                ProjectionExpression="PK",
                **({"ExclusiveStartKey": start} if start else {}),
            )
            ids += [i["PK"].split("#", 1)[1] for i in resp.get("Items", [])]
            start = resp.get("LastEvaluatedKey")
            if not start:
                break
        return [b for b in (self.get_batch(i) for i in sorted(ids)) if b]

    def batches_citing_lead(self) -> dict[str, list[str]]:
        return {}
