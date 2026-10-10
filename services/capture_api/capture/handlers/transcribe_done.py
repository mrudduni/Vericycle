"""EventBridge: Transcribe job state change (COMPLETED/FAILED) -> extract -> draft READY."""
from __future__ import annotations

import os

import boto3
from aws_lambda_powertools import Logger, Tracer

from extract import transcribe as tr

from .. import chat
from .wiring import REGION, extractor, service

logger = Logger(service="transcribe-done")
tracer = Tracer(service="transcribe-done")
s3 = boto3.client("s3", region_name=REGION)


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler
def handler(event, context):
    d = event.get("detail", {})
    name, status = d.get("TranscriptionJobName", ""), d.get("TranscriptionJobStatus")
    draft_id = tr.draft_id_from_job(name, os.environ["STAGE"])
    if not draft_id:
        return {"ignored": name}
    svc = service()
    if status != "COMPLETED":
        chat.complete_voice_draft(svc, draft_id, "", extractor(), error="Could not understand the voice note. Please try again or type it.")
        return {"draft_id": draft_id, "status": "FAILED"}
    text, lang = tr.read_transcript(s3, svc.settings.evidence_bucket, draft_id)
    logger.info("transcribed", extra={"draft_id": draft_id, "language": lang, "chars": len(text)})
    chat.complete_voice_draft(svc, draft_id, text, extractor(), transcript_key=f"transcripts/{draft_id}.json")
    return {"draft_id": draft_id, "status": "READY"}
