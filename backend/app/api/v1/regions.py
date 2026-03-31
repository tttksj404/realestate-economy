import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import RealEstateListing, RealEstateTransaction
from app.data.schemas import ListingResponse, TransactionResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# 주요 법정동 코드 매핑 (시도별 대표 코드)
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
    {"code": "42", "name": "강원특별자치도"},
    {"code": "43", "name": "충청북도"},
    {"code": "44", "name": "충청남도"},
    {"code": "45", "name": "전라북도"},
    {"code": "46", "name": "전라남도"},
    {"code": "47", "name": "경상북도"},
    {"code": "48", "name": "경상남도"},
    {"code": "50", "name": "제주특별자치도"},
]


@router.get(
    "",
    summary="지역 목록 조회",
    description="부동산 분석 서비스에서 지원하는 지역 목록을 반환합니다.",
)
async def get_regions() -> List[dict]:
    """지원 지역 목록 반환 (시도 단위 법정동 코드 포함)"""
    return REGION_LIST


@router.get(
    "/{region}/listings",
    response_model=List[ListingResponse],
    summary="지역별 매물 현황",
    description="특정 지역의 현재 부동산 매물 목록을 반환합니다.",
)
async def get_region_listings(
    region: str,
    property_type: Optional[str] = Query(
        default=None,
        description="매물 유형 필터 (아파트/빌라/오피스텔)",
        example="아파트",
    ),
    limit: int = Query(default=50, ge=1, le=200, description="최대 반환 건수"),
    offset: int = Query(default=0, ge=0, description="페이지 오프셋"),
    db: AsyncSession = Depends(get_db),
) -> List[ListingResponse]:
    """
    지역별 매물 현황 조회

    - 공공API 및 네이버 부동산 수집 매물 포함
    - 매물 유형별 필터링 가능
    - 페이지네이션 지원
    """
    try:
        query = select(RealEstateListing).where(
            RealEstateListing.region_code.startswith(region)
        )
        if property_type:
            query = query.where(RealEstateListing.property_type == property_type)

        query = query.order_by(RealEstateListing.listed_at.desc()).limit(limit).offset(offset)

        result = await db.execute(query)
        listings = result.scalars().all()

        return [
            ListingResponse(
                id=listing.id,
                region_code=listing.region_code,
                region_name=listing.region_name,
                property_type=listing.property_type,
                listing_price=listing.listing_price,
                actual_price=listing.actual_price,
                jeonse_price=listing.jeonse_price,
                area_sqm=listing.area_sqm,
                floor=listing.floor,
                built_year=listing.built_year,
                listed_at=listing.listed_at,
                source=listing.source,
            )
            for listing in listings
        ]
    except Exception as e:
        logger.error(f"Listings fetch failed for region {region}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"매물 목록 조회 중 오류가 발생했습니다: {str(e)}")


@router.get(
    "/{region}/prices",
    response_model=List[TransactionResponse],
    summary="지역별 가격 추이",
    description="특정 지역의 실거래가 이력을 반환합니다.",
)
async def get_region_prices(
    region: str,
    property_type: Optional[str] = Query(
        default=None,
        description="매물 유형 필터 (아파트/빌라/오피스텔)",
    ),
    from_date: Optional[str] = Query(
        default=None,
        description="조회 시작 날짜 (YYYY-MM-DD)",
        example="2024-01-01",
    ),
    to_date: Optional[str] = Query(
        default=None,
        description="조회 종료 날짜 (YYYY-MM-DD)",
        example="2025-03-31",
    ),
    limit: int = Query(default=100, ge=1, le=500, description="최대 반환 건수"),
    db: AsyncSession = Depends(get_db),
) -> List[TransactionResponse]:
    """
    지역별 실거래가 추이 조회

    - 국토부 실거래가 API 수집 데이터
    - 날짜 범위 필터링
    - 매물 유형별 필터링
    - 가격 추이 차트 렌더링용 데이터 포함
    """
    try:
        from datetime import date
        from sqlalchemy import and_

        query = select(RealEstateTransaction).where(
            RealEstateTransaction.region_code.startswith(region)
        )

        filters = []
        if property_type:
            filters.append(RealEstateTransaction.property_type == property_type)
        if from_date:
            filters.append(RealEstateTransaction.deal_date >= from_date)
        if to_date:
            filters.append(RealEstateTransaction.deal_date <= to_date)

        if filters:
            query = query.where(and_(*filters))

        query = query.order_by(RealEstateTransaction.deal_date.desc()).limit(limit)

        result = await db.execute(query)
        transactions = result.scalars().all()

        return [
            TransactionResponse(
                id=tx.id,
                region_code=tx.region_code,
                region_name=tx.region_name,
                property_type=tx.property_type,
                deal_amount=tx.deal_amount,
                area_sqm=tx.area_sqm,
                deal_date=tx.deal_date,
                floor=tx.floor,
                built_year=tx.built_year,
                source=tx.source,
            )
            for tx in transactions
        ]
    except Exception as e:
        logger.error(f"Price history fetch failed for region {region}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"가격 추이 조회 중 오류가 발생했습니다: {str(e)}")
