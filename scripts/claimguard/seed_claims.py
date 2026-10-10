"""Load the demo claims, facilities and evidence index into a stage's claims table, then run ClaimGuard on each.

    python scripts/claimguard/seed_claims.py --stage mrudduni [--profile openaeye] [--ledger-stage prod]

Idempotent: re-running overwrites the same items. --ledger-stage reads that ChainTrack stage's live ledger for the
checks (otherwise the demo fixture). Never run against a table you do not own.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "services" / "claimguard"), str(ROOT / "services" / "review_api")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--profile", default="openaeye")
    ap.add_argument("--ledger-stage")
    ap.add_argument("--no-check", action="store_true")
    a = ap.parse_args()

    import boto3

    session = boto3.Session(profile_name=a.profile, region_name="ap-south-1")
    ssm = session.client("ssm")
    param = lambda n: ssm.get_parameter(Name=n)["Parameter"]["Value"]  # noqa: E731
    claims_table = session.resource("dynamodb").Table(param(f"/openaeye/{a.stage}/claims/table-name"))

    from claimguard import io as cg_io
    from claimguard.dynamo_ledger import DynamoLedgerReader
    from claimguard.ledger_reader import FixtureLedgerReader
    from claimguard.sources import SourcesRegistry
    from review.repo import DynamoRepo
    from review.service import ReviewService

    repo = DynamoRepo(claims_table.name, table=claims_table)
    for pid, f in json.loads((cg_io.DATA_DIR / "facilities.json").read_text(encoding="utf-8")).items():
        repo.put_facility(pid, f)
    for e in cg_io.load_evidence_index().values():
        repo.put_evidence(e)
    claims = cg_io.load_claims_dir()
    for c in claims:
        repo.put_claim(c)
    print(f"seeded {len(claims)} claims, facilities and evidence into {claims_table.name}")

    if a.no_check:
        return
    if a.ledger_stage:
        ledger = DynamoLedgerReader(param(f"/openaeye/{a.ledger_stage}/ledger/table-name"),
                                    table=session.resource("dynamodb").Table(param(f"/openaeye/{a.ledger_stage}/ledger/table-name")))
    else:
        ledger = FixtureLedgerReader()
    svc = ReviewService(repo, ledger, SourcesRegistry.load())
    for c in claims:
        run = svc.check_claim(c.claim_id)
        flags = [f"{r['rule_id']}:{r['severity']}" for r in run["rule_results"] if r["outcome"] == "FLAG"]
        print(f"  {c.claim_id}: flags={flags or '-'} coverage={run['scores']['traceability_coverage']:.0%}")


if __name__ == "__main__":
    main()
