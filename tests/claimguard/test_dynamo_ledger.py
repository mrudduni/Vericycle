"""DynamoLedgerReader.all_batches imports only what boto3 really ships (it 500'd /impact on AWS)."""
from claimguard.dynamo_ledger import DynamoLedgerReader


class FakeTable:
    def scan(self, **kw):
        assert "FilterExpression" in kw
        return {"Items": [{"PK": "BATCH#B-0042"}, {"PK": "BATCH#B-0041"}]}


def test_all_batches_scans_batch_heads(monkeypatch):
    r = DynamoLedgerReader("t", table=FakeTable())
    seen = []
    monkeypatch.setattr(r, "get_batch", lambda i: seen.append(i) or None)
    assert r.all_batches() == []
    assert seen == ["B-0041", "B-0042"]
