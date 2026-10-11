# Deploy runbook: OpenAEye MVP on AWS (ap-southeast-2)

Two CDK apps, one AWS account. ChainTrack (`infra/chaintrack`) owns capture, ledger, Cognito and Cedar.
ClaimGuard (`infra/claimguard`) owns claims, the review API and the dashboard. They share only SSM
parameters under `/openaeye/<stage>/` (CONTRACT §2). Per-app detail: `infra/chaintrack/README.md`.

Stages: `shaurya` and `mrudduni` for solo testing, `prod` for the demo. Never deploy to or delete another stage.

## 0. Before anything

1. **Account and region.** Account `206690614182`, region `ap-southeast-2` (Sydney), profile `openaeye` (CONTRACT §2, §10).
   The account's organisation policy denies `ap-south-1`, Amazon Transcribe, Amazon Textract and End User Messaging
   Social, so `prod` is deployed with voice off and without WhatsApp. Bedrock returned "account is being verified" on
   10 Oct; extraction and the copilot fall back to their deterministic paths until it clears.
2. `aws login --profile openaeye --region ap-southeast-2` (browser). Sessions last 12 hours.
3. Budget alarm: AWS Billing → Budgets → alerts at $20, $50, $100.
4. Bedrock model: Amazon Nova Lite is available in `ap-southeast-2` (`amazon.nova-lite-v1:0`, or the
   `apac.amazon.nova-lite-v1:0` profile). Test with
   `aws bedrock-runtime converse --model-id amazon.nova-lite-v1:0 --messages '[{"role":"user","content":[{"text":"ok"}]}]' --profile openaeye`. Set it with `-c modelId=amazon.nova-lite-v1:0` on the Capture stack, then run
   `python scripts/chaintrack/run_eval.py --model amazon.nova-lite-v1:0 --profile openaeye`.
5. Bootstrap once: `npx cdk bootstrap aws://206690614182/ap-southeast-2` (done; `CDKToolkit` exists).

## 1. Integrated demo stack (`prod`)

ChainTrack in one command (bootstrap check, build, Core, CaptureWeb, Capture, seed, demo users, PWA, smoke test):

```bash
MODEL_ID=amazon.nova-lite-v1:0 OAE_VOICE=off bash scripts/chaintrack/deploy_all.sh prod
```

Or step by step:

```bash
export AWS_PROFILE=openaeye AWS_REGION=ap-southeast-2
# ChainTrack first (it creates the table, Cognito pool and the Cedar store ClaimGuard reads)
bash scripts/chaintrack/build_lambdas.sh
cd infra/chaintrack && npm ci
npx cdk deploy -c stage=prod OAE-Prod-Core OAE-Prod-CaptureWeb
CAP=$(aws ssm get-parameter --name /openaeye/prod/capture/web-url --query Parameter.Value --output text)
# Review web hosting must exist before CORS origins can be set: deploy it from the claimguard app first (step below), then:
npx cdk deploy -c stage=prod -c webUrl=$CAP -c webOrigins=$CAP,$REV -c modelId=amazon.nova-lite-v1:0 -c voice=off OAE-Prod-Capture
cd ../.. && python scripts/chaintrack/seed_demo.py --stage prod
python scripts/chaintrack/create_demo_users.py --stage prod
OAE_VOICE=off bash scripts/chaintrack/deploy_web.sh prod

# ClaimGuard
COPILOT=1 bash scripts/claimguard/build_lambdas.sh   # COPILOT=1 adds the Strands agent layer; omit for deterministic explanations only
cd infra/claimguard && npm ci
npx cdk deploy -c stage=prod -c ledgerStage=prod OAE-Prod-ReviewWeb
REV=$(aws ssm get-parameter --name /openaeye/prod/review/web-url --query Parameter.Value --output text)
npx cdk deploy -c stage=prod -c ledgerStage=prod -c webOrigins=$REV -c copilotModel=amazon.nova-lite-v1:0 OAE-Prod-Claims
cd ../.. && python scripts/claimguard/seed_claims.py --stage prod --ledger-stage prod
bash scripts/claimguard/deploy_web.sh prod prod
```

The review client in the Cognito pool (`user-pool-client-id-review`) and its groups come from ChainTrack's Core stack, so
`create_demo_users.py` users (auditor, recycler, producer) sign in to the dashboard too. If the auditor user does not exist
there yet, create one in the `AUDITOR` group with `custom:party_id = AUD-01`.

