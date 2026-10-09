# Build plan: Shaurya (ChainTrack: capture, ledger, PWA, access control)

You are the coding agent working for **Shaurya**. Read this whole file, then [`CONTRACT.md`](CONTRACT.md), then [`SOLUTION.md`](../../SOLUTION.md) sections 3, 4, 5, 7, 8, 13 and 14, before writing code.

Mrudduni builds ClaimGuard (rules, evidence, dashboard, copilot) at the same time, from [`MRUDDUNI.md`](MRUDDUNI.md). You never edit her folders and she never edits yours. You meet only through `CONTRACT.md`.

| | |
|---|---|
| Your half | Record the first handover and every handover after it: WhatsApp and voice capture, the tamper-evident ledger, receipts and QR, handler confirmation, the mobile PWA, and Cedar access control |
| Your branch | `shaurya/chaintrack` |
| Your AWS stage | `shaurya` (`cdk deploy -c stage=shaurya`) |
| Today | 10 October 2026: build and test your half alone, push often |
| Tomorrow | 11 October 2026: integrate with Mrudduni, test end to end, record the video, submit |

---

## 0. How you work with Shaurya and Mrudduni

These rules apply for the whole build, including future sessions that read this file.

**Ask Shaurya before you:**

- change anything in `CONTRACT.md`, or need Mrudduni's side to behave differently than the contract says;
- depart from the design in `SOLUTION.md` (privacy rules P5 and P6, append-only history P8, confirmation channels, the architecture);
- add an AWS service that is not in `SOLUTION.md`, or anything with a fixed monthly cost;
- delete or replace any AWS resource, S3 object or DynamoDB item that you did not create in this session;
- set an S3 Object Lock retention longer than 1 day (compliance mode cannot be shortened or deleted by anyone, including the account root);
- push to `main`, merge any branch, rewrite history, or force-push;
- turn off a security control (cdk-nag rule, encryption, auth) even temporarily;
- choose a login method for collectors (see 3.9), or any choice that changes what a handler or judge sees.

The AWS account and the GitHub repo belong to Mrudduni. Anything account-wide (billing, plan upgrade, IAM beyond your own stage, credits, deleting shared resources) goes through Shaurya to Mrudduni.

**Tell Shaurya straight away when:**

- a step fails twice, or you are about to use a fallback from this plan;
- you find a mistake or gap in `CONTRACT.md` or `SOLUTION.md` (say what and where);
- an AWS Budget alarm fires, or a service or model is not available in `ap-south-1`;
- Meta or WhatsApp onboarding needs something from a person (phone number, OTP, business details);
- something needs Mrudduni. Write the message for Shaurya to forward, in two or three lines.

**After every push**, add a short entry to `docs/team/log-shaurya.md` and give Shaurya the same three lines in chat: what works now, what is next, what is blocked. Keep reporting even when things go well.

Write to Shaurya plainly. No filler, no hype. If you are not sure something works, say so and say how you checked.

---

## 1. Set up (first 45 minutes)

### 1.1 Access you need from Mrudduni first

Shaurya needs, from Mrudduni:

1. Collaborator access to `github.com/mrudduni/OpenAEye`.
2. An IAM user with console access in Mrudduni's AWS account. Never use or ask for Mrudduni's root login or access keys.

If either is missing, stop and tell Shaurya.

### 1.2 AWS Agent Toolkit

Run this prompt in your coding agent (Claude Code, Codex, Kiro or any MCP tool):

```text
Set up Agent Toolkit for AWS by following instructions:
https://raw.githubusercontent.com/aws/agent-toolkit-for-aws/refs/heads/main/setup-instructions/setup.md
```

What it does, so you can check each step:

1. Installs AWS CLI v2 if `aws` is missing.
2. Runs `aws login`, which opens a browser. **Shaurya signs in with the IAM user from 1.1.** Never ask for access keys or secret keys, and never paste keys into chat or files. Credentials last 12 hours and refresh for up to 90 days.
3. Confirms identity with `aws sts get-caller-identity`. The account ID must be Mrudduni's account.
4. Configures the AWS MCP server and core AWS skills. The toolkit's own endpoint runs in `us-east-1`. That is only the toolkit. **Every OpenAEye resource goes in `ap-south-1`.**
5. Adds AWS rules to your agent's rules file (`CLAUDE.md` for Claude Code, `AGENTS.md` for Codex, `.kiro/steering/` for Kiro).

