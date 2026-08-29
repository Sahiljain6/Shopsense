#!/bin/sh
set -e

echo "[STARTUP] Running database migrations (alembic upgrade head)..."
if ! alembic upgrade head; then
    echo "[CRITICAL] Alembic migration failed! Exiting to prevent running on invalid schema." >&2
    exit 1
fi

PORT=""
echo "[STARTUP] Migrations complete. Launching ShopSense API on port ${PORT}..."
exec uvicorn app.main:app --host 0.0.0.0 --port ""
