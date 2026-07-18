#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_PYTHON="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"

is_supported_python() {
  "$1" -c 'import sys; raise SystemExit(not ((3, 12) <= sys.version_info[:2] < (3, 14)))' \
    >/dev/null 2>&1
}

find_python() {
  local candidate
  local candidates=(
    "${PYTHON_BIN:-}"
    "python3.13"
    "python3.12"
    "$CODEX_PYTHON"
    "python3"
  )

  for candidate in "${candidates[@]}"; do
    [[ -n "$candidate" ]] || continue
    if command -v "$candidate" >/dev/null 2>&1 && is_supported_python "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

if ! PYTHON_BIN="$(find_python)"; then
  echo "Python 3.12 or 3.13 is required." >&2
  exit 1
fi

if [[ -x "$ROOT_DIR/backend/.venv/bin/python" ]] && \
  ! is_supported_python "$ROOT_DIR/backend/.venv/bin/python"; then
  "$PYTHON_BIN" -m venv --clear "$ROOT_DIR/backend/.venv"
elif [[ ! -x "$ROOT_DIR/backend/.venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$ROOT_DIR/backend/.venv"
fi

echo "Using $("$ROOT_DIR/backend/.venv/bin/python" --version 2>&1)."
"$ROOT_DIR/backend/.venv/bin/python" -m pip install -e "$ROOT_DIR/backend[dev]"
npm --prefix "$ROOT_DIR/frontend" install

echo "MedReg Copilot dependencies are ready."
