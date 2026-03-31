import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.data.schemas import EconomyOverview, RegionDetail
from app.services.economy_analyzer import EconomyAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/overview",
    response_model=EconomyOverview,
    summary="전국 경제상황 요약",
    description="전국 주요 지역의 부동산 경제 상황을 종합 분석하여 반환합니다.",
)
async def get_economy_overview(
    period: Optional[str] = Query(
        default=None,
        description="분석 기준 연월 (YYYYMM 형식, 기본값: 현재 월)",
        example="202503",
    ),
    db: AsyncSession = Depends(get_db),
) -> EconomyOverview:
    """
    전국 부동산 경제 상황 요약 조회

    - 주요 지역별 경제 신호 (호황/보통/침체) 집계
    - 전국 평균 지표 (저가매물비율, 매물증감률, 가격갭비율 등)
    - 지역별 상세 신호 목록 포함
    """
    try:
        analyzer = EconomyAnalyzer(db)
        overview = await analyzer.get_overview(period=period)
        return overview
    except Exception as e:
        logger.error(f"Economy overview fetch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"경제 현황 조회 중 오류가 발생했습니다: {str(e)}")


@router.get(
    "/{region}",
    response_model=RegionDetail,
    summary="지역별 경제 분석",
    description="특정 지역의 부동산 경제 상황을 상세 분석합니다.",
)
async def get_region_economy(
    region: str,
    period: Optional[str] = Query(
        default=None,
        description="분석 기준 연월 (YYYYMM 형식)",
        example="202503",
    ),
    db: AsyncSession = Depends(get_db),
) -> RegionDetail:
    """
    지역별 부동산 경제 상황 분석

    - 6개 핵심 지표: 저가매물비율, 매물증감률, 호가/실거래가 괴리율,
                    가격지수변동, 매물소진기간, 전세가율
    - 룰 기반 경제 신호 판정 (호황/보통/침체)
    - LLM 기반 자연어 분석 리포트
    - 유사 시장 상황 RAG 컨텍스트 참조
    """
    try:
        analyzer = EconomyAnalyzer(db)
        detail = await analyzer.analyze(region=region, period=period)
        return detail
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Region economy analysis failed for {region}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"지역 분석 중 오류가 발생했습니다: {str(e)}")
