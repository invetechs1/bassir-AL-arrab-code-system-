#!/usr/bin/env bash
# Dump the production PostgreSQL database to ./backups/ (gzip, timestamped).
set -euo pipefail
cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-backups}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/alarrab-$STAMP.sql.gz"

docker compose -f docker-compose.prod.yml --env-file .env exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$OUT"

echo "==> Backup written: $OUT"

# Keep the most recent 14 backups.
ls -1t "$BACKUP_DIR"/alarrab-*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm --
