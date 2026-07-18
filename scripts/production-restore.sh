#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.production"
COMPOSE_FILE="$ROOT_DIR/compose.production.yaml"
HELPER_IMAGE="${BACKUP_HELPER_IMAGE:-alpine:3.21}"
BACKUP_INPUT="${1:-}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing .env.production; run 'make prod-init' first." >&2
  exit 1
fi

if [[ -z "$BACKUP_INPUT" || ! -d "$BACKUP_INPUT" ]]; then
  echo "Usage: MEDREG_CONFIRM_RESTORE=restore:<backup-name> $0 <backup-directory>" >&2
  exit 1
fi

BACKUP_DIR="$(cd "$BACKUP_INPUT" && pwd)"
BACKUP_NAME="$(basename "$BACKUP_DIR")"
EXPECTED_CONFIRMATION="restore:$BACKUP_NAME"
if [[ "${MEDREG_CONFIRM_RESTORE:-}" != "$EXPECTED_CONFIRMATION" ]]; then
  echo "Restore not confirmed. Set MEDREG_CONFIRM_RESTORE=$EXPECTED_CONFIRMATION." >&2
  exit 1
fi

volumes=(
  medreg-prod-postgres-data
  medreg-prod-redis-data
  medreg-prod-minio-data
  medreg-prod-qdrant-data
  medreg-prod-neo4j-data
)

for volume in "${volumes[@]}"; do
  if [[ ! -f "$BACKUP_DIR/$volume.tar.gz" ]]; then
    echo "Backup archive $volume.tar.gz is missing." >&2
    exit 1
  fi
  if ! docker volume inspect "$volume" >/dev/null 2>&1; then
    echo "Required target volume $volume does not exist." >&2
    exit 1
  fi
done

if [[ ! -f "$BACKUP_DIR/SHA256SUMS" ]]; then
  echo "Backup checksum manifest is missing." >&2
  exit 1
fi

(
  cd "$BACKUP_DIR"
  shasum -a 256 -c SHA256SUMS
)

compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
"${compose[@]}" config --quiet

restart_stack() {
  echo "Starting production services..."
  "${compose[@]}" up -d --wait >/dev/null || true
}
trap restart_stack EXIT

echo "Entering maintenance window for restore $BACKUP_NAME..."
"${compose[@]}" stop --timeout 60

for volume in "${volumes[@]}"; do
  docker run --rm \
    -v "$volume:/target" \
    -v "$BACKUP_DIR:/backup:ro" \
    "$HELPER_IMAGE" \
    sh -ceu \
    'rm -rf /target/* /target/.[!.]* /target/..?*; tar -xzf "/backup/$1.tar.gz" -C /target' \
    restore "$volume"
done

trap - EXIT
restart_stack
"$ROOT_DIR/scripts/production-smoke.sh"
echo "Restore completed from $BACKUP_DIR"
