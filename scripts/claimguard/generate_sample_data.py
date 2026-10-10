#!/usr/bin/env python3
"""Deterministically writes every sample-data file ClaimGuard's offline
tests and demo run against: data/facilities.json, data/fixtures/ledger_events.json,
data/claims/*.json and data/evidence/evidence_index.json.

Run with: python scripts/claimguard/generate_sample_data.py

Every number here is chosen to land each of the 9 claims in
docs/team/CONTRACT.md section 8 on its exact expected outcome. Facility and
rule-band numbers not drawn from data/sources.yaml are DEMO VALUEs (see
that file's own notes); this script does not invent new ones, it only
arranges them.

This is JSON-only today: it produces the data the pure rule engine reads
directly, without generating actual photo/invoice/slip files. Real image
and document generation (for the Textract and R5-vision demo pipeline) is
docs/team/MRUDDUNI.md block 8 (P1) and is not required for the offline
acceptance test in tests/claimguard/test_acceptance.py.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"

IST = "+05:30"


def iso(s: str) -> str:
    """Appends IST offset if the string has no offset already."""
    return s if ("+" in s[10:] or s.endswith("Z")) else s + IST


# ---------------------------------------------------------------------------
# facilities.json
# ---------------------------------------------------------------------------

FACILITIES = {
    "REC-01": {
        "rated_t_per_hr": 4,
        "hours_per_day": 20,
        "operating_days": 330,
        "licensed_t_per_yr": 26400,
        "lat": None,
        "lon": None,
        "source_ids": ["cpcb-capacity-guideline"],
    },
    "REC-02": {
        "rated_t_per_hr": 1,
        "hours_per_day": 16,
        "operating_days": 300,
        "licensed_t_per_yr": 4800,
        "lat": None,
        "lon": None,
        "source_ids": ["cpcb-capacity-guideline"],
    },
    "REC-03": {
        "rated_t_per_hr": 2,
        "hours_per_day": 16,
        "operating_days": 300,
        "licensed_t_per_yr": 9600,
        "lat": 28.73,
        "lon": 77.78,
        "source_ids": ["cpcb-capacity-guideline", "hapur-plant-coordinates"],
    },
}


# ---------------------------------------------------------------------------
# fixtures/ledger_events.json  (docs/team/CONTRACT.md section 8)
# ---------------------------------------------------------------------------

def field(value, role, confirmed=(), channel="NONE", basis="STATED", unit=None):
    return {
        "value": value,
        "unit": unit,
        "asserted_by_role": role,
        "confirmed_by_roles": list(confirmed),
        "confirmation_channel": channel,
        "basis": basis,
    }


def handover(seq, at, actor, counterparty, count, weight_kg, source_category,
             confirmed=(), channel="NONE", confirm_weight=False):
    return {
        "seq": seq,
        "type": "HANDOVER",
        "material": "BATTERY_LEAD_ACID",
        "at_device": iso(at),
        "at_server": iso(at),
        "actor_party_id": actor,
        "counterparty_party_id": counterparty,
        "fields": {
            "count": field(count, "COLLECTOR", confirmed, channel),
            "weight_kg": field(weight_kg, "COLLECTOR", confirmed if confirm_weight else (),
                               channel if confirm_weight else "NONE", unit="kg"),
            "source_category": field(source_category, "COLLECTOR", confirmed, channel),
        },
        "evidence_ids": [],
        "prev_hash": "0" * 64,
        "hash": "FIXTURE",
    }


def transfer(seq, at, actor, weight_kg):
    return {
        "seq": seq,
        "type": "TRANSFER",
        "material": "BATTERY_LEAD_ACID",
        "at_device": iso(at),
        "at_server": iso(at),
        "actor_party_id": actor,
        "fields": {"weight_kg": field(weight_kg, "COLLECTOR", basis="WEIGHED", unit="kg")},
        "evidence_ids": [],
        "prev_hash": "FIXTURE",
        "hash": "FIXTURE",
    }


def intake(seq, at, actor, weight_kg, material="BATTERY_LEAD_ACID"):
    return {
        "seq": seq,
        "type": "INTAKE",
        "material": material,
        "at_device": iso(at),
        "at_server": iso(at),
        "actor_party_id": actor,
        "fields": {"weight_kg": field(weight_kg, "RECYCLER", basis="WEIGHED", unit="kg")},
        "evidence_ids": [],
        "prev_hash": "FIXTURE",
        "hash": "FIXTURE",
    }


def split(seq, at, actor, child_weights_kg):
    return {
        "seq": seq,
        "type": "SPLIT",
        "material": "BATTERY_LEAD_ACID",
        "at_device": iso(at),
        "at_server": iso(at),
        "actor_party_id": actor,
        "child_batch_ids": list(child_weights_kg.keys()),
        "fields": {"weight_kg": field(sum(child_weights_kg.values()), "AGGREGATOR", basis="WEIGHED", unit="kg")},
        "evidence_ids": [],
        "prev_hash": "FIXTURE",
        "hash": "FIXTURE",
    }


def split_child(seq, at, parent_batch_id, weight_kg):
    return {
        "seq": seq,
        "type": "SPLIT",
        "material": "BATTERY_LEAD_ACID",
        "at_device": iso(at),
        "at_server": iso(at),
        "actor_party_id": "AGG-01",
        "parent_batch_ids": [parent_batch_id],
        "fields": {"weight_kg": field(weight_kg, "AGGREGATOR", basis="WEIGHED", unit="kg")},
        "evidence_ids": [],
        "prev_hash": "FIXTURE",
        "hash": "FIXTURE",
    }


LEDGER_BATCHES = {
    "B-0041": {
        "material": "BATTERY_LEAD_ACID",
        "events": [
            handover(1, "2026-10-02T09:40:00", "COL-118", "HND-7f3a9c", 4, 120,
                      "DRIVER", confirmed=["HANDLER"], channel="OWN_DEVICE_WHATSAPP"),
            transfer(2, "2026-10-04T15:10:00", "COL-118", 118),
            intake(3, "2026-10-06T11:05:00", "REC-01", 117),
        ],
    },
    "B-0042": {
        "material": "BATTERY_LEAD_ACID",
        "events": [
            handover(1, "2026-10-03T10:14:00", "COL-118", "HND-2b81d0", 6, 180, "DRIVER"),
            transfer(2, "2026-10-04T15:20:00", "COL-118", 176),
            intake(3, "2026-10-06T11:30:00", "REC-01", 175),
        ],
    },
    "B-0043": {
        "material": "BATTERY_LEAD_ACID",
        "events": [
            handover(1, "2026-10-03T17:02:00", "COL-118", "HND-c4e5f6", 4, 120,
                      "DRIVER", confirmed=["HANDLER"], channel="SAME_DEVICE"),
            intake(2, "2026-10-07T10:00:00", "REC-01", 118),
        ],
    },
    "B-0046": {
        "material": "BATTERY_LEAD_ACID",
        "events": [
            handover(1, "2026-10-05T12:00:00", "COL-118", "HND-91aa07", 4, 120,
                      "DRIVER", confirmed=["HANDLER"], channel="OWN_DEVICE_LINK", confirm_weight=True),
            transfer(2, "2026-10-06T09:00:00", "COL-118", 119),
            split(3, "2026-10-06T09:30:00", "AGG-01", {"B-0046.1": 60, "B-0046.2": 58}),
        ],
    },
    "B-0046.1": {
        "material": "BATTERY_LEAD_ACID",
        "events": [split_child(1, "2026-10-06T09:30:00", "B-0046", 60)],
    },
    "B-0046.2": {
        "material": "BATTERY_LEAD_ACID",
        "events": [split_child(1, "2026-10-06T09:30:00", "B-0046", 58)],
    },
    "P-0101": {
        "material": "EWASTE_PHONE",
        "events": [
            {**handover(1, "2026-07-14T13:00:00", "COL-207", "HND-5d3e12", 12, 2.1,
                         "RETAIL_EXCHANGE", confirmed=["HANDLER"], channel="OWN_DEVICE_WHATSAPP",
                         confirm_weight=True),
             "material": "EWASTE_PHONE"},
            {**transfer(2, "2026-07-16T10:00:00", "COL-207", 2.08), "material": "EWASTE_PHONE"},
            {**intake(3, "2026-07-18T10:00:00", "REC-02", 2.05, material="EWASTE_PHONE"),
             "evidence_ids": ["EV-0101-PHOTO"]},
        ],
    },
    "P-0102": {
        "material": "EWASTE_PHONE",
        "events": [
            {**handover(1, "2026-08-11T10:00:00", "COL-207", None, 9, 1.6, "RETAIL_EXCHANGE"),
             "material": "EWASTE_PHONE", "counterparty_party_id": None},
            {**intake(2, "2026-08-14T10:00:00", "REC-02", 1.58, material="EWASTE_PHONE"),
             "evidence_ids": ["EV-0102-PHOTO"]},
        ],
    },
    "P-0103": {
        "material": "EWASTE_PHONE",
        "events": [
            {**handover(1, "2026-09-09T10:00:00", "COL-207", None, 15, 2.6, "RETAIL_EXCHANGE"),
             "material": "EWASTE_PHONE", "counterparty_party_id": None},
            {**intake(2, "2026-09-12T10:00:00", "REC-02", 2.57, material="EWASTE_PHONE"),
             "evidence_ids": ["EV-0103-PHOTO"]},
        ],
    },
    "A-0001": {
        "material": "AC_REFRIGERANT",
        "events": [
            {
                "seq": 1,
                "type": "HANDOVER",
                "material": "AC_REFRIGERANT",
                "at_device": iso("2026-10-04T16:00:00"),
                "at_server": iso("2026-10-04T16:00:00"),
                "actor_party_id": "COL-330",
                "fields": {
                    "count": field(1, "COLLECTOR"),
                    "gas_type": field("R-32", "COLLECTOR"),
                    "charge_kg": field(0.9, "COLLECTOR", unit="kg"),
                },
                "evidence_ids": [],
                "prev_hash": "0" * 64,
                "hash": "FIXTURE",
            }
        ],
    },
}


# ---------------------------------------------------------------------------
# claims/*.json
# ---------------------------------------------------------------------------

def claim(**kw):
    return kw


CLAIMS = {
    "C-101": claim(
        claim_id="C-101", recycler_party_id="REC-01", product="BATTERY_LEAD_ACID",
        period_start=iso("2026-10-01T00:00:00"), period_end=iso("2026-10-31T23:59:59"),
        input_t=0.500, processed_t=0.500, output={"LEAD": 0.30},
        batch_ids=["B-0041", "B-0042", "B-0043"],
        evidence_ids=["EV-C101-PHOTO", "EV-C101-INVOICE"],
        opening_stock_t=0.0, closing_stock_t=0.0, documented_losses_t=0.0,
        electricity_kwh=80, diesel_generator_logged=False,
        submitted_at=iso("2026-10-07T09:00:00"),
    ),
    "C-102": claim(
        claim_id="C-102", recycler_party_id="REC-01", product="BATTERY_LEAD_ACID",
        period_start=iso("2026-01-01T00:00:00"), period_end=iso("2026-12-31T23:59:59"),
        input_t=30000, processed_t=30000, output={"LEAD": 18000},
        batch_ids=[], evidence_ids=[],
        opening_stock_t=0.0, closing_stock_t=0.0, documented_losses_t=0.0,
        electricity_kwh=6000000, diesel_generator_logged=False,
        submitted_at=iso("2026-10-07T09:05:00"),
    ),
    "C-103": claim(
        claim_id="C-103", recycler_party_id="REC-01", product="BATTERY_LEAD_ACID",
        period_start=iso("2026-10-01T00:00:00"), period_end=iso("2026-10-31T23:59:59"),
        input_t=1.0, processed_t=1.0, output={"LEAD": 0.90},
        batch_ids=[], evidence_ids=[],
        opening_stock_t=0.0, closing_stock_t=0.0, documented_losses_t=0.0,
        electricity_kwh=200, diesel_generator_logged=False,
        submitted_at=iso("2026-10-07T09:10:00"),
    ),
    "C-104": claim(
        claim_id="C-104", recycler_party_id="REC-01", product="BATTERY_LEAD_ACID",
        period_start=iso("2026-10-01T00:00:00"), period_end=iso("2026-10-31T23:59:59"),
        input_t=50.0, processed_t=50.0, output={"LEAD": 30.0},
        batch_ids=[], evidence_ids=[],
        opening_stock_t=0.0, closing_stock_t=0.0, documented_losses_t=0.0,
        electricity_kwh=500, diesel_generator_logged=False,
        submitted_at=iso("2026-10-07T09:15:00"),
    ),
    "C-105": claim(
        claim_id="C-105", recycler_party_id="REC-01", product="BATTERY_LEAD_ACID",
        period_start=iso("2025-06-01T00:00:00"), period_end=iso("2025-06-30T23:59:59"),
        input_t=0.1, processed_t=0.1, output={"LEAD": 0.05},
        batch_ids=[], evidence_ids=["EV-C105-PHOTO"],
        opening_stock_t=0.0, closing_stock_t=0.0, documented_losses_t=0.0,
        electricity_kwh=20, diesel_generator_logged=False,
        submitted_at=iso("2026-10-07T09:20:00"),
    ),
    "C-105b": claim(
        claim_id="C-105b", recycler_party_id="REC-01", product="BATTERY_LEAD_ACID",
        period_start=iso("2025-06-01T00:00:00"), period_end=iso("2025-06-30T23:59:59"),
        input_t=0.1, processed_t=0.1, output={"LEAD": 0.05},
        batch_ids=[], evidence_ids=["EV-C105b-PHOTO"],
        opening_stock_t=0.0, closing_stock_t=0.0, documented_losses_t=0.0,
        electricity_kwh=20, diesel_generator_logged=False,
        submitted_at=iso("2026-10-07T09:25:00"),
    ),
    "C-106": claim(
        claim_id="C-106", recycler_party_id="REC-02", product="EWASTE_PHONE",
        period_start=iso("2026-07-01T00:00:00"), period_end=iso("2026-09-30T23:59:59"),
        input_t=0.0062, processed_t=0.0062, output={"COPPER": 0.001},
        batch_ids=["P-0101", "P-0102", "P-0103"],
        evidence_ids=["EV-0101-PHOTO", "EV-0102-PHOTO", "EV-0103-PHOTO"],
        opening_stock_t=0.0, closing_stock_t=0.0, documented_losses_t=0.0,
        electricity_kwh=1, diesel_generator_logged=False,
        submitted_at=iso("2026-10-07T09:30:00"),
    ),
    "C-107": claim(
        claim_id="C-107", recycler_party_id="REC-01", product="BATTERY_LEAD_ACID",
        period_start=iso("2026-10-01T00:00:00"), period_end=iso("2026-10-31T23:59:59"),
        input_t=0.1, processed_t=0.1, output={"LEAD": 0.05},
        batch_ids=["B-0042"], evidence_ids=[],
        opening_stock_t=0.0, closing_stock_t=0.0, documented_losses_t=0.0,
        electricity_kwh=20, diesel_generator_logged=False,
        # deliberately submitted AFTER C-101, so the double-claim flag lands
        # on this claim, not on C-101 (CONTRACT.md's tie-break rule)
        submitted_at=iso("2026-10-08T09:00:00"),
    ),
    "C-108": claim(
        claim_id="C-108", recycler_party_id="REC-02", product="EWASTE_PHONE",
        period_start=iso("2026-09-01T00:00:00"), period_end=iso("2026-09-30T23:59:59"),
        input_t=0.02, processed_t=0.02, output={},
        batch_ids=[], evidence_ids=["EV-C108-PHOTO"],
        opening_stock_t=None, closing_stock_t=None, documented_losses_t=None,
        electricity_kwh=None, diesel_generator_logged=False,
        submitted_at=iso("2026-10-07T09:35:00"),
    ),
}


# ---------------------------------------------------------------------------
# evidence/evidence_index.json
# ---------------------------------------------------------------------------

def photo_evidence(sha256, phash, dt_original, lat, lon, light_class, batch_id=None, offset=True):
    exif = {
        "DateTimeOriginal": dt_original if offset else dt_original[:19],
        "gps_lat": lat,
        "gps_lon": lon,
        "_demo_light_class": light_class,
    }
    if offset:
        exif["OffsetTimeOriginal"] = "+05:30"
    return {
        "kind": "PHOTO",
        "sha256": sha256,
        "phash": phash,
        "exif": exif,
        "received_at_server": dt_original if offset else dt_original + "+05:30",
        "batch_id": batch_id,
    }


def invoice_evidence(sha256, invoice_number, total_weight_t, date_str, gstin, batch_id=None):
    return {
        "kind": "INVOICE",
        "sha256": sha256,
        "exif": {},
        "extracted": {
            "invoice_number": invoice_number,
            "total_weight_t": total_weight_t,
            "date": date_str,
            "gstin": gstin,
        },
        "received_at_server": "2026-10-07T00:00:00+05:30",
        "batch_id": batch_id,
    }


EVIDENCE = {
    "EV-C101-PHOTO": photo_evidence(
        sha256="s" * 7 + "c101", phash="a" * 16,
        dt_original="2026-10-06T11:00:00", lat=28.60, lon=77.20,
        light_class="DIRECT_SUN_HARD_SHADOWS", batch_id="B-0041",
    ),
    "EV-C101-INVOICE": invoice_evidence(
        sha256="s" * 7 + "c101inv", invoice_number="INV-C101-0001",
        total_weight_t=0.48, date_str="2026-10-15", gstin="99AAAAA0000A1ZR",
        batch_id="B-0041",
    ),
    "EV-C105-PHOTO": photo_evidence(
        sha256="s" * 7 + "c105", phash="b" * 16,
        dt_original="2025-06-16T20:22:00", lat=28.73, lon=77.78,
        light_class="DIRECT_SUN_HARD_SHADOWS",
    ),
    "EV-C105b-PHOTO": photo_evidence(
        sha256="s" * 7 + "c105b", phash="c" * 16,
        dt_original="2025-06-16T19:48:00", lat=28.73, lon=77.78,
        light_class="BRIGHT_DIFFUSE_DAYLIGHT",
    ),
    # EV-DUP-PHOTO cluster: the same weighbridge photo reused across three
    # different phone batches, caught by R6. P-0101 and P-0103 are the
    # exact same file (identical sha256); P-0102 is a re-encoded copy
    # (different sha256, identical phash -> caught by the near-duplicate
    # check instead of the exact-match check).
    "EV-0101-PHOTO": photo_evidence(
        sha256="dupfile0001", phash="d" * 16,
        dt_original="2026-07-18T09:00:00", lat=28.65, lon=77.30,
        light_class="BRIGHT_DIFFUSE_DAYLIGHT", batch_id="P-0101",
    ),
    "EV-0102-PHOTO": photo_evidence(
        sha256="dupfile0002-reencoded", phash="d" * 16,
        dt_original="2026-08-14T09:00:00", lat=28.65, lon=77.30,
        light_class="BRIGHT_DIFFUSE_DAYLIGHT", batch_id="P-0102",
    ),
    "EV-0103-PHOTO": photo_evidence(
        sha256="dupfile0001", phash="d" * 16,
        dt_original="2026-09-12T09:00:00", lat=28.65, lon=77.30,
        light_class="BRIGHT_DIFFUSE_DAYLIGHT", batch_id="P-0103",
    ),
    "EV-C108-PHOTO": {
        "kind": "PHOTO",
        "sha256": "s" * 7 + "c108",
        "phash": "e" * 16,
        "exif": {},  # deliberately no DateTimeOriginal: "no EXIF on photos"
        "received_at_server": "2026-09-20T00:00:00+05:30",
        "batch_id": None,
    },
}


def main() -> None:
    (DATA_DIR / "facilities.json").write_text(json.dumps(FACILITIES, indent=2) + "\n", encoding="utf-8")

    (DATA_DIR / "fixtures").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "fixtures" / "ledger_events.json").write_text(
        json.dumps({"batches": LEDGER_BATCHES}, indent=2) + "\n", encoding="utf-8"
    )

    claims_dir = DATA_DIR / "claims"
    claims_dir.mkdir(parents=True, exist_ok=True)
    for old in claims_dir.glob("*.json"):
        old.unlink()
    for claim_id, data in CLAIMS.items():
        (claims_dir / f"{claim_id}.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    (DATA_DIR / "evidence").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "evidence" / "evidence_index.json").write_text(
        json.dumps(EVIDENCE, indent=2) + "\n", encoding="utf-8"
    )

    print(f"Wrote facilities.json, fixtures/ledger_events.json, "
          f"{len(CLAIMS)} claim files, and evidence_index.json to {DATA_DIR}")


if __name__ == "__main__":
    main()
