"""Review API logic (CONTRACT.md section 7, "Review API"). No HTTP or AWS here, so it is unit-testable."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any

from claimguard import io as cg_io
from claimguard.engine import FAMILIES, build_claims_citing_batch, run_family
from claimguard.context import RuleContext
from claimguard.engine import coverage_inputs, cited_handover_events
from claimguard.model import (
    Claim,
    ClaimProduct,
    EventType,
    Material,
    RefrigerantClaimError,
    ReviewAction,
    RuleOutcome,
    RuleResult,
    Severity,
)
from claimguard.scores import compute_scores
from claimguard.sources import SourcesRegistry

IST = timezone(timedelta(hours=5, minutes=30))
CLAIM_ID_RE = re.compile(r"^C-\d{3}[a-z]?$")
GWP_SOURCE_BY_GAS = {"R-32": "ipcc-gwp100-r32", "R-410A": "ipcc-gwp100-r410a", "R-22": "ipcc-gwp100-r22"}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def now_iso() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


def handover_asked_fields(event) -> tuple[str, ...]:
    """CONTRACT §3: count, source_category and, if stated, weight_kg."""
    names = []
    for n in ("count", "source_category", "weight_kg"):
        fv = event.fields.get(n)
        if fv is None or (n == "weight_kg" and fv.basis.value != "STATED"):
            continue
        names.append(n)
    return tuple(names)


class ReviewService:
    def __init__(self, repo, ledger, sources: SourcesRegistry, authz=None):
        from .authz import DevAuthorizer  # noqa: PLC0415

        self.repo, self.ledger, self.sources = repo, ledger, sources
        self.authz = authz or DevAuthorizer()

    # ---- claims ----------------------------------------------------------
    def list_claims(self) -> dict:
        rows = []
        for c in sorted(self.repo.list_claims(), key=lambda c: c.claim_id):
            run = self.repo.latest_run(c.claim_id)
            flags = {"hard": 0, "soft": 0}
            if run:
                for r in run["rule_results"]:
                    if r["outcome"] == "FLAG":
                        flags["hard" if r["severity"] == "HARD" else "soft"] += 1
            rows.append({
                "claim_id": c.claim_id, "recycler_party_id": c.recycler_party_id, "product": c.product.value,
                "period_start": c.period_start.isoformat(), "period_end": c.period_end.isoformat(),
                "flags": flags, "has_run": run is not None,
                "coverage": run["scores"]["traceability_coverage"] if run else None,
                "last_run_at": run["ran_at"] if run else None,
            })
        return {"claims": rows}

    def submit_claim(self, body: dict) -> dict:
        if str(body.get("product", "")).upper() in ("AC_REFRIGERANT", "REFRIGERANT"):
            raise ApiError(422, "REFRIGERANT_CLAIM_NOT_ALLOWED",
                           "No certificate exists for refrigerant, so a refrigerant claim cannot be created.")
        cid = body.get("claim_id")
        if not isinstance(cid, str) or not CLAIM_ID_RE.match(cid):
            raise ApiError(422, "INVALID_CLAIM_ID", "claim_id must look like C-123.")
        if self.repo.get_claim(cid):
            raise ApiError(409, "CLAIM_EXISTS", f"{cid} already exists.")
        body = {**body, "submitted_at": body.get("submitted_at") or now_iso()}
        try:
            claim = cg_io.claim_from_dict(body)
        except (KeyError, ValueError) as e:
            if "AC_REFRIGERANT" in str(e):
                raise ApiError(422, "REFRIGERANT_CLAIM_NOT_ALLOWED", "Refrigerant claims cannot be represented.") from e
            raise ApiError(422, "INVALID_CLAIM", f"Invalid claim: {e}") from e
        self.repo.put_claim(claim)
        return {"claim": cg_io.claim_to_dict(claim)}

    def _claim_or_404(self, claim_id: str) -> Claim:
        c = self.repo.get_claim(claim_id)
        if not c:
            raise ApiError(404, "CLAIM_NOT_FOUND", f"No claim {claim_id}.")
        return c

    def _ctx(self, claim: Claim) -> RuleContext:
        claims = self.repo.list_claims()
        return RuleContext(
            facility=self.repo.get_facility(claim.recycler_party_id),
            sources=self.sources,
            evidence=self.repo.all_evidence(),
            claims_citing_batch=build_claims_citing_batch(claims),
            claim_submitted_at={c.claim_id: c.submitted_at for c in claims},
            ledger_reader=self.ledger,
        )

    def run_rule_family(self, claim_id: str, family: str) -> list[dict]:
        """One Step Functions branch. Returns JSON-able rule results."""
        if family not in FAMILIES:
            raise ApiError(422, "INVALID_FAMILY", f"family must be one of {list(FAMILIES)}.")
        claim = self._claim_or_404(claim_id)
        return [r.to_dict() for r in run_family(claim, self._ctx(claim), family)]

    def finalize_run(self, claim_id: str, result_lists: list[list[dict]]) -> dict:
        """Joins the branches, computes the three scores and stores the run."""
        claim = self._claim_or_404(claim_id)
        ctx = self._ctx(claim)
        flat = sorted((r for lst in result_lists for r in lst), key=lambda r: (r["rule_id"][:2], r["rule_id"]))
        results = [RuleResult(
            claim_id=r["claim_id"], rule_id=r["rule_id"], rule_version=r["rule_version"], outcome=RuleOutcome(r["outcome"]),
            severity=Severity(r["severity"]), observed=r["observed"], limit=r["limit"], formula_rendered=r["formula_rendered"],
            evidence_ids=tuple(r["evidence_ids"]), source_ids=tuple(r["source_ids"]), demo_value=r["demo_value"],
            next_action=r["next_action"]) for r in flat]
        covered_kg, claimed_kg = coverage_inputs(claim, ctx)
        events = cited_handover_events(claim, ctx)
        asked = {(e.batch_id, e.seq): handover_asked_fields(e) for e in events}
        scores = compute_scores(claim.claim_id, results, covered_kg, claimed_kg, events, asked)
        ran_at = now_iso()
        run = {
            "run_id": ran_at, "ran_at": ran_at,
            "rule_results": [r.to_dict() for r in results],
            "scores": {
                "physical_consistency": scores.physical_consistency,
                "physical_capped_by_hard_flag": scores.physical_consistency_capped_by_hard_flag,
                "traceability_coverage": scores.traceability_coverage,
                "covered_kg": scores.covered_kg, "claimed_kg": scores.claimed_kg,
                "evidence_quality": asdict(scores.evidence_quality),
                "evidence_rules": {k: v.value for k, v in scores.evidence_quality_rule_outcomes.items()},
            },
        }
        self.repo.put_run(claim_id, run)
        return run

    def check_claim(self, claim_id: str) -> dict:
        """Synchronous run (solo stages, tests, seeding). Same families, same join as the Step Functions workflow."""
        self._claim_or_404(claim_id)
        return self.finalize_run(claim_id, [self.run_rule_family(claim_id, f) for f in FAMILIES])

    def start_check(self, claim_id: str, state_machine_arn: str, sfn_client=None) -> dict:
        """Starts the ClaimGuard workflow and returns immediately; the finished run appears on GET /claims/{id}."""
        self._claim_or_404(claim_id)
        if sfn_client is None:
            import boto3  # noqa: PLC0415

            sfn_client = boto3.client("stepfunctions")
        name = f"{claim_id}-{datetime.now(IST).strftime('%Y%m%dT%H%M%S')}"
        r = sfn_client.start_execution(stateMachineArn=state_machine_arn, name=name, input=json.dumps({"claim_id": claim_id}))
        return {"status": "RUNNING", "execution_id": name, "execution_arn": r["executionArn"]}

    def get_claim(self, claim_id: str) -> dict:
        claim = self._claim_or_404(claim_id)
        run = self.repo.latest_run(claim_id)
        ev = self.repo.get_evidence(list(claim.evidence_ids))
        source_ids = sorted({s for r in (run["rule_results"] if run else []) for s in r["source_ids"]})
        return {
            "claim": cg_io.claim_to_dict(claim),
            "run": run,
            "evidence": [cg_io.evidence_to_dict(e) for e in ev.values()],
            "lineage": self._lineage(claim),
            "reviews": self.repo.reviews(claim_id),
            "sources": {sid: self._source_dict(sid) for sid in source_ids},
        }

    # ---- evidence upload -------------------------------------------------
    EVIDENCE_KINDS = ("PHOTO", "WEIGH_SLIP", "INVOICE", "POWER_BILL")
    EVIDENCE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "application/pdf": "pdf"}
    MAX_EVIDENCE_BYTES = 10 * 1024 * 1024

    def presign_evidence(self, principal: dict, body: dict, bucket: str, s3_client=None) -> dict:
        """Pre-signed POST into the claim-evidence bucket (SOLUTION.md section 8: size and type limits).

        Only the recycler that owns the claim may upload. The key follows the evidence processor's convention
        evidence/<claim_id>/<KIND>/<random>.<ext>; the processor's S3 event does the rest.
        """
        import secrets  # noqa: PLC0415

        claim = self._claim_or_404(str(body.get("claim_id", "")))
        if principal.get("role") != "RECYCLER" or principal.get("party_id") != claim.recycler_party_id:
            raise ApiError(403, "FORBIDDEN", "Only the recycler that owns this claim can upload evidence for it.")
        kind, ctype = body.get("kind"), body.get("content_type")
        if kind not in self.EVIDENCE_KINDS:
            raise ApiError(422, "INVALID_KIND", f"kind must be one of {list(self.EVIDENCE_KINDS)}.")
        if ctype not in self.EVIDENCE_TYPES:
            raise ApiError(422, "INVALID_CONTENT_TYPE", f"content_type must be one of {sorted(self.EVIDENCE_TYPES)}.")
        if not bucket:
            raise ApiError(503, "NOT_CONFIGURED", "No evidence bucket is configured for this stage.")
        key = f"evidence/{claim.claim_id}/{kind}/{secrets.token_hex(8)}.{self.EVIDENCE_TYPES[ctype]}"
        if s3_client is None:
            import boto3  # noqa: PLC0415

            s3_client = boto3.client("s3")
        post = s3_client.generate_presigned_post(
            Bucket=bucket, Key=key, Fields={"Content-Type": ctype},
            Conditions=[{"Content-Type": ctype}, ["content-length-range", 1, self.MAX_EVIDENCE_BYTES]], ExpiresIn=300)
        return {"upload": post, "key": key, "max_bytes": self.MAX_EVIDENCE_BYTES, "expires_in": 300}

    # ---- reviews ---------------------------------------------------------
    def add_review(self, claim_id: str, body: dict, principal: dict) -> dict:
        self._claim_or_404(claim_id)
        try:
            action = ReviewAction(body.get("action"))
        except ValueError:
            raise ApiError(422, "INVALID_ACTION", f"action must be one of {[a.value for a in ReviewAction]}.") from None
        role = principal.get("role", "AUDITOR")
        if action is ReviewAction.RECYCLER_RESPONSE and role != "RECYCLER":
            raise ApiError(403, "FORBIDDEN", "Only the recycler can add a response.")
        if action is not ReviewAction.RECYCLER_RESPONSE and role not in ("AUDITOR", "PRODUCER"):
            raise ApiError(403, "FORBIDDEN", "Only an auditor can take review actions.")
        note = str(body.get("note", ""))[:2000]
        return self.repo.append_review(claim_id, {
            "action": action.value, "note": note, "by_party_id": principal.get("party_id", "?"),
            "by_role": role, "at": now_iso(),
        })

    # ---- lineage ---------------------------------------------------------
    def _lineage(self, claim: Claim) -> dict:
        nodes, edges, seen = [], [], set()
        queue = list(claim.batch_ids)
        while queue:
            bid = queue.pop(0)
            if bid in seen:
                continue
            seen.add(bid)
            b = self.ledger.get_batch(bid)
            if not b:
                continue
            events = []
            for e in b.events:
                asked = handover_asked_fields(e) if e.type is EventType.HANDOVER else ()
                events.append({
                    "seq": e.seq, "type": e.type.value, "at_server": e.at_server.isoformat(),
                    "actor_party_id": e.actor_party_id,
                    "weight_kg": e.fields["weight_kg"].value if "weight_kg" in e.fields else None,
                    "basis": e.fields["weight_kg"].basis.value if "weight_kg" in e.fields else None,
                    "confirmation": e.event_confirmation_status(asked).value if asked else None,
                    "fields": {n: {"status": f.field_status().value, "channel": f.confirmation_channel.value}
                               for n, f in e.fields.items() if n in asked},
                    "evidence_ids": list(e.evidence_ids),
                })
            nodes.append({"batch_id": bid, "material": b.material.value, "status": b.status, "events": events})
            for e in b.events:
                if e.type is EventType.SPLIT and e.child_batch_ids:
                    kg = e.fields.get("child_weights_kg")
                    for child in e.child_batch_ids:
                        w = None
                        cb = self.ledger.get_batch(child)
                        if cb:
                            w = next((x.fields["weight_kg"].value for x in cb.events if "weight_kg" in x.fields), None)
                        edges.append({"from": bid, "to": child, "kind": "SPLIT", "weight_kg": w})
                        queue.append(child)
        return {"root_batch_ids": list(claim.batch_ids), "nodes": nodes, "edges": edges}

    # ---- impact ----------------------------------------------------------
    def _source_dict(self, sid: str) -> dict | None:
        s = self.sources.get(sid)
        if s is None:
            return None
        return {"id": s.id, "title": s.title, "status": s.status, "date": s.date, "locator": s.locator,
                "url": s.url, "value": s.value, "note": s.note, "demo_value": s.is_demo_value}

    def get_source(self, sid: str) -> dict:
        d = self._source_dict(sid)
        if d is None:
            raise ApiError(404, "SOURCE_NOT_FOUND", f"No source {sid}.")
        return d

    def impact(self) -> dict:
        batches = self.ledger.all_batches()
        recyclers = {c.recycler_party_id for c in self.repo.list_claims()} | {
            e.actor_party_id for b in batches for e in b.events if e.type is EventType.INTAKE}
        lead_frac = self.sources.get("lead-fraction-lead-acid-max")
        battery_kg = phones = batteries_with_record = ac_co2e = 0.0
        phones_traced = 0
        for b in batches:
            intakes = [e for e in b.events if e.type is EventType.INTAKE and "weight_kg" in e.fields]
            if b.material is Material.BATTERY_LEAD_ACID:
                if any(e.type is EventType.HANDOVER for e in b.events):
                    handover = next(e for e in b.events if e.type is EventType.HANDOVER)
                    batteries_with_record += handover.fields["count"].value if "count" in handover.fields else 0
                if intakes:
                    battery_kg += max(e.fields["weight_kg"].value for e in intakes)
            elif b.material is Material.EWASTE_PHONE and intakes:
                phones_traced += next((e.fields["count"].value for e in b.events
                                       if e.type is EventType.HANDOVER and "count" in e.fields), 0)
            elif b.material is Material.AC_REFRIGERANT:
                for e in b.events:
                    if e.type is EventType.HANDOVER:
                        gas = e.fields.get("gas_type")
                        charge = e.fields.get("charge_kg")
                        count = e.fields["count"].value if "count" in e.fields else 1
                        gwp_src = GWP_SOURCE_BY_GAS.get(gas.value) if gas else None
                        gwp = self.sources.get(gwp_src).value if gwp_src and self.sources.get(gwp_src) else None
                        kg = charge.value if charge else self.sources.get("ac-refrigerant-default-charge-kg").value
                        if gwp:
                            ac_co2e += kg * count * gwp / 1000.0
        lead_kg = battery_kg * (lead_frac.value if lead_frac and lead_frac.value else 0)
        run_cov = [r["scores"] for r in (self.repo.latest_run(c.claim_id) for c in self.repo.list_claims()) if r]
        covered = sum(s["covered_kg"] for s in run_cov)
        claimed = sum(s["claimed_kg"] for s in run_cov)
        return {"metrics": [
            {"id": "lead_traced_kg", "label": "Lead traced to a registered recycler", "value": round(lead_kg, 1), "unit": "kg",
             "source_ids": ["lead-fraction-lead-acid-max"], "demo_value": True,
             "note": "Weighed battery intake at a recycler x maximum lead fraction (an upper bound, not a measurement)."},
            {"id": "batteries_recorded", "label": "Batteries with a first-handover record", "value": int(batteries_with_record),
             "unit": "batteries", "source_ids": [], "demo_value": False, "note": "Count from the custody ledger."},
            {"id": "phones_traced", "label": "Phones traced end to end", "value": int(phones_traced), "unit": "phones",
             "source_ids": [], "demo_value": False, "note": "Handed over and received at a recycler."},
            {"id": "refrigerant_uncounted_t_co2e", "label": "Refrigerant harm no certificate counts", "value": round(ac_co2e, 2),
             "unit": "t CO2e", "source_ids": ["ipcc-gwp100-r32", "ipcc-gwp100-r410a", "ipcc-gwp100-r22", "ac-refrigerant-default-charge-kg"],
             "demo_value": True, "note": "Potential release if vented. No refrigerant certificate exists, so no claim can be made."},
            {"id": "coverage", "label": "Traceability coverage across checked claims",
             "value": round(covered / claimed, 3) if claimed else None, "unit": "ratio", "source_ids": [], "demo_value": False,
             "note": "Weighed intake kg linked to recorded handovers / kg claimed. A metric, not a verdict."},
        ], "recyclers_seen": sorted(recyclers)}
