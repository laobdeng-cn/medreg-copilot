#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -x "$ROOT_DIR/backend/.venv/bin/uvicorn" ]]; then
  echo "Run 'make bootstrap' first." >&2
  exit 1
fi

if [[ ! -x "$ROOT_DIR/backend/.venv/bin/alembic" ]]; then
  echo "Run 'make bootstrap' to install database dependencies." >&2
  exit 1
fi

docker compose -f "$ROOT_DIR/compose.yaml" up -d --wait postgres minio redis qdrant
(
  cd "$ROOT_DIR/backend"
  .venv/bin/alembic upgrade head
)

cleanup() {
  kill "${API_PID:-}" "${WORKER_PID:-}" "${BEAT_PID:-}" "${WEB_PID:-}" 2>/dev/null || true
  wait "${API_PID:-}" "${WORKER_PID:-}" "${BEAT_PID:-}" "${WEB_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd "$ROOT_DIR/backend"
  .venv/bin/uvicorn medreg.main:app --reload --host 127.0.0.1 --port 8200
) &
API_PID=$!

(
  cd "$ROOT_DIR/backend"
  .venv/bin/celery -A medreg.core.celery_app:celery_app worker \
    --loglevel=INFO --pool=solo
) &
WORKER_PID=$!

(
  cd "$ROOT_DIR/backend"
  .venv/bin/celery -A medreg.core.celery_app:celery_app beat \
    --loglevel=INFO --schedule /tmp/medreg-celerybeat-schedule
) &
BEAT_PID=$!

(
  cd "$ROOT_DIR/frontend"
  npm run dev -- --host 127.0.0.1 --port 5273
) &
WEB_PID=$!

while kill -0 "$API_PID" 2>/dev/null \
  && kill -0 "$WORKER_PID" 2>/dev/null \
  && kill -0 "$BEAT_PID" 2>/dev/null \
  && kill -0 "$WEB_PID" 2>/dev/null; do
  sleep 1
done
