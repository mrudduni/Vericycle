"""Loads data/facilities.json, data/claims/*.json and data/evidence/evidence_index.json
into the model objects the engine uses. No AWS imports.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from .model import ClaimProduct, Evidence, EvidenceKind, Facility
from .model import Claim

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def load_facilities(path: Path | str | None = None) -> dict[str, Facility]:
    p = Path(path) if path else DATA_DIR / "facilities.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for party_id, f in raw.items():
        out[party_id] = Facility(
            recycler_party_id=party_id,
            rated_t_per_hr=f.get("rated_t_per_hr"),
            hours_per_day=f.get("hours_per_day"),
            operating_days=f.get("operating_days"),
            licensed_t_per_yr=f.get("licensed_t_per_yr"),
            lat=f.get("lat"),
            lon=f.get("lon"),
            source_ids=tuple(f.get("source_ids", [])),
        )
    return out


def load_claim(path: Path | str) -> Claim:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return Claim(
        claim_id=raw["claim_id"],
        recycler_party_id=raw["recycler_party_id"],
        product=ClaimProduct(raw["product"]),
        period_start=datetime.fromisoformat(raw["period_start"]),
        period_end=datetime.fromisoformat(raw["period_end"]),
        input_t=raw.get("input_t"),
        processed_t=raw.get("processed_t"),
        output=dict(raw.get("output", {})),
        batch_ids=tuple(raw.get("batch_ids", [])),
        evidence_ids=tuple(raw.get("evidence_ids", [])),
        opening_stock_t=raw.get("opening_stock_t"),
        closing_stock_t=raw.get("closing_stock_t"),
        documented_losses_t=raw.get("documented_losses_t"),
        electricity_kwh=raw.get("electricity_kwh"),
        diesel_generator_logged=raw.get("diesel_generator_logged", False),
        submitted_at=datetime.fromisoformat(raw["submitted_at"]) if raw.get("submitted_at") else None,
    )


def load_claims_dir(path: Path | str | None = None) -> list[Claim]:
    p = Path(path) if path else DATA_DIR / "claims"
    return [load_claim(f) for f in sorted(p.glob("*.json"))]


def load_evidence_index(path: Path | str | None = None) -> dict[str, Evidence]:
    p = Path(path) if path else DATA_DIR / "evidence" / "evidence_index.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for eid, e in raw.items():
        exif = dict(e.get("exif", {}))
        if "DateTimeOriginal" in exif and exif["DateTimeOriginal"] is not None:
            exif["DateTimeOriginal"] = datetime.fromisoformat(exif["DateTimeOriginal"])
        extracted = dict(e.get("extracted", {}))
        if "date" in extracted and extracted["date"] is not None:
            extracted["date"] = date.fromisoformat(extracted["date"])
        out[eid] = Evidence(
            evidence_id=eid,
            kind=EvidenceKind(e["kind"]),
            s3_key=e.get("s3_key", ""),
            sha256=e.get("sha256", ""),
            received_at_server=datetime.fromisoformat(e["received_at_server"])
            if e.get("received_at_server")
            else datetime.now(),
            phash=e.get("phash"),
            exif=exif,
            extracted=extracted,
            batch_id=e.get("batch_id"),
        )
    return out
