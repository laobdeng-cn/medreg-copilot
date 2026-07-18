#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.production"
COMPOSE_FILE="$ROOT_DIR/compose.production.yaml"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="${MEDREG_BACKUP_DIR:-$ROOT_DIR/backups/$STAMP}"
HELPER_IMAGE="${BACKUP_HELPER_IMAGE:-alpine:3.21}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing .env.production; run 'make prod-init' first." >&2
  exit 1
fi

compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
volumes=(
  medreg-prod-postgres-data
  medreg-prod-redis-data
  medreg-prod-minio-data
  medreg-prod-qdrant-data
  medreg-prod-neo4j-data
)

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

restart_stack() {
  echo "Restarting production services..."
  "${compose[@]}" up -d --wait >/dev/null || true
}
trap restart_stack EXIT

echo "Entering maintenance window for a consistent multi-store backup..."
"${compose[@]}" stop --timeout 60

for volume in "${volumes[@]}"; do
  if ! docker volume inspect "$volume" >/dev/null 2>&1; then
    echo "Required volume $volume does not exist." >&2
    exit 1
  fi
  docker run --rm \
    -v "$volume:/source:ro" \
    -v "$BACKUP_DIR:/backup" \
    "$HELPER_IMAGE" \
    sh -c "cd /source && tar -czf /backup/$volume.tar.gz ."
done

(
  cd "$BACKUP_DIR"
  shasum -a 256 ./*.tar.gz >SHA256SUMS
)
"${compose[@]}" images --format json >"$BACKUP_DIR/images.json"
chmod 600 "$BACKUP_DIR"/*

trap - EXIT
restart_stack
echo "Backup completed: $BACKUP_DIR"
