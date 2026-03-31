#!/bin/sh
set -eu

mkdir -p /app/logs /app/chroma_db /app/ml/models

if [ "${ENABLE_SCHEDULER:-true}" = "true" ]; then
  echo "[entrypoint] Starting scheduler in background"
  python scripts/scheduler_runner.py >> /app/logs/scheduler.log 2>&1 &
fi

echo "[entrypoint] Running alembic migrations"
alembic upgrade head

echo "[entrypoint] Starting FastAPI server"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --loop uvloop --http httptools
