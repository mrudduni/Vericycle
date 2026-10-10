"""EventBridge "Object Created" -> evidence record in the claims table (CONTRACT §6 `EV#<id>/META`).

Object key convention (both buckets): ``evidence/<batch_id or claim_id>/<KIND>/<file>`` where KIND is one of
PHOTO, WEIGH_SLIP, INVOICE, POWER_BILL. Keys outside ``evidence/`` (qr/, audio/, transcripts/) are ignored.
Idempotent: the evidence ID is derived from the bucket+key, so a retried event rewrites the same item.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from .image_meta import analyze_photo, sha256_hex
from .textract_parse import parse_expense

IST = timezone(timedelta(hours=5, minutes=30))
KINDS = {"PHOTO", "WEIGH_SLIP", "INVOICE", "POWER_BILL"}


def evidence_id_for(bucket: str, key: str) -> str:
    return "EV-" + hashlib.sha256(f"{bucket}/{key}".encode()).hexdigest()[:20].upper()


def parse_key(key: str) -> tuple[str, str] | None:
    parts = key.split("/")
    if len(parts) < 4 or parts[0] != "evidence" or parts[2] not in KINDS:
        return None
    return parts[1], parts[2]


def process(bucket: str, key: str, data: bytes, textract=None) -> dict | None:
    """Returns the evidence dict (evidence_to_dict shape) or None if the key is not evidence."""
    parsed = parse_key(key)
    if parsed is None:
        return None
    ref, kind = parsed
    rec: dict[str, Any] = {
        "evidence_id": evidence_id_for(bucket, key), "kind": kind, "s3_key": key,
        "sha256": sha256_hex(data), "phash": None, "exif": {}, "extracted": {},
        "received_at_server": datetime.now(IST).isoformat(timespec="seconds"),
        "batch_id": ref if not ref.startswith("C-") else None,
        "claim_id": ref if ref.startswith("C-") else None,
    }
    if kind == "PHOTO":
        meta = analyze_photo(data)
        rec.update(phash=meta["phash"], exif=meta["exif"])
    elif kind in ("INVOICE", "WEIGH_SLIP", "POWER_BILL") and textract is not None:
        resp = textract.analyze_expense(Document={"Bytes": data})
        rec["extracted"] = parse_expense(resp)
    return rec


def handler(event: dict, context: Any = None) -> dict:
    import boto3  # noqa: PLC0415

    from review.repo import DynamoRepo  # noqa: PLC0415
    from claimguard.io import evidence_from_dict  # noqa: PLC0415

    s3 = boto3.client("s3")
    textract = boto3.client("textract")
    repo = DynamoRepo(os.environ["CLAIMS_TABLE"])
    d = event.get("detail", {})
    bucket, key = d["bucket"]["name"], d["object"]["key"]
    obj = s3.get_object(Bucket=bucket, Key=key)
    rec = process(bucket, key, obj["Body"].read(), textract)
    if rec is None:
        return {"ignored": key}
    # The light class is stored in exif as `light_class`; R5 reads it from there.
    repo.put_evidence(evidence_from_dict(rec["evidence_id"], rec))
    return {"evidence_id": rec["evidence_id"], "kind": rec["kind"]}