Answers to give the wizard: profile name `openaeye`, Region `ap-south-1`. If the MCP server fails with a parameter error, add `"env": {"AWS_MCP_PROXY_PROFILES": "openaeye"}` to the `aws-mcp` entry in the MCP config and restart the agent.

**Keep toolkit files out of git.** Mrudduni's agent writes its own copy. The repo's `.gitignore` already ignores `CLAUDE.md`, `AGENTS.md`, `.kiro/`, `.mcp.json` and `.claude/`. Check with `git status` after setup that none of them shows up.

### 1.3 Start WhatsApp onboarding now (it has lead time)

Real WhatsApp goes through **AWS End User Messaging Social** (EUMS), which is available in `ap-south-1`. Linking a number uses Meta's embedded sign-up from the EUMS console. Ask Shaurya for:

- a phone number that can receive an SMS or voice OTP and is **not** registered on WhatsApp or WhatsApp Business (or whose WhatsApp account is deleted first);
- a Meta Business account (can be created during sign-up) and a business display name.

Customer-initiated conversations and replies inside the 24-hour window need no template approval, and interactive reply buttons work inside that window. Unverified business accounts have low daily limits, which is fine for a demo. If onboarding stalls, do not wait: the web chat (3.4) uses the same pipeline and is the demo path. Report the status to Shaurya either way.

Also check whether the account's plan (Free or Paid) allows EUMS. If not, tell Shaurya so Mrudduni can decide.

### 1.4 Repo and branch

```bash
git clone https://github.com/mrudduni/OpenAEye && cd OpenAEye
git checkout -b shaurya/chaintrack
git push -u origin shaurya/chaintrack
```

Create `docs/team/log-shaurya.md` with a first entry and push it. That proves the push path works.

### 1.5 Tools

Node 20+, AWS CDK v2 (`npm i -g aws-cdk`), Python 3.12, `uv`, Git, the Cedar CLI (`cargo install cedar-policy-cli`) or the `cedarpy` Python package. Detect the OS first. No Docker needed (`CONTRACT.md` section 2).

Bootstrap CDK in `ap-south-1` if `CDKToolkit` does not exist. Check first with `aws cloudformation describe-stacks --stack-name CDKToolkit --region ap-south-1`. If Mrudduni already bootstrapped it, skip.

---

## 2. Git rules

- Work only on `shaurya/chaintrack`. Never commit to `main`. Never merge or pull Mrudduni's branch today.
- **Commit every time something small works** (a test passes, a stack deploys, a screen renders). **Push at least every 45 minutes**, and always before you stop, before a long deploy, and before you switch tasks. A session must never end with unpushed commits.
- Commit messages: `feat(ledger): hash chain with KMS signature`, `feat(web-capture): chat capture screen`, `fix(...)`, `test(...)`. One idea per commit.
- Never commit secrets, `.env`, `cdk.out/`, `node_modules/`, `.build/`, voice recordings, real phone numbers or other personal data.
- Only write inside your folders (`CONTRACT.md` section 1). If you need a file outside them, ask Shaurya.
- If `main` gets a contract update, `git fetch && git merge origin/main`. Rebase and `--force-with-lease` only after asking Shaurya.
- Hackathon rule: repository history must match the event dates. Commit as you go; never backdate.

---

## 3. What you build

Folder map (yours only):

```text
services/ledger/
  pyproject.toml
  ledger/
    canonical.py        # canonical JSON + hash, exactly CONTRACT §5
    writer.py           # append_event(): conditional write on last_seq, KMS sign
    verify_chain.py     # CLI + library: verify a batch, report failed seq or gap
    digest.py           # Merkle root of a day's events
    handlers/           # writer, digest Lambdas
services/ingest/        # whatsapp.py (SNS from EUMS), webchat.py
services/extract/       # transcribe.py, bedrock_extract.py, schema.json, prompts/
services/capture_api/
  materials.yaml        # per-material fields, units, labels (en, hi), extraction hints
  handlers/             # one module per route in CONTRACT §7 capture API
policies/
  schema.cedarschema
  *.cedar
  tests/                # allow/deny cases
web-capture/            # React PWA
infra/chaintrack/       # CDK app
scripts/chaintrack/     # seed_demo.py, tamper_demo.py, build_lambdas.sh
tests/chaintrack/
```

