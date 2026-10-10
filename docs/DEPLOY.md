# Deploy runbook: OpenAEye MVP on AWS (ap-south-1)

Two CDK apps, one AWS account. ChainTrack (`infra/chaintrack`) owns capture, ledger, Cognito and Cedar.
ClaimGuard (`infra/claimguard`) owns claims, the review API and the dashboard. They share only SSM
parameters under `/openaeye/<stage>/` (CONTRACT §2). Per-app detail: `infra/chaintrack/README.md`.

Stages: `shaurya` and `mrudduni` for solo testing, `prod` for the demo. Never deploy to or delete another stage.

## 0. Before anything

1. **AWS account fully registered.** Test: `aws s3api list-buckets --profile openaeye` must not say `NotSignedUp`, and
   `aws lambda list-functions --region ap-south-1` must not say `SubscriptionRequiredException`.
   If it does, finish registration at https://portal.aws.amazon.com/billing/signup.
2. `aws login --profile openaeye` (browser). Sessions last 12 hours.
3. Budget alarm: AWS Billing → Budgets → alerts at $20, $50, $100.
4. Bedrock model: Amazon Nova Lite is available in `ap-south-1` (`amazon.nova-lite-v1:0`). Check access in the Bedrock
   console → Model access. Set it with `-c modelId=amazon.nova-lite-v1:0` on the Capture stack, then run
   `python scripts/chaintrack/run_eval.py --model amazon.nova-lite-v1:0 --profile openaeye`.
5. Bootstrap once: `npx cdk bootstrap aws://773870812969/ap-south-1` (skip if `CDKToolkit` exists).

## 1. Integrated demo stack (`prod`)

```bash
export AWS_PROFILE=openaeye
# ChainTrack first (it creates the table, Cognito pool and the Cedar store ClaimGuard reads)
bash scripts/chaintrack/build_lambdas.sh
cd infra/chaintrack && npm ci
npx cdk deploy -c stage=prod OAE-Prod-Core OAE-Prod-CaptureWeb
CAP=$(aws ssm get-parameter --name /openaeye/prod/capture/web-url --query Parameter.Value --output text)
# Review web hosting must exist before CORS origins can be set: deploy it from the claimguard app first (step below), then:
npx cdk deploy -c stage=prod -c webUrl=$CAP -c webOrigins=$CAP -c modelId=amazon.nova-lite-v1:0 OAE-Prod-Capture
cd ../.. && python scripts/chaintrack/seed_demo.py --stage prod
python scripts/chaintrack/create_demo_users.py --stage prod
bash scripts/chaintrack/deploy_web.sh prod

# ClaimGuard
bash scripts/claimguard/build_lambdas.sh
cd infra/claimguard && npm ci
npx cdk deploy -c stage=prod -c ledgerStage=prod OAE-Prod-ReviewWeb
REV=$(aws ssm get-parameter --name /openaeye/prod/review/web-url --query Parameter.Value --output text)
npx cdk deploy -c stage=prod -c ledgerStage=prod -c webOrigins=$REV OAE-Prod-Claims
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

## 2. WhatsApp (real number)

Needs a phone number that can receive an SMS or voice OTP and is **not** currently registered on the WhatsApp or
WhatsApp Business app (delete that account first if it is). Do not commit the number to the repo.

1. AWS console (region **Asia Pacific (Mumbai)**) → **End User Messaging Social** → **Link business account** →
   **Launch Facebook portal**. Sign in to Facebook, create or choose a Meta Business portfolio, create a WhatsApp Business
   Account, **add the phone number**, enter the OTP. Pick a display name (Meta reviews it; use "OpenAEye").
2. Back in the console, confirm the number shows **Active**. Get its identifiers:
   `aws socialmessaging list-linked-whatsapp-business-accounts --region ap-south-1`
   (copy the phone number ID, e.g. `phone-number-id-…`, and the full ARN).
3. Redeploy ChainTrack with WhatsApp resources:
   `npx cdk deploy -c stage=prod … -c waPhoneNumberId=<phone-number-id ARN> -c waNumber=<digits only> OAE-Prod-Capture`
4. In the EUMS console, open the WABA → **Event destination** → set it to the SNS topic in the stack output
   `WhatsAppTopicArn`, with **message and event logging** enabled.
5. Register each collector's number (stored only as an HMAC): `register_collector_phone(repo, hmac(number), "COL-118")`
   from `services/capture_api` (see `infra/chaintrack/README.md`).
6. Test: send a Hindi voice note from the registered collector's phone. Expect a card with ✅ / ✏️ buttons within seconds,
   then the receipt and two QR images after ✅. The seller confirms by tapping the `wa.me` link on their own phone.

Notes: replies inside 24 hours of the user's message need no template. An unverified Meta business starts with low daily
limits (fine for a demo). If linking stalls, the WhatsApp-style chat inside the PWA runs the same pipeline.

## 3. Cost control

Everything is on-demand. Delete experiment stages with `cdk destroy -c stage=<stage>` (never `prod` after the demo
without saving the evidence). Object Lock digest objects cannot be deleted before their 1-day retention ends.
