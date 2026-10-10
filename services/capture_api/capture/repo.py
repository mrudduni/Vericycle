"""Storage for everything in the ledger table that is not an event (CONTRACT §6):
parties, tokens, receipts, drafts, evidence. Events go only through ledger.writer."""
from __future__ import annotations

import copy
import threading
from typing import Any, Protocol

from ledger.writer import MemoryStore


class Repo(Protocol):
    store: Any  # ledger.writer.Store + list_events(batch_id) + get_head_item(batch_id)

    def get(self, pk: str, sk: str = "META") -> dict | None: ...
    def put_new(self, item: dict) -> bool:
        """Put if (PK, SK) does not exist. False if it already exists."""
    def put(self, item: dict) -> None: ...
    def claim_token(self, pk: str, used_at: str, now_epoch: int) -> dict | None:
        """Atomically set used_at if unset and not expired; return the item, or None if used/expired/missing."""
    def increment(self, pk: str, sk: str, attr: str, ttl_epoch: int) -> int: ...


class MemoryRepo:
    def __init__(self) -> None:
        self.store = _MemLedger()
        self.items: dict[tuple[str, str], dict] = {}
        self._lock = threading.Lock()

    def get(self, pk, sk="META"):
        with self._lock:
            it = self.items.get((pk, sk))
            return copy.deepcopy(it) if it else None

    def put_new(self, item):
        with self._lock:
            k = (item["PK"], item["SK"])
            if k in self.items:
                return False
            self.items[k] = copy.deepcopy(item)
            return True

    def put(self, item):
        with self._lock:
            self.items[(item["PK"], item["SK"])] = copy.deepcopy(item)

    def claim_token(self, pk, used_at, now_epoch):
        with self._lock:
            it = self.items.get((pk, "META"))
            if not it or it.get("used_at") or int(it.get("expires_at", 0)) <= now_epoch:
                return None
            it["used_at"] = used_at
            return copy.deepcopy(it)

    def increment(self, pk, sk, attr, ttl_epoch):
        with self._lock:
            it = self.items.setdefault((pk, sk), {"PK": pk, "SK": sk, attr: 0, "expires_at": ttl_epoch})
            it[attr] += 1
            return it[attr]


class _MemLedger(MemoryStore):
    def get_head_item(self, batch_id):
        with self._lock:
            h = self.heads.get(batch_id)
            return copy.deepcopy(h) if h else None


class DynamoRepo:
    """Same contract on DynamoDB. boto3 is imported lazily so tests never need it."""

    def __init__(self, table_name: str, region: str = "ap-south-1"):
        from ledger.aws import DynamoStore, _item, _plain  # noqa: PLC0415

        self.store = DynamoStore(table_name, region)
        self.ddb = self.store.ddb
        self.table = table_name
        self._item, self._plain = _item, _plain

    def get(self, pk, sk="META"):
        r = self.ddb.get_item(TableName=self.table, Key=self._item({"PK": pk, "SK": sk}), ConsistentRead=True)
        return self._plain(r["Item"]) if "Item" in r else None

    def put_new(self, item):
        try:
            self.ddb.put_item(TableName=self.table, Item=self._item(item), ConditionExpression="attribute_not_exists(PK)")
            return True
        except self.ddb.exceptions.ConditionalCheckFailedException:
            return False

    def put(self, item):
        if str(item.get("PK", "")).startswith("BATCH#") and str(item.get("SK", "")).startswith("EVT#"):
            raise RuntimeError("event items are written only by ledger.writer")
        self.ddb.put_item(TableName=self.table, Item=self._item(item))

    def claim_token(self, pk, used_at, now_epoch):
        try:
            r = self.ddb.update_item(
                TableName=self.table, Key=self._item({"PK": pk, "SK": "META"}),
                UpdateExpression="SET used_at = :u",
                ConditionExpression="attribute_exists(PK) AND attribute_not_exists(used_at) AND expires_at > :now",
                ExpressionAttributeValues=self._item({":u": used_at, ":now": now_epoch}),
                ReturnValues="ALL_NEW",
            )
            return self._plain(r["Attributes"])
        except self.ddb.exceptions.ConditionalCheckFailedException:
            return None

    def increment(self, pk, sk, attr, ttl_epoch):
        r = self.ddb.update_item(
            TableName=self.table, Key=self._item({"PK": pk, "SK": sk}),
            UpdateExpression="ADD #a :one SET expires_at = if_not_exists(expires_at, :ttl)",
            ExpressionAttributeNames={"#a": attr},
            ExpressionAttributeValues=self._item({":one": 1, ":ttl": ttl_epoch}),
            ReturnValues="UPDATED_NEW",
        )
        return int(self._plain(r["Attributes"])[attr])
