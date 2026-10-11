"""Capture API business logic. Handlers in ``handlers/`` are thin wrappers over this class."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Iterable

from ledger.verify_chain import verify_events
from ledger.writer import IST, LedgerBusyError, append_event, now_ist

from . import ids, materials as M
from . import anomalies
from .authz import Principal, handler_token
from .errors import ApiError, bad, forbidden, gone, not_found, unprocessable
from .status import CHIP_TEXT, asked_fields, event_status, evidence_badge, effective_events, field_status

TOKEN_DAYS = 7
SPLIT_TOLERANCE = 0.02
BUSINESS_EVENT_TYPES = {"TRANSFER", "SPLIT", "MERGE", "INTAKE", "PROCESS", "OUTPUT", "CORRECTION"}
STATUS_AFTER = {"INTAKE": "AT_RECYCLER", "PROCESS": "PROCESSED", "SPLIT": "SPLIT", "MERGE": "MERGED"}
PRIVATE_KEYS = {"phone_hmac", "phone", "phone_e164", "display_name", "creator_device_id", "sender_hmac"}
EVIDENCE_KINDS = {"PHOTO", "WEIGH_SLIP", "INVOICE", "POWER_BILL", "VOICE_TRANSCRIPT", "AUDIO"}
CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "audio/webm", "audio/ogg", "audio/mp4", "application/pdf"}


def scrub(obj: Any) -> Any:
    """Remove anything that could identify a handler (P6). Applied to every API response."""
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items() if k not in PRIVATE_KEYS and k != "kms_sig_raw"}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    return obj


def _parse_time(s: Any, name: str) -> str:
    if not isinstance(s, str):
        raise bad("INVALID_TIME", f"{name} must be an ISO 8601 time with offset.")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise bad("INVALID_TIME", f"{name} must be an ISO 8601 time with offset.") from None
    if dt.tzinfo is None:
        raise bad("INVALID_TIME", f"{name} needs a UTC offset, e.g. +05:30.")
    return dt.isoformat(timespec="seconds")


def _plain(v: Any) -> Any:
    return v.get("value") if isinstance(v, dict) and "value" in v else v


def _claimed_roles(body: Any) -> set[str]:
    """Every confirmed_by_roles value anywhere in a request body (fed to Cedar as context)."""
    found: set[str] = set()
    if isinstance(body, dict):
        for k, v in body.items():
            if k == "confirmed_by_roles" and isinstance(v, list):
                found |= {str(x) for x in v}
            else:
                found |= _claimed_roles(v)
    elif isinstance(body, list):
        for v in body:
            found |= _claimed_roles(v)
    return found


@dataclass
class Settings:
    web_url: str = "https://localhost:5173"
    wa_number: str | None = None           # Vericycle WhatsApp number, digits only, for wa.me links
    evidence_bucket: str = "local-evidence"


class CaptureService:
    def __init__(self, repo, signer, authz, settings: Settings | None = None,
                 clock: Callable[[], str] = now_ist, presigner=None, digest_reader=None):
        self.repo, self.signer, self.authz = repo, signer, authz
        self.settings = settings or Settings()
        self.clock = clock
        self.presigner = presigner
        self.digest_reader = digest_reader

    # ---------------------------------------------------------------- helpers
    def _epoch(self) -> int:
        return int(datetime.fromisoformat(self.clock()).timestamp())

    def _require(self, principal: Principal, action: str, resource, context: dict) -> None:
        if principal is None:
            raise ApiError(401, "UNAUTHENTICATED", "Please sign in.")
        if not self.authz.is_authorized(principal, action, resource, context):
            raise forbidden()

    def _append(self, batch_id: str, body: dict, head_updates: dict | None = None, at_server: str | None = None) -> dict:
        try:
            return append_event(self.repo.store, self.signer, batch_id, body,
                                head_updates=head_updates, clock=self.clock, at_server=at_server)
        except LedgerBusyError:
            raise ApiError(503, "LEDGER_BUSY", "Too many writes to this batch at once. Please retry.") from None

    def _events(self, batch_id: str) -> list[dict]:
        from ledger.canonical import event_from_item
        return [event_from_item(e) for e in self.repo.store.list_events(batch_id)]

    def _head(self, batch_id: str) -> dict:
        h = self.repo.store.get_head_item(batch_id)
        if not h:
            raise not_found(f"Batch {batch_id} not found.")
        return h

    def _new_tokens(self, batch_id: str, event: dict, creator_device_id: str | None, receipt: str) -> dict:
        expires = self._epoch() + TOKEN_DAYS * 86400
        self.repo.put_new({"PK": f"RECEIPT#{receipt}", "SK": "META", "batch_id": batch_id})
        out = {"receipt_token": receipt, "receipt_url": f"{self.settings.web_url}/r/{receipt}"}
        if event["type"] == "HANDOVER" and event.get("counterparty_party_id"):
            names = asked_fields(event, M.material(event["material"]))
            confirm = ids.token()
            code = ids.short_code()
            self.repo.put_new({"PK": f"CONFIRM#{confirm}", "SK": "META", "batch_id": batch_id, "seq": event["seq"],
                               "field_names": names, "creator_device_id": creator_device_id,
                               "short_code": code, "expires_at": expires})
            self.repo.put_new({"PK": f"WACODE#{code}", "SK": "META", "token": confirm, "expires_at": expires})
            out.update(confirm_token=confirm, confirm_url=f"{self.settings.web_url}/c/{confirm}", confirm_code=code)
            if self.settings.wa_number:
                out["wa_confirm_link"] = f"https://wa.me/{self.settings.wa_number}?text=HAAN%20{code}"
        return out

    def view_event(self, ev: dict) -> dict:
        """Event (without kms_sig) plus derived confirmation status, chip text and evidence badge."""
        v = {k: x for k, x in ev.items() if k != "kms_sig"}
        if ev["type"] == "HANDOVER":
            asked = asked_fields(ev, M.material(ev["material"]))
            status = event_status(ev, asked)
            chip = status
            if status == "BUYER_REPORTED" and any(field_status(ev["fields"][f]) == "SAME_DEVICE_CONFIRMED" for f in asked):
                chip = "SAME_DEVICE_CONFIRMED"
            v["confirmation"] = {"status": status, "asked_fields": asked,
                                 "field_status": {f: field_status(ev["fields"][f]) for f in asked},
                                 "chip": CHIP_TEXT[chip]}
        v["evidence_badge"] = evidence_badge(ev)
        return v

    # ---------------------------------------------------------------- handover
    def create_handover(self, principal: Principal, body: dict, *, at_server: str | None = None,
                        batch_id: str | None = None, counterparty: str | None = None) -> dict:
        material = body.get("material")
        mcfg = M.material(material) if material else None
        if not mcfg:
            raise unprocessable("MISSING_FIELD", "material is required.")
        self._require(principal, "CreateEvent", ("Batch", batch_id or "new", {"material": material}),
                      {"event_type": "HANDOVER", "confirmed_by_roles": sorted(_claimed_roles(body))})
        raw = body.get("fields") or {}
        basis = body.get("weight_basis", "STATED")
        if basis not in ("STATED", "WEIGHED"):
            raise unprocessable("INVALID_BASIS", "weight_basis must be STATED or WEIGHED.")
        fields = {n: M.field_value(n, _plain(v), principal.role, basis if n == "weight_kg" else "STATED")
                  for n, v in raw.items() if _plain(v) is not None}
        M.check_fields("HANDOVER", material, fields)
        geohash = body.get("geohash5") if body.get("location_consent") is True else None
        if geohash is not None and (not isinstance(geohash, str) or len(geohash) != 5):
            raise bad("INVALID_GEOHASH", "geohash5 must be exactly 5 characters.")
        if counterparty is None and material != "AC_REFRIGERANT" or body.get("with_handler"):
            counterparty = counterparty or ids.handler_id()
        if counterparty:
            self.repo.put_new({"PK": f"PARTY#{counterparty}", "SK": "META", "role": "HANDLER",
                               "display_name": None, "registration_no": None})
        batch_id = batch_id or ids.batch_id(mcfg["batch_prefix"])
        receipt = ids.token()
        event = self._append(batch_id, {
            "type": "HANDOVER", "material": material,
            "at_device": _parse_time(body.get("at_device") or self.clock(), "at_device"),
            "actor_party_id": principal.party_id, "counterparty_party_id": counterparty,
            "parent_batch_ids": [], "child_batch_ids": [],
            "fields": fields, "evidence_ids": list(body.get("evidence_ids") or []), "geohash5": geohash,
        }, head_updates={"receipt_token": receipt}, at_server=at_server)
        tokens = self._new_tokens(batch_id, event, body.get("device_id"), receipt)
        resp = {"batch_id": batch_id, "event": self.view_event(event), **tokens}
        if mcfg.get("receipt_note"):
            resp["receipt_note"] = mcfg["receipt_note"]
        return resp

    # ---------------------------------------------------------------- other events
    def add_event(self, principal: Principal, batch_id: str, body: dict, *, at_server: str | None = None) -> dict:
        etype = body.get("type")
        if etype not in BUSINESS_EVENT_TYPES:
            raise unprocessable("UNKNOWN_EVENT_TYPE", f"type must be one of {sorted(BUSINESS_EVENT_TYPES)}.")
        head = self.repo.store.get_head_item(batch_id)
        material = (head or {}).get("material") or body.get("material")
        if not material:
            raise unprocessable("MISSING_FIELD", "material is required for a new batch.")
        M.material(material)
        self._require(principal, "CreateEvent", ("Batch", batch_id, {"material": material}),
                      {"event_type": etype, "confirmed_by_roles": sorted(_claimed_roles(body))})
        warnings: list[dict] = []
        if not head:
            if etype != "INTAKE":
                raise not_found(f"Batch {batch_id} not found.")
            warnings.append({"code": "NO_UPSTREAM_EVENT",
                             "message": "No earlier event on this batch. Intake is recorded; ClaimGuard will see it."})
        if head and head.get("status") in ("SPLIT", "MERGED") and etype != "CORRECTION":
            raise unprocessable("BATCH_CLOSED", f"Batch {batch_id} was {head['status'].lower()}; record on its child batch.")
        at_device = _parse_time(body.get("at_device") or self.clock(), "at_device")
        raw = body.get("fields") or {}
        bases = body.get("bases") or {}
        if etype == "SPLIT":
            return self._split(principal, batch_id, material, raw, at_device, at_server)
        if etype == "MERGE":
            return self._merge(principal, batch_id, material, body, raw, at_device, at_server)
        default_basis = "WEIGHED" if etype in ("TRANSFER", "INTAKE") else "STATED"
        fields = {}
        for n, v in raw.items():
            basis = bases.get(n, default_basis if n.endswith("_kg") else "STATED")
            fields[n] = M.field_value(n, _plain(v), principal.role, basis)
        if etype == "CORRECTION":
            self._check_correction(batch_id, fields)
        M.check_fields(etype, material, fields)
        if etype == "INTAKE" and principal.party_id and "facility_id" in fields \
                and fields["facility_id"]["value"] != principal.party_id:
            raise forbidden("A recycler can only record intake at its own facility.")
        receipt = None if head else ids.token()
        ev = self._append(batch_id, {
            "type": etype, "material": material, "at_device": at_device,
            "actor_party_id": principal.party_id,
            "counterparty_party_id": body.get("counterparty_party_id"),
            "fields": fields, "evidence_ids": list(body.get("evidence_ids") or []),
        }, head_updates={"status": STATUS_AFTER.get(etype), "receipt_token": receipt}, at_server=at_server)
        out = {"batch_id": batch_id, "events": [self.view_event(ev)], "warnings": warnings}
        if receipt:
            out.update(self._new_tokens(batch_id, ev, body.get("device_id"), receipt))
        return out

    def _check_correction(self, batch_id: str, fields: dict) -> None:
        seq = fields.get("corrects_seq", {}).get("value")
        if not any(e["seq"] == seq for e in self._events(batch_id)):
            raise unprocessable("INVALID_FIELD", f"corrects_seq {seq} does not exist on {batch_id}.")

    def _last_weighed_kg(self, batch_id: str) -> float | None:
        for ev in reversed(effective_events(self._events(batch_id))):
            fv = ev.get("fields", {}).get("weight_kg")
            if fv and fv.get("basis") in ("WEIGHED", "OCR"):
                return float(fv["value"])
        return None

    def _split(self, principal, batch_id, material, raw, at_device, at_server) -> dict:
        weights = _plain(raw.get("child_weights_kg"))
        if isinstance(weights, list):  # client may send just the weights; IDs are server-assigned
            weights = {f"{batch_id}.{i}": w for i, w in enumerate(weights, start=1)}
        M.check_value("child_weights_kg", weights)
        expected_ids = [f"{batch_id}.{i}" for i in range(1, len(weights) + 1)]
        if sorted(weights) != sorted(expected_ids) or len(weights) < 2:
            raise unprocessable("INVALID_FIELD", f"child IDs must be {', '.join(expected_ids)} (at least 2).")
        parent_kg = self._last_weighed_kg(batch_id)
        if parent_kg is None:
            raise unprocessable("NO_WEIGHED_WEIGHT", "Weigh the batch before splitting it.")
        total = sum(weights.values())
        if abs(total - parent_kg) > SPLIT_TOLERANCE * parent_kg:
            raise unprocessable("SPLIT_WEIGHT_MISMATCH",
                                f"Children add up to {total:g} kg but the batch was weighed at {parent_kg:g} kg (more than 2% apart).")
        for cid in expected_ids:
            if self.repo.store.get_head_item(cid):
                raise unprocessable("BATCH_EXISTS", f"{cid} already exists.")
        events = [self._append(batch_id, {
            "type": "SPLIT", "material": material, "at_device": at_device, "actor_party_id": principal.party_id,
            "child_batch_ids": expected_ids,
            "fields": {"child_weights_kg": M.field_value("child_weights_kg", weights, principal.role, "WEIGHED")},
        }, head_updates={"status": "SPLIT", "child_batch_ids": expected_ids}, at_server=at_server)]
        receipts = {}
        for cid in expected_ids:
            receipt = ids.token()
            ev = self._append(cid, {
                "type": "SPLIT", "material": material, "at_device": at_device, "actor_party_id": principal.party_id,
                "parent_batch_ids": [batch_id],
                "fields": {"child_weights_kg": M.field_value("child_weights_kg", {cid: weights[cid]}, principal.role, "WEIGHED"),
                           "weight_kg": M.field_value("weight_kg", weights[cid], principal.role, "WEIGHED")},
            }, head_updates={"status": "OPEN", "parent_batch_ids": [batch_id], "receipt_token": receipt}, at_server=at_server)
            events.append(ev)
            receipts[cid] = self._new_tokens(cid, ev, None, receipt)["receipt_url"]
        return {"batch_id": batch_id, "events": [self.view_event(e) for e in events],
                "child_receipt_urls": receipts, "warnings": []}

    def _merge(self, principal, batch_id, material, body, raw, at_device, at_server) -> dict:
        """POST /batches/{any parent}/events {type: MERGE, parent_batch_ids: [...], fields: {weight_kg}}."""
        parents = list(dict.fromkeys([batch_id, *(body.get("parent_batch_ids") or [])]))
        if len(parents) < 2:
            raise unprocessable("INVALID_FIELD", "MERGE needs at least two parent_batch_ids.")
        for p in parents:
            h = self.repo.store.get_head_item(p)
            if not h:
                raise not_found(f"Batch {p} not found.")
            if h.get("material") != material:
                raise unprocessable("MATERIAL_MISMATCH", "Only batches of the same material can be merged.")
            if h.get("status") in ("SPLIT", "MERGED"):
                raise unprocessable("BATCH_CLOSED", f"{p} is already {h['status'].lower()}.")
        new_id = ids.batch_id(M.material(material)["batch_prefix"])
        total = M.field_value("weight_kg", _plain(raw.get("weight_kg")), principal.role,
                              (body.get("bases") or {}).get("weight_kg", "WEIGHED"))
        receipt = ids.token()
        events = [self._append(new_id, {
            "type": "MERGE", "material": material, "at_device": at_device, "actor_party_id": principal.party_id,
            "parent_batch_ids": parents, "fields": {"weight_kg": total},
        }, head_updates={"status": "OPEN", "parent_batch_ids": parents, "receipt_token": receipt}, at_server=at_server)]
        for p in parents:
            kg = self._last_weighed_kg(p)
            pf = {"weight_kg": M.field_value("weight_kg", kg, principal.role, "COMPUTED")} if kg else {}
            if not pf:
                raise unprocessable("NO_WEIGHED_WEIGHT", f"Weigh {p} before merging it.")
            events.append(self._append(p, {
                "type": "MERGE", "material": material, "at_device": at_device, "actor_party_id": principal.party_id,
                "child_batch_ids": [new_id], "fields": pf,
            }, head_updates={"status": "MERGED", "child_batch_ids": [new_id]}, at_server=at_server))
        tokens = self._new_tokens(new_id, events[0], None, receipt)
        return {"batch_id": new_id, "events": [self.view_event(e) for e in events], "warnings": [], **tokens}

    # ---------------------------------------------------------------- reads
    def get_batch(self, principal: Principal, batch_id: str) -> dict:
        head = self._head(batch_id)
        self._require(principal, "ReadBatch", ("Batch", batch_id, {"material": head.get("material", "")}), {})
        return scrub(self._batch_doc(batch_id, head))

    def _batch_doc(self, batch_id: str, head: dict) -> dict:
        events = self._events(batch_id)
        eff = {e["seq"]: e for e in effective_events(events)}
        return {
            "batch_id": batch_id,
            "material": head.get("material"),
            "status": head.get("status"),
            "parent_batch_ids": head.get("parent_batch_ids", []),
            "child_batch_ids": head.get("child_batch_ids", []),
            "last_seq": head.get("last_seq"),
            "receipt_token": head.get("receipt_token"),
            "events": [{k: v for k, v in e.items() if k != "kms_sig"} for e in events],
            "view": [self.view_event(eff[e["seq"]]) for e in events],
            "anomalies": anomalies.flags_for(self.repo, batch_id, events),
        }

    def lineage(self, principal: Principal, root: str) -> dict:
        head = self._head(root)
        self._require(principal, "ReadBatch", ("Batch", root, {"material": head.get("material", "")}), {})
        seen, queue, nodes, edges = set(), [root], [], []
        edge_keys = set()
        while queue:
            b = queue.pop(0)
            if b in seen:
                continue
            seen.add(b)
            h = self.repo.store.get_head_item(b)
            if not h:
                continue
            events = self._events(b)
            nodes.append({"batch_id": b, "material": h.get("material"), "status": h.get("status"),
                          "events": [{k: v for k, v in e.items() if k != "kms_sig"} for e in events]})
            for e in events:
                if e["type"] == "SPLIT" and e.get("child_batch_ids"):
                    w = _plain(e["fields"].get("child_weights_kg")) or {}
                    for c in e["child_batch_ids"]:
                        edge_keys.add((b, c, "SPLIT", w.get(c)))
                if e["type"] == "MERGE" and e.get("child_batch_ids"):
                    for c in e["child_batch_ids"]:
                        edge_keys.add((b, c, "MERGE", _plain(e["fields"].get("weight_kg"))))
            queue += list(h.get("child_batch_ids", [])) + list(h.get("parent_batch_ids", []))
        for f, t, kind, w in sorted(edge_keys, key=lambda x: (x[0], x[1])):
            edges.append({"from": f, "to": t, "kind": kind, "weight_kg": w})
        return scrub({"root_batch_id": root, "nodes": nodes, "edges": edges})

    def receipt(self, token: str) -> dict:
        r = self.repo.get(f"RECEIPT#{token}")
        if not r:
            raise not_found("Receipt not found.")
        batch_id = r["batch_id"]
        head = self._head(batch_id)
        events = effective_events(self._events(batch_id))
        first = events[0] if events else {}
        f = first.get("fields", {})
        chain = self.verify(batch_id)
        mcfg = M.material(head["material"])
        def by_role(e):
            return next(iter(e.get("fields", {}).values()), {}).get("asserted_by_role")
        return scrub({
            "batch_id": batch_id,
            "material": head["material"],
            "material_label": mcfg["label"],
            "count": _plain(f.get("count")),
            "approx_weight_kg": _plain(f.get("weight_kg")),
            "date": (first.get("at_server") or "")[:10],
            "confirmation": self.view_event(first).get("confirmation", {}).get("chip") if first else None,
            "steps": [{"seq": e["seq"], "type": e["type"], "date": e["at_server"][:10],
                       "by_role": by_role(e)}
                      for e in events],
            "chain": {"ok": chain["ok"], "checked": chain["checked"], "failed_at_seq": chain["failed_at_seq"]},
            "note": mcfg.get("receipt_note"),
            "verify_url": f"{self.settings.web_url}/v/{batch_id}",
        })

    # ---------------------------------------------------------------- handler confirmation
    def _token_item(self, token: str) -> dict:
        t = self.repo.get(f"CONFIRM#{token}")
        if not t:
            raise not_found("This confirmation link is not valid.")
        if t.get("used_at"):
            raise gone("TOKEN_USED", "This confirmation link has already been used.")
        if int(t.get("expires_at", 0)) <= self._epoch():
            raise gone("TOKEN_EXPIRED", "This confirmation link has expired.")
        return t

    def confirm_get(self, token: str) -> dict:
        t = self._token_item(token)
        ev = next((e for e in self._events(t["batch_id"]) if e["seq"] == int(t["seq"])), None)
        if not ev:
            raise not_found()
        mcfg = M.material(ev["material"])
        f = ev["fields"]
        return {
            "material": ev["material"], "material_label": mcfg["label"], "unit_label": mcfg["unit_label"],
            "count": _plain(f.get("count")),
            "approx_weight_kg": _plain(f.get("weight_kg")) if "weight_kg" in t["field_names"] else None,
            "source_category": _plain(f.get("source_category")),
            "date": ev["at_server"][:10],
            "asks": list(t["field_names"]),
            "purpose": {"en": "This record shows the batteries or devices reached a registered recycler. Your name is never stored.",
                        "hi": "यह रिकॉर्ड दिखाता है कि माल किसी पंजीकृत रीसाइक्लर तक पहुँचा। आपका नाम कभी दर्ज नहीं होता।"},
        }

    def confirm_post(self, token: str, answer: str, *, device_id: str | None = None,
                     channel: str | None = None, sender_hmac: str | None = None) -> dict:
        """``channel`` is set only by the WhatsApp ingest (OWN_DEVICE_WHATSAPP / SAME_DEVICE)."""
        if answer not in ("yes", "no"):
            raise bad("INVALID_ANSWER", "answer must be yes or no.")
        t = self._token_item(token)
        batch_id, seq, names = t["batch_id"], int(t["seq"]), list(t["field_names"])
        ev = next((e for e in self._events(batch_id) if e["seq"] == seq), None)
        if not ev:
            raise not_found()
        principal = handler_token(token, batch_id, seq, names)
        if not self.authz.is_authorized(principal, "ConfirmHandlerField",
                                        ("Event", f"{batch_id}#{seq}", {"batch_id": batch_id, "seq": seq,
                                                                        "type": ev["type"], "material": ev["material"]}),
                                        {"field_names": names}):
            raise forbidden()
        if channel is None:
            creator = t.get("creator_device_id")
            channel = "SAME_DEVICE" if creator and device_id and device_id == creator else "OWN_DEVICE_LINK"
        if not self.repo.claim_token(f"CONFIRM#{token}", self.clock(), self._epoch()):
            raise gone("TOKEN_USED", "This confirmation link has already been used.")
        handler = ev.get("counterparty_party_id") or ids.handler_id()
        base = {"type": "CORRECTION", "material": ev["material"], "at_device": self.clock(),
                "actor_party_id": handler, "counterparty_party_id": ev["actor_party_id"]}
        corr = lambda field, new_value, reason: dict(base, fields={  # noqa: E731
            "corrects_seq": M.field_value("corrects_seq", seq, "HANDLER"),
            "field": M.field_value("field", field, "HANDLER"),
            "new_value": {"value": new_value, "unit": None, "asserted_by_role": "HANDLER",
                          "confirmed_by_roles": [], "confirmation_channel": "NONE", "basis": "STATED"},
            "reason": M.field_value("reason", reason, "HANDLER"),
        })
        written = []
        if answer == "yes":
            for n in names:
                fv = dict(ev["fields"][n], confirmed_by_roles=["HANDLER"], confirmation_channel=channel)
                written.append(self._append(batch_id, corr(n, fv, "HANDLER_CONFIRMED")))
        else:
            written.append(self._append(batch_id, corr("handover", None, "HANDLER_REJECTED")))
        if answer == "yes":
            anomalies.record_confirmation(self.repo, batch_id=batch_id, seq=seq, handler_id=handler,
                                          key=anomalies.device_key(device_id, sender_hmac))
        eff = next(e for e in effective_events(self._events(batch_id)) if e["seq"] == seq)
        view = self.view_event(eff)
        return {"recorded": answer, "channel": channel, "status": view.get("confirmation", {}).get("status"),
                "chip": view.get("confirmation", {}).get("chip")}

    def token_for_code(self, code: str) -> str | None:
        it = self.repo.get(f"WACODE#{code.strip().upper()}")
        return it["token"] if it and int(it.get("expires_at", 0)) > self._epoch() else None

    # ---------------------------------------------------------------- verify, digests, evidence
    def verify(self, batch_id: str) -> dict:
        head = self._head(batch_id)
        pem = self.signer.public_key_pem()
        r = verify_events(self.repo.store.list_events(batch_id), pem, head)
        digest = self.digest_reader.latest() if self.digest_reader else None
        return {"batch_id": batch_id, "ok": r.ok, "checked": r.checked, "failed_at_seq": r.failed_at_seq,
                "reason": r.reason, "public_key_pem": pem, "digest": digest}

    def presign(self, principal: Principal, body: dict) -> dict:
        if principal is None:
            raise ApiError(401, "UNAUTHENTICATED", "Please sign in.")
        kind = body.get("kind")
        ctype = body.get("content_type")
        if kind not in EVIDENCE_KINDS:
            raise bad("INVALID_KIND", f"kind must be one of {sorted(EVIDENCE_KINDS)}.")
        if ctype not in CONTENT_TYPES:
            raise bad("INVALID_CONTENT_TYPE", f"content_type must be one of {sorted(CONTENT_TYPES)}.")
        sha = body.get("sha256")
        if sha is not None and (not isinstance(sha, str) or len(sha) != 64):
            raise bad("INVALID_SHA256", "sha256 must be 64 hex characters.")
        size = int(body.get("size_bytes") or 0)
        limit = 15_000_000 if kind == "AUDIO" else 10_000_000
        if size <= 0 or size > limit:
            raise bad("INVALID_SIZE", f"size_bytes must be between 1 and {limit}.")
        evid = ids.evidence_id()
        ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "audio/webm": "webm",
               "audio/ogg": "ogg", "audio/mp4": "m4a", "application/pdf": "pdf"}[ctype]
        key = f"audio/{evid}.{ext}" if kind == "AUDIO" else f"evidence/{body.get('batch_id') or 'unlinked'}/{evid}.{ext}"
        self.repo.put_new({"PK": f"EV#{evid}", "SK": "META", "kind": kind, "s3_bucket": self.settings.evidence_bucket,
                           "s3_key": key, "sha256": sha, "received_at_server": self.clock(),
                           "batch_id": body.get("batch_id"), "uploaded_by_party_id": principal.party_id})
        url = self.presigner(key, ctype, size, sha) if self.presigner else f"memory://{key}"
        return {"evidence_id": evid, "upload_url": url, "s3_key": key,
                "headers": {"Content-Type": ctype, **({"x-amz-checksum-sha256": _b64_of_hex(sha)} if sha else {})}}


def _b64_of_hex(h: str) -> str:
    import base64
    return base64.b64encode(bytes.fromhex(h)).decode()
