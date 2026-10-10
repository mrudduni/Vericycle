"""DynamoDB rejects unused ExpressionAttributeNames/Values; check every update the adapters build."""
import re

import pytest

pytest.importorskip("boto3")

from ledger.aws import DynamoStore
from ledger.signing import LocalSigner
from ledger.writer import Head, build_event


class FakeDdb:
    def __init__(self):
        self.calls = []

    def transact_write_items(self, TransactItems):
        self.calls.append(TransactItems)


def used(expr_parts, names, values):
    text = " ".join(expr_parts)
    tokens = set(re.findall(r"[#:][A-Za-z0-9_]+", text))
    return set(names) - tokens, set(values) - tokens


@pytest.mark.parametrize("head_updates", [
    {}, {"status": "AT_RECYCLER"}, {"status": "SPLIT", "child_batch_ids": ["B-1.1", "B-1.2"]},
    {"receipt_token": "t", "material": "BATTERY_LEAD_ACID"}, {"status": "OPEN", "parent_batch_ids": ["B-1"]},
    {"status": None, "receipt_token": None},
])
@pytest.mark.parametrize("expected", [0, 3])
def test_no_unused_placeholders(head_updates, expected):
    store = DynamoStore("t", client=FakeDdb())
    ev = build_event("B-1", {"type": "TRANSFER", "material": "BATTERY_LEAD_ACID", "actor_party_id": "COL-1",
                             "at_device": "2026-10-10T10:00:00+05:30", "fields": {}},
                     Head(expected, "0" * 64), LocalSigner(), "2026-10-10T10:00:05+05:30")
    store.append(ev, expected_last_seq=expected, head_updates=head_updates)
    upd = store.ddb.calls[-1][1]["Update"]
    unused_names, unused_values = used([upd["UpdateExpression"], upd["ConditionExpression"]],
                                       upd["ExpressionAttributeNames"], upd["ExpressionAttributeValues"])
    assert not unused_names and not unused_values, (unused_names, unused_values)
