from datetime import date
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import get_db
from app.db.models import Base, EconomyIndicator, RealEstateListing, RealEstateTransaction
from app.main import create_app


@pytest_asyncio.fixture(scope="session")
async def test_engine(tmp_path_factory: pytest.TempPathFactory):
    db_dir: Path = tmp_path_factory.mktemp("db")
    db_path = db_dir / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def session_maker(test_engine):
    return async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(session_maker):
    async with session_maker() as session:
        await session.execute(delete(EconomyIndicator))
        await session.execute(delete(RealEstateTransaction))
        await session.execute(delete(RealEstateListing))
        await session.commit()
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def app(session_maker):
    application = create_app()

    async def override_get_db():
        async with session_maker() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    yield application
    application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app, lifespan="off")
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


@pytest_asyncio.fixture
async def sample_data(db_session: AsyncSession):
    listings = [
        RealEstateListing(
            id=1,
            region_code="11110",
            region_name="서울 종로구",
            property_type="아파트",
            listing_price=120000,
            actual_price=115000,
            jeonse_price=70000,
            area_sqm=84.5,
            floor=10,
            built_year=2015,
            listed_at=date(2025, 3, 10),
            source="공공API",
        ),
        RealEstateListing(
            id=2,
            region_code="11110",
            region_name="서울 종로구",
            property_type="빌라",
            listing_price=60000,
            actual_price=55000,
            jeonse_price=42000,
            area_sqm=42.2,
            floor=4,
            built_year=2008,
            listed_at=date(2025, 3, 8),
            source="네이버",
        ),
    ]

    transactions = [
        RealEstateTransaction(
            id=1,
            region_code="11110",
            region_name="서울 종로구",
            property_type="아파트",
            deal_amount=110000,
            area_sqm=84.0,
            deal_date=date(2025, 1, 15),
            floor=9,
            built_year=2015,
            source="공공API",
        ),
        RealEstateTransaction(
            id=2,
            region_code="11110",
            region_name="서울 종로구",
            property_type="아파트",
            deal_amount=120000,
            area_sqm=84.0,
            deal_date=date(2025, 1, 20),
            floor=11,
            built_year=2015,
            source="공공API",
        ),
        RealEstateTransaction(
            id=3,
            region_code="11110",
            region_name="서울 종로구",
            property_type="아파트",
            deal_amount=118000,
            area_sqm=84.0,
            deal_date=date(2025, 2, 5),
            floor=12,
            built_year=2015,
            source="공공API",
        ),
    ]

    indicators = [
        EconomyIndicator(
            id=1,
            region_code="11",
            region_name="서울특별시",
            period="202503",
            low_price_listing_ratio=12.1,
            listing_count_change=8.0,
            price_gap_ratio=6.1,
            regional_price_index=1.3,
            sale_speed=54.0,
            jeonse_ratio=62.0,
            signal="보통",
            confidence=0.72,
        ),
        EconomyIndicator(
            id=2,
            region_code="26",
            region_name="부산광역시",
            period="202503",
            low_price_listing_ratio=18.2,
            listing_count_change=22.0,
            price_gap_ratio=10.5,
            regional_price_index=-2.1,
            sale_speed=99.0,
            jeonse_ratio=81.0,
            signal="침체",
            confidence=0.84,
        ),
        EconomyIndicator(
            id=3,
            region_code="11110",
            region_name="서울 종로구",
            period="202503",
            low_price_listing_ratio=10.0,
            listing_count_change=3.0,
            price_gap_ratio=4.0,
            regional_price_index=0.8,
            sale_speed=48.0,
            jeonse_ratio=59.0,
            signal="보통",
            confidence=0.65,
        ),
    ]

    db_session.add_all(listings + transactions + indicators)
    await db_session.commit()
