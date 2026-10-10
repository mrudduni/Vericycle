# OpenAEye shared contract

This file is the only thing Mrudduni's work and Shaurya's work share while they build in parallel on 10 October 2026. Both plans (`MRUDDUNI.md`, `SHAURYA.md`) depend on it. If both sides follow it exactly, integration on 11 October is wiring, not rewriting.

**Changing this file:** neither agent edits it alone. If something here is wrong or missing, stop, tell your human (Mrudduni or Shaurya), and they agree the change with each other. The agreed change is committed to `main` by Mrudduni, and both branches pull it.

Design source of truth: [`SOLUTION.md`](../../SOLUTION.md). Where this file differs from `SOLUTION.md`, the difference is listed in section 10 with the reason.

---

## 1. Who owns which folder

An agent writes only inside its owner's folders. Reading anything is fine.

| Path | Owner | Contents |
|---|---|---|
| `infra/chaintrack/` | Shaurya | CDK app: core, ledger, capture, capture-web stacks |
| `services/ingest/` | Shaurya | WhatsApp (EUMS) and web-chat intake Lambdas |
| `services/extract/` | Shaurya | Transcribe + Bedrock extraction |
| `services/ledger/` | Shaurya | Ledger writer, `verify_chain`, Merkle digest |
| `services/capture_api/` | Shaurya | Capture HTTP API handlers |
| `policies/` | Shaurya | Cedar schema, policies, policy tests |
| `web-capture/` | Shaurya | Mobile PWA: chat capture, QR, forms, receipt, handler confirmation, public verify page |
| `scripts/chaintrack/` | Shaurya | Seed, build and tamper-demo scripts |
| `tests/chaintrack/` | Shaurya | Tests for the above |
| `docs/team/log-shaurya.md` | Shaurya | Running work log |
| `infra/claimguard/` | Mrudduni | CDK app: claims, evidence, claimguard, review-web, ai stacks |
| `services/claimguard/` | Mrudduni | Pure rule engine, rule YAML, solar, scores, Lambda handlers |
| `services/evidence/` | Mrudduni | Textract, EXIF, pHash processor |
| `services/review_api/` | Mrudduni | Review HTTP API handlers |
| `agent/` | Mrudduni | Strands copilot and MCP tool server |
| `web-review/` | Mrudduni | Desktop review dashboard and impact panel |
| `data/` | Mrudduni | `sources.yaml`, facilities, claims, sample evidence, ledger fixture |
| `scripts/claimguard/` | Mrudduni | Data generators, seed, build scripts |
| `tests/claimguard/` | Mrudduni | Tests for the above |
| `docs/team/log-mrudduni.md` | Mrudduni | Running work log |
| `docs/team/CONTRACT.md`, `SOLUTION.md`, `README.md`, `LICENSE`, `.gitignore` | Shared | Change only by agreement (see top) |

Each owner's Python area has its own `pyproject.toml` (managed with `uv`), and each web app has its own `package.json`. There is no shared root `package.json` or `pyproject.toml` today, so nothing merges into the same lockfile.

---

## 2. Stack, versions and conventions

| Item | Choice |
|---|---|
| Region | `ap-southeast-2` (Sydney) for every OpenAEye resource, AWS account `206690614182` (changed from `ap-south-1` by agreement on 10 Oct 2026, see §10) |
| Infrastructure | AWS CDK v2, TypeScript, one CDK app per owner, `cdk-nag` AwsSolutions pack on both |
| Lambda runtime | Python 3.12, `arm64` (Graviton) |
| Lambda utilities | Powertools for AWS Lambda (Python), via the public Powertools Lambda layer |
| Packaging | No Docker requirement. Build dependencies with `uv pip install --python-platform aarch64-manylinux2014 --python-version 3.12 --only-binary :all: --target <dir>`, then `Code.fromAsset` |
| Web | React 18 + Vite + TypeScript, Amplify UI components for sign-in, hosted on Amplify Hosting |
| Time | ISO 8601 with offset, IST `+05:30` in demo data. Server times come from the server clock only |
| Weights | kilograms in events, tonnes in claims. Field names carry the unit (`weight_kg`, `processed_t`) |
| Money | none in the data model |

### Stage names and resource names

Every deploy takes a stage: `cdk deploy -c stage=<stage>`.

