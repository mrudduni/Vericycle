# ChainTrack infrastructure (Shaurya)

CDK app with three stacks per stage, all in `ap-southeast-2`, tagged `project=openaeye`, `stage`, `owner=shaurya`,
checked by `cdk-nag` AwsSolutions (every acknowledgement carries a written reason in code).

| Stack | Contents |
|---|---|
| `OAE-<Stage>-Core` | KMS data key, ECDSA P-256 ledger signing key, HMAC-256 phone key; `oae-<stage>-ledger` table (CONTRACT §6, GSI2, PITR, TTL `expires_at`); capture evidence bucket (`audio/` expires after 1 day, EventBridge on); Object Lock digest bucket (compliance, 1 day); Cognito pool + groups + capture/review clients; Verified Permissions store loaded from `policies/`; SSM parameters (CONTRACT §2) |
| `OAE-<Stage>-CaptureWeb` | Amplify Hosting app for `web-capture/` (manual deploys) |
| `OAE-<Stage>-Capture` | HTTP API (Cognito JWT on business routes, public receipt/confirm/verify/digest routes, throttled, access-logged); Lambdas `capture-api`, `transcribe-done`, `ledger-digest`; Transcribe completion rule; nightly digest 00:15 IST; idempotency table; model ID in SSM. Optional WhatsApp topic + `whatsapp-ingest` when `-c waPhoneNumberId=...` |

## Deploy a stage (first time)

```bash
export AWS_PROFILE=openaeye                       # from `aws login`
aws sts get-caller-identity                       # must be Mrudduni's account
aws cloudformation describe-stacks --stack-name CDKToolkit --region ap-southeast-2 \
  || npx cdk bootstrap aws://<account>/ap-southeast-2

bash scripts/chaintrack/build_lambdas.sh           # arm64 deps + code, no Docker
cd infra/chaintrack && npm ci
npx cdk deploy -c stage=shaurya OAE-Shaurya-Core OAE-Shaurya-CaptureWeb
WEB=$(aws ssm get-parameter --name /openaeye/shaurya/capture/web-url --query Parameter.Value --output text)
npx cdk deploy -c stage=shaurya -c webUrl=$WEB -c webOrigins=$WEB,http://localhost:5173 \
  -c modelId=<model or profile id | offline> OAE-Shaurya-Capture
cd ../.. && python scripts/chaintrack/seed_demo.py --stage shaurya
python scripts/chaintrack/create_demo_users.py --stage shaurya   # usernames col-118, agg-01, rec-01…; passwords → ~/.openaeye_demo_users_shaurya.txt
bash scripts/chaintrack/deploy_web.sh shaurya
```

Smoke checks: `curl $API/verify/B-0042` → `ok: true, checked: 3`;
`python -m ledger.verify_chain --stage shaurya --batch B-0046` (from `services/ledger`);
tamper demo: `python scripts/chaintrack/tamper_demo.py --stage shaurya --batch B-0042 --seq 2`, then `--restore`;
digest on demand: `aws lambda invoke --function-name oae-shaurya-ledger-digest --payload '{"date":"2026-10-06"}' --cli-binary-format raw-in-base64-out /dev/stdout`.

## Choosing the model

```bash
aws bedrock list-inference-profiles --region ap-southeast-2 --query 'inferenceProfileSummaries[].inferenceProfileId'
aws bedrock list-foundation-models --region ap-southeast-2 --by-output-modality TEXT --query 'modelSummaries[].modelId'
python scripts/chaintrack/run_eval.py --model <id> --profile openaeye
```
Change it later without a deploy: `aws ssm put-parameter --name /openaeye/<stage>/extract/model-id --value <id> --overwrite`
(Lambdas cache it per cold start). The privacy page states the processing region.

## WhatsApp (after the number is linked in the EUMS console)

Redeploy Capture with `-c waPhoneNumberId=<phone-number-id ARN> -c waNumber=<digits>`, then set the
`WhatsAppTopicArn` output as the WABA event destination. Register each collector's number:
`register_collector_phone(repo, hmac(number), "COL-118")` (stores only the HMAC; erasure = delete `PHONE#<hmac>`).

## Never

Deploy to or delete anything on stage `mrudduni`; set Object Lock retention above 1 day without Shaurya's
approval (the app refuses unless `-c approvedLongRetention=true`); delete the ledger signing key (RETAIN).
