#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="api-client-types"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

OPENAPI_FILE="${1:-/tmp/openapi.json}"

if [ ! -f "$OPENAPI_FILE" ]; then
  echo "Generating OpenAPI schema from app code ..."
  OPENAPI_FILE=$(mktemp)
  uv run python3 -c "
import json, sys
sys.path.insert(0, '$PROJECT_DIR')
from app.main import app
with open('$OPENAPI_FILE', 'w') as f:
    json.dump(app.openapi(), f)
"
fi

echo "Generating TypeScript types from $OPENAPI_FILE ..."
mkdir -p "$OUT_DIR"

npx --yes openapi-typescript@latest "$OPENAPI_FILE" \
  --output "$OUT_DIR/api.ts" \
  --prettier-config '{"printWidth": 100, "singleQuote": true}' 2>&1

echo "Done — types written to $OUT_DIR/api.ts"
echo "Copy these into your React Native / Next.js projects."