The ledger library imports `boto3` only in the writer's KMS and DynamoDB adapter, so hashing and verification are testable offline.

### 3.1 Core infrastructure (`infra/chaintrack/`, stack `Core`)

- KMS keys: symmetric key for S3 and DynamoDB encryption; asymmetric `ECC_NIST_P256` `SIGN_VERIFY` key for ledger signatures; `HMAC_256` key for phone numbers (`GenerateMac`).
- DynamoDB `oae-<stage>-ledger`, exactly `CONTRACT.md` section 6, with `GSI2`.
- S3 `oae-<stage>-capture-evidence-<account>`: SSE-KMS, block public access, lifecycle rule deleting `audio/` after 1 day (raw voice deleted within 24 h), CORS for the PWA origin.
- S3 `oae-<stage>-ledger-digests-<account>`: Object Lock **enabled at creation**, compliance mode, default retention **1 day** on stage buckets. Ask Shaurya before setting anything longer for `prod`.
- Cognito user pool: groups `COLLECTOR`, `AGGREGATOR`, `RECYCLER`, `AUDITOR`, `PRODUCER`; custom attribute `custom:party_id`; app clients for capture and review.
- Verified Permissions policy store loaded from `policies/`.
- SSM parameters from `CONTRACT.md` section 2.
- `cdk-nag` AwsSolutions; document each suppression with a reason.

### 3.2 Ledger (`services/ledger/`)

- `append_event(batch_id, event)`:
  1. Read batch head (`last_seq`, `last_hash`).
  2. Set `seq = last_seq + 1`, `prev_hash = last_hash`, `at_server` = server clock now.
  3. Compute `hash` per `CONTRACT.md` section 5; sign with KMS.
  4. One `TransactWriteItems`: put the event item with `attribute_not_exists(PK)` and update the head with condition `last_seq = :expected`. On condition failure, retry from step 1 (max 3).
- Never update or delete an event item. Corrections are `CORRECTION` events.
- `verify_chain(batch_id)`: recompute every hash, check `prev_hash` links, check `seq` has no gaps, verify each signature with the KMS public key (fetch it once with `GetPublicKey`, then verify locally with `cryptography`). Returns `{ok, checked, failed_at_seq, reason}`.
- `digest.py`: Merkle root (SHA-256, pairwise, duplicate the last leaf when odd) over the hashes of events with `at_server` on that IST date, ordered by `(at_server, batch_id, seq)`. Writes `digests/YYYY-MM-DD.json` (`date`, `root`, `count`, `first`, `last`, `signature`) to the Object Lock bucket. Runs nightly via EventBridge Scheduler and on demand (for the demo).
- Add `GET /digests/latest` and `GET /digests/{date}` to your capture API for the public verify page. Nobody else depends on these, so they are not a contract change.
- `scripts/chaintrack/seed_demo.py`: writes the parties and batches in `CONTRACT.md` section 8 through the real writer. Seed mode may set `at_server` to the table's times; the API never can.
- `scripts/chaintrack/tamper_demo.py --stage <s> --batch B-0042 --seq 2`: edits `weight_kg` of one stored event directly in DynamoDB (refuses to run on `prod` without `--yes-prod`), then runs `verify_chain` to show the failure; `--restore` puts it back.

### 3.3 Voice and text extraction (`services/extract/`)

- Input: audio in S3 (WhatsApp voice notes are OGG/Opus; browser recordings are WebM/Opus; Transcribe accepts both) or plain text.
- Transcribe batch job with `IdentifyLanguage` and `LanguageOptions` `hi-IN`, `en-IN`. Poll with Step Functions or an EventBridge rule on job completion; do not sleep in a Lambda.
- Bedrock Converse with a tool whose input schema is the extraction schema, so the model must return valid JSON:

```json
{
  "material": "BATTERY_LEAD_ACID | EWASTE_PHONE | AC_REFRIGERANT | UNKNOWN",
  "count": "integer or null",
  "weight_kg": "number or null",
  "weight_basis": "STATED | WEIGHED",
  "source_category": "DRIVER | HOUSEHOLD | TECHNICIAN | RETAIL_EXCHANGE | INSTITUTION | OTHER | UNKNOWN",
  "gas_type": "R-22 | R-32 | R-410A | UNKNOWN | null",
  "charge_kg": "number or null",
  "language": "hi | en | mixed",
  "uncertain_fields": ["field names the model is unsure about"]
}
```