Acceptance check on `prod`: `python scripts/claimguard/seed_claims.py --stage prod --ledger-stage prod` prints, per claim,
the flags below. Any difference from the offline run means one side diverged from `docs/team/CONTRACT.md`.

| Claim | Expected |
|---|---|
| C-101 | no flags, coverage 82% |
| C-102 | R1 HARD |
| C-103 | R2b HARD |
| C-104 | R3 SOFT |
| C-105 | R5 HARD |
| C-105b | no flag (R5 inconclusive) |
| C-106 | R6 SOFT |
| C-107 | R4 HARD |
| C-108 | no flags, coverage 0% |

Copilot: `POST /claims/{id}/copilot` always returns a deterministic, cited explanation of the rule results. With
`-c copilotModel=...` it also asks a Strands agent on Bedrock (read-only tools, a Guardrail denying fraud verdicts about
named parties) and keeps the answer only if every sentence cites a real rule or source id. It runs inside the review
Lambda, not on AgentCore Runtime.

Evidence: upload photos, weigh slips, invoices and power bills to `evidence/<claim_id or batch_id>/<PHOTO|WEIGH_SLIP|INVOICE|POWER_BILL>/<file>`
in the claim-evidence bucket (or the capture bucket); the processor extracts EXIF, hashes, light class and Textract fields.
`python scripts/claimguard/make_sample_photos.py` renders sample photos.

## 2. WhatsApp (Meta Cloud API)

Account 206690614182 cannot use AWS End User Messaging Social, so WhatsApp goes straight to Meta's
WhatsApp Cloud API: Meta calls `GET/POST /whatsapp/webhook` on the capture API, and replies go out through
the Graph API. The chat logic is the same as the EUMS path (`ingest/whatsapp.py`); only the transport differs
(`ingest/cloud.py`). Voice notes get a "please type" reply while voice is off.

1. **Meta app (a person does this).** developers.facebook.com → My Apps → Create app → add the **WhatsApp**
   product. On **WhatsApp → API Setup** note the **test phone number**, its **Phone number ID**, and add up to five
   recipient numbers (the collector's and the seller's phones) in the "To" list.
2. **Deploy** with the phone number ID (not secret) and the display number (digits only):
   ```bash
   cd infra/chaintrack && npx cdk deploy -c stage=prod -c region=ap-southeast-2 -c webUrl=$CAP -c webOrigins=$CAP,$REV \
     -c modelId=amazon.nova-lite-v1:0 -c voice=off -c waMode=cloud -c waPhoneNumberId=<id> -c waNumber=<digits> OAE-Prod-Capture
   ```
   Outputs: `WhatsAppWebhookUrl` and `WhatsAppSecretName` (`oae-prod-whatsapp-cloud`).
3. **Secrets (a person does this; never commit or paste them in chat).** AWS console → Secrets Manager →
   `oae-prod-whatsapp-cloud` → Retrieve → Edit: set `access_token` (API Setup) and `app_secret`
   (App settings → Basic). Copy the generated `verify_token`.
4. **Webhook.** Meta app → WhatsApp → Configuration → Edit: Callback URL = `WhatsAppWebhookUrl`, Verify token =
   `verify_token` → Verify and save. Under Webhook fields, **subscribe to `messages`**.
5. **Register the collector's phone** (number typed at a hidden prompt, stored only as an HMAC):
   `AWS_PROFILE=openaeye python scripts/chaintrack/register_phone.py --stage prod --party COL-118`
6. **Test.** From that phone, message the test number: "4 e-rickshaw batteries from a driver, about 120 kg".
   Expect a read-back card with ✅ / ✏️ buttons, then the receipt link and two QR images after ✅.

Notes: the API Setup token expires after 24 hours; for the demo, create a System User token in Meta Business
Settings (permissions `whatsapp_business_messaging`, `whatsapp_business_management`) and replace `access_token`.
The test number can only message the numbers on its "To" list. Replies within 24 hours of a user's message need no template.

## 3. Cost control

Everything is on-demand. Delete experiment stages with `cdk destroy -c stage=<stage>` (never `prod` after the demo
without saving the evidence). Object Lock digest objects cannot be deleted before their 1-day retention ends.