| Stage | Who | When |
|---|---|---|
| `mrudduni` | Mrudduni's agent | 10 October, parallel build |
| `shaurya` | Shaurya's agent | 10 October, parallel build |
| `prod` | Both, together | 11 October, after merge |

Name pattern: `oae-<stage>-<thing>` for resources, `OAE-<Stage>-<Stack>` for stacks. Both people deploy into the **same AWS account**, so the stage prefix is what keeps them apart. Never deploy to or delete the other person's stage.

Tag every resource: `project=openaeye`, `stage=<stage>`, `owner=<mrudduni|shaurya>`.

### Cross-app references (SSM Parameter Store)

The two CDK apps never import each other's code. They exchange names and ARNs through SSM parameters under `/openaeye/<stage>/`.

Written by Shaurya's app:

| Parameter | Value |
|---|---|
| `/openaeye/<stage>/ledger/table-name` | `oae-<stage>-ledger` |
| `/openaeye/<stage>/ledger/table-arn` | table ARN |
| `/openaeye/<stage>/capture/evidence-bucket` | `oae-<stage>-capture-evidence-<account>` |
| `/openaeye/<stage>/capture/api-url` | capture HTTP API base URL |
| `/openaeye/<stage>/capture/web-url` | capture PWA URL |
| `/openaeye/<stage>/auth/user-pool-id` | Cognito user pool ID |
| `/openaeye/<stage>/auth/user-pool-client-id-review` | app client for the review dashboard |
| `/openaeye/<stage>/authz/policy-store-id` | Verified Permissions policy store ID |
| `/openaeye/<stage>/ledger/signing-key-arn` | KMS asymmetric signing key ARN |

Written by Mrudduni's app:

| Parameter | Value |
|---|---|
| `/openaeye/<stage>/claims/table-name` | `oae-<stage>-claims` |
| `/openaeye/<stage>/claims/table-arn` | table ARN |
| `/openaeye/<stage>/review/api-url` | review HTTP API base URL |
| `/openaeye/<stage>/review/web-url` | review dashboard URL |
| `/openaeye/<stage>/evidence/processor-fn-arn` | evidence processor Lambda ARN |

On 10 October, Mrudduni's app runs without Shaurya's parameters (fixture mode, section 8). It reads them only when deployed with `-c ledgerStage=<stage>`.

---

## 3. Enums

These strings are exact. Do not add members without agreement.

```text
Material            BATTERY_LEAD_ACID | EWASTE_PHONE | AC_REFRIGERANT
ClaimProduct        BATTERY_LEAD_ACID | EWASTE_PHONE          # no AC_REFRIGERANT, ever
Role                HANDLER | COLLECTOR | AGGREGATOR | RECYCLER | AUDITOR | PRODUCER
EventType           HANDOVER | TRANSFER | SPLIT | MERGE | INTAKE | PROCESS | OUTPUT | CORRECTION
Basis               STATED | WEIGHED | OCR | COMPUTED
ConfirmationChannel OWN_DEVICE_WHATSAPP | OWN_DEVICE_SMS | OWN_DEVICE_LINK | SAME_DEVICE | NONE
SourceCategory      DRIVER | HOUSEHOLD | TECHNICIAN | RETAIL_EXCHANGE | INSTITUTION | OTHER | UNKNOWN
EvidenceKind        PHOTO | WEIGH_SLIP | INVOICE | POWER_BILL | VOICE_TRANSCRIPT
RuleOutcome         PASS | FLAG | INSUFFICIENT_EVIDENCE | INCONCLUSIVE
Severity            HARD | SOFT | NONE
ReviewAction        ACCEPT | REQUEST_EVIDENCE | ESCALATE | RECYCLER_RESPONSE
```

### Confirmation status (derived, never stored)

Both sides compute it with the same rules.

**Per field**, from one `FieldValue`:

| Status | Condition | Counts as witnessed? |
|---|---|---|
| `HANDLER_CONFIRMED` | `confirmed_by_roles` contains `HANDLER` and `confirmation_channel` is `OWN_DEVICE_WHATSAPP`, `OWN_DEVICE_SMS` or `OWN_DEVICE_LINK` | Yes |
| `SAME_DEVICE_CONFIRMED` | `confirmed_by_roles` contains `HANDLER` and `confirmation_channel` is `SAME_DEVICE` | **No** |
| `BUYER_REPORTED` | `confirmed_by_roles` is empty | No |

