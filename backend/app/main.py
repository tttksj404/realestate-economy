import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.v1.router import router as v1_router
from app.db.database import engine
from app.db.models import Base

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 리소스 초기화 및 정리"""
    # 시작 시: DB 테이블 생성, 벡터 스토어 초기화
    logger.info("Starting up 부동산 경제 분석 서비스...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized.")

    # ChromaDB 컬렉션 초기화
    try:
        from app.db.vector_store import VectorStore
        vs = VectorStore()
        vs.init_collection()
        logger.info("ChromaDB vector store initialized.")
    except Exception as e:
        logger.warning(f"ChromaDB initialization warning: {e}")

    yield

    # 종료 시: 연결 해제
    logger.info("Shutting down...")
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="부동산 시장 경제 상황 분석 및 RAG 기반 AI 채팅 서비스",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS 미들웨어
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API v1 라우터 등록
    app.include_router(v1_router, prefix="/api/v1")

    # 헬스체크 엔드포인트
    @app.get("/health", tags=["system"])
    async def health_check() -> JSONResponse:
        """서비스 상태 확인"""
        return JSONResponse(
            content={
                "status": "healthy",
                "service": settings.APP_NAME,
                "version": settings.APP_VERSION,
            }
        )

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
