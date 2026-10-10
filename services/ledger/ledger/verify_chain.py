"""Verify one batch's chain: recompute hashes, check prev_hash links, seq gaps and signatures.

Library: ``verify_events(events, public_key, head=None)``.
CLI:     ``python -m ledger.verify_chain --stage shaurya --batch B-0042``.
"""
from __future__ import annotations

import argparse
import os
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from .canonical import GENESIS_HASH, compute_hash, event_from_item
from .signing import load_public_key, verify_signature


@dataclass
class VerifyResult:
    ok: bool
    checked: int
    failed_at_seq: int | None = None
    reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def verify_events(
    events: Iterable[Mapping[str, Any]],
    public_key,
    head: Mapping[str, Any] | None = None,
) -> VerifyResult:
    """``events`` may be raw DynamoDB items; storage keys are stripped before hashing.

    ``head`` (the batch META item) lets a deleted *last* event be detected too:
    its ``last_seq``/``last_hash`` must match the final event.
    """
    if isinstance(public_key, (str, bytes)):
        public_key = load_public_key(public_key)
    evs = sorted((event_from_item(e) for e in events), key=lambda e: e.get("seq", 0))
    prev = GENESIS_HASH
    checked = 0
    for expected_seq, ev in enumerate(evs, start=1):
        seq = ev.get("seq")
        if seq != expected_seq:
            return VerifyResult(False, checked, expected_seq, f"GAP: expected seq {expected_seq}, found {seq}")
        if ev.get("prev_hash") != prev:
            return VerifyResult(False, checked, seq, "PREV_HASH_MISMATCH")
        recomputed = compute_hash(prev, ev)
        if recomputed != ev.get("hash"):
            return VerifyResult(False, checked, seq, "HASH_MISMATCH: stored event differs from what was signed")
        if not verify_signature(public_key, ev["hash"], ev.get("kms_sig") or ""):
            return VerifyResult(False, checked, seq, "BAD_SIGNATURE")
        prev = ev["hash"]
        checked += 1
    if head is not None:
        last_seq = int(head.get("last_seq", 0))
        if last_seq != checked:
            return VerifyResult(False, checked, checked + 1, f"GAP: head says {last_seq} events, found {checked}")
        if checked and head.get("last_hash") != prev:
            return VerifyResult(False, checked, checked, "HEAD_HASH_MISMATCH")
    if checked == 0:
        return VerifyResult(False, 0, None, "NOT_FOUND")
    return VerifyResult(True, checked)


def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify a batch's hash chain and KMS signatures")
    ap.add_argument("--stage", required=True)
    ap.add_argument("--batch", required=True)
    ap.add_argument("--region", default=os.environ.get("AWS_REGION") or "ap-south-1")
    args = ap.parse_args(argv)
    from .aws import DynamoStore, KmsSigner  # boto3 only here

    store = DynamoStore.for_stage(args.stage, region=args.region)
    signer = KmsSigner.for_stage(args.stage, region=args.region)
    result = verify_events(store.list_events(args.batch), signer.public_key_pem(), store.get_head_item(args.batch))
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(_main())
