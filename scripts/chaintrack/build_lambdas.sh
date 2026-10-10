#!/usr/bin/env bash
# Build Lambda assets without Docker (CONTRACT §2): arm64 wheels via uv, then plain directories
# that CDK zips with Code.fromAsset. Powertools comes from the public layer, not from here.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/.build/chaintrack"
rm -rf "$OUT" && mkdir -p "$OUT/deps" "$OUT/app"

uv pip install --quiet --python-platform aarch64-manylinux2014 --python-version 3.12 --only-binary :all: \
  --target "$OUT/deps/python" "cryptography>=42" "pyyaml>=6"

# One code asset shared by every ChainTrack function (handlers pick their module).
cp -r "$ROOT/services/ledger/ledger" "$OUT/app/"
cp -r "$ROOT/services/capture_api/capture" "$OUT/app/"
cp "$ROOT/services/capture_api/materials.yaml" "$OUT/app/"
cp -r "$ROOT/services/extract/extract" "$OUT/app/"
mkdir -p "$OUT/app/policies" && cp "$ROOT"/policies/*.cedar "$ROOT/policies/schema.cedarschema.json" "$OUT/app/policies/"
find "$OUT" -name '__pycache__' -type d -prune -exec rm -rf {} +
echo "built $OUT (deps layer: $OUT/deps, code: $OUT/app)"
