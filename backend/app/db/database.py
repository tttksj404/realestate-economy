from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings

# 비동기 SQLAlchemy 엔진 생성 (asyncpg 드라이버)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    # 커넥션 풀 설정
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # 연결 유효성 사전 확인
    pool_recycle=3600,   # 1시간마다 커넥션 재활용
)

# 비동기 세션 팩토리
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 의존성 주입용 DB 세션 제공자

    사용법:
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
