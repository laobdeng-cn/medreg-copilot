#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.production"
COMPOSE_FILE="$ROOT_DIR/compose.production.yaml"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing .env.production; run 'make prod-init' first." >&2
  exit 1
fi

if [[ ! -s "$ROOT_DIR/secrets/production/deepseek_api_key" ]]; then
  echo "DeepSeek secret is empty; refusing a production deployment without the configured model." >&2
  exit 1
fi

compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

"${compose[@]}" config --quiet
"${compose[@]}" build --pull
"${compose[@]}" up -d --wait
"$ROOT_DIR/scripts/production-smoke.sh"

echo "MedReg Copilot production stack is ready."
