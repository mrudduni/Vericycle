#!/usr/bin/env bash
# Build web-review against the stage's API and publish it to Amplify Hosting (manual deployment).
#   scripts/claimguard/deploy_web.sh mrudduni            # dev auth (picker), fixture-backed stage
#   scripts/claimguard/deploy_web.sh prod prod           # Cognito sign-in using ChainTrack stage "prod"
set -euo pipefail
STAGE="${1:?stage}"; AUTH_STAGE="${2:-}"; PROFILE="${AWS_PROFILE:-openaeye}"; REGION=ap-southeast-2
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
S="$(tr '[:lower:]' '[:upper:]' <<< "${STAGE:0:1}")${STAGE:1}"
aws_() { aws --profile "$PROFILE" --region "$REGION" "$@"; }
API_URL=$(aws_ ssm get-parameter --name "/openaeye/$STAGE/review/api-url" --query Parameter.Value --output text)
APP_ID=$(aws_ cloudformation describe-stacks --stack-name "OAE-$S-ReviewWeb" --query "Stacks[0].Outputs[?OutputKey=='AppId'].OutputValue" --output text)
cd "$ROOT/web-review"
if [ -n "$AUTH_STAGE" ]; then
  POOL=$(aws_ ssm get-parameter --name "/openaeye/$AUTH_STAGE/auth/user-pool-id" --query Parameter.Value --output text)
  CLIENT=$(aws_ ssm get-parameter --name "/openaeye/$AUTH_STAGE/auth/user-pool-client-id-review" --query Parameter.Value --output text)
  # Landing page: links to the capture PWA and runs live chain checks against the capture API (needs the review origin in its CORS list).
  CAP_WEB=$(aws_ ssm get-parameter --name "/openaeye/$AUTH_STAGE/capture/web-url" --query Parameter.Value --output text 2>/dev/null || true)
  CAP_API=$(aws_ ssm get-parameter --name "/openaeye/$AUTH_STAGE/capture/api-url" --query Parameter.Value --output text 2>/dev/null || true)
  VITE_API_URL="$API_URL" VITE_USER_POOL_ID="$POOL" VITE_USER_POOL_CLIENT_ID="$CLIENT" VITE_CAPTURE_WEB_URL="$CAP_WEB" VITE_CAPTURE_API_URL="$CAP_API" VITE_DEV_AUTH=0 npm run build
else
  VITE_API_URL="$API_URL" VITE_DEV_AUTH=1 npm run build
fi
rm -f /tmp/oae-review-web.zip && (cd dist && zip -qr /tmp/oae-review-web.zip .)
read -r JOB URL < <(aws_ amplify create-deployment --app-id "$APP_ID" --branch-name main --query '[jobId,zipUploadUrl]' --output text)
curl -sS -T /tmp/oae-review-web.zip "$URL" >/dev/null
aws_ amplify start-deployment --app-id "$APP_ID" --branch-name main --job-id "$JOB" >/dev/null
echo "deploying job $JOB to https://main.$APP_ID.amplifyapp.com"
