#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${MEDREG_PRODUCTION_ENV:-$ROOT_DIR/.env.production}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE; run 'make prod-init' first." >&2
  exit 1
fi

http_port="$(awk -F= '/^MEDREG_HTTP_PORT=/{print $2; exit}' "$ENV_FILE")"
http_port="${http_port:-8080}"
base_url="${MEDREG_BASE_URL:-http://127.0.0.1:$http_port}"
response_file="$(mktemp)"
headers_file="$(mktemp)"
trap 'rm -f "$response_file" "$headers_file"' EXIT

probe_json() {
  local label="$1"
  local path="$2"
  curl --fail --silent --show-error --retry 8 --retry-all-errors \
    --retry-delay 2 --max-time 20 "$base_url$path" >"$response_file"
  if ! grep -q '"status"' "$response_file"; then
    echo "$label returned an unexpected response." >&2
    return 1
  fi
  printf 'OK      %s\n' "$label"
}

curl --fail --silent --show-error --retry 8 --retry-all-errors \
  --retry-delay 2 --max-time 20 -D "$headers_file" -o "$response_file" "$base_url/"
grep -qi '<div id="root"></div>' "$response_file"
grep -qi '^X-Content-Type-Options: nosniff' "$headers_file"
printf 'OK      Web entrypoint and security headers\n'

probe_json "API liveness" "/api/v1/health"
probe_json "Dependency readiness" "/api/v1/ready"

curl --fail --silent --show-error --max-time 20 \
  "$base_url/api/v1/agent/runtime" >"$response_file"
grep -q '"workflow_version"' "$response_file"
printf 'OK      Agent runtime contract\n'

printf 'Production smoke test passed at %s.\n' "$base_url"
