#!/usr/bin/env bash
# Deploy/update the production stack on an Ubuntu VPS.
# Prerequisites: docker + docker compose plugin, a filled-in .env file.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example to .env and fill in real values." >&2
  exit 1
fi

if grep -q "CHANGE_ME" .env; then
  echo "ERROR: .env still contains CHANGE_ME placeholders. Refusing to deploy." >&2
  exit 1
fi

echo "==> Pulling latest images and building..."
docker compose -f docker-compose.prod.yml --env-file .env build --pull

echo "==> Starting stack..."
docker compose -f docker-compose.prod.yml --env-file .env up -d --remove-orphans

echo "==> Waiting for API health..."
for i in $(seq 1 30); do
  if docker compose -f docker-compose.prod.yml --env-file .env exec -T api \
    python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/v1/health', timeout=3).status==200 else 1)" 2>/dev/null; then
    echo "==> API healthy."
    exit 0
  fi
  sleep 2
done

echo "ERROR: API did not become healthy in time. Check: docker compose -f docker-compose.prod.yml logs api" >&2
exit 1
