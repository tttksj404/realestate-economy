# Python 3.11 slim 베이스 이미지
FROM python:3.11-slim

# 시스템 메타
LABEL maintainer="realestate-economy-service"
LABEL description="부동산 경제 분석 FastAPI 서비스"

# 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 시스템 패키지 설치 (asyncpg, lxml, bitsandbytes 빌드 의존성)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libxml2-dev \
    libxslt-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 먼저 복사 (레이어 캐싱 최적화)
COPY requirements.txt .

# Python 패키지 설치
# torch는 CPU 전용 버전 먼저 설치 (GPU 필요 시 별도 Dockerfile 작성)
RUN pip install --upgrade pip && \
    pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip install -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# ChromaDB 영구 저장 디렉토리
RUN mkdir -p /app/chroma_db

# 비루트 사용자 생성 (보안)
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app

USER appuser

# 포트 노출
EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 실행 명령
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--loop", "uvloop", \
     "--http", "httptools"]
