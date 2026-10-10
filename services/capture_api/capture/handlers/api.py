"""Capture HTTP API (CONTRACT §7) on one Lambda with the Powertools router.

Every POST is idempotent on the client's ``Idempotency-Key`` header (a ULID made on the device).
"""
from __future__ import annotations

import json
import os

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, Response
from aws_lambda_powertools.utilities.idempotency import (
    DynamoDBPersistenceLayer, IdempotencyConfig, idempotent_function,
)

from ..errors import ApiError, bad
from ..service import scrub
from .. import chat
from .wiring import extractor, principal_from_claims, service, transcriber

logger = Logger(service="capture-api")
tracer = Tracer(service="capture-api")
def _serialize(obj) -> str:
    # Every JSON body passes through scrub() as a last line of defence for P6.
    return json.dumps(scrub(obj), separators=(",", ":"), ensure_ascii=False, default=_default)


def _default(o):
    from decimal import Decimal
    if isinstance(o, Decimal):
        return int(o) if o == o.to_integral_value() else float(o)
    raise TypeError(type(o).__name__)


app = APIGatewayHttpResolver(serializer=_serialize)

persistence = DynamoDBPersistenceLayer(table_name=os.environ.get("IDEMPOTENCY_TABLE", "unset"))
idem_config = IdempotencyConfig(expires_after_seconds=24 * 3600, raise_on_no_idempotency_key=True)


def _principal():
    ctx = app.current_event.request_context.authorizer
    claims = ctx.jwt_claim if ctx else None
    return principal_from_claims(claims)


def _body() -> dict:
    b = app.current_event.json_body
    if not isinstance(b, dict):
        raise bad("INVALID_BODY", "Body must be a JSON object.")
    return b


@idempotent_function(data_keyword_argument="req", config=idem_config, persistence_store=persistence)
def _run_post(req: dict) -> dict:
    """``req`` = route, idempotency key, caller and body: the same key replays the first result."""
    svc, p, body = service(), _principal(), req["body"]
    route, a = req["route"], req["args"]
    if route == "handovers":
        return svc.create_handover(p, body)
    if route == "events":
        return svc.add_event(p, a["batch_id"], body)
    if route == "confirm":
        return svc.confirm_post(a["token"], body.get("answer"), device_id=body.get("device_id"))
    if route == "presign":
        return svc.presign(p, body)
    if route == "chat_message":
        return chat.chat_message(svc, p, body, extractor=extractor(), transcriber=transcriber())
    if route == "chat_confirm":
        return chat.confirm_draft(svc, p, a["draft_id"], body)
    raise bad("UNKNOWN_ROUTE", route)


def _post(route: str, **args):
    key = (app.current_event.headers or {}).get("idempotency-key") or (app.current_event.headers or {}).get("Idempotency-Key")
    if not key or len(key) > 64:
        raise bad("MISSING_IDEMPOTENCY_KEY", "Send an Idempotency-Key header (a ULID made on the device).")
    p = _principal()
    caller = f"{p.kind}:{p.id}" if p else "public"
    idem_config.register_lambda_context(app.lambda_context)
    return _run_post(req={"route": route, "args": args, "key": key, "caller": caller, "body": _body()})


@app.post("/handovers")
def post_handover():
    return _post("handovers")


@app.post("/batches/<batch_id>/events")
def post_event(batch_id: str):
    return _post("events", batch_id=batch_id)


@app.post("/chat/messages")
def post_chat_message():
    return _post("chat_message")


@app.post("/chat/drafts/<draft_id>/confirm")
def post_chat_confirm(draft_id: str):
    return _post("chat_confirm", draft_id=draft_id)


@app.post("/evidence/presign")
def post_presign():
    return _post("presign")


@app.post("/confirm/<token>")
def post_confirm(token: str):
    return _post("confirm", token=token)


@app.get("/chat/drafts/<draft_id>")
def get_chat_draft(draft_id: str):
    return chat.get_draft(service(), _principal(), draft_id)


@app.get("/confirm/<token>")
def get_confirm(token: str):
    return service().confirm_get(token)


@app.get("/batches/<batch_id>")
def get_batch(batch_id: str):
    return service().get_batch(_principal(), batch_id)


@app.get("/batches/<batch_id>/lineage")
def get_lineage(batch_id: str):
    return service().lineage(_principal(), batch_id)


@app.get("/r/<token>")
def get_receipt(token: str):
    return service().receipt(token)


@app.get("/verify/<batch_id>")
def get_verify(batch_id: str):
    return service().verify(batch_id)


@app.get("/digests/latest")
def get_digest_latest():
    d = service().digest_reader.latest()
    if not d:
        raise ApiError(404, "NOT_FOUND", "No digest published yet.")
    return d


@app.get("/digests/<date>")
def get_digest(date: str):
    d = service().digest_reader.for_date(date)
    if not d:
        raise ApiError(404, "NOT_FOUND", f"No digest for {date}.")
    return d


@app.exception_handler(ApiError)
def handle_api_error(e: ApiError):
    return Response(status_code=e.status, content_type="application/json", body=e.body())


@app.exception_handler(Exception)
def handle_other(e: Exception):
    logger.exception("unhandled")
    return Response(status_code=500, content_type="application/json",
                    body={"error": {"code": "INTERNAL", "message": "Something went wrong. Please retry."}})


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler
def handler(event, context):
    resp = app.resolve(event, context)
    return resp

