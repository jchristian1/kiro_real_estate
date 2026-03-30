#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Step 1: Validate required secrets
# ---------------------------------------------------------------------------
validate_secret() {
    local var_name="$1"
    local var_value="${!var_name:-}"

    if [[ -z "$var_value" ]]; then
        echo "ERROR: Required environment variable '$var_name' is not set." >&2
        echo "       Generate a secure value with: openssl rand -hex 32" >&2
        exit 1
    fi

    if [[ "${#var_value}" -lt 32 ]]; then
        echo "ERROR: Environment variable '$var_name' is too short (${#var_value} chars)." >&2
        echo "       It must be at least 32 characters long." >&2
        echo "       Generate a secure value with: openssl rand -hex 32" >&2
        exit 1
    fi
}

validate_secret "ENCRYPTION_KEY"
validate_secret "SECRET_KEY"

# ---------------------------------------------------------------------------
# Step 2: Run database migrations
# ---------------------------------------------------------------------------
echo "Running database migrations..."
if ! alembic upgrade head; then
    echo "ERROR: Database migration failed. See stack trace above." >&2
    exit 1
fi
echo "Migrations complete."

# ---------------------------------------------------------------------------
# Step 3: Start the application (exec replaces the shell process)
# ---------------------------------------------------------------------------
echo "Starting API server..."
exec uvicorn api.main:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --log-level "${LOG_LEVEL:-info}"
