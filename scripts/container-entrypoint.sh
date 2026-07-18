#!/bin/sh
set -eu

if [ -z "${DEEPSEEK_API_KEY:-}" ] && [ -n "${DEEPSEEK_API_KEY_FILE:-}" ]; then
    if [ ! -r "$DEEPSEEK_API_KEY_FILE" ]; then
        echo "DeepSeek secret file is not readable." >&2
        exit 1
    fi
    DEEPSEEK_API_KEY="$(cat "$DEEPSEEK_API_KEY_FILE")"
    export DEEPSEEK_API_KEY
fi

exec "$@"
