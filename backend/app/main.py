import logging
import logging.config
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import router as v1_router
from app.config import settings
from app.db.database import engine
from app.db.models import Base


def _configure_logging() -> None:
    level = settings.LOG_LEVEL.upper()
    fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    if settings.is_production:
        fmt = '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"default": {"format": fmt, "datefmt": "%Y-%m-%dT%H:%M:%S%z"}},
            "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "default"}},
            "root": {"level": level, "handlers": ["console"]},
        }
    )


_configure_logging()
logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started_at = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "%s %s -> %s (%.2fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/health", "/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        queue = self.requests[client_ip]

        while queue and queue[0] <= now - self.window_seconds:
            queue.popleft()

        if len(queue) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": "요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
                    }
                },
            )

        queue.append(now)
        return await call_next(request)


_PUBLIC_PATHS = {"/health", "/", "/docs", "/openapi.json", "/redoc"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.API_KEY:
            return await call_next(request)
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if api_key != settings.API_KEY:
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "unauthorized", "message": "유효한 API 키가 필요합니다."}},
            )
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up 부동산 경제 분석 서비스...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized.")

    try:
        from app.db.vector_store import VectorStore

        vs = VectorStore()
        vs.init_collection()
        logger.info("ChromaDB vector store initialized.")
    except Exception as exc:
        logger.warning("ChromaDB initialization warning: %s", exc)

    yield

    logger.info("Shutting down...")
    await engine.dispose()


def create_app() -> FastAPI:
    enable_docs = not settings.is_production
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="부동산 시장 경제 상황 분석 및 RAG 기반 AI 채팅 서비스",
        docs_url="/docs" if enable_docs else None,
        redoc_url="/redoc" if enable_docs else None,
        openapi_url="/openapi.json" if enable_docs else None,
        lifespan=lifespan,
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(APIKeyMiddleware)
    app.add_middleware(RateLimitMiddleware, max_requests=120, window_seconds=60)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "http_error",
                    "message": exc.detail,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "요청 값이 올바르지 않습니다.",
                    "details": exc.errors(),
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled server error: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_server_error",
                    "message": "서버 내부 오류가 발생했습니다.",
                }
            },
        )

    app.include_router(v1_router, prefix="/api/v1")

    @app.get("/health", tags=["system"])
    async def health_check() -> JSONResponse:
        return JSONResponse(content={"status": "ok"})

    @app.get("/", tags=["system"])
    async def root() -> JSONResponse:
        return JSONResponse(
            content={
                "message": f"{settings.APP_NAME} API",
                "docs": "/docs",
                "version": settings.APP_VERSION,
            }
        )

    return app


app = create_app()
