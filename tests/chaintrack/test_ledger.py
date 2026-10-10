import copy
import hashlib
import json
import threading
from datetime import date
from decimal import Decimal

import pytest

from ledger.canonical import GENESIS_HASH, canonical_bytes, compute_hash, event_from_item
from ledger.digest import build_digest, merkle_root
from ledger.signing import LocalSigner, verify_signature
from ledger.verify_chain import verify_events
from ledger.writer import ConflictError, LedgerBusyError, MemoryStore, append_event


def fv(value, unit=None, basis="STATED", role="COLLECTOR"):
    return {"value": value, "unit": unit, "asserted_by_role": role, "confirmed_by_roles": [],
            "confirmation_channel": "NONE", "basis": basis}


def handover(at_device="2026-10-03T10:14:03+05:30"):
    return {
        "type": "HANDOVER", "material": "BATTERY_LEAD_ACID", "at_device": at_device,
        "actor_party_id": "COL-118", "counterparty_party_id": "HND-2b81d0",
        "fields": {"count": fv(6), "weight_kg": fv(180, "kg"), "source_category": fv("DRIVER")},
    }


def transfer(kg):
    return {"type": "TRANSFER", "material": "BATTERY_LEAD_ACID", "at_device": "2026-10-04T15:20:00+05:30",
            "actor_party_id": "COL-118", "counterparty_party_id": "AGG-01",
            "fields": {"weight_kg": fv(kg, "kg", "WEIGHED")}}


@pytest.fixture
def chain():
    store, signer = MemoryStore(), LocalSigner()
    times = iter(["2026-10-03T10:14:09+05:30", "2026-10-04T15:20:05+05:30", "2026-10-06T11:30:00+05:30"])
    append_event(store, signer, "B-0042", handover(), clock=lambda: next(times))
    append_event(store, signer, "B-0042", transfer(176), clock=lambda: next(times))
    append_event(store, signer, "B-0042", transfer(175.5), clock=lambda: next(times))
    return store, signer


# --- canonical form -------------------------------------------------------

def test_canonical_matches_contract_recipe():
    ev = {"b": 1, "a": "हाँ", "hash": "x", "kms_sig": "y", "w": 2.5}
    assert canonical_bytes(ev) == '{"a":"हाँ","b":1,"w":2.5}'.encode("utf-8")


def test_decimal_from_dynamodb_hashes_like_original():
    ev = {"seq": 1, "fields": {"weight_kg": {"value": 2.1}, "count": {"value": 6}}}
    stored = {"seq": Decimal("1"), "fields": {"weight_kg": {"value": Decimal("2.1")}, "count": {"value": Decimal("6")}}}
    assert compute_hash(GENESIS_HASH, ev) == compute_hash(GENESIS_HASH, stored)


def test_integral_float_written_as_int():
    assert canonical_bytes({"w": 120.0}) == b'{"w":120}'


def test_storage_keys_not_hashed(chain):
    store, _ = chain
    ev = store.list_events("B-0042")[0]
    item = dict(ev, PK="BATCH#B-0042", SK="EVT#000001", GSI2PK="PARTY#COL-118", GSI2SK=ev["at_server"])
    assert compute_hash(GENESIS_HASH, event_from_item(item)) == ev["hash"]


# --- writer ----------------------------------------------------------------

def test_writer_sets_seq_prev_hash_and_server_time(chain):
    store, _ = chain
    evs = store.list_events("B-0042")
    assert [e["seq"] for e in evs] == [1, 2, 3]
    assert evs[0]["prev_hash"] == GENESIS_HASH
    assert evs[1]["prev_hash"] == evs[0]["hash"]
    assert evs[0]["at_server"] == "2026-10-03T10:14:09+05:30"
    head = store.heads["B-0042"]
    assert head["last_seq"] == 3 and head["last_hash"] == evs[2]["hash"]


def test_client_cannot_set_seq_hash_or_signature():
    store, signer = MemoryStore(), LocalSigner()
    body = dict(handover(), seq=99, prev_hash="f" * 64, hash="a" * 64, kms_sig="forged")
    ev = append_event(store, signer, "B-1", body)
    assert ev["seq"] == 1 and ev["prev_hash"] == GENESIS_HASH and ev["kms_sig"] != "forged"


def test_concurrent_writers_get_unique_contiguous_seqs():
    store, signer = MemoryStore(), LocalSigner()
    errors = []

    def worker(n):
        for _ in range(n):
            while True:  # LedgerBusyError (after 3 attempts) is a 503; the client retries
                try:
                    append_event(store, signer, "B-C", transfer(1))
                    break
                except LedgerBusyError:
                    errors.append(1)

    threads = [threading.Thread(target=worker, args=(10,)) for _ in range(8)]
    for t in threads: t.start()
    for t in threads: t.join()
    seqs = [e["seq"] for e in store.list_events("B-C")]
    assert seqs == list(range(1, 81))
    assert verify_events(store.list_events("B-C"), signer.public_key_pem(), store.heads["B-C"]).ok


