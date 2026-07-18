#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -x "$ROOT_DIR/backend/.venv/bin/python" ]]; then
  echo "Run 'make bootstrap' first." >&2
  exit 1
fi

docker compose -f "$ROOT_DIR/compose.yaml" up -d --wait postgres minio redis qdrant neo4j
(
  cd "$ROOT_DIR/backend"
  .venv/bin/alembic upgrade head
)

PYTHONPATH="$ROOT_DIR/backend/src" \
  "$ROOT_DIR/backend/.venv/bin/python" "$ROOT_DIR/scripts/seed_demo.py"

exec "$ROOT_DIR/scripts/dev.sh"
