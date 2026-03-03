#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting Gmail Lead Sync API..."
exec uvicorn api.main:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --log-level "${LOG_LEVEL:-info}"
