"""Amazon Transcribe batch jobs. Completion arrives as an EventBridge event; no Lambda ever sleeps."""
from __future__ import annotations

import json
import re

LANGS = ["hi-IN", "en-IN"]
JOB_PREFIX = "oae-"


def job_name(stage: str, draft_id: str) -> str:
    return re.sub(r"[^0-9a-zA-Z._-]", "-", f"{JOB_PREFIX}{stage}-{draft_id}")[:200]


def start(client, *, stage: str, draft_id: str, bucket: str, key: str, kms_key_arn: str) -> str:
    name = job_name(stage, draft_id)
    fmt = key.rsplit(".", 1)[-1].lower()
    media_format = {"ogg": "ogg", "opus": "ogg", "webm": "webm", "m4a": "mp4", "mp4": "mp4", "wav": "wav", "mp3": "mp3"}.get(fmt, "webm")
    client.start_transcription_job(
        TranscriptionJobName=name,
        Media={"MediaFileUri": f"s3://{bucket}/{key}"},
        MediaFormat=media_format,
        IdentifyLanguage=True,
        LanguageOptions=LANGS,
        OutputBucketName=bucket,
        OutputKey=f"transcripts/{draft_id}.json",
        OutputEncryptionKMSKeyId=kms_key_arn,
        Tags=[{"Key": "project", "Value": "openaeye"}, {"Key": "stage", "Value": stage}],
    )
    return name


def draft_id_from_job(name: str, stage: str) -> str | None:
    prefix = f"{JOB_PREFIX}{stage}-"
    return name[len(prefix):] if name.startswith(prefix) else None


def read_transcript(s3, bucket: str, draft_id: str) -> tuple[str, str | None]:
    doc = json.loads(s3.get_object(Bucket=bucket, Key=f"transcripts/{draft_id}.json")["Body"].read())
    text = " ".join(t["transcript"] for t in doc["results"]["transcripts"]).strip()
    lang = doc["results"].get("language_code")
    return text, lang
