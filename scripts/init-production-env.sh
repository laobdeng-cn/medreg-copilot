#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.production"
SECRET_DIR="$ROOT_DIR/secrets/production"
DEEPSEEK_SECRET="$SECRET_DIR/deepseek_api_key"

if [[ -e "$ENV_FILE" && "${1:-}" != "--force" ]]; then
  echo ".env.production already exists; use --force to rotate all generated credentials." >&2
  exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "OpenSSL is required to generate production credentials." >&2
  exit 1
fi

umask 077
mkdir -p "$SECRET_DIR"

postgres_password="$(openssl rand -hex 24)"
redis_password="$(openssl rand -hex 24)"
minio_password="$(openssl rand -hex 24)"
neo4j_password="$(openssl rand -hex 24)"
qdrant_api_key="$(openssl rand -hex 32)"

cat >"$ENV_FILE" <<EOF
MEDREG_IMAGE_TAG=local
MEDREG_HTTP_BIND=127.0.0.1
MEDREG_HTTP_PORT=8080
WEB_CONCURRENCY=2
CELERY_CONCURRENCY=2

APP_ALLOWED_HOSTS=["localhost","127.0.0.1"]
APP_CORS_ORIGINS=[]

POSTGRES_DB=medreg
POSTGRES_USER=medreg
POSTGRES_PASSWORD=$postgres_password
REDIS_PASSWORD=$redis_password
MINIO_ROOT_USER=medreg
MINIO_ROOT_PASSWORD=$minio_password
MINIO_BUCKET=medreg-documents
NEO4J_PASSWORD=$neo4j_password
QDRANT_API_KEY=$qdrant_api_key
QDRANT_COLLECTION=medreg_legal_chunks_v1

DEEPSEEK_API_KEY_FILE=./secrets/production/deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_TIMEOUT_SECONDS=45
EOF

deepseek_key=""
if [[ -f "$ROOT_DIR/.env" ]]; then
  deepseek_key="$(awk -F= '/^[[:space:]]*DEEPSEEK_API_KEY[[:space:]]*=/{sub(/^[^=]*=/, ""); print; exit}' "$ROOT_DIR/.env")"
  deepseek_key="${deepseek_key%$'\r'}"
  if [[ "$deepseek_key" == \"*\" && "$deepseek_key" == *\" ]]; then
    deepseek_key="${deepseek_key:1:${#deepseek_key}-2}"
  elif [[ "$deepseek_key" == \'*\' && "$deepseek_key" == *\' ]]; then
    deepseek_key="${deepseek_key:1:${#deepseek_key}-2}"
  fi
fi
printf '%s' "$deepseek_key" >"$DEEPSEEK_SECRET"
chmod 600 "$ENV_FILE" "$DEEPSEEK_SECRET"

echo "Production environment initialized."
if [[ -n "$deepseek_key" ]]; then
  echo "DeepSeek secret imported from the local runtime configuration."
else
  echo "DeepSeek secret is empty; fill secrets/production/deepseek_api_key before deployment."
fi
echo "Review APP_ALLOWED_HOSTS and MEDREG_HTTP_BIND before exposing the service."