**Per event**, over the fields the confirmation token asked the handler about (`field_names` on the token; for a `HANDOVER` these are `count`, `source_category` and, if stated, `weight_kg`):

| Status | Condition |
|---|---|
| `BOTH_PARTIES_CONFIRMED` | The buyer created the event (always true) and **every** asked field is `HANDLER_CONFIRMED` |
| `HANDLER_CONFIRMED` | At least one asked field is `HANDLER_CONFIRMED`, but not all |
| `BUYER_REPORTED` | No asked field is `HANDLER_CONFIRMED` (this includes `SAME_DEVICE_CONFIRMED`) |

Evidence badge, separate from the above: `EVIDENCE_ATTACHED` when `evidence_ids` is non-empty, else `EVIDENCE_MISSING`. It never means the evidence is true.

The UI shows status as an icon plus text, never colour alone.

---

## 4. Identifiers

| Thing | Format | Example |
|---|---|---|
| Batch (demo seed) | `B-` + 4 digits (battery), `P-` + 4 digits (phone), `A-` + 4 digits (AC) | `B-0042` |
| Batch (created live) | `B-`/`P-`/`A-` + 8 Crockford base32 chars | `B-7KQ2M9XD` |
| Child batch of a split | parent ID + `.` + 1-based index | `B-0046.1` |
| Handler | `HND-` + first 6 hex of the phone HMAC, or random 6 hex when no phone | `HND-7f3a9c` |
| Business party | `COL-` / `AGG-` / `REC-` / `AUD-` / `PRD-` + 2 or 3 digits | `COL-118` |
| Claim | `C-` + 3 digits, optional letter | `C-105b` |
| Evidence | `EV-` + ULID | `EV-01JA3W6Z8T5Q9F0B2C4D6E8G1H` |
| Confirmation token | 22-char URL-safe random, single use, 7-day expiry | — |
| Receipt token (QR) | 22-char URL-safe random, opaque, maps to `batch_id` | — |

QR codes encode only `https://<capture-web-url>/r/<receipt_token>`. Never data.

---

## 5. Event schema and hashing

### Event

```json
{
  "batch_id": "B-0042",
  "seq": 1,
  "type": "HANDOVER",
  "material": "BATTERY_LEAD_ACID",
  "at_device": "2026-10-03T10:14:03+05:30",
  "at_server": "2026-10-03T10:14:09+05:30",
  "actor_party_id": "COL-118",
  "counterparty_party_id": "HND-2b81d0",
  "parent_batch_ids": [],
  "child_batch_ids": [],
  "fields": {
    "count":     {"value": 6,   "unit": null, "asserted_by_role": "COLLECTOR", "confirmed_by_roles": [], "confirmation_channel": "NONE", "basis": "STATED"},
    "weight_kg": {"value": 180, "unit": "kg", "asserted_by_role": "COLLECTOR", "confirmed_by_roles": [], "confirmation_channel": "NONE", "basis": "STATED"},
    "source_category": {"value": "DRIVER", "unit": null, "asserted_by_role": "COLLECTOR", "confirmed_by_roles": [], "confirmation_channel": "NONE", "basis": "STATED"}
  },
  "evidence_ids": ["EV-01JA..."],
  "geohash5": null,
  "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "hash": "<64 hex>",
  "kms_sig": "<base64 DER ECDSA signature>"
}
```

`material` is repeated on every event so readers never need the batch item to know the product.

### Fields expected per event type

| Type | Required fields | Optional fields |
|---|---|---|
| `HANDOVER` | `count`, `source_category`; battery and phone: `weight_kg` | AC: `gas_type` (`R-22`, `R-32`, `R-410A`, `UNKNOWN`), `charge_kg`; phone: `device_category` |
| `TRANSFER` | `weight_kg` | `count` |
| `SPLIT` | `child_weights_kg` (map child ID → kg) | — |
| `MERGE` | `weight_kg` (merged total) | — |
| `INTAKE` | `weight_kg` (basis `WEIGHED` or `OCR`), `facility_id` | `count` |
| `PROCESS` | `input_kg`, `run_id` | — |
| `OUTPUT` | `metal` (`LEAD`, `COPPER`, `ALUMINIUM`, `IRON`, `GOLD`), `output_kg` | — |
| `CORRECTION` | `corrects_seq`, `field`, `new_value`, `reason` | — |

