#!/usr/bin/env bash
set -euo pipefail
BASE="${1:-http://127.0.0.1:8080}"
curl -fsS "${BASE}/healthz" >/dev/null
curl -fsS "${BASE}/readyz" >/dev/null
curl -fsS "${BASE}/metrics" | head -n 5 >/dev/null
curl -fsS -X POST "${BASE}/predict" -H "Content-Type: application/json" \
  -d '{"text":"production outage sev1"}' | jq -e '.label' >/dev/null
echo "smoke OK"
