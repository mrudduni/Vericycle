#!/usr/bin/env bash
# Build Lambda assets without Docker (CONTRACT §2): arm64 wheels via uv, plain directories CDK zips with Code.fromAsset.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/.build/claimguard"
rm -rf "$OUT" && mkdir -p "$OUT/deps" "$OUT/app/data/fixtures"

uv pip install --quiet --python-platform aarch64-manylinux2014 --python-version 3.12 --only-binary :all: \
  --target "$OUT/deps/python" "pyyaml>=6" "pillow>=10.4"

cp -r "$ROOT/services/claimguard/claimguard" "$OUT/app/"
cp -r "$ROOT/services/review_api/review" "$OUT/app/"
cp -r "$ROOT/services/evidence/evidence" "$OUT/app/"
cp "$ROOT/data/sources.yaml" "$OUT/app/data/"
cp "$ROOT/data/fixtures/ledger_events.json" "$OUT/app/data/fixtures/"
find "$OUT" -name '__pycache__' -type d -prune -exec rm -rf {} +
echo "built $OUT"