### Hash chain (both sides must compute this identically)

1. Take the event object and remove `hash` and `kms_sig`.
2. `canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`. Numbers: integers as integers; non-integers as decimals with no trailing zeros (convert DynamoDB `Decimal` back to `int` or `float` first).
3. `hash = sha256(bytes.fromhex(prev_hash) + canonical).hexdigest()`.
4. `prev_hash` of `seq 1` is 64 zeros. `seq` starts at 1 per batch and has no gaps.
5. `kms_sig = KMS.Sign(KeyId=<signing key>, Message=bytes.fromhex(hash), MessageType="DIGEST", SigningAlgorithm="ECDSA_SHA_256")`, base64. Key spec `ECC_NIST_P256`, usage `SIGN_VERIFY`.

A split writes a `SPLIT` event on the parent and a first event (`type: SPLIT`, `parent_batch_ids: [parent]`) on each child. A merge writes a `MERGE` event on the new batch with `parent_batch_ids`, and a `MERGE` event on each parent with `child_batch_ids: [new]`.

---

## 6. DynamoDB tables

Both tables: on-demand, SSE-KMS, point-in-time recovery on, deletion protection on for `prod`.

### `oae-<stage>-ledger` (Shaurya writes; Mrudduni reads only)

| Item | PK | SK | Attributes |
|---|---|---|---|
| Event | `BATCH#<batch_id>` | `EVT#<seq zero-padded to 6>` | every Event field from section 5, top level |
| Batch head | `BATCH#<batch_id>` | `META` | `material`, `status` (`OPEN`, `AT_RECYCLER`, `PROCESSED`, `SPLIT`, `MERGED`), `last_seq`, `last_hash`, `parent_batch_ids`, `child_batch_ids`, `receipt_token` |
| Party | `PARTY#<party_id>` | `META` | `role`, `display_name` (null for handlers), `registration_no`, `phone_hmac` (never returned by any API) |
| Capture evidence | `EV#<evidence_id>` | `META` | `kind`, `s3_bucket`, `s3_key`, `sha256`, `received_at_server`, `batch_id`, `uploaded_by_party_id` |
| Confirmation token | `CONFIRM#<token>` | `META` | `batch_id`, `seq`, `field_names`, `creator_device_id`, `expires_at` (TTL), `used_at` |
| Receipt token | `RECEIPT#<token>` | `META` | `batch_id` |

GSI `GSI2` (party timeline): PK `GSI2PK = PARTY#<actor_party_id>`, SK `GSI2SK = <at_server>`. Set on event items only.

Updates to an event item after write are forbidden. The batch head is updated with a condition on `last_seq` so two writers can never produce the same `seq`.

### `oae-<stage>-claims` (Mrudduni writes; Shaurya never needs it)

| Item | PK | SK |
|---|---|---|
| Claim | `CLAIM#<claim_id>` | `META` |
| Batch cited by claim | `CLAIM#<claim_id>` | `BATCH#<batch_id>` |
| Rule result | `CLAIM#<claim_id>` | `RULE#<rule_id>#<version>#<run_id>` |
| Review or response (append-only) | `CLAIM#<claim_id>` | `REVIEW#<seq 6>` |
| Facility | `FACILITY#<party_id>` | `META` |
| Processed evidence | `EV#<evidence_id>` | `META` (`exif`, `extracted`, `sha256`, `phash`, `source_bucket`) |
| Claims citing a batch | GSI `GSI1`: `GSI1PK = BATCH#<batch_id>`, `GSI1SK = CLAIM#<claim_id>` | — |
| Evidence by pHash prefix | GSI `GSI3`: `GSI3PK = PHASH#<first 4 hex>`, `GSI3SK = EV#<evidence_id>` | — |

---

## 7. HTTP APIs

All responses are JSON. Errors: `{"error": {"code": "<UPPER_SNAKE>", "message": "<plain English>"}}` with a matching HTTP status. Both APIs are API Gateway HTTP APIs with CORS limited to the two web app origins.

### Capture API (Shaurya)

