#!/usr/bin/env bash
# Build web-capture against the stage's API and publish it to Amplify Hosting (manual deployment).
#   scripts/chaintrack/deploy_web.sh shaurya
set -euo pipefail
STAGE="${1:?stage}"; PROFILE="${AWS_PROFILE:-openaeye}"; REGION="${OAE_REGION:-ap-south-1}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
S="$(tr '[:lower:]' '[:upper:]' <<< "${STAGE:0:1}")${STAGE:1}"
aws_() { if [ -n "${AWS_ACCESS_KEY_ID:-}" ]; then aws --region "$REGION" "$@"; else aws --profile "$PROFILE" --region "$REGION" "$@"; fi; }
API_URL=$(aws_ ssm get-parameter --name "/openaeye/$STAGE/capture/api-url" --query Parameter.Value --output text)
POOL=$(aws_ ssm get-parameter --name "/openaeye/$STAGE/auth/user-pool-id" --query Parameter.Value --output text)
CLIENT=$(aws_ ssm get-parameter --name "/openaeye/$STAGE/auth/user-pool-client-id-capture" --query Parameter.Value --output text)
APP_ID=$(aws_ cloudformation describe-stacks --stack-name "OAE-$S-CaptureWeb" --query "Stacks[0].Outputs[?OutputKey=='AppId'].OutputValue" --output text)
cd "$ROOT/web-capture"
# Clean install for THIS machine: node_modules made on another OS lacks the native build binaries.
rm -rf node_modules && npm ci --no-audit --no-fund
VITE_API_URL="$API_URL" VITE_USER_POOL_ID="$POOL" VITE_USER_POOL_CLIENT_ID="$CLIENT" VITE_AWS_REGION="$REGION" VITE_DEV_AUTH=0 npm run build
node scripts/size.mjs
rm -f /tmp/oae-web.zip && (cd dist && zip -qr /tmp/oae-web.zip .)
read -r JOB URL < <(aws_ amplify create-deployment --app-id "$APP_ID" --branch-name main --query '[jobId,zipUploadUrl]' --output text)
curl -sS -T /tmp/oae-web.zip "$URL" >/dev/null
aws_ amplify start-deployment --app-id "$APP_ID" --branch-name main --job-id "$JOB" >/dev/null
echo "deploying job $JOB to https://main.$APP_ID.amplifyapp.com"