- The transcript goes into the prompt as quoted data inside clear delimiters, never as instructions.
- Numbers spoken as Hindi words ("chaar", "assi", "dedh sau") must work. Every numeric field is read back on the card for the collector to confirm; the model never has the last word.
- Model choice: list what works with `aws bedrock list-inference-profiles --region ap-south-1` and `list-foundation-models`. Default to a small, cheap model (Amazon Nova Lite or Micro, or an APAC cross-region Claude Haiku profile if the account allows Marketplace models). Keep the model ID in an SSM parameter, not in code. Tell Shaurya which model and which region processes the data.
- Eval set: record at least 10 voice notes (Shaurya and friends, with consent; Hindi, Hinglish, English, one noisy). Target: `count` exact on at least 9 of 10. Store transcripts and expected JSON in `tests/chaintrack/eval/`, never the audio.

### 3.4 Capture channels (`services/ingest/`)

**Web chat (build first; it is the guaranteed demo path).** `POST /chat/messages` takes text or an uploaded audio `evidence_id`, runs extraction, and returns a draft card. `POST /chat/drafts/{id}/confirm` turns the draft into a `HANDOVER` via the ledger writer. Drafts live 24 hours (DynamoDB TTL item `DRAFT#<id>` in your table).

**WhatsApp via EUMS (build when the number is linked).**

- EUMS publishes inbound events to an SNS topic. A Lambda subscribed to it parses `whatsAppWebhookEntry`, applies Powertools idempotency on the WhatsApp message ID (Meta retries), and handles:
  - voice note: `GetWhatsAppMessageMedia` straight to S3 `audio/`, then the same extraction pipeline;
  - text: extraction directly;
  - button reply ✅ / ✏️: confirm the draft or ask which field to change.
- Replies go out with `SendWhatsAppMessage` (Meta Cloud API message JSON as the payload): an interactive message with the numbers in Hindi and English and ✅ / ✏️ buttons. After ✅: the receipt link and a QR image.
- Sender authorisation: only numbers registered as `COLLECTOR` parties (stored as HMACs) can create records. Others get a polite reply saying how to register.
- Per-phone rate limit (for example 30 messages an hour) to prevent spam.

**Handler confirmation without a message template.** Business-initiated WhatsApp messages need an approved template. Avoid that: the receipt card shows a second QR and a share link to `https://wa.me/<OpenAEye number>?text=HAAN%20<6-char code>`. The handler scans or taps it on **their own phone** and sends it, which makes it a customer-initiated message. The Lambda matches the code to the confirmation token, compares the sender's phone HMAC with the collector's, and records `OWN_DEVICE_WHATSAPP` if they differ, `SAME_DEVICE` if they match. The same card offers the link `/c/<token>` for handlers without WhatsApp (`OWN_DEVICE_LINK` when opened on a different device, see 3.6).

**SMS** is out of scope for this build: sending SMS in India needs DLT registration that cannot finish in time. Keep `OWN_DEVICE_SMS` in the enum; list it as a limitation.

### 3.5 Capture API (`services/capture_api/`)

Every route in `CONTRACT.md` section 7 under "Capture API", plus the digest routes in 3.2.

- Powertools: logger, tracer, idempotency on every POST (client sends `Idempotency-Key`, a ULID created on the device).
- Event validation from `materials.yaml` and the per-type field table in `CONTRACT.md` section 5. Adding a material is a YAML change only; prove it with the phone batch.
- Event order checks at write time: an `INTAKE` on a batch with no earlier event is still accepted (R4 needs to see it), but the response carries a warning `NO_UPSTREAM_EVENT`. Do not add fields to the event for this.
- `POST /batches/{id}/events` with `SPLIT`: children's weights must sum to the parent's last weighed weight within 2%, else 422.
- Responses never contain `phone_hmac`, phone numbers, or a handler's `display_name`. Test this.
- Authorisation through Verified Permissions `IsAuthorized` (3.8).

### 3.6 Receipts, QR and handler confirmation