| Method | Path | Caller | Purpose |
|---|---|---|---|
| POST | `/chat/messages` | collector (web chat) | Text or audio (`evidence_id` of uploaded audio). Returns a draft card |
| POST | `/chat/drafts/{draft_id}/confirm` | collector | Turns a draft into a `HANDOVER` event. Body may carry edits |
| POST | `/handovers` | collector | Create a handover directly (form path) |
| POST | `/batches/{batch_id}/events` | aggregator, recycler | `TRANSFER`, `SPLIT`, `MERGE`, `INTAKE`, `PROCESS`, `OUTPUT`, `CORRECTION` |
| GET | `/batches/{batch_id}` | business users | Batch head plus events |
| GET | `/batches/{batch_id}/lineage` | auditor, producer, owning parties | Lineage graph (shape below) |
| GET | `/r/{receipt_token}` | public | Receipt view data. No party IDs except role labels |
| GET | `/confirm/{token}` | handler, no account | What the handler is asked to confirm |
| POST | `/confirm/{token}` | handler, no account | Confirm or reject |
| POST | `/evidence/presign` | business users | Pre-signed PUT URL into the capture evidence bucket |
| GET | `/verify/{batch_id}` | public | Re-verifies the chain; returns `{ok, checked, failed_at_seq, public_key_pem, digest}` |