def test_conflict_retries_then_gives_up():
    class AlwaysConflict(MemoryStore):
        calls = 0
        def append(self, *a, **k):
            AlwaysConflict.calls += 1
            raise ConflictError("x")
    with pytest.raises(LedgerBusyError):
        append_event(AlwaysConflict(), LocalSigner(), "B-X", handover())
    assert AlwaysConflict.calls == 3


# --- verification ------------------------------------------------------------

def test_intact_chain_verifies(chain):
    store, signer = chain
    r = verify_events(store.list_events("B-0042"), signer.public_key_pem(), store.heads["B-0042"])
    assert r.ok and r.checked == 3 and r.failed_at_seq is None


@pytest.mark.parametrize("seq", [1, 2, 3])
def test_tampering_one_field_fails_at_exactly_that_seq(chain, seq):
    store, signer = chain
    evs = store.list_events("B-0042")
    evs[seq - 1]["fields"]["weight_kg"]["value"] = 1  # edit stored data, keep stored hash
    r = verify_events(evs, signer.public_key_pem())
    assert not r.ok and r.failed_at_seq == seq and r.reason.startswith("HASH_MISMATCH")


def test_rehashing_tampered_event_still_fails_on_signature(chain):
    store, signer = chain
    evs = store.list_events("B-0042")
    evs[1]["fields"]["weight_kg"]["value"] = 1
    evs[1]["hash"] = compute_hash(evs[1]["prev_hash"], evs[1])
    r = verify_events(evs, signer.public_key_pem())
    assert not r.ok and r.failed_at_seq == 2 and r.reason == "BAD_SIGNATURE"


def test_valid_hash_with_forged_signature_fails(chain):
    store, signer = chain
    evs = store.list_events("B-0042")
    evs[0]["kms_sig"] = LocalSigner().sign(evs[0]["hash"])  # attacker's own key
    r = verify_events(evs, signer.public_key_pem())
    assert not r.ok and r.failed_at_seq == 1 and r.reason == "BAD_SIGNATURE"


def test_deleted_middle_event_is_a_gap(chain):
    store, signer = chain
    evs = store.list_events("B-0042")
    del evs[1]
    r = verify_events(evs, signer.public_key_pem())
    assert not r.ok and r.failed_at_seq == 2 and r.reason.startswith("GAP")


def test_deleted_last_event_detected_via_head(chain):
    store, signer = chain
    evs = store.list_events("B-0042")[:-1]
    r = verify_events(evs, signer.public_key_pem(), store.heads["B-0042"])
    assert not r.ok and r.failed_at_seq == 3 and r.reason.startswith("GAP")


def test_signature_roundtrip_matches_kms_digest_mode():
    s = LocalSigner()
    h = hashlib.sha256(b"x").hexdigest()
    from ledger.signing import load_public_key
    assert verify_signature(load_public_key(s.public_key_pem()), h, s.sign(h))


# --- merkle digest -------------------------------------------------------------

def test_merkle_known_values():
    a, b, c = (hashlib.sha256(x).hexdigest() for x in (b"a", b"b", b"c"))
    H = lambda x, y: hashlib.sha256(bytes.fromhex(x) + bytes.fromhex(y)).hexdigest()
    assert merkle_root([]) == GENESIS_HASH
    assert merkle_root([a]) == a
    assert merkle_root([a, b]) == H(a, b)
    assert merkle_root([a, b, c]) == H(H(a, b), H(c, c))


def test_digest_recomputes_from_raw_events(chain):
    store, signer = chain
    evs = store.list_events("B-0042")
    d = build_digest(evs, date(2026, 10, 4), signer)
    assert d["count"] == 1 and d["root"] == evs[1]["hash"]
    raw = json.loads(json.dumps(evs))
    assert build_digest(raw, date(2026, 10, 4))["root"] == d["root"]
    from ledger.signing import load_public_key
    assert verify_signature(load_public_key(signer.public_key_pem()), d["root"], d["signature"])


def test_digest_uses_ist_date_and_order():
    store, signer = MemoryStore(), LocalSigner()
    # 23:30 IST on the 3rd and 00:10 IST on the 4th (18:40 UTC on the 3rd)
    append_event(store, signer, "B-2", handover(), at_server="2026-10-03T23:30:00+05:30")
    append_event(store, signer, "B-1", handover(), at_server="2026-10-03T18:40:00+00:00")
    evs = store.list_events("B-1") + store.list_events("B-2")
    d3 = build_digest(evs, date(2026, 10, 3))
    d4 = build_digest(evs, date(2026, 10, 4))
    assert d3["count"] == 1 and d3["first"]["batch_id"] == "B-2"
    assert d4["count"] == 1 and d4["first"]["batch_id"] == "B-1"