- After a `HANDOVER`: create a receipt token (QR target `/r/<token>`) and a confirmation token scoped to that event and the fields `count`, `source_category`, and `weight_kg` if stated.
- `/c/<token>` page: Hindi first with an English toggle. Shows only the material, count and approximate weight in large type, and two big buttons: "हाँ, मैंने बेचा / Yes, I sold this" and "नहीं / No". Asks for nothing personal. Explains in one line what the record is for.
- Device check: the PWA stores a random `device_id` in local storage. The confirmation token records the creator's `device_id`. If the confirm page sees the same `device_id`, the channel is `SAME_DEVICE`. If it sees a different one or none, `OWN_DEVICE_LINK`.
- Tokens are single use and expire after 7 days. A rejection is recorded as a `CORRECTION` event with reason `HANDLER_REJECTED`.
- Confirmation writes go through Cedar: only a `HandlerToken` principal may add `HANDLER` to `confirmed_by_roles`.

### 3.7 Mobile PWA (`web-capture/`)

React + Vite + TypeScript, installable, Hindi and English (`react-i18next`), designed for a cheap Android phone on a slow connection. Use the tokens in `CONTRACT.md` section 9 so it matches Mrudduni's dashboard and the team's design document.

Targets: initial JS under 200 KB gzipped, tap targets at least 48 px, body text at least 16 px, works on Chrome for Android, no horizontal scroll at 360 px wide.

Screens:

1. **Chat capture** (collector). Looks and behaves like a WhatsApp chat on purpose, so the fallback feels like the real thing: message bubbles, a hold-to-record mic button, a text box, and the draft card with ✅ / ✏️. After ✅ the chat shows the receipt card with both QR codes (next handler, seller confirmation).
2. **Scan** (aggregator, recycler). Camera QR scan (`BarcodeDetector` where available, else a small library such as `@zxing/browser`). Opens the batch.
3. **Batch view**. Timeline of events with confirmation chips (icon + text, never colour alone): "Seller confirmed on own phone", "Entered by buyer only", "Confirmed on buyer's phone (not independent)". Actions by role: Transfer, Split, Merge, Intake, Process, Output, Correct.
4. **Intake form** (recycler). Weighed kg, facility, weigh slip photo from the **in-app camera**: capture to canvas, hash with WebCrypto SHA-256 on the device, upload with a pre-signed URL; the server stores its own receipt time and checks the hash.
5. **Offline queue**. Events made offline go into IndexedDB with their `Idempotency-Key` and sync once on reconnect. A small banner shows "3 records waiting to send".
6. **Receipt page** `/r/<token>` (public). Material, count, approximate weight, date, chain status. No names. Printable.
7. **Confirm page** `/c/<token>` (3.6).
8. **Public verify page** `/v/<batch_id>`. Calls `/verify/{batch_id}` and `/digests/latest`; shows "Chain intact: 3 of 3 events check out" or the failing seq. This is where the tamper demo is shown.
9. **AC record** (technician). Same chat flow with material `AC_REFRIGERANT`: gas type and nameplate charge if visible. The receipt says: "Refrigerant earns no recycling certificate. This record counts towards the uncounted-harm figure." There is no claim path for AC anywhere.

### 3.8 Cedar policies (`policies/`) and Verified Permissions

Entities: `BusinessUser` (attributes `role`, `party_id`), `HandlerToken` (`batch_id`, `seq`, `field_names`), `Copilot`. Resources: `Batch`, `Event`, `Claim` (`recycler_party_id`, `producer_party_ids`). Actions: `CreateEvent`, `ConfirmHandlerField`, `ReadBatch`, `ReadClaim`, `Write`.

Required tests (allow or deny, run locally with the Cedar CLI or `cedarpy`, and in CI):

| Case | Expected |
|---|---|
| Collector writing `confirmed_by_roles: ["HANDLER"]` | **deny** |
| `HandlerToken` confirming fields of its own event | allow |
| `HandlerToken` confirming another batch's event | deny |
| Recycler reading another recycler's claim | deny |
| Producer reading a claim that cites its products | allow |
| Copilot doing any write | deny |
| Aggregator creating `INTAKE` | deny (recyclers only) |

Mrudduni's review API calls the claim policies tomorrow. Write them today from this table so they are ready.

### 3.9 Collector sign-in

SOLUTION.md says "Phone OTP". Cognito SMS in India needs DLT registration, which will not finish in time. Options: email one-time code (Cognito passwordless) or username and password for demo accounts. On WhatsApp the sender number is the identity, so this only affects the PWA. **Ask Shaurya which one before building it.**

### 3.10 Privacy checks (judging criterion: nobody informal is exposed)

