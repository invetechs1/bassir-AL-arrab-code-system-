#!/usr/bin/env bash
# Simple external health probe; suitable for cron. Exits non-zero on failure.
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"

STATUS=$(curl -fsS -o /dev/null -w "%{http_code}" "$BASE_URL/v1/health" || echo "000")
if [ "$STATUS" != "200" ]; then
  echo "UNHEALTHY: $BASE_URL/v1/health returned $STATUS" >&2
  exit 1
fi
echo "OK: $BASE_URL/v1/health -> 200"
