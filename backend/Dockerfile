FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip wheel --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim AS runtime

LABEL maintainer="realestate-economy-service"
LABEL description="FastAPI backend for realestate-economy"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/home/appuser/.local/bin:${PATH}"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    libxml2 \
    libxslt1.1 \
    tzdata \
    && rm -rf /var/lib/apt/lists/* && \
    addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser

COPY requirements.txt .
COPY --from=builder /wheels /wheels
RUN pip install --upgrade pip && \
    pip install --no-index --find-links /wheels -r requirements.txt && \
    rm -rf /wheels

COPY . .
RUN mkdir -p /app/chroma_db /app/logs /app/ml/models && \
    chmod +x /app/entrypoint.sh && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
