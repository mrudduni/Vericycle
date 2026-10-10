"""Builds the CaptureService from Lambda environment variables (cold start, once)."""
from __future__ import annotations

import functools
import json
import logging
import os

import boto3
from botocore.config import Config

from ..authz import AvpAuthorizer, business_user
from ..repo import DynamoRepo
from ..service import CaptureService, Settings

REGION = os.environ.get("AWS_REGION", "ap-southeast-2")


class S3Presigner:
    def __init__(self, bucket: str):
        self.bucket = bucket
        self.s3 = boto3.client("s3", region_name=REGION, config=Config(signature_version="s3v4"))

    def __call__(self, key: str, content_type: str, size: int, sha256_hex: str | None) -> str:
        import base64
        params = {"Bucket": self.bucket, "Key": key, "ContentType": content_type, "ContentLength": size}
        if sha256_hex:
            params["ChecksumSHA256"] = base64.b64encode(bytes.fromhex(sha256_hex)).decode()
        return self.s3.generate_presigned_url("put_object", Params=params, ExpiresIn=900)


class S3DigestReader:
    def __init__(self, bucket: str):
        self.bucket = bucket
        self.s3 = boto3.client("s3", region_name=REGION)

    def _get(self, key: str):
        try:
            return json.loads(self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read())
        except self.s3.exceptions.NoSuchKey:
            return None

    def latest(self):
        return self._get("digests/latest.json")

    def for_date(self, date: str):
        return self._get(f"digests/{date}.json")


@functools.lru_cache(maxsize=1)
def service() -> CaptureService:
    from ledger.aws import KmsSigner

    env = os.environ
    return CaptureService(
        repo=DynamoRepo(env["TABLE_NAME"], REGION),
        signer=KmsSigner(env["SIGNING_KEY_ARN"], REGION),
        authz=AvpAuthorizer(env["POLICY_STORE_ID"], REGION),
        settings=Settings(web_url=env.get("WEB_URL", "").rstrip("/"), wa_number=env.get("WA_NUMBER") or None,
                          evidence_bucket=env["EVIDENCE_BUCKET"]),
        presigner=S3Presigner(env["EVIDENCE_BUCKET"]),
        digest_reader=S3DigestReader(env["DIGEST_BUCKET"]),
    )


def principal_from_claims(claims: dict | None):
    """Cognito JWT claims -> BusinessUser. Role = the single business group; party from custom:party_id."""
    if not claims:
        return None
    groups = claims.get("cognito:groups") or []
    if isinstance(groups, str):  # HTTP API passes arrays as "[A B]"
        groups = groups.strip("[]").replace(",", " ").split()
    roles = [g for g in groups if g in {"COLLECTOR", "AGGREGATOR", "RECYCLER", "AUDITOR", "PRODUCER"}]
    party = claims.get("custom:party_id")
    if len(roles) != 1 or not party:
        return None
    return business_user(party, roles[0])


@functools.lru_cache(maxsize=1)
def _model_id() -> str:
    name = os.environ.get("MODEL_ID_PARAM")
    if not name:
        return os.environ.get("MODEL_ID", "")
    return boto3.client("ssm", region_name=REGION).get_parameter(Name=name)["Parameter"]["Value"]


def extractor():
    """Bedrock extraction, or the deterministic reader when EXTRACT_MODE=offline or no model is set."""
    from extract import bedrock_extract as bx

    model = _model_id() if os.environ.get("EXTRACT_MODE") != "offline" else ""
    if not model:
        return bx.extract_offline
    client = boto3.client("bedrock-runtime", region_name=os.environ.get("BEDROCK_REGION", REGION))

    def run(text: str) -> dict:
        # A model outage must not block a handover: the deterministic reader marks every field uncertain,
        # so the collector checks them on the read-back card.
        try:
            return bx.extract(text, model, client)
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).warning("bedrock extraction failed; using deterministic reader", exc_info=True)
            return bx.extract_offline(text)
    return run


def transcriber():
    if os.environ.get("VOICE_MODE") == "off":
        return None  # chat answers VOICE_UNAVAILABLE and asks for typed text
    from extract import transcribe as tr

    client = boto3.client("transcribe", region_name=REGION)
    stage, kms = os.environ["STAGE"], os.environ["DATA_KEY_ARN"]
    return lambda draft_id, bucket, key: tr.start(client, stage=stage, draft_id=draft_id, bucket=bucket, key=key, kms_key_arn=kms)
