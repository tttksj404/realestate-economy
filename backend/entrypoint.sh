#!/bin/sh
set -eu

mkdir -p /app/logs /app/chroma_db /app/ml/models

# Auto-generate SECRET_KEY if not set (development convenience)
if [ -z "${SECRET_KEY:-}" ]; then
  export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
  echo "[entrypoint] Generated random SECRET_KEY (will change on restart)"
fi

# Auto-download models on first run (GPU container)
if [ "${AUTO_DOWNLOAD_MODELS:-false}" = "true" ]; then
  if [ ! -d "/app/ml/models/hf_cache/hub/models--${LLM_MODEL_PATH:-beomi/Llama-3-Open-Ko-8B}" ] 2>/dev/null; then
    echo "[entrypoint] Downloading models (first run)..."
    python scripts/download_model.py \
      --llm "${LLM_MODEL_PATH:-beomi/Llama-3-Open-Ko-8B}" \
      --embedding "${EMBEDDING_MODEL_NAME:-intfloat/multilingual-e5-large}" \
      || echo "[entrypoint] Model download warning (may already be cached)"
  else
    echo "[entrypoint] Models already cached"
  fi
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
