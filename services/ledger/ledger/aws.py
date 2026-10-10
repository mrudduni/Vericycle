"""AWS adapters: the only module in the ledger package that imports boto3."""
from __future__ import annotations

import base64
import functools
from decimal import Decimal
from typing import Any, Mapping

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError

from .writer import ConflictError, Head

_ser, _deser = TypeSerializer(), TypeDeserializer()
DEFAULT_REGION = "ap-south-1"


def _to_dynamo(v: Any) -> Any:
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, float):
        return Decimal(str(v))
    if isinstance(v, dict):
        return {k: _to_dynamo(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_to_dynamo(x) for x in v]
    return v


def _item(d: Mapping[str, Any]) -> dict:
    return {k: _ser.serialize(_to_dynamo(v)) for k, v in d.items()}


def _plain(item: Mapping[str, Any]) -> dict:
    return {k: _deser.deserialize(v) for k, v in item.items()}


@functools.lru_cache(maxsize=None)
def ssm_param(name: str, region: str = DEFAULT_REGION) -> str:
    return boto3.client("ssm", region_name=region).get_parameter(Name=name)["Parameter"]["Value"]


class DynamoStore:
    def __init__(self, table_name: str, region: str = DEFAULT_REGION, client=None):
        self.table = table_name
        self.ddb = client or boto3.client("dynamodb", region_name=region)

    @classmethod
    def for_stage(cls, stage: str, region: str = DEFAULT_REGION) -> "DynamoStore":
        return cls(f"oae-{stage}-ledger", region)

    def get_head_item(self, batch_id: str) -> dict | None:
        r = self.ddb.get_item(TableName=self.table, Key=_item({"PK": f"BATCH#{batch_id}", "SK": "META"}), ConsistentRead=True)
        return _plain(r["Item"]) if "Item" in r else None

    def get_head(self, batch_id: str) -> Head:
        h = self.get_head_item(batch_id)
        if not h:
            return Head()
        return Head(int(h["last_seq"]), h["last_hash"], True, h)

    def list_events(self, batch_id: str) -> list[dict]:
        out, kwargs = [], {
            "TableName": self.table,
            "KeyConditionExpression": "PK = :pk AND begins_with(SK, :evt)",
            "ExpressionAttributeValues": _item({":pk": f"BATCH#{batch_id}", ":evt": "EVT#"}),
            "ConsistentRead": True,
        }
        while True:
            r = self.ddb.query(**kwargs)
            out += [_plain(i) for i in r["Items"]]
            if "LastEvaluatedKey" not in r:
                return out
            kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]

    def append(self, event: dict, expected_last_seq: int, head_updates: Mapping[str, Any]) -> None:
        pk = f"BATCH#{event['batch_id']}"
        ev_item = dict(event, PK=pk, SK=f"EVT#{event['seq']:06d}",
                       GSI2PK=f"PARTY#{event['actor_party_id']}", GSI2SK=event["at_server"])
        names = {"#ls": "last_seq", "#lh": "last_hash", "#st": "status", "#pb": "parent_batch_ids", "#cb": "child_batch_ids"}
        values: dict[str, Any] = {":ls": event["seq"], ":lh": event["hash"], ":open": "OPEN", ":empty": []}
        sets = ["#ls = :ls", "#lh = :lh"]
        updates = {k: v for k, v in head_updates.items() if v is not None}
        for i, (k, v) in enumerate(sorted(updates.items())):
            names[f"#u{i}"] = k
            values[f":u{i}"] = v
            sets.append(f"#u{i} = :u{i}")
        for key, default in (("status", ":open"), ("parent_batch_ids", ":empty"), ("child_batch_ids", ":empty")):
            if key not in updates:
                alias = {"status": "#st", "parent_batch_ids": "#pb", "child_batch_ids": "#cb"}[key]
                sets.append(f"{alias} = if_not_exists({alias}, {default})")
        if expected_last_seq == 0:
            cond = "attribute_not_exists(PK)"
        else:
            cond = "#ls = :expected"
            values[":expected"] = expected_last_seq
        try:
            self.ddb.transact_write_items(TransactItems=[
                {"Put": {"TableName": self.table, "Item": _item(ev_item), "ConditionExpression": "attribute_not_exists(PK)"}},
                {"Update": {"TableName": self.table, "Key": _item({"PK": pk, "SK": "META"}),
                            "UpdateExpression": "SET " + ", ".join(sets), "ConditionExpression": cond,
                            "ExpressionAttributeNames": names, "ExpressionAttributeValues": _item(values)}},
            ])
        except ClientError as e:
            if e.response["Error"]["Code"] == "TransactionCanceledException":
                raise ConflictError(event["batch_id"]) from e
            raise


class KmsSigner:
    def __init__(self, key_id: str, region: str = DEFAULT_REGION, client=None):
        self.key_id = key_id
        self.kms = client or boto3.client("kms", region_name=region)
        self._pem: str | None = None

    @classmethod
    def for_stage(cls, stage: str, region: str = DEFAULT_REGION) -> "KmsSigner":
        return cls(ssm_param(f"/openaeye/{stage}/ledger/signing-key-arn", region), region)

    def sign(self, hash_hex: str) -> str:
        r = self.kms.sign(KeyId=self.key_id, Message=bytes.fromhex(hash_hex),
                          MessageType="DIGEST", SigningAlgorithm="ECDSA_SHA_256")
        return base64.b64encode(r["Signature"]).decode("ascii")

    def public_key_pem(self) -> str:
        if self._pem is None:
            from .signing import der_to_pem
            self._pem = der_to_pem(self.kms.get_public_key(KeyId=self.key_id)["PublicKey"])
        return self._pem


class KmsPhoneHasher:
    """HMAC-SHA256 of a phone number with a KMS-held HMAC_256 key. Plain numbers are never stored."""

    def __init__(self, key_id: str, region: str = DEFAULT_REGION, client=None):
        self.key_id = key_id
        self.kms = client or boto3.client("kms", region_name=region)

    def __call__(self, phone_e164: str) -> str:
        r = self.kms.generate_mac(KeyId=self.key_id, Message=phone_e164.encode("utf-8"), MacAlgorithm="HMAC_SHA_256")
        return r["Mac"].hex()
