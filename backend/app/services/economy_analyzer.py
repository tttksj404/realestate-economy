"""
부동산 경제 분석 오케스트레이터

피처 엔지니어링 → 룰 기반 신호 판정 → RAG 컨텍스트 검색 → LLM 분석 리포트 생성
전체 파이프라인을 통합 조율합니다.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.data.schemas import (
    EconomyOverview,
    IndicatorData,
    RegionDetail,
    RegionSignal,
)
from app.db.models import EconomyIndicator, RealEstateListing, RealEstateTransaction
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

# 주요 분석 지역 (시도 코드 → 지역명)
ANALYSIS_REGIONS = {
    "11": "서울특별시",
    "26": "부산광역시",
    "27": "대구광역시",
    "28": "인천광역시",
    "29": "광주광역시",
    "30": "대전광역시",
    "31": "울산광역시",
    "36": "세종특별자치시",
    "41": "경기도",
}

# 경제 신호 판정 임계값 (룰 기반)
# 각 지표별로 호황/보통/침체를 구분하는 기준값
THRESHOLDS = {
    # 저가 매물 비율: 높을수록 침체
    "low_price_listing_ratio": {"boom": 5.0, "recession": 15.0},
    # 매물 증감률: 높을수록 공급 과잉 (침체)
    "listing_count_change": {"boom": -5.0, "recession": 10.0},
    # 호가/실거래가 괴리율: 높을수록 침체
    "price_gap_ratio": {"boom": 2.0, "recession": 8.0},
    # 가격지수 변동: 낮을수록 침체 (음수 = 하락)
    "regional_price_index": {"boom": 1.0, "recession": -1.0},
    # 매물 소진 기간: 낮을수록 호황
    "sale_speed": {"boom": 30.0, "recession": 90.0},
    # 전세가율: 높을수록 투자 위험 (매매 침체)
    "jeonse_ratio": {"boom": 55.0, "recession": 75.0},
}


class EconomyAnalyzer:
    """
    부동산 경제 분석기

    DB에서 매물/거래 데이터를 조회하고,
    피처 엔지니어링 → 신호 판정 → LLM 분석 리포트 생성 파이프라인을 실행합니다.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.rag_service = RAGService()
        self.llm_service = LLMService()

    def _get_current_period(self) -> str:
        """현재 연월 반환 (YYYYMM 형식)"""
        now = datetime.now()
        return f"{now.year}{str(now.month).zfill(2)}"

    def _get_prev_period(self, period: str) -> str:
        """전월 기간 반환"""
        year = int(period[:4])
        month = int(period[4:6])
        if month == 1:
            return f"{year - 1}12"
        return f"{year}{str(month - 1).zfill(2)}"

    async def _fetch_listings(
        self, region: str, period: str
    ) -> List[Dict]:
        """DB에서 지역/기간 매물 데이터 조회"""
        from datetime import date

        year = int(period[:4])
        month = int(period[4:6])
        start_date = date(year, month, 1)
        if month == 12:
            from datetime import timedelta
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1)

        query = select(RealEstateListing).where(
            and_(
                RealEstateListing.region_code.startswith(region),
                RealEstateListing.listed_at >= start_date,
                RealEstateListing.listed_at < end_date,
            )
        )
        result = await self.db.execute(query)
        rows = result.scalars().all()

        return [
            {
                "region_code": r.region_code,
                "listing_price": float(r.listing_price) if r.listing_price else None,
                "jeonse_price": float(r.jeonse_price) if r.jeonse_price else None,
                "actual_price": float(r.actual_price) if r.actual_price else None,
                "area_sqm": r.area_sqm,
                "property_type": r.property_type,
            }
            for r in rows
        ]

    async def _fetch_transactions(
        self, region: str, period: str
    ) -> List[Dict]:
        """DB에서 지역/기간 실거래가 데이터 조회"""
        from datetime import date

        year = int(period[:4])
        month = int(period[4:6])
        start_date = date(year, month, 1)
        if month == 12:
            from datetime import timedelta
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1)

        query = select(RealEstateTransaction).where(
            and_(
                RealEstateTransaction.region_code.startswith(region),
                RealEstateTransaction.deal_date >= start_date,
                RealEstateTransaction.deal_date < end_date,
            )
        )
        result = await self.db.execute(query)
        rows = result.scalars().all()

        return [
            {
                "region_code": r.region_code,
                "deal_amount": float(r.deal_amount) if r.deal_amount else None,
                "area_sqm": r.area_sqm,
                "deal_date": r.deal_date,
                "property_type": r.property_type,
            }
            for r in rows
        ]

    def rule_based_signal(
        self, indicators: Dict
    ) -> Tuple[str, float]:
        """
        룰 기반 경제 신호 판정

        6개 지표에 대해 각각 점수를 부여하고 합산하여 최종 신호를 결정합니다.

        점수 체계:
        - 호황 신호: +1점
        - 보통 신호: 0점
        - 침체 신호: -1점

        최종 판정:
        - 합계 >= 2: 호황
        - 합계 <= -2: 침체
        - 나머지: 보통

        Args:
            indicators: 6개 지표 딕셔너리

        Returns:
            (signal, confidence) 튜플
        """
        scores = []
        valid_count = 0

        # 저가 매물 비율 (낮을수록 호황)
        lpr = indicators.get("low_price_listing_ratio")
        if lpr is not None:
            valid_count += 1
            if lpr <= THRESHOLDS["low_price_listing_ratio"]["boom"]:
                scores.append(1)
            elif lpr >= THRESHOLDS["low_price_listing_ratio"]["recession"]:
                scores.append(-1)
            else:
                scores.append(0)

        # 매물 증감률 (감소할수록 호황)
        lcc = indicators.get("listing_count_change")
        if lcc is not None:
            valid_count += 1
            if lcc <= THRESHOLDS["listing_count_change"]["boom"]:
                scores.append(1)
            elif lcc >= THRESHOLDS["listing_count_change"]["recession"]:
                scores.append(-1)
            else:
                scores.append(0)

        # 호가/실거래가 괴리율 (낮을수록 호황)
        pgr = indicators.get("price_gap_ratio")
        if pgr is not None:
            valid_count += 1
            if pgr <= THRESHOLDS["price_gap_ratio"]["boom"]:
                scores.append(1)
            elif pgr >= THRESHOLDS["price_gap_ratio"]["recession"]:
                scores.append(-1)
            else:
                scores.append(0)

        # 가격지수 변동 (높을수록 호황)
        rpi = indicators.get("regional_price_index")
        if rpi is not None:
            valid_count += 1
            if rpi >= THRESHOLDS["regional_price_index"]["boom"]:
                scores.append(1)
            elif rpi <= THRESHOLDS["regional_price_index"]["recession"]:
                scores.append(-1)
            else:
                scores.append(0)

        # 매물 소진 기간 (짧을수록 호황)
        ss = indicators.get("sale_speed")
        if ss is not None:
            valid_count += 1
            if ss <= THRESHOLDS["sale_speed"]["boom"]:
                scores.append(1)
            elif ss >= THRESHOLDS["sale_speed"]["recession"]:
                scores.append(-1)
            else:
                scores.append(0)

        # 전세가율 (낮을수록 호황: 매매가 강세)
        jr = indicators.get("jeonse_ratio")
        if jr is not None:
            valid_count += 1
            if jr <= THRESHOLDS["jeonse_ratio"]["boom"]:
                scores.append(1)
            elif jr >= THRESHOLDS["jeonse_ratio"]["recession"]:
                scores.append(-1)
            else:
                scores.append(0)

        if not scores:
            return "보통", 0.0

        total_score = sum(scores)
        max_possible = len(scores)

        # 신뢰도: 극단적 점수일수록 높음
        confidence = abs(total_score) / max_possible if max_possible > 0 else 0.0

        # 데이터 충분성에 따라 신뢰도 조정 (6개 중 4개 이상이면 풀 신뢰)
        data_completeness = valid_count / 6
        confidence = confidence * data_completeness

        # 신호 판정 (총점의 1/3 이상 극단이면 해당 신호)
        threshold = max(2, max_possible // 3)

        if total_score >= threshold:
            signal = "호황"
        elif total_score <= -threshold:
            signal = "침체"
        else:
            signal = "보통"

        return signal, round(confidence, 3)

    async def analyze(
        self,
        region: str,
        period: Optional[str] = None,
    ) -> RegionDetail:
        """
        지역별 종합 경제 분석

        Args:
            region: 지역 코드 (시도 2자리 또는 시군구 5자리)
            period: 분석 기준 연월 (YYYYMM, 기본: 현재 월)

        Returns:
            RegionDetail 스키마 인스턴스
        """
        if period is None:
            period = self._get_current_period()

        region_name = ANALYSIS_REGIONS.get(region[:2], f"지역({region})")
        prev_period = self._get_prev_period(period)

        logger.info(f"Starting analysis: region={region}, period={period}")

        # 데이터 수집 (병렬)
        current_listings, current_transactions, prev_listings, prev_transactions = (
            await asyncio.gather(
                self._fetch_listings(region, period),
                self._fetch_transactions(region, period),
                self._fetch_listings(region, prev_period),
                self._fetch_transactions(region, prev_period),
            )
        )

        logger.info(
            f"Data fetched: listings={len(current_listings)}, "
            f"transactions={len(current_transactions)}"
        )

        # 피처 엔지니어링
        from app.data.processors.feature_engineer import compute_all_indicators

        jeonse_listings = [l for l in current_listings if l.get("jeonse_price")]

        raw_indicators = compute_all_indicators(
            region=region,
            period=period,
            current_listings=current_listings,
            prev_listings=prev_listings,
            current_transactions=current_transactions,
            prev_transactions=prev_transactions,
            jeonse_listings=jeonse_listings if jeonse_listings else None,
        )

        # 룰 기반 신호 판정
        signal, confidence = self.rule_based_signal(raw_indicators)

        # RAG 컨텍스트 검색
        query_text = f"{region_name} 부동산 시장 {period} {signal} 분석"
        context = await self.rag_service.retrieve(
            query=query_text,
            region=region[:2],  # 시도 단위로 검색
            indicators={**raw_indicators, "signal": signal},
        )

        # LLM 분석 리포트 생성
        analysis_report = await self.llm_service.analyze(
            indicators=raw_indicators,
            context=context,
            signal=signal,
            region_name=region_name,
            period=period,
        )

        # 분석 결과 벡터 스토어 저장 (향후 RAG 활용)
        await self.rag_service.add_analysis_to_store(
            region_code=region,
            region_name=region_name,
            period=period,
            signal=signal,
            indicators=raw_indicators,
            analysis_text=analysis_report,
        )

        # DB에 지표 저장
        await self._save_indicators(
            region_code=region,
            region_name=region_name,
            period=period,
            indicators=raw_indicators,
            signal=signal,
            confidence=confidence,
        )

        indicator_data = IndicatorData(**raw_indicators)

        return RegionDetail(
            region_code=region,
            region_name=region_name,
            period=period,
            signal=signal,
            confidence=confidence,
            indicators=indicator_data,
            analysis_report=analysis_report,
            rag_context_count=context.count("[참고 ") if context else 0,
            generated_at=datetime.now(),
        )

    async def get_overview(
        self,
        period: Optional[str] = None,
    ) -> EconomyOverview:
        """
        전국 경제 상황 요약

        주요 지역별 분석을 병렬 수행하고 전국 요약을 생성합니다.

        Args:
            period: 분석 기준 연월

        Returns:
            EconomyOverview 스키마 인스턴스
        """
        if period is None:
            period = self._get_current_period()

        logger.info(f"Computing national overview for period={period}")

        # 주요 지역 병렬 분석 (오류 발생 지역은 스킵)
        region_tasks = [
            self._safe_analyze(region, period)
            for region in ANALYSIS_REGIONS.keys()
        ]
        results = await asyncio.gather(*region_tasks)

        # 유효한 결과만 필터링
        region_signals: List[RegionSignal] = []
        all_indicators: List[Dict] = []

        for result in results:
            if result is not None:
                region_signals.append(
                    RegionSignal(
                        region_code=result.region_code,
                        region_name=result.region_name,
                        signal=result.signal,
                        confidence=result.confidence,
                        indicators=result.indicators,
                    )
                )
                all_indicators.append(result.indicators.model_dump())

        # 카운팅
        boom_count = sum(1 for r in region_signals if r.signal == "호황")
        normal_count = sum(1 for r in region_signals if r.signal == "보통")
        recession_count = sum(1 for r in region_signals if r.signal == "침체")

        # 전국 평균 지표 계산
        national_avg = self._compute_national_avg(all_indicators)

        # 전국 요약 텍스트 생성
        summary = self._generate_overview_summary(
            period=period,
            boom=boom_count,
            normal=normal_count,
            recession=recession_count,
            total=len(region_signals),
            national_avg=national_avg,
        )

        return EconomyOverview(
            period=period,
            total_regions=len(region_signals),
            boom_count=boom_count,
            normal_count=normal_count,
            recession_count=recession_count,
            national_avg_indicators=IndicatorData(**national_avg),
            regions=region_signals,
            summary=summary,
            generated_at=datetime.now(),
        )

    async def _safe_analyze(
        self, region: str, period: str
    ) -> Optional[RegionDetail]:
        """오류 발생 시 None 반환하는 안전한 analyze 래퍼"""
        try:
            return await self.analyze(region=region, period=period)
        except Exception as e:
            logger.warning(f"Analysis failed for region={region}: {e}")
            return None

    async def _save_indicators(
        self,
        region_code: str,
        region_name: str,
        period: str,
        indicators: Dict,
        signal: str,
        confidence: float,
    ) -> None:
        """계산된 지표를 DB에 저장 (upsert 방식)"""
        try:
            # 기존 레코드 조회
            existing = await self.db.execute(
                select(EconomyIndicator).where(
                    and_(
                        EconomyIndicator.region_code == region_code,
                        EconomyIndicator.period == period,
                    )
                )
            )
            record = existing.scalar_one_or_none()

            if record:
                # 업데이트
                record.signal = signal
                record.confidence = confidence
                for key, value in indicators.items():
                    if hasattr(record, key):
                        setattr(record, key, value)
            else:
                # 신규 생성
                record = EconomyIndicator(
                    region_code=region_code,
                    region_name=region_name,
                    period=period,
                    signal=signal,
                    confidence=confidence,
                    **{k: v for k, v in indicators.items() if hasattr(EconomyIndicator, k)},
                )
                self.db.add(record)

            await self.db.flush()

        except Exception as e:
            logger.error(f"Failed to save indicators: {e}")

    @staticmethod
    def _compute_national_avg(all_indicators: List[Dict]) -> Dict:
        """전국 평균 지표 계산"""
        if not all_indicators:
            return {k: None for k in ["low_price_listing_ratio", "listing_count_change",
                                       "price_gap_ratio", "regional_price_index",
                                       "sale_speed", "jeonse_ratio"]}

        keys = ["low_price_listing_ratio", "listing_count_change",
                "price_gap_ratio", "regional_price_index",
                "sale_speed", "jeonse_ratio"]

        result = {}
        for key in keys:
            values = [ind.get(key) for ind in all_indicators if ind.get(key) is not None]
            if values:
                result[key] = round(sum(values) / len(values), 2)
            else:
                result[key] = None

        return result

    @staticmethod
    def _generate_overview_summary(
        period: str,
        boom: int,
        normal: int,
        recession: int,
        total: int,
        national_avg: Dict,
    ) -> str:
        """전국 경제 상황 요약 텍스트 생성"""
        year = period[:4]
        month = period[4:6]

        # 전반적 시장 판단
        if boom > recession and boom > normal:
            overall = "전반적으로 호황세를 보이고 있습니다"
        elif recession > boom and recession > normal:
            overall = "전반적으로 침체 양상을 보이고 있습니다"
        else:
            overall = "전반적으로 관망세가 지속되고 있습니다"

        # 지표 하이라이트
        highlights = []
        if national_avg.get("jeonse_ratio") is not None:
            jr = national_avg["jeonse_ratio"]
            if jr >= 70:
                highlights.append(f"전국 평균 전세가율이 {jr:.1f}%로 높은 수준")
            elif jr < 60:
                highlights.append(f"전국 평균 전세가율이 {jr:.1f}%로 낮아 매매 강세")

        if national_avg.get("regional_price_index") is not None:
            rpi = national_avg["regional_price_index"]
            if rpi > 0:
                highlights.append(f"가격지수 전월 대비 {rpi:.1f}% 상승")
            elif rpi < 0:
                highlights.append(f"가격지수 전월 대비 {abs(rpi):.1f}% 하락")

        highlight_text = ", ".join(highlights) if highlights else "지표 집계 중"

        return (
            f"{year}년 {month}월 기준 전국 {total}개 주요 지역 부동산 시장은 {overall}. "
            f"호황 {boom}곳, 보통 {normal}곳, 침체 {recession}곳으로 나타났으며, "
            f"{highlight_text}."
        )
