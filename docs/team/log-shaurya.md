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

## 2026-10-10 ~11:15 IST: PWA, WhatsApp logic, hosting, runbook

- Works (offline, verified): PWA `web-capture/` (chat capture with Hindi/English read-back card, ✅/✏️, receipt card with both QR codes, seller confirm page, batch timeline with icon+text chips, transfer/split/merge/intake/process/output/correction forms, in-app camera with on-device SHA-256, offline IndexedDB queue, public receipt and verify pages, privacy page). Initial JS 82 KB gzipped. Browser e2e at 360 px (`tests/chaintrack/e2e/flow.mjs`): chat → ✅ → seller confirms on a second browser → chip shows "Seller confirmed on own phone" → offline transfer syncs exactly once → recycler intake → public receipt/verify → token single-use; no horizontal scroll; no control under 40 px. WhatsApp intake logic with tests (EUMS SNS parsing, Meta retry dedupe, unregistered-number reply, voice note → Transcribe → card back on WhatsApp, `HAAN <code>` handler confirmation with own-phone vs same-phone detection). Optional WhatsApp CDK resources. Amplify Hosting stack + `deploy_web.sh`. `run_eval.py`. Runbook in `infra/chaintrack/README.md`. 97 Python tests pass.
- Next: deploy stage `shaurya` as soon as there is an AWS login; choose Bedrock model with `run_eval.py`; real collector sign-in once the method is chosen; anomaly checks (P2).
- Blocked: IAM user (no AWS access yet); GitHub push access; WhatsApp number; collector sign-in method; deadline time. The deployed PWA cannot sign business users in until the sign-in method is built (local dev uses a demo-party picker against `scripts/chaintrack/local_api.py`).

## 2026-10-10 ~12:15 IST: remaining non-AWS items

- Works: confirmation anomaly flags (FAST_CONFIRM under 60 s, DEVICE_FANOUT when one phone confirms for 3+ sellers), review signals only, shown in the batch view and returned by `GET /batches/{id}` as `anomalies`; DLQ (SSE-SQS) for Transcribe-completion, nightly digest and WhatsApp deliveries + CloudWatch alarms (each Lambda's errors, API 5xx, DLQ depth) to `oae-<stage>-chaintrack-alarms`; collector sign-in = **username + password** (Shaurya's choice) via Cognito + Amplify UI Authenticator, lazy-loaded (initial JS still 83 KB gz); `create_demo_users.py`; WhatsApp now also sends the two QR codes as images; CI workflow `.github/workflows/chaintrack.yml` (Shaurya approved; path-filtered to ChainTrack folders). 102 Python tests + browser e2e pass.
- Next: AWS deploy as soon as there is an IAM login.
- Blocked: IAM user, GitHub push access, WhatsApp number, deadline time, real voice recordings for the eval, untrained-user test.
- For Mrudduni: (1) `.github/workflows/chaintrack.yml` is new and only runs on ChainTrack paths. (2) WhatsApp QR images are written to the capture evidence bucket under `qr/`; tomorrow's ObjectCreated → evidence-processor rule should match only `evidence/` (weigh slips, photos), not `qr/`, `audio/` or `transcripts/`. (3) The ledger table also holds `ANOMALY#`, `CONFDEV#`, `PHONE#`, `DRAFT#`, `WACODE#`, `WAMSG#`, `RATE#` items; ClaimGuard can ignore any PK it does not know.

## Third-party libraries and licences

| Library | Used in | Licence |
|---|---|---|
| cryptography | ledger signatures | Apache-2.0 / BSD-3-Clause |
| boto3 | AWS adapters | Apache-2.0 |
| cedarpy | Cedar policy tests | Apache-2.0 |
| pytest | tests | MIT |
| react, react-dom | web-capture | MIT |
| i18next, react-i18next | web-capture | MIT |
| qrcode-generator | web-capture QR codes | MIT |
| @zxing/browser | QR scan fallback (lazy) | MIT |
| vite, @vitejs/plugin-react | web-capture build | MIT |
| Playwright (pre-installed, e2e only) | tests | Apache-2.0 |
| aws-amplify, @aws-amplify/ui-react | PWA sign-in | Apache-2.0 |
| segno | WhatsApp QR images | BSD-3-Clause |
