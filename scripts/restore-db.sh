#!/usr/bin/env bash
# Restore a PostgreSQL backup produced by backup-db.sh.
# Usage: scripts/restore-db.sh backups/alarrab-YYYYmmdd-HHMMSS.sql.gz
set -euo pipefail
cd "$(dirname "$0")/.."

BACKUP_FILE="${1:?usage: restore-db.sh <backup-file.sql.gz>}"
[ -f "$BACKUP_FILE" ] || { echo "ERROR: file not found: $BACKUP_FILE" >&2; exit 1; }

echo "WARNING: this will overwrite the current database. Type 'restore' to continue:"
read -r CONFIRM
[ "$CONFIRM" = "restore" ] || { echo "aborted."; exit 1; }

gunzip -c "$BACKUP_FILE" | docker compose -f docker-compose.prod.yml --env-file .env exec -T db \
  sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'

echo "==> Restore complete from $BACKUP_FILE"
