#!/bin/sh
set -eu

mkdir -p /app/logs /app/chroma_db /app/ml/models

# Auto-generate SECRET_KEY if not set (development convenience)
if [ -z "${SECRET_KEY:-}" ]; then
  export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
  echo "[entrypoint] Generated random SECRET_KEY (will change on restart)"
fi

if [ "${ENABLE_SCHEDULER:-true}" = "true" ]; then
  echo "[entrypoint] Starting scheduler in background"
  python scripts/scheduler_runner.py >> /app/logs/scheduler.log 2>&1 &
fi

echo "[entrypoint] Running alembic migrations"
alembic upgrade head

WORKERS="${WEB_CONCURRENCY:-1}"
echo "[entrypoint] Starting FastAPI server (workers=${WORKERS})"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WORKERS}" --loop uvloop --http httptools