- No field anywhere for a handler's name, Aadhaar, GSTIN or exact address.
- Phone numbers only as HMACs with the KMS key. Erasure = delete the mapping item (crypto-shredding).
- Location only as a 5-character geohash, only with explicit consent, off by default.
- Raw audio deleted after 1 day by lifecycle; only the transcript is kept.
- Privacy notice in Hindi and English, linked from the confirm page and the chat start message. Mention the Bedrock processing region if it is outside `ap-south-1`.

---

## 4. Order of work today

Each block ends with a commit and push. Do P0 fully before P1.

| Block | Work | Done when |
|---|---|---|
| 1 | Access check, toolkit setup, branch, log file; start Meta onboarding (1.3) in the background | `log-shaurya.md` is on GitHub |
| 2 | `canonical.py`, `writer.py`, `verify_chain.py` + offline tests; `Core` stack | Tampering one field fails verification at exactly that seq (offline and on AWS) |
| 3 | Capture API: handovers, events (all types), batch, lineage, verify, presign; `seed_demo.py` | All CONTRACT §8 batches seeded on stage `shaurya`; `/batches/B-0046/lineage` returns the split |
| 4 | Extraction: Transcribe + Bedrock + schema; web chat endpoints | A recorded Hindi voice note becomes a correct draft card |
| 5 | PWA: chat capture, receipt + QR, confirm page, scan, batch view, intake form | Full flow on a phone: voice → ✅ → seller confirms on a second phone → scan → intake |
| 6 | Cedar policies + tests; Verified Permissions wired into the API | The deny tests pass, including through the API |
| 7 | WhatsApp via EUMS, if the number is linked; `wa.me` confirmation | Voice note on real WhatsApp → card → ✅ → receipt |
| 8 (P1) | Offline queue, in-app camera hashing, digest job + Object Lock + public verify page, AC flow | Airplane-mode event syncs exactly once |
| 9 (P2) | Confirmation anomaly checks (one device confirming for many handlers, confirmation seconds after creation), DLQs, alarms, X-Ray, cdk-nag clean | — |

**Never cut:** field confirmation statuses everywhere, the second product (phone) through the same flow as config only, handler privacy (3.10), the hash chain with KMS signatures.

**Cut in this order if short of time:** anomaly checks → nightly digest schedule (keep on-demand digest) → offline queue → in-app camera hashing → real WhatsApp (the web chat stays and looks the same).

Record short screen captures as features start working (a voice note becoming a card, the second phone confirming, the verify page failing after tamper). The video tomorrow must **show AWS being used**; a mention in the writeup does not count.

---

## 5. Your tests today

| Test | Assertion |
|---|---|
| Hash chain | change one stored field → `verify_chain` fails at exactly that seq |
| Gap | delete an event → gap detected |
| Concurrency | two writers appending to one batch at once → seqs 1..n with no duplicates or gaps |
| Signatures | a valid hash with a forged signature fails |
| Idempotency | the same WhatsApp message ID or `Idempotency-Key` twice → one event |
| Object Lock | deleting a digest object as admin → denied |
| Merkle | recompute a published root from raw events → matches |
| Cedar | every row of the table in 3.8 |
| API privacy | no response from any route contains a phone number, `phone_hmac` or handler name |
| Phone product | phone batch through the same flow; diff between battery and phone support is `materials.yaml` only |
| Extraction eval | `count` exact on at least 9 of 10 voice notes; prompt-injection text in a note changes nothing |
| Confirmation | buyer's API token cannot set `HANDLER` confirmation (403); token single use; expired token rejected |
| Untrained user (dry run) | one person not on the team records a handover in the PWA chat without help, under 60 s |

---

## 6. Hand-off state at the end of today

Push, then write a final log entry and tell Shaurya:

- What works on stage `shaurya`, with URLs for the capture API and PWA.
- Which tests pass.
- WhatsApp status (linked or not, and what is blocking).
- What is unfinished, in priority order.
- Every assumption you made that Mrudduni's side must match.

---

## 7. Tomorrow (11 October): integration with Mrudduni

Only things that need both people are left for tomorrow. Both agents follow this list in order. Shaurya and Mrudduni decide who drives each step.

