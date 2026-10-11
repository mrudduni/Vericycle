"""Link a collector's WhatsApp number to a party, e.g. COL-118 (CONTRACT §5, P6).

    AWS_PROFILE=openaeye python scripts/chaintrack/register_phone.py --stage prod --party COL-118

The number is typed at a hidden prompt, turned into a KMS HMAC at once, and never printed, logged or
stored. Use the international form without '+' or spaces, exactly as WhatsApp sends it (e.g. 9198XXXXXXXX).
"""
from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "services/ledger"), str(ROOT / "services/capture_api"), str(ROOT / "services/ingest")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--party", required=True, help="collector party ID, e.g. COL-118")
    ap.add_argument("--region", default=os.environ.get("AWS_REGION") or "ap-southeast-2")
    a = ap.parse_args()
    import boto3

    from capture.repo import DynamoRepo
    from ingest.whatsapp import register_collector_phone
    from ledger.aws import KmsPhoneHasher

    number = re.sub(r"[\s+\-()]", "", getpass.getpass("WhatsApp number (digits with country code, hidden): "))
    if not re.fullmatch(r"\d{8,15}", number):
        sys.exit("That does not look like a number in international form (8-15 digits, e.g. 9198XXXXXXXX).")
    ssm = boto3.client("ssm", region_name=a.region)
    table = ssm.get_parameter(Name=f"/openaeye/{a.stage}/ledger/table-name")["Parameter"]["Value"]
    kms = boto3.client("kms", region_name=a.region)
    alias = f"alias/oae-{a.stage}-phone-hmac"
    key_id = kms.describe_key(KeyId=alias)["KeyMetadata"]["KeyId"]
    repo = DynamoRepo(table, region=a.region)
    register_collector_phone(repo, KmsPhoneHasher(key_id, a.region)(number), a.party)
    print(f"Linked a WhatsApp number to {a.party}. The number itself was not stored.")


if __name__ == "__main__":
    main()
