# OpenAEye

India certifies electronics and battery recycling mainly on documents the recycler uploads about its own work. Tax officers, state boards and audit teams check those documents afterwards and have caught fakes, but nobody is required to witness the product changing hands before a certificate is issued.

OpenAEye adds two things:

- **ChainTrack** records the first handover. A collector types what they bought, in Hindi or English. The record is signed, the seller gets a receipt with a QR code, and each later handover (aggregator, recycler intake, split, merge) links to the same batch. Every field shows who stated it and who confirmed it.
- **ClaimGuard** checks a recycler's claim against arithmetic and evidence: tonnage above licensed capacity, output above input, power use too low for the tonnage, a photo whose light contradicts its timestamp, the same photo reused across batches, a batch cited by two claims. Every flag shows the observed value, the limit, the evidence used and the published source of the limit.

Deterministic rules decide every flag. Generative AI only reads free text and explains flags with citations. It can never raise or clear one.

WeMakeDevs × AWS Environmental Hacks, track: Waste and Energy. Full design: [`SOLUTION.md`](SOLUTION.md). Team contract: [`docs/team/CONTRACT.md`](docs/team/CONTRACT.md).

## Live demo (AWS, ap-southeast-2)

| What | URL |
|---|---|
| Capture app (collectors, aggregators, recyclers; mobile) | https://main.d2aof528zfa6ax.amplifyapp.com |
| Public verify page for batch B-0042 | https://main.d2aof528zfa6ax.amplifyapp.com/v/B-0042 |
| Review dashboard (auditors, producers; desktop) | https://main.dgf1yym1lb668.amplifyapp.com |
| Capture API | https://m5mvi60sjd.execute-api.ap-southeast-2.amazonaws.com |
| Review API | REVIEW_API |

All demo data is synthetic. Demo sign-ins are created by `scripts/chaintrack/create_demo_users.py`; their passwords are not in this repo.

## Principles

1. Consistency, not certification: a passing claim is "consistent with available data", never "verified".
2. Missing data is not fraud: every rule returns `PASS`, `FLAG`, `INSUFFICIENT_EVIDENCE` or `INCONCLUSIVE`.
3. No source, no rule: every limit comes from [`data/sources.yaml`](data/sources.yaml).
4. Three separate scores (physical consistency, traceability coverage, evidence quality), never blended.
5. One-sided is never shown as witnessed.
6. No informal-worker exposure: no names, IDs or addresses; phone numbers only as keyed hashes.
7. AI explains and never decides.
8. History is append-only: corrections are new events.

## AWS architecture

| Need | Service |
|---|---|
| APIs | API Gateway HTTP API + Lambda (Python 3.12, arm64, Powertools) |
| Event store | DynamoDB on-demand (`oae-<stage>-ledger`, `oae-<stage>-claims`) |
| Tamper evidence | Hash chain per batch, KMS asymmetric signatures, nightly Merkle digest to S3 Object Lock |
| Authorisation | Amazon Verified Permissions (Cedar), field-level |
| Users | Cognito (business users only; handlers never get accounts) |
| Claim checks | Step Functions workflow running rules R1–R9 |
| Evidence | S3 (SSE-KMS) → EventBridge → evidence processor (SHA-256, EXIF, dHash, light class) |
| Text extraction and copilot | Amazon Bedrock (Amazon Nova Lite), Bedrock Guardrails, Strands Agents |
| Satellite check (R9, optional) | Sentinel-2 from the Registry of Open Data on AWS |
| Hosting | Amplify Hosting |
| Infrastructure | Two AWS CDK apps (`infra/chaintrack`, `infra/claimguard`) with cdk-nag, linked only through SSM parameters |
| Operations | CloudWatch alarms, DLQs, X-Ray |

## What is deployed, and what is not

- **Region.** The project runs in `ap-southeast-2` (Sydney), account `206690614182`. The design targeted Mumbai, but this account's organisation policy denies `ap-south-1` (CONTRACT §10).
- **Voice notes (Amazon Transcribe): off in the deployment.** The account denies Transcribe, so the chat is typed only. The voice code path exists and is tested offline.
- **Weigh slip and bill reading (Amazon Textract): unavailable in the deployment** for the same reason. Uploaded documents are still hashed and stored; rules that need their fields return `INSUFFICIENT_EVIDENCE`.
- **WhatsApp (End User Messaging Social): not deployed.** Denied in the account. The capture app's WhatsApp-style chat runs the same pipeline. The WhatsApp code path is tested offline.
- **Bedrock:** on 10 Oct 2026 the account returned "account is being verified". Until it clears, extraction uses the deterministic reader (every field marked "please check") and the copilot gives its deterministic, cited explanation. No change is needed when it clears.
- **Not built:** hosting the copilot on Bedrock AgentCore Runtime (it runs inside the review Lambda); Automated Reasoning checks.
- **R9 satellite:** run on real Sentinel-2 imagery over Hapur; it can only pass or be inconclusive, never flag. Its 1.5× threshold is a demo value. Off by default.
- **R5 photo light classifier:** calibrated only on synthetic images.

## Run it locally (no AWS)

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e "services/ledger[dev]" -e services/claimguard pyyaml "aws-lambda-powertools>=3" aws-xray-sdk segno hypothesis pytest boto3 cedarpy
.venv/bin/python -m pytest -q tests/chaintrack tests/claimguard
```

- Capture app: `python scripts/chaintrack/local_api.py`, then `cd web-capture && npm ci && npm run dev`.
- Review dashboard: `python scripts/claimguard/local_review_api.py`, then `cd web-review && npm ci && npm run dev`.

## Deploy

See [`docs/DEPLOY.md`](docs/DEPLOY.md). ChainTrack in one command:

```bash
MODEL_ID=amazon.nova-lite-v1:0 OAE_VOICE=off bash scripts/chaintrack/deploy_all.sh prod
```

Then the ClaimGuard stacks, seeding and the dashboard, as in the runbook.

## Acceptance check (claims C-101 … C-108)

| Claim | Expected |
|---|---|
| C-101 | no flags, coverage 82% |
| C-102 | R1 HARD (CPCB erratum: 46,200 printed, 26,400 correct) |
| C-103 | R2b HARD |
| C-104 | R3 SOFT, next action "request DG logs" |
| C-105 | R5 HARD (photo at 20:22 IST in Hapur shows hard sun shadows) |
| C-105b | no flag (R5 inconclusive) |
| C-106 | R6 SOFT (same photo across three phone batches) |
| C-107 | R4 HARD (B-0042 also cited by C-101) |
| C-108 | no flags, coverage 0% (missing data is not fraud) |

## Repository layout

| Path | What |
|---|---|
| `infra/chaintrack/`, `services/{ingest,extract,ledger,capture_api}/`, `policies/`, `web-capture/` | ChainTrack |
| `infra/claimguard/`, `services/{claimguard,evidence,review_api,copilot}/`, `web-review/`, `data/` | ClaimGuard |
| `scripts/`, `tests/` | Build, seed and deploy scripts and tests for each side |

## AI coding tools used

Claude Code (Anthropic) was used to write and test code, infrastructure and documentation. Each person reviewed decisions in their own area. Work logs: [`docs/team/log-mrudduni.md`](docs/team/log-mrudduni.md), [`docs/team/log-shaurya.md`](docs/team/log-shaurya.md).

## Licence

Apache-2.0, see [`LICENSE`](LICENSE). Third-party libraries and their licences are listed in the work logs.