1. Both branches pushed and green on their own. Open PRs `shaurya/chaintrack → main` and `mrudduni/claimguard → main`. Merge Shaurya's first (it creates the `prod` core resources others read), then Mrudduni's.
2. Deploy Shaurya's app to `prod`, then run `seed_demo.py --stage prod`.
3. Mrudduni deploys her app to `prod` with `-c ledgerStage=prod`; ClaimGuard now reads the live ledger.
4. Run the acceptance test (CONTRACT §8) against `prod`. It must match Mrudduni's offline result exactly. Any difference means one side diverged from `CONTRACT.md`; fix that side.
5. Review API gets the Cognito authorizer; claim reads go through your Verified Permissions policy store.
6. EventBridge rule: capture evidence bucket `ObjectCreated` → Mrudduni's evidence processor (Textract, pHash on intake weigh slips).
7. Dashboard lineage view and copilot point at your live API and table. Link from the dashboard's batch chips to your public receipt and verify pages.
8. Live end to end: voice note → handover → handler confirms on a second phone → aggregator scans QR → recycler intake with weigh slip → claim cites the batch → ClaimGuard runs → dashboard shows it.
9. Tamper demo on `prod`: `tamper_demo.py` → verify page fails at that seq → `--restore`.
10. Untrained-user test (SOLUTION §13.5): at least 3 people, at least 1 not comfortable in English.
11. Freeze the deploy. Record the 3-minute video, write the writeup, make the repo public, submit.

---

## 8. Hackathon rules that affect your work

Source: [Environmental Hacks rules](https://www.wemakedevs.org/aws/env/rules) and [event page](https://www.wemakedevs.org/aws/env). Track: **Waste and Energy**.

- Build window 8 to 11 October 2026. Work started before the opening does not count; history must match the dates.
- The project must use AWS **and the demo video must show it**. To be prize-eligible it must use at least one AWS open-source tool or be deployed on AWS. OpenAEye does both.
- Submission: a public repo, a YouTube video of **up to 3 minutes** (public or unlisted, check it opens signed out), and a short writeup on the problem, the build and where AWS fits. No live demo. Judges score only what is submitted.
- List the AI coding tools used in the writeup.
- Anything not written by the team needs a credit and a licence that allows use. Keep a running list in your log of every library, sample, icon or dataset you pull in, with its licence. The repo is Apache-2.0.
- Judging: idea and impact, built on AWS, design and usability, execution (working beats polished), demo video.
- The exact submission deadline time is not on the rules page. Ask Shaurya to confirm it with Mrudduni and write it at the top of your log.

### AWS open-source tools in your half (name them in the writeup and show them in the video)

| Tool | Where |
|---|---|
| Cedar (policy language, CLI) | `policies/`, enforced through Amazon Verified Permissions |
| AWS CDK + `cdk-nag` | `infra/chaintrack/` |
| Powertools for AWS Lambda (Python) | every Lambda, idempotency for WhatsApp retries |
| Amplify UI | PWA sign-in |
| `aws-samples` End User Messaging Social WhatsApp samples | starting point for the SNS → Lambda → reply wiring (search the org for "end user messaging social whatsapp"; credit what you reuse) |

AWS services in your half: End User Messaging Social, SNS, Lambda, API Gateway, Transcribe, Bedrock, DynamoDB, S3 (Object Lock), KMS (sign, HMAC), Cognito, Verified Permissions, EventBridge Scheduler, Amplify Hosting, CloudWatch, X-Ray, SSM.

---

## 9. AWS credits and cost

- The account is Mrudduni's. A new account gets $100 in credits at sign-up and up to $100 more for starter activities; Mrudduni handles those and the budget alarms.
- On the **Free plan** the account shuts down when credits run out. Report any cost surprise to Shaurya at once.
- Extra credits: the team leader requests **$25** through the organisers' form (one per team): https://forms.gle/b453U3c63mfBXHVr5
- Main cost drivers in your half: Transcribe minutes, Bedrock tokens, WhatsApp messages (Meta charges per message outside the free service window). Use a small model for extraction. Keep voice notes short in testing.
- Tag every resource `project=openaeye`, `owner=shaurya`. Delete experiments before the end of the day. Never delete anything on stage `mrudduni` or `prod`.

---

## 10. Questions to ask Shaurya before starting, if not answered yet

1. Has Mrudduni given repo access and an IAM user?
2. Is there a phone number for WhatsApp onboarding, and who holds it?
3. Email code or username and password for collector sign-in in the PWA?
4. What is the exact submission deadline time?
