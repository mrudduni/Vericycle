"""Tamper demo: edit one stored event directly in DynamoDB, show verify_chain failing, then restore.

    python scripts/chaintrack/tamper_demo.py --stage shaurya --batch B-0042 --seq 2
    python scripts/chaintrack/tamper_demo.py --stage shaurya --batch B-0042 --seq 2 --restore

This is the only code that ever writes to an event item, and only for the demo. The original
value is kept in a local file so --restore puts back exactly what was there.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "services/ledger")]

BACKUP = Path.home() / ".openaeye_tamper_backup.json"  # outside the repo (shared .gitignore is not ours to edit)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--batch", required=True)
    ap.add_argument("--seq", type=int, required=True)
    ap.add_argument("--region", default="ap-south-1")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--yes-prod", action="store_true")
    a = ap.parse_args(argv)
    if a.stage == "prod" and not a.yes_prod:
        ap.error("refusing to tamper with prod without --yes-prod")
    if a.stage == "mrudduni":
        ap.error("never touch Mrudduni's stage")

    from ledger.aws import DynamoStore, KmsSigner, _item
    from ledger.verify_chain import verify_events

    store = DynamoStore.for_stage(a.stage, a.region)
    key = _item({"PK": f"BATCH#{a.batch}", "SK": f"EVT#{a.seq:06d}"})
    backups = json.loads(BACKUP.read_text()) if BACKUP.exists() else {}
    bkey = f"{a.stage}/{a.batch}/{a.seq}"

    if a.restore:
        if bkey not in backups:
            print(f"nothing to restore for {bkey}")
            return 1
        original = backups.pop(bkey)
        store.ddb.update_item(TableName=store.table, Key=key, UpdateExpression="SET #f.#w.#v = :v",
                              ExpressionAttributeNames={"#f": "fields", "#w": "weight_kg", "#v": "value"},
                              ExpressionAttributeValues=_item({":v": original}))
        BACKUP.write_text(json.dumps(backups))
        print(f"restored weight_kg on {a.batch} seq {a.seq} to {original}")
    else:
        item = store.ddb.get_item(TableName=store.table, Key=key, ConsistentRead=True).get("Item")
        if not item or "weight_kg" not in item["fields"]["M"]:
            print("event not found or has no weight_kg")
            return 1
        original = float(item["fields"]["M"]["weight_kg"]["M"]["value"]["N"])
        if bkey in backups:
            print("already tampered; run with --restore first")
            return 1
        tampered = round(original * 1.5, 2)
        backups[bkey] = original
        BACKUP.write_text(json.dumps(backups))
        store.ddb.update_item(TableName=store.table, Key=key, UpdateExpression="SET #f.#w.#v = :v",
                              ExpressionAttributeNames={"#f": "fields", "#w": "weight_kg", "#v": "value"},
                              ExpressionAttributeValues=_item({":v": tampered}))
        print(f"TAMPERED {a.batch} seq {a.seq}: weight_kg {original:g} -> {tampered:g} (direct DynamoDB edit)")

    signer = KmsSigner.for_stage(a.stage, a.region)
    r = verify_events(store.list_events(a.batch), signer.public_key_pem(), store.get_head_item(a.batch))
    print(json.dumps(r.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
