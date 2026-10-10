# Shaurya's work log (ChainTrack)

**Submission deadline:** _not confirmed yet. Ask Mrudduni and fill in._

## 2026-10-10 08:55 IST: setup

- Works: repo cloned, branch `shaurya/chaintrack` created, contract and solution read.
- Next: ledger library (canonical hash, writer, verify_chain, Merkle digest) with offline tests; Cedar policies; CDK Core stack.
- Blocked: the Claude GitHub app cannot see `mrudduni/OpenAEye` (Mrudduni must add the repo to her Claude app installation), so pushes wait. AWS login not done yet (needs Shaurya at a browser). WhatsApp number and collector sign-in method not decided.

## 2026-10-10 ~10:30 IST: blocks 2–4 built offline

- Works: ledger (hash chain, KMS-compatible signatures, conditional writer, verify_chain, Merkle digest); Cedar policies + Verified Permissions store; Core and Capture CDK stacks synth with cdk-nag clean (each acknowledgement has a reason); capture API service + Lambda router (every CONTRACT §7 capture route, plus `GET /chat/drafts/{id}` and the digest routes); `seed_demo.py` (all CONTRACT §8 batches, dry run OK); `tamper_demo.py`; extraction (Transcribe job + Bedrock forced-tool schema + deterministic Hindi number reader as cross-check and offline fallback); web chat drafts. 89 offline tests pass (`cd services/ledger && .venv/bin/python -m pytest ../../tests/chaintrack`).
- Next: PWA (block 5).
- Blocked: no AWS login yet (needs the IAM user from Mrudduni), so nothing deployed; GitHub push access (Claude app not installed on OpenAEye); WhatsApp number; collector sign-in choice; Bedrock model not chosen (stack defaults to the offline reader until `-c modelId=...`).

### Proposed contract additions (need Shaurya + Mrudduni agreement)

1. **Live handler confirmation.** Events are immutable, so a confirmation that arrives after the HANDOVER is a `CORRECTION` event by the handler (`actor_party_id` = HND id) with `corrects_seq`, `field` = the confirmed field, `new_value` = the full updated FieldValue (`confirmed_by_roles: ["HANDLER"]`, channel), `reason` = `HANDLER_CONFIRMED`. Readers apply CORRECTIONs in seq order before deriving status. Rejection: one CORRECTION with `field` = `handover`, `new_value` null, `reason` = `HANDLER_REJECTED`. Seeded data has confirmations inside seq 1, as the fixture does.
2. **Hashing of whole-number floats.** `120.0` is serialised as `120`.
3. **Split child events.** The first event on a child batch (type SPLIT) carries `child_weights_kg` = `{<child>: kg}` and also `weight_kg` (WEIGHED).
4. **Seed evidence IDs.** B-0041 weigh slip = `EV-01JA3W6Z8T5Q9F0B2C4D6E8G1H`; phone intakes use the literal `EV-DUP-PHOTO`. P-0102/P-0103 have no counterparty; their source_category is RETAIL_EXCHANGE; A-0001 source_category is TECHNICIAN. Times not in §8 are 11:00 / 12:00 IST.

### Third-party code added since last entry
| Library | Used in | Licence |
|---|---|---|
| aws-cdk-lib, constructs, aws-cdk | infra | Apache-2.0 |
| cdk-nag | infra | Apache-2.0 |
| aws-lambda-powertools (layer) | Lambdas | MIT-0 |
| aws-xray-sdk | tests | Apache-2.0 |
| PyYAML | capture API | MIT |
| typescript, ts-node, @types/node | infra | Apache-2.0 / MIT / MIT |

## Third-party libraries and licences

| Library | Used in | Licence |
|---|---|---|
| cryptography | ledger signatures | Apache-2.0 / BSD-3-Clause |
| boto3 | AWS adapters | Apache-2.0 |
| cedarpy | Cedar policy tests | Apache-2.0 |
| pytest | tests | MIT |
