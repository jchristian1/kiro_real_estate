#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Worker entrypoint — watcher runtime only.
# Migrations and seed data are the API container's responsibility.
# This container waits briefly for the DB to be ready, then starts watchers.
# ---------------------------------------------------------------------------

validate_secret() {
    local var_name="$1"
    local var_value="${!var_name:-}"
    if [[ -z "$var_value" ]]; then
        echo "ERROR: Required environment variable '$var_name' is not set." >&2
        exit 1
    fi
    if [[ "${#var_value}" -lt 32 ]]; then
        echo "ERROR: '$var_name' is too short (${#var_value} chars, need >=32)." >&2
        exit 1
    fi
}

validate_secret "ENCRYPTION_KEY"
validate_secret "SECRET_KEY"

echo "Starting worker (watcher runtime)..."
exec python -m worker.main
