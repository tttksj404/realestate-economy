import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.data.schemas import EconomyOverview, MacroInterpretation, RegionDetail
from app.services.economy_analyzer import EconomyAnalyzer
from app.services.cache import response_cache
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

router = APIRouter()
CACHE_TTL_SECONDS = 3600


@router.get(
    "/overview",
    response_model=EconomyOverview,
    summary="전국 경제상황 요약",
)
async def get_economy_overview(
    period: Optional[str] = Query(default=None, example="202601"),
    db: AsyncSession = Depends(get_db),
) -> EconomyOverview:
    try:
        cache_key = f"economy:overview:{period or 'current'}"
        cached = await response_cache.get(cache_key)
        if cached:
            return EconomyOverview.model_validate_json(cached)

        analyzer = EconomyAnalyzer(db)
        overview = await analyzer.get_overview(period=period)
        await response_cache.set(cache_key, overview.model_dump_json(), CACHE_TTL_SECONDS)
        return overview
    except Exception as e:
        logger.error(f"Economy overview fetch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="경제 현황 조회 중 오류가 발생했습니다.")


@router.get(
    "/macro/interpret",
    response_model=MacroInterpretation,
    summary="거시경제 해석 및 예측",
    description="전국 부동산 지표를 종합하여 거시경제 상황을 AI가 해석하고 단기 전망을 제시합니다.",
)
async def get_macro_interpretation(
    period: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> MacroInterpretation:
    from datetime import datetime

    try:
        cache_key = f"economy:macro:{period or 'current'}"
        cached = await response_cache.get(cache_key)
        if cached:
            return MacroInterpretation.model_validate_json(cached)

        analyzer = EconomyAnalyzer(db)
        overview = await analyzer.get_overview(period=period)

        region_signals = [
            {"region_name": r.region_name, "signal": r.signal, "confidence": r.confidence}
            for r in overview.regions
        ]
        national_avg = overview.national_avg_indicators.model_dump()

        # RAG 컨텍스트
        rag_context = ""
        try:
            from app.services.rag_service import RAGService
            rag = RAGService()
            rag_context = await rag.retrieve(
                query=f"한국 부동산 거시경제 {overview.period} 종합 분석",
                indicators=national_avg,
            )
        except Exception as e:
            logger.warning(f"RAG context retrieval failed: {e}")

        # LLM 거시경제 해석
        llm = LLMService()
        interpretation = await llm.interpret_macro(
            national_indicators=national_avg,
            region_signals=region_signals,
            period=overview.period,
            context=rag_context,
        )

        if overview.boom_count > overview.recession_count and overview.boom_count > overview.normal_count:
            overall = "호황"
        elif overview.recession_count > overview.boom_count and overview.recession_count > overview.normal_count:
            overall = "침체"
        else:
            overall = "보통"

        result = MacroInterpretation(
            period=overview.period,
            overall_signal=overall,
            national_avg_indicators=overview.national_avg_indicators,
            interpretation=interpretation,
            region_count=overview.total_regions,
            generated_at=datetime.now(),
        )

        await response_cache.set(cache_key, result.model_dump_json(), CACHE_TTL_SECONDS)
        return result

    except Exception as e:
        logger.error(f"Macro interpretation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="거시경제 해석 중 오류가 발생했습니다.")


@router.get(
    "/{region}",
    response_model=RegionDetail,
    summary="지역별 경제 분석",
)
async def get_region_economy(
    region: str,
    period: Optional[str] = Query(default=None, example="202601"),
    db: AsyncSession = Depends(get_db),
) -> RegionDetail:
    try:
        cache_key = f"economy:region:{region}:{period or 'current'}"
        cached = await response_cache.get(cache_key)
        if cached:
            return RegionDetail.model_validate_json(cached)

        analyzer = EconomyAnalyzer(db)
        detail = await analyzer.analyze(region=region, period=period)
        await response_cache.set(cache_key, detail.model_dump_json(), CACHE_TTL_SECONDS)
        return detail
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Region economy analysis failed for {region}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="지역 분석 중 오류가 발생했습니다.")
