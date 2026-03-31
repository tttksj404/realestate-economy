"""
Alembic 환경 설정 — 비동기 PostgreSQL 지원

asyncpg 드라이버를 사용하는 비동기 SQLAlchemy 환경에서
autogenerate 마이그레이션이 동작하도록 구성합니다.

지원 방식:
- online migration : 실제 DB에 연결하여 마이그레이션 실행 (asyncio 모드)
- offline migration: SQL 스크립트만 생성 (DB 연결 불필요)
"""

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ---------------------------------------------------------------------------
# 프로젝트 루트(backend/)를 sys.path에 추가
# alembic 명령어는 backend/ 디렉토리에서 실행하는 것을 전제로 합니다.
# ---------------------------------------------------------------------------
_ALEMBIC_DIR = Path(__file__).resolve().parent      # alembic/
_BACKEND_DIR = _ALEMBIC_DIR.parent                  # backend/
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ---------------------------------------------------------------------------
# 앱 설정 및 모델 임포트
# ---------------------------------------------------------------------------
from app.config import settings  # noqa: E402 — sys.path 추가 후 임포트
from app.db.models import Base   # noqa: E402 — 모든 모델이 Base에 등록됨

# alembic.ini의 로깅 설정 적용
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate 비교 대상 메타데이터
# app.db.models의 모든 테이블이 Base.metadata에 등록되어 있어야 합니다.
target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# DB URL 주입
# ---------------------------------------------------------------------------
# alembic.ini의 sqlalchemy.url 대신 app.config.settings에서 자동 로드합니다.
# asyncpg URL을 synchronous 방식(offline)에서도 활용하기 위해
# psycopg2 호환 URL로 변환하는 헬퍼를 제공합니다.

def get_async_url() -> str:
    """비동기 DB URL (asyncpg) 반환"""
    return settings.DATABASE_URL


def get_sync_url() -> str:
    """
    동기 DB URL 반환 (offline 마이그레이션용)

    postgresql+asyncpg://... → postgresql+psycopg2://... 변환
    psycopg2가 없는 환경에서는 asyncpg URL 그대로 반환합니다.
    """
    url = settings.DATABASE_URL
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


# ---------------------------------------------------------------------------
# Offline 마이그레이션 (SQL 스크립트 출력)
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """
    'offline' 모드: DB에 연결하지 않고 SQL 스크립트만 생성합니다.

    alembic upgrade head --sql 명령과 함께 사용합니다.
    """
    url = get_sync_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # 컬럼 타입 비교 활성화 (autogenerate에서 타입 변경 감지)
        compare_type=True,
        # 서버 기본값 비교 활성화
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online 마이그레이션 (비동기)
# ---------------------------------------------------------------------------

def do_run_migrations(connection: Connection) -> None:
    """동기 컨텍스트에서 실제 마이그레이션 실행"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # 컬럼 타입 변경 감지
        compare_type=True,
        # 서버 기본값 변경 감지
        compare_server_default=True,
        # 네이밍 컨벤션 적용 (PostgreSQL 제약조건 이름 충돌 방지)
        render_as_batch=False,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    'online' 모드: 비동기 엔진으로 실제 DB에 연결하여 마이그레이션을 실행합니다.

    asyncpg 드라이버와 호환되도록 async_engine_from_config를 사용합니다.
    """
    # alembic 설정에 DB URL 동적 주입
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_async_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        # 마이그레이션은 단일 연결로 충분
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # 비동기 연결을 동기 컨텍스트로 래핑하여 Alembic이 사용할 수 있게 함
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """asyncio 이벤트 루프에서 비동기 마이그레이션 실행"""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
