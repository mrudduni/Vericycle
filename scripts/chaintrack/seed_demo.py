"""Seed CONTRACT.md §8 parties and batches through the real ledger writer (real hashes and signatures).

    python scripts/chaintrack/seed_demo.py --stage shaurya          # DynamoDB + KMS
    python scripts/chaintrack/seed_demo.py --dry-run                # in memory, prints a summary

Seed mode may fix at_server to the contract's times; the API never can.
Already-seeded batches are skipped (events are immutable), so re-running is safe.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "services/ledger"), str(ROOT / "services/capture_api")]

from ledger.writer import append_event  # noqa: E402

WEIGH_SLIP_B0041 = "EV-01JA3W6Z8T5Q9F0B2C4D6E8G1H"   # assumed ID; Mrudduni's fixture must use the same
DUP_PHOTO = "EV-DUP-PHOTO"                           # literal ID from CONTRACT §8

PARTIES = [
    *[(h, "HANDLER", None, None) for h in ("HND-7f3a9c", "HND-2b81d0", "HND-c4e5f6", "HND-91aa07", "HND-5d3e12")],
    ("COL-118", "COLLECTOR", "Demo battery dealer, Delhi", None),
    ("COL-207", "COLLECTOR", "Demo phone retailer exchange counter, Delhi", None),
    ("COL-330", "COLLECTOR", "Demo AC technician, Delhi", None),
    ("AGG-01", "AGGREGATOR", "Demo aggregator, Ghaziabad", None),
    ("REC-01", "RECYCLER", "Demo lead recycler", "DEMO-REG-0001"),
    ("REC-02", "RECYCLER", "Demo e-waste recycler", "DEMO-REG-0002"),
    ("AUD-01", "AUDITOR", "Demo auditor", None),
    ("PRD-01", "PRODUCER", "Demo battery brand", None),
]

BAT, PHONE, AC = "BATTERY_LEAD_ACID", "EWASTE_PHONE", "AC_REFRIGERANT"
UNITS = {"weight_kg": "kg", "charge_kg": "kg", "child_weights_kg": "kg"}


def fv(name, value, role, basis="STATED", channel=None):
    return {"value": value, "unit": UNITS.get(name), "asserted_by_role": role,
            "confirmed_by_roles": ["HANDLER"] if channel else [],
            "confirmation_channel": channel or "NONE", "basis": basis}


def handover(at, actor, cp, material, count, kg, src, confirm=None, ch=None, **extra):
    confirm = confirm or []
    f = {"count": fv("count", count, "COLLECTOR", channel=ch if "count" in confirm else None),
         "source_category": fv("source_category", src, "COLLECTOR", channel=ch if "source_category" in confirm else None)}
    if kg is not None:
        f["weight_kg"] = fv("weight_kg", kg, "COLLECTOR", channel=ch if "weight_kg" in confirm else None)
    for k, v in extra.items():
        f[k] = fv(k, v, "COLLECTOR")
    return at, {"type": "HANDOVER", "material": material, "actor_party_id": actor, "counterparty_party_id": cp,
                "fields": f}, {}


def transfer(at, actor, cp, material, kg):
    return at, {"type": "TRANSFER", "material": material, "actor_party_id": actor, "counterparty_party_id": cp,
                "fields": {"weight_kg": fv("weight_kg", kg, "COLLECTOR", "WEIGHED")}}, {}


def intake(at, rec, material, kg, evidence=None):
    return at, {"type": "INTAKE", "material": material, "actor_party_id": rec,
                "fields": {"weight_kg": fv("weight_kg", kg, "RECYCLER", "WEIGHED"),
                           "facility_id": fv("facility_id", rec, "RECYCLER")},
                "evidence_ids": [evidence] if evidence else []}, {"status": "AT_RECYCLER"}


def T(d, hm):
    return f"2026-{d}T{hm}:00+05:30"


ALL3 = ["count", "source_category", "weight_kg"]
BATCHES = {
    "B-0041": [handover(T("10-02", "09:40"), "COL-118", "HND-7f3a9c", BAT, 4, 120, "DRIVER", ["count", "source_category"], "OWN_DEVICE_WHATSAPP"),
               transfer(T("10-04", "15:10"), "COL-118", "AGG-01", BAT, 118),
               intake(T("10-06", "11:05"), "REC-01", BAT, 117, WEIGH_SLIP_B0041)],
    "B-0042": [handover(T("10-03", "10:14"), "COL-118", "HND-2b81d0", BAT, 6, 180, "DRIVER"),
               transfer(T("10-04", "15:20"), "COL-118", "AGG-01", BAT, 176),
               intake(T("10-06", "11:30"), "REC-01", BAT, 175)],
    "B-0043": [handover(T("10-03", "17:02"), "COL-118", "HND-c4e5f6", BAT, 4, 120, "DRIVER", ["count", "source_category"], "SAME_DEVICE"),
               intake(T("10-07", "10:00"), "REC-01", BAT, 118)],
    "B-0046": [handover(T("10-05", "12:00"), "COL-118", "HND-91aa07", BAT, 4, 120, "DRIVER", ALL3, "OWN_DEVICE_LINK"),
               transfer(T("10-06", "09:00"), "COL-118", "AGG-01", BAT, 119)],   # SPLIT added below
    "P-0101": [handover(T("07-14", "13:00"), "COL-207", "HND-5d3e12", PHONE, 12, 2.1, "RETAIL_EXCHANGE", ALL3, "OWN_DEVICE_WHATSAPP"),
               transfer(T("07-16", "11:00"), "COL-207", "AGG-01", PHONE, 2.08),
               intake(T("07-18", "11:00"), "REC-02", PHONE, 2.05, DUP_PHOTO)],
    "P-0102": [handover(T("08-11", "12:00"), "COL-207", None, PHONE, 9, 1.6, "RETAIL_EXCHANGE"),
               intake(T("08-14", "12:00"), "REC-02", PHONE, 1.58, DUP_PHOTO)],
    "P-0103": [handover(T("09-09", "12:00"), "COL-207", None, PHONE, 15, 2.6, "RETAIL_EXCHANGE"),
               intake(T("09-12", "12:00"), "REC-02", PHONE, 2.57, DUP_PHOTO)],
    "A-0001": [handover(T("10-04", "16:00"), "COL-330", None, AC, 1, None, "TECHNICIAN", gas_type="R-32", charge_kg=0.9)],
}
SPLIT_AT, SPLIT_CHILDREN = T("10-06", "09:30"), {"B-0046.1": 60, "B-0046.2": 58}


def seed(repo, signer, log=print) -> dict:
    from capture import ids  # noqa: PLC0415

    for pid, role, name, reg in PARTIES:
        repo.put_new({"PK": f"PARTY#{pid}", "SK": "META", "role": role, "display_name": name, "registration_no": reg})
    written = {}

    def put(batch_id, at, body, head_updates):
        receipt = None
        if not repo.store.get_head_item(batch_id):
            receipt = ids.token()
            repo.put_new({"PK": f"RECEIPT#{receipt}", "SK": "META", "batch_id": batch_id})
        hu = dict(head_updates)
        if receipt:
            hu["receipt_token"] = receipt
        body = dict(body, at_device=at)
        ev = append_event(repo.store, signer, batch_id, body, head_updates=hu, at_server=at)
        written.setdefault(batch_id, []).append(ev["seq"])

    for batch_id, events in BATCHES.items():
        if repo.store.get_head_item(batch_id):
            log(f"skip {batch_id} (already seeded)")
            continue
        for at, body, hu in events:
            put(batch_id, at, body, hu)
        if batch_id == "B-0046":
            put("B-0046", SPLIT_AT, {"type": "SPLIT", "material": BAT, "actor_party_id": "AGG-01",
                                      "child_batch_ids": list(SPLIT_CHILDREN),
                                      "fields": {"child_weights_kg": fv("child_weights_kg", SPLIT_CHILDREN, "AGGREGATOR", "WEIGHED")}},
                {"status": "SPLIT", "child_batch_ids": list(SPLIT_CHILDREN)})
            for cid, kg in SPLIT_CHILDREN.items():
                put(cid, SPLIT_AT, {"type": "SPLIT", "material": BAT, "actor_party_id": "AGG-01",
                                    "parent_batch_ids": ["B-0046"],
                                    "fields": {"child_weights_kg": fv("child_weights_kg", {cid: kg}, "AGGREGATOR", "WEIGHED"),
                                               "weight_kg": fv("weight_kg", kg, "AGGREGATOR", "WEIGHED")}},
                    {"status": "OPEN", "parent_batch_ids": ["B-0046"]})
        log(f"seeded {batch_id}: seq {written.get(batch_id)}")
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage")
    ap.add_argument("--region", default=__import__("os").environ.get("AWS_REGION") or "ap-south-1")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.dry_run:
        from capture.repo import MemoryRepo  # noqa: PLC0415
        from ledger.signing import LocalSigner  # noqa: PLC0415
        seed(MemoryRepo(), LocalSigner())
        return 0
    if not a.stage:
        ap.error("--stage is required unless --dry-run")
    from capture.repo import DynamoRepo  # noqa: PLC0415
    from ledger.aws import KmsSigner  # noqa: PLC0415
    seed(DynamoRepo(f"oae-{a.stage}-ledger", a.region), KmsSigner.for_stage(a.stage, a.region))
    return 0


if __name__ == "__main__":
    sys.exit(main())
