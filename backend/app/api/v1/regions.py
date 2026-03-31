import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.schemas import (
    ListingResponse,
    PaginatedListingsResponse,
    PriceTrendPoint,
)
from app.db.database import get_db
from app.db.models import RealEstateListing, RealEstateTransaction

logger = logging.getLogger(__name__)

router = APIRouter()

# 대시보드 핵심 9개 권역
REGION_LIST = [
    {"code": "11", "name": "서울특별시"},
    {"code": "26", "name": "부산광역시"},
    {"code": "27", "name": "대구광역시"},
    {"code": "28", "name": "인천광역시"},
    {"code": "29", "name": "광주광역시"},
    {"code": "30", "name": "대전광역시"},
    {"code": "31", "name": "울산광역시"},
    {"code": "36", "name": "세종특별자치시"},
    {"code": "41", "name": "경기도"},
]


@router.get("", summary="지역 목록 조회", description="서비스에서 지원하는 핵심 지역 목록을 반환합니다.")
async def get_regions() -> List[dict]:
    return REGION_LIST


@router.get(
    "/{region}/listings",
    response_model=PaginatedListingsResponse,
    summary="지역별 매물 현황",
    description="특정 지역의 매물 목록을 페이지네이션/필터링하여 반환합니다.",
)
async def get_region_listings(
    region: str,
    page: int = Query(default=1, ge=1, description="페이지 번호 (1-base)"),
    size: int = Query(default=20, ge=1, le=200, description="페이지 크기"),
    property_type: Optional[str] = Query(default=None, description="매물 유형 필터"),
    min_price: Optional[float] = Query(default=None, ge=0, description="최소 호가 (만원)"),
    max_price: Optional[float] = Query(default=None, ge=0, description="최대 호가 (만원)"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedListingsResponse:
    try:
        if min_price is not None and max_price is not None and min_price > max_price:
            raise HTTPException(status_code=400, detail="min_price는 max_price보다 클 수 없습니다.")

        base_query = select(RealEstateListing).where(RealEstateListing.region_code.startswith(region))

        if property_type:
            base_query = base_query.where(RealEstateListing.property_type == property_type)
        if min_price is not None:
            base_query = base_query.where(RealEstateListing.listing_price >= min_price)
        if max_price is not None:
            base_query = base_query.where(RealEstateListing.listing_price <= max_price)

        count_query = select(func.count()).select_from(base_query.subquery())
        total = int((await db.execute(count_query)).scalar_one())

        offset = (page - 1) * size
        page_query = (
            base_query.order_by(RealEstateListing.listed_at.desc(), RealEstateListing.id.desc())
            .limit(size)
            .offset(offset)
        )
        rows = (await db.execute(page_query)).scalars().all()

        return PaginatedListingsResponse(
            page=page,
            size=size,
            total=total,
            items=[ListingResponse.model_validate(row) for row in rows],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Listings fetch failed for region %s: %s", region, e, exc_info=True)
        raise HTTPException(status_code=500, detail="매물 목록 조회 중 오류가 발생했습니다.")


@router.get(
    "/{region}/prices",
    response_model=List[PriceTrendPoint],
    summary="지역별 가격 추이",
    description="기간별 실거래가 평균/최저/최고/건수를 집계해 반환합니다.",
)
async def get_region_prices(
    region: str,
    property_type: Optional[str] = Query(default=None, description="매물 유형 필터"),
    from_date: Optional[date] = Query(default=None, description="조회 시작일"),
    to_date: Optional[date] = Query(default=None, description="조회 종료일"),
    db: AsyncSession = Depends(get_db),
) -> List[PriceTrendPoint]:
    try:
        if from_date and to_date and from_date > to_date:
            raise HTTPException(status_code=400, detail="from_date는 to_date보다 늦을 수 없습니다.")

        # AsyncSession에서 dialect 감지: get_bind()로 engine 접근
        try:
            bind = db.get_bind()
            dialect_name = bind.dialect.name
        except Exception:
            dialect_name = "postgresql"

        if dialect_name == "sqlite":
            period_expr = func.strftime("%Y-%m", RealEstateTransaction.deal_date)
        else:
            period_expr = func.to_char(func.date_trunc("month", RealEstateTransaction.deal_date), "YYYY-MM")

        query = (
            select(
                period_expr.label("period"),
                func.avg(RealEstateTransaction.deal_amount).label("avg_deal_amount"),
                func.min(RealEstateTransaction.deal_amount).label("min_deal_amount"),
                func.max(RealEstateTransaction.deal_amount).label("max_deal_amount"),
                func.count(RealEstateTransaction.id).label("transaction_count"),
            )
            .where(RealEstateTransaction.region_code.startswith(region))
            .group_by(period_expr)
            .order_by(period_expr)
        )

        if property_type:
            query = query.where(RealEstateTransaction.property_type == property_type)
        if from_date:
            query = query.where(RealEstateTransaction.deal_date >= from_date)
        if to_date:
            query = query.where(RealEstateTransaction.deal_date <= to_date)

        rows = (await db.execute(query)).all()
        return [
            PriceTrendPoint(
                period=row.period,
                avg_deal_amount=round(float(row.avg_deal_amount), 2),
                min_deal_amount=round(float(row.min_deal_amount), 2),
                max_deal_amount=round(float(row.max_deal_amount), 2),
                transaction_count=int(row.transaction_count),
            )
            for row in rows
            if row.period is not None
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Price history fetch failed for region %s: %s", region, e, exc_info=True)
        raise HTTPException(status_code=500, detail="가격 추이 조회 중 오류가 발생했습니다.")
