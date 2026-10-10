"""SNS (from AWS End User Messaging Social) -> WhatsAppIngest. Deployed only when WhatsApp is linked."""
from __future__ import annotations

import base64
import json
import os

import boto3
from aws_lambda_powertools import Logger, Tracer

from capture.handlers.wiring import REGION, extractor, service, transcriber
from ledger.aws import KmsPhoneHasher

from .whatsapp import WA_API, WhatsAppIngest, parse_sns

logger = Logger(service="whatsapp-ingest")
tracer = Tracer(service="whatsapp-ingest")
social = boto3.client("socialmessaging", region_name=REGION)
kms = boto3.client("kms", region_name=REGION)
_ingest = None


def ingest() -> WhatsAppIngest:
    global _ingest
    if _ingest is None:
        svc = service()
        data_key = os.environ["DATA_KEY_ARN"]

        def send(origin, payload):
            social.send_whatsapp_message(originationPhoneNumberId=origin or os.environ["WA_PHONE_NUMBER_ID"],
                                         message=json.dumps(payload).encode(), metaApiVersion=WA_API)

        def fetch(media_id, origin, key):
            social.get_whatsapp_message_media(mediaId=media_id,
                                              originationPhoneNumberId=origin or os.environ["WA_PHONE_NUMBER_ID"],
                                              destinationS3File={"bucketName": svc.settings.evidence_bucket, "key": key})

        _ingest = WhatsAppIngest(
            svc, hmac=KmsPhoneHasher(os.environ["PHONE_HMAC_KEY_ARN"], REGION), send=send, fetch_media=fetch,
            encrypt=lambda s: base64.b64encode(kms.encrypt(KeyId=data_key, Plaintext=s.encode(),
                                                           EncryptionContext={"use": "wa-reply"})["CiphertextBlob"]).decode(),
            decrypt=lambda s: kms.decrypt(CiphertextBlob=base64.b64decode(s),
                                          EncryptionContext={"use": "wa-reply"})["Plaintext"].decode(),
            extractor=extractor(), transcriber=transcriber())
    return _ingest


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler
def handler(event, context):
    results = []
    for rec in event.get("Records", []):
        for m in parse_sns(rec["Sns"]["Message"]):
            try:
                results.append(ingest().on_message(m))
            except Exception:  # noqa: BLE001  one bad message must not block the batch
                logger.exception("message failed", extra={"message_id": m.message_id, "kind": m.kind})
                results.append("error")
    logger.info("processed", extra={"results": results})  # never log numbers or text
    return {"results": results}
