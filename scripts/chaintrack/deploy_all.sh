#!/usr/bin/env bash
# One-shot deploy of ChainTrack to a stage, run from a normal terminal on your Mac.
#   bash scripts/chaintrack/deploy_all.sh shaurya
# Writes a log (no secrets) to ../deploy-<stage>.log next to the repo so Claude can read it.
set -uo pipefail
STAGE="${1:-shaurya}"; PROFILE="${AWS_PROFILE:-openaeye}"; REGION=ap-south-1
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="$ROOT/../deploy-$STAGE.log"
S="$(tr '[:lower:]' '[:upper:]' <<< "${STAGE:0:1}")${STAGE:1}"
: > "$LOG"
say()  { printf '\n=== %s ===\n' "$*" | tee -a "$LOG"; }
fail() { printf '\n!!! FAILED: %s\n' "$*" | tee -a "$LOG"; exit 1; }
run()  { "$@" 2>&1 | tee -a "$LOG"; return "${PIPESTATUS[0]}"; }
[ "$STAGE" = "mrudduni" ] && fail "never deploy to Mrudduni's stage"

say "1/9 tools"
for t in aws node npm uv python3 zip curl; do
  if command -v "$t" >/dev/null; then echo "ok  $t $($t --version 2>&1 | head -1)" | tee -a "$LOG"
  else echo "MISSING $t" | tee -a "$LOG"; MISSING=1; fi
done
[ -n "${MISSING:-}" ] && fail "install the missing tools (macOS: brew install awscli node uv) and re-run"
aws --version 2>&1 | grep -q 'aws-cli/2' || fail "AWS CLI v2 is required (brew install awscli)"

say "2/9 sign-in (profile $PROFILE)"
if ! aws sts get-caller-identity --profile "$PROFILE" >/dev/null 2>&1; then
  echo "Opening the browser for aws login…" | tee -a "$LOG"
  aws configure set region "$REGION" --profile "$PROFILE"
  aws login --profile "$PROFILE" || fail "aws login"
fi
ACCOUNT=$(aws sts get-caller-identity --profile "$PROFILE" --query Account --output text) || fail "sts"
echo "account $ACCOUNT  identity $(aws sts get-caller-identity --profile "$PROFILE" --query Arn --output text | sed 's/.*://')" | tee -a "$LOG"
# Short-lived credentials for CDK and Python, in this shell only (never written to disk).
eval "$(aws configure export-credentials --profile "$PROFILE" --format env)" || fail "export-credentials"
export AWS_REGION=$REGION AWS_DEFAULT_REGION=$REGION CDK_DEFAULT_ACCOUNT=$ACCOUNT CDK_DEFAULT_REGION=$REGION

say "3/9 can we use ap-south-1 (Mumbai)?"
run aws dynamodb list-tables --region $REGION --max-items 1 >/dev/null || fail "ap-south-1 is not usable from this account (new-experience project region?). Tell Claude."
echo "ap-south-1 OK" | tee -a "$LOG"

say "4/9 CDK bootstrap"
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region $REGION >/dev/null 2>&1; then
  (cd "$ROOT/infra/chaintrack" && npm ci --no-audit --no-fund >/dev/null && run npx cdk bootstrap "aws://$ACCOUNT/$REGION") || fail "bootstrap"
else echo "already bootstrapped" | tee -a "$LOG"; fi

say "5/9 build Lambda assets"
run bash "$ROOT/scripts/chaintrack/build_lambdas.sh" || fail "build_lambdas"
cd "$ROOT/infra/chaintrack" && npm ci --no-audit --no-fund >/dev/null

say "6/9 deploy Core + CaptureWeb"
run npx cdk deploy -c stage="$STAGE" "OAE-$S-Core" "OAE-$S-CaptureWeb" --require-approval never || fail "Core/CaptureWeb"
WEB=$(aws ssm get-parameter --name "/openaeye/$STAGE/capture/web-url" --query Parameter.Value --output text)
echo "web $WEB" | tee -a "$LOG"

say "7/9 deploy Capture (extraction model: ${MODEL_ID:-offline})"
run npx cdk deploy -c stage="$STAGE" -c webUrl="$WEB" -c webOrigins="$WEB,http://localhost:5173" \
  -c modelId="${MODEL_ID:-offline}" ${ALARM_EMAIL:+-c alarmEmail=$ALARM_EMAIL} "OAE-$S-Capture" --require-approval never || fail "Capture"
API=$(aws ssm get-parameter --name "/openaeye/$STAGE/capture/api-url" --query Parameter.Value --output text)
echo "api $API" | tee -a "$LOG"

say "8/9 seed demo data + demo users"
cd "$ROOT"
PYDEPS=(--with boto3 --with "cryptography>=42" --with pyyaml --with segno)
run uv run --python 3.12 "${PYDEPS[@]}" python scripts/chaintrack/seed_demo.py --stage "$STAGE" || fail "seed"
# Passwords go to your terminal and ~/.openaeye_demo_users_<stage>.txt only, never to the log.
uv run --python 3.12 --with boto3 python scripts/chaintrack/create_demo_users.py --stage "$STAGE" || fail "demo users"
echo "demo users created (passwords in ~/.openaeye_demo_users_$STAGE.txt)" >> "$LOG"

say "9/9 publish the PWA + smoke test"
run bash "$ROOT/scripts/chaintrack/deploy_web.sh" "$STAGE" || fail "deploy_web"
run curl -sS "${API%/}/verify/B-0042" | head -c 200; echo | tee -a "$LOG"
(cd "$ROOT/services/ledger" && run uv run --python 3.12 --with boto3 --with "cryptography>=42" python -m ledger.verify_chain --stage "$STAGE" --batch B-0046) || true

say "DONE"
echo "API  $API" | tee -a "$LOG"
echo "App  $WEB   (sign in as col-118, agg-01, rec-01 … passwords in ~/.openaeye_demo_users_$STAGE.txt)" | tee -a "$LOG"
echo "Verify page: $WEB/v/B-0042" | tee -a "$LOG"