Lineage response (Mrudduni's dashboard builds against this today using the fixture):

```json
{
  "root_batch_id": "B-0046",
  "nodes": [
    {"batch_id": "B-0046", "material": "BATTERY_LEAD_ACID", "status": "SPLIT",
     "events": [ /* Event objects, section 5, without kms_sig */ ]}
  ],
  "edges": [
    {"from": "B-0046", "to": "B-0046.1", "kind": "SPLIT", "weight_kg": 60}
  ]
}
```

### Review API (Mrudduni)

| Method | Path | Caller | Purpose |
|---|---|---|---|
| GET | `/claims` | auditor, producer, owning recycler | List with flag counts |
| POST | `/claims` | recycler | Submit a claim |
| GET | `/claims/{claim_id}` | auditor, producer, owning recycler | Claim with latest rule results and three scores |
| POST | `/claims/{claim_id}/check` | auditor | Start a ClaimGuard run (Step Functions) |
| GET | `/claims/{claim_id}/runs/{run_id}` | auditor | Run status |
| POST | `/claims/{claim_id}/reviews` | auditor, owning recycler | Append `ACCEPT`, `REQUEST_EVIDENCE`, `ESCALATE` or `RECYCLER_RESPONSE` |
| POST | `/claim-evidence/presign` | recycler | Pre-signed PUT URL into the claim evidence bucket |
| GET | `/impact` | public | Impact numbers, each with `source_id` |
| GET | `/sources/{source_id}` | public | One entry from `data/sources.yaml` |

### Auth

- Business users sign in with Cognito (user pool owned by Shaurya). Groups: `COLLECTOR`, `AGGREGATOR`, `RECYCLER`, `AUDITOR`, `PRODUCER`. Custom attribute `custom:party_id`.
- Handlers never get accounts. A confirmation token is their only credential.
- On 10 October each side may run its own stage without the other's Cognito: Shaurya's stage has the pool; Mrudduni's stage runs the review API with `AUTH_MODE=dev` (no authorizer, synthetic data only, CORS locked). On 11 October the review API gets the Cognito JWT authorizer from `prod`.

---

## 8. Demo dataset

Both sides produce exactly these batches. Shaurya seeds them into the ledger through his real writer (real hashes and signatures). Mrudduni writes the same events into `data/fixtures/ledger_events.json` (hash fields may be `"FIXTURE"`). On 11 October the ClaimGuard expected-outcome test must give the same result against the fixture and against the `prod` ledger.

Weights are `DEMO VALUE`s. An e-rickshaw lead-acid battery is taken as about 30 kg (Mrudduni to source or label it).

### Parties

| ID | Role | Display name |
|---|---|---|
| `HND-7f3a9c`, `HND-2b81d0`, `HND-c4e5f6`, `HND-91aa07`, `HND-5d3e12` | HANDLER | null |
| `COL-118` | COLLECTOR | Demo battery dealer, Delhi |
| `COL-207` | COLLECTOR | Demo phone retailer exchange counter, Delhi |
| `COL-330` | COLLECTOR | Demo AC technician, Delhi |
| `AGG-01` | AGGREGATOR | Demo aggregator, Ghaziabad |
| `REC-01` | RECYCLER | Demo lead recycler (registration `DEMO-REG-0001`) |
| `REC-02` | RECYCLER | Demo e-waste recycler (registration `DEMO-REG-0002`) |
| `AUD-01` | AUDITOR | Demo auditor |
| `PRD-01` | PRODUCER | Demo battery brand |

All names are fictional. Never use a real company's name or logo.

### Batches and events

Times are IST on the dates shown. `→` marks counterparty.

| Batch | Material | Events (seq: type, actor → counterparty, key fields, confirmation) | Cited by |
|---|---|---|---|
| `B-0041` | battery | 1: HANDOVER 2026-10-02 09:40, COL-118 → HND-7f3a9c, count 4, 120 kg STATED, DRIVER, handler confirmed `OWN_DEVICE_WHATSAPP` on count and source_category, not weight (event status HANDLER_CONFIRMED) · 2: TRANSFER 10-04 15:10, COL-118 → AGG-01, 118 kg WEIGHED · 3: INTAKE 10-06 11:05, REC-01, 117 kg WEIGHED, weigh slip evidence | C-101 |
| `B-0042` | battery | 1: HANDOVER 10-03 10:14, COL-118 → HND-2b81d0, count 6, 180 kg STATED, DRIVER, `NONE` (buyer-reported) · 2: TRANSFER 10-04 15:20, COL-118 → AGG-01, 176 kg WEIGHED · 3: INTAKE 10-06 11:30, REC-01, 175 kg WEIGHED | C-101 **and** C-107 |
| `B-0043` | battery | 1: HANDOVER 10-03 17:02, COL-118 → HND-c4e5f6, count 4, 120 kg STATED, DRIVER, handler confirmed `SAME_DEVICE` on count and source_category (event status BUYER_REPORTED) · 2: INTAKE 10-07 10:00, REC-01, 118 kg WEIGHED | C-101 |
| `B-0046` | battery | 1: HANDOVER 10-05 12:00, COL-118 → HND-91aa07, count 4, 120 kg STATED, DRIVER, handler confirmed `OWN_DEVICE_LINK` on count, source_category and weight_kg (event status BOTH_PARTIES_CONFIRMED) · 2: TRANSFER 10-06 09:00, COL-118 → AGG-01, 119 kg WEIGHED · 3: SPLIT 10-06 09:30, AGG-01, children `B-0046.1` 60 kg, `B-0046.2` 58 kg | none (lineage demo) |
| `P-0101` | phone | 1: HANDOVER 2026-07-14 13:00, COL-207 → HND-5d3e12, count 12, 2.1 kg STATED, RETAIL_EXCHANGE, handler confirmed `OWN_DEVICE_WHATSAPP` on all asked fields (BOTH_PARTIES_CONFIRMED) · 2: TRANSFER 07-16, COL-207 → AGG-01, 2.08 kg WEIGHED · 3: INTAKE 07-18, REC-02, 2.05 kg WEIGHED, photo evidence `EV-DUP-PHOTO` | C-106 |
| `P-0102` | phone | 1: HANDOVER 2026-08-11, COL-207, count 9, 1.6 kg STATED, `NONE` · 2: INTAKE 08-14, REC-02, 1.58 kg WEIGHED, photo evidence `EV-DUP-PHOTO` (same file, re-encoded) | C-106 |
| `P-0103` | phone | 1: HANDOVER 2026-09-09, COL-207, count 15, 2.6 kg STATED, `NONE` · 2: INTAKE 09-12, REC-02, 2.57 kg WEIGHED, photo evidence `EV-DUP-PHOTO` | C-106 |
| `A-0001` | AC | 1: HANDOVER 10-04 16:00, COL-330 → (no counterparty), count 1, gas_type R-32, charge_kg 0.9 STATED (default from problem statement) | never (harm-only) |

C-101 coverage check: intake weighed total = 117 + 175 + 118 = 410 kg. C-101 claims 0.500 t input, so coverage is 82%. C-102 to C-105b and C-108 cite no batches (0% coverage, which is a metric, not a flag).

### Expected ClaimGuard outcomes (the acceptance test)

| Claim | Expected |
|---|---|
| C-101 | All `PASS`; coverage 82% |
| C-102 | R1 `FLAG HARD`; card shows the CPCB erratum (46,200 printed, 26,400 correct) |
| C-103 | R2 `FLAG HARD` |
| C-104 | R3 `FLAG SOFT`, next action "request DG logs" |
| C-105 | R5 `FLAG HARD` (16 June 2025 20:22 IST at Hapur, hard sun shadows) |
| C-105b | R5 `INCONCLUSIVE` (19:48 IST, bright diffuse light) |
| C-106 | R6 `FLAG SOFT` (same photo across P-0101, P-0102, P-0103) |
| C-107 | R4 `FLAG HARD` (B-0042 also cited by C-101) |
| C-108 | R3 and R5 `INSUFFICIENT_EVIDENCE`; coverage 0%; **no FLAG** |

---

## 9. Design tokens (both web apps)

Taken from the team's design document (navy headers, green section titles, pale blue callouts). Both apps copy this block into their own CSS so they look like one product.

```css
:root {
  --oae-navy: #17324d;        /* headers, primary buttons */
  --oae-navy-ink: #0f2236;
  --oae-green: #2e7d5b;       /* section titles, confirm actions */
  --oae-callout: #eef4f8;     /* callout panels */
  --oae-callout-border: #d5e2ec;
  --oae-bg: #ffffff;
  --oae-surface: #f7f9fb;
  --oae-text: #1c2733;
  --oae-muted: #5b6b7a;

  /* rule outcomes, SOLUTION §6: PASS is grey, never green "verified" */
  --oae-pass: #6b7785;
  --oae-flag-hard: #b42318;
  --oae-flag-soft: #b54708;
  --oae-insufficient: #1d5fa8;
  --oae-inconclusive: #8a96a3;

  --oae-radius: 10px;
  --oae-font: "Noto Sans", "Noto Sans Devanagari", system-ui, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    --oae-bg: #0e1620; --oae-surface: #152230; --oae-text: #e6edf3; --oae-muted: #9fb0c0;
    --oae-callout: #1a2b3c; --oae-callout-border: #2a4058;
  }
}
```

Wording rules for both UIs: a passing claim is "consistent with available data", never "verified" or "genuine". No party is ever called "fraudulent". Every number has an ⓘ that opens its source.

---

## 10. Deliberate differences from SOLUTION.md

| SOLUTION.md | Here | Why |
|---|---|---|
| One DynamoDB table | Two tables (`ledger`, `claims`) with the same key patterns | Each person writes only their own table, so parallel work cannot corrupt the other's data |
| One CDK app under `infra/stacks/` | Two CDK apps, `infra/chaintrack/` and `infra/claimguard/`, linked by SSM parameters | No shared `bin/app.ts` or lockfile to conflict on |
| One web app | `web-capture/` (mobile, collectors, aggregators, recyclers, handlers) and `web-review/` (desktop, auditors, producers) | Different users and devices; zero file overlap |
| `/claims/{id}:check`, `/evidence:presign` | `/claims/{id}/check`, `/evidence/presign` | API Gateway path parameters must fill a whole segment |
| WhatsApp only for F1 | WhatsApp via EUMS **plus** a WhatsApp-style chat screen in the PWA that calls the same pipeline | Meta number setup can take longer than the time left; the demo must not depend on it |
| Demo script of 4 minutes (§18) | 3 minutes | Hackathon rule: video of up to three minutes, no live demo |
| Mumbai (`ap-south-1`); data stays in India | Sydney (`ap-southeast-2`), account `206690614182`; the privacy page says so | Agreed by Mrudduni and Shaurya on 10 Oct 2026. Account 773870812969 never activated; the working account's organisation policy denies `ap-south-1`. Demo data is synthetic, so no real personal data leaves India |
| Voice notes via Amazon Transcribe; slips and bills via Amazon Textract; WhatsApp via EUMS | Deployed with voice off (`-c voice=off`, `OAE_VOICE=off`): typed chat only. Textract failures record the file with `extracted.unavailable`. WhatsApp not deployed | The account's organisation policy denies Transcribe, Textract and End User Messaging Social. The code paths remain and are tested offline |
