"""Daily Merkle digest -> S3 Object Lock bucket (nightly via EventBridge Scheduler, or on demand).

Event: {"date": "2026-10-10"} (optional; default = yesterday in IST). On-demand demo calls use today.
Writes digests/<date>.json and digests/latest.json. Scans the ledger table for event items of that
IST date; fine at demo scale (a GSI on the date would replace the scan at pilot scale).
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta

import boto3
from aws_lambda_powertools import Logger

from ..aws import KmsSigner, _plain
from ..digest import IST, build_digest

logger = Logger(service="ledger-digest")
REGION = os.environ.get("AWS_REGION", "ap-south-1")


def _events_for(ddb, table: str, day: date) -> list[dict]:
    start = datetime(day.year, day.month, day.day, tzinfo=IST)
    lo, hi = start.isoformat(timespec="seconds"), (start + timedelta(days=1)).isoformat(timespec="seconds")
    out, kwargs = [], {"TableName": table, "FilterExpression": "begins_with(SK, :e) AND at_server BETWEEN :lo AND :hi",
                       "ExpressionAttributeValues": {":e": {"S": "EVT#"}, ":lo": {"S": lo}, ":hi": {"S": hi}}}
    while True:
        r = ddb.scan(**kwargs)
        out += [_plain(i) for i in r["Items"]]
        if "LastEvaluatedKey" not in r:
            return out
        kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]


@logger.inject_lambda_context
def handler(event, context):
    day = date.fromisoformat(event["date"]) if event.get("date") else (datetime.now(IST) - timedelta(days=1)).date()
    ddb = boto3.client("dynamodb", region_name=REGION)
    s3 = boto3.client("s3", region_name=REGION)
    signer = KmsSigner(os.environ["SIGNING_KEY_ARN"], REGION)
    doc = build_digest(_events_for(ddb, os.environ["TABLE_NAME"], day), day, signer)
    doc["public_key_pem"] = signer.public_key_pem()
    body = json.dumps(doc, indent=2).encode()
    for key in (f"digests/{day.isoformat()}.json", "digests/latest.json"):
        s3.put_object(Bucket=os.environ["DIGEST_BUCKET"], Key=key, Body=body, ContentType="application/json")
    logger.info("digest written", extra={"date": doc["date"], "count": doc["count"], "root": doc["root"]})
    return {k: doc[k] for k in ("date", "root", "count")}
