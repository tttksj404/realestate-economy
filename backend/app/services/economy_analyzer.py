"""
부동산 경제 분석 오케스트레이터 (V2)

R-ONE 공식 통계 + 국토부 실거래 + 온비드 공매 기반 6개 지표로 시장 판단.

파이프라인:
  R-ONE 데이터 수집 → 국토부 거래량 집계 → 온비드 공매 집계
  → 피처 엔지니어링 → 룰 기반 신호 판정 → RAG 컨텍스트 → LLM 분석 리포트
"""

import asyncio
import logging
from datetime import date, datetime
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

# V2 임계값: R-ONE 공식 통계 기반
# 한국부동산원 지수와 실거래 데이터에서 도출한 기준
THRESHOLDS_V2 = {
    # 매매가격지수 변동률 (%)
    #   호황: +0.3% 이상 상승 (월간)
    #   침체: -0.3% 이하 하락
    "sale_index_change": {"boom": 0.3, "recession": -0.3},
    # 전세가율 (%)
    #   호황: 55% 이하 (매매 강세)
    #   침체: 75% 이상 (갭투자 위험)
    "jeonse_ratio": {"boom": 55.0, "recession": 75.0},
    # 미분양 증감률 (%)
    #   호황: -10% 이하 (미분양 감소)
    #   침체: +10% 이상 (미분양 증가)
    "unsold_change": {"boom": -10.0, "recession": 10.0},
    # 거래량 변동률 (%)
    #   호황: +10% 이상 (거래 활발)
    #   침체: -10% 이하 (거래 위축)
    "tx_count_change": {"boom": 10.0, "recession": -10.0},
    # 매매수급동향 (지수, 100=균형)
    #   호황: 105 이상 (수요 우위)
    #   침체: 95 이하 (공급 우위)
    "supply_demand": {"boom": 105.0, "recession": 95.0},
    # 공매 증감률 (%)
    #   호황: -10% 이하 (공매 감소)
    #   침체: +10% 이상 (공매 증가)
    "auction_change": {"boom": -10.0, "recession": 10.0},
}

V2_INDICATOR_KEYS = [
    "sale_index_change", "jeonse_ratio", "unsold_change",
    "tx_count_change", "supply_demand", "auction_change",
]


class EconomyAnalyzer:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.rag_service = RAGService()
        self.llm_service = LLMService()

    @staticmethod
    def _get_current_period() -> str:
        now = datetime.now()
        return f"{now.year}{str(now.month).zfill(2)}"

    @staticmethod
    def _get_prev_period(period: str) -> str:
        year = int(period[:4])
        month = int(period[4:6])
        if month == 1:
            return f"{year - 1}12"
        return f"{year}{str(month - 1).zfill(2)}"

    async def _count_transactions(self, region: str, period: str) -> int:
        """해당 지역/기간의 실거래 건수"""
        year = int(period[:4])
        month = int(period[4:6])
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        query = select(func.count()).select_from(RealEstateTransaction).where(
            and_(
                RealEstateTransaction.region_code.startswith(region),
                RealEstateTransaction.deal_date >= start_date,
                RealEstateTransaction.deal_date < end_date,
            )
        )
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def _count_auctions(self, region: str, period: str) -> int:
        """해당 지역/기간의 온비드 공매 건수"""
        year = int(period[:4])
        month = int(period[4:6])
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        query = select(func.count()).select_from(RealEstateListing).where(
            and_(
                RealEstateListing.region_code.startswith(region),
                RealEstateListing.source == "온비드",
                RealEstateListing.listed_at >= start_date,
                RealEstateListing.listed_at < end_date,
            )
        )
        result = await self.db.execute(query)
        return result.scalar() or 0

    def rule_based_signal(self, indicators: Dict) -> Tuple[str, float]:
        """
        V2 룰 기반 경제 신호 판정

        6개 지표별 점수 부여:
          호황 방향: +1, 보통: 0, 침체 방향: -1
        """
        scores = []
        valid_count = 0

        for key in V2_INDICATOR_KEYS:
            val = indicators.get(key)
            if val is None:
                continue
            valid_count += 1
            thresh = THRESHOLDS_V2[key]

            if key in ("sale_index_change", "tx_count_change"):
                # 높을수록 호황
                if val >= thresh["boom"]:
                    scores.append(1)
                elif val <= thresh["recession"]:
                    scores.append(-1)
                else:
                    scores.append(0)
            elif key == "supply_demand":
                # 100 초과 = 수요 우위 = 호황
                if val >= thresh["boom"]:
                    scores.append(1)
                elif val <= thresh["recession"]:
                    scores.append(-1)
                else:
                    scores.append(0)
            elif key == "jeonse_ratio":
                # 낮을수록 호황
                if val <= thresh["boom"]:
                    scores.append(1)
                elif val >= thresh["recession"]:
                    scores.append(-1)
                else:
                    scores.append(0)
            elif key in ("unsold_change", "auction_change"):
                # 감소할수록 호황
                if val <= thresh["boom"]:
                    scores.append(1)
                elif val >= thresh["recession"]:
                    scores.append(-1)
                else:
                    scores.append(0)

        if not scores:
            return "보통", 0.0

        total_score = sum(scores)
        max_possible = len(scores)
        confidence = abs(total_score) / max_possible if max_possible > 0 else 0.0
        data_completeness = valid_count / 6
        confidence = confidence * data_completeness

        threshold = max(2, max_possible // 3)
        if total_score >= threshold:
            signal = "호황"
        elif total_score <= -threshold:
            signal = "침체"
        else:
            signal = "보통"

        return signal, round(confidence, 3)

    async def analyze(
        self, region: str, period: Optional[str] = None,
    ) -> RegionDetail:
        if period is None:
            period = self._get_current_period()

        region_name = ANALYSIS_REGIONS.get(region[:2], f"지역({region})")
        prev_period = self._get_prev_period(period)

        # DB 캐시 확인
        saved = await self._load_saved_indicator(region, period)
        if saved is not None:
            payload = {k: getattr(saved, k, None) for k in V2_INDICATOR_KEYS}
            return RegionDetail(
                region_code=saved.region_code,
                region_name=saved.region_name or region_name,
                period=saved.period,
                signal=saved.signal or "보통",
                confidence=float(saved.confidence or 0.0),
                indicators=IndicatorData(**payload),
                analysis_report=(
                    f"{saved.region_name} {saved.period} 분석 결과. "
                    f"신호: {saved.signal or '보통'}, 신뢰도: {float(saved.confidence or 0.0):.2f}"
                ),
                rag_context_count=0,
                generated_at=datetime.now(),
            )

        logger.info(f"Starting V2 analysis: region={region}, period={period}")

        # R-ONE + 국토부 + 온비드 데이터 병렬 수집
        from app.data.collectors.reb_api import fetch_all_reb_monthly, fetch_weekly_supply_demand

        reb_current, reb_prev, cur_tx, prev_tx, cur_auction, prev_auction = (
            await asyncio.gather(
                fetch_all_reb_monthly(period),
                fetch_all_reb_monthly(prev_period),
                self._count_transactions(region, period),
                self._count_transactions(region, prev_period),
                self._count_auctions(region, period),
                self._count_auctions(region, prev_period),
            )
        )

        # 주간 수급동향 (최근 주차 추정: period의 마지막 주)
        month = int(period[4:6])
        approx_week = f"{period[:4]}{month * 4:02d}"
        supply_demand_data = await fetch_weekly_supply_demand(approx_week)
        reb_current["supply_demand"] = supply_demand_data

        # 피처 엔지니어링
        from app.data.processors.feature_engineer import compute_all_indicators_v2

        raw_indicators = compute_all_indicators_v2(
            region=region,
            period=period,
            reb_data=reb_current,
            prev_reb_data=reb_prev,
            current_tx_count=cur_tx,
            prev_tx_count=prev_tx,
            current_auction_count=cur_auction,
            prev_auction_count=prev_auction,
        )

        # 룰 기반 신호 판정
        signal, confidence = self.rule_based_signal(raw_indicators)

        # RAG 컨텍스트
        query_text = f"{region_name} 부동산 시장 {period} {signal} 분석"
        context = await self.rag_service.retrieve(
            query=query_text,
            region=region[:2],
            indicators={**raw_indicators, "signal": signal},
        )

        # LLM 분석 리포트
        analysis_report = await self.llm_service.analyze(
            indicators=raw_indicators,
            context=context,
            signal=signal,
            region_name=region_name,
            period=period,
        )

        # 벡터스토어 저장
        await self.rag_service.add_analysis_to_store(
            region_code=region,
            region_name=region_name,
            period=period,
            signal=signal,
            indicators=raw_indicators,
            analysis_text=analysis_report,
        )

        # DB 저장
        await self._save_indicators(
            region_code=region,
            region_name=region_name,
            period=period,
            indicators=raw_indicators,
            signal=signal,
            confidence=confidence,
        )

        return RegionDetail(
            region_code=region,
            region_name=region_name,
            period=period,
            signal=signal,
            confidence=confidence,
            indicators=IndicatorData(**raw_indicators),
            analysis_report=analysis_report,
            rag_context_count=context.count("[참고 ") if context else 0,
            generated_at=datetime.now(),
        )

    async def get_overview(self, period: Optional[str] = None) -> EconomyOverview:
        if period is None:
            period = self._get_current_period()

        logger.info(f"Computing national overview for period={period}")

        # DB 캐시 확인
        db_rows = (
            await self.db.execute(
                select(EconomyIndicator).where(EconomyIndicator.period == period)
            )
        ).scalars().all()

        if db_rows:
            return self._build_overview_from_db(db_rows, period)

        # 전 지역 병렬 분석
        results = await asyncio.gather(
            *[self._safe_analyze(r, period) for r in ANALYSIS_REGIONS.keys()]
        )
        return self._build_overview_from_results(
            [r for r in results if r is not None], period
        )

    def _build_overview_from_db(
        self, rows: List[EconomyIndicator], period: str
    ) -> EconomyOverview:
        region_signals = []
        all_indicators = []

        for row in rows:
            payload = {k: getattr(row, k, None) for k in V2_INDICATOR_KEYS}
            ind = IndicatorData(**payload)
            region_signals.append(
                RegionSignal(
                    region_code=row.region_code,
                    region_name=row.region_name,
                    signal=row.signal or "보통",
                    confidence=float(row.confidence or 0.0),
                    indicators=ind,
                )
            )
            all_indicators.append(ind.model_dump())

        return self._finalize_overview(region_signals, all_indicators, period)

    def _build_overview_from_results(
        self, results: List[RegionDetail], period: str
    ) -> EconomyOverview:
        region_signals = []
        all_indicators = []

        for r in results:
            region_signals.append(
                RegionSignal(
                    region_code=r.region_code,
                    region_name=r.region_name,
                    signal=r.signal,
                    confidence=r.confidence,
                    indicators=r.indicators,
                )
            )
            all_indicators.append(r.indicators.model_dump())

        return self._finalize_overview(region_signals, all_indicators, period)

    def _finalize_overview(
        self,
        region_signals: List[RegionSignal],
        all_indicators: List[Dict],
        period: str,
    ) -> EconomyOverview:
        boom = sum(1 for r in region_signals if r.signal == "호황")
        normal = sum(1 for r in region_signals if r.signal == "보통")
        recession = sum(1 for r in region_signals if r.signal == "침체")
        national_avg = self._compute_national_avg(all_indicators)
        summary = self._generate_overview_summary(
            period=period, boom=boom, normal=normal,
            recession=recession, total=len(region_signals),
            national_avg=national_avg,
        )

        return EconomyOverview(
            period=period,
            total_regions=len(region_signals),
            boom_count=boom,
            normal_count=normal,
            recession_count=recession,
            national_avg_indicators=IndicatorData(**national_avg),
            regions=region_signals,
            summary=summary,
            generated_at=datetime.now(),
        )

    async def _load_saved_indicator(
        self, region: str, period: str
    ) -> Optional[EconomyIndicator]:
        query = (
            select(EconomyIndicator)
            .where(and_(
                EconomyIndicator.period == period,
                EconomyIndicator.region_code.startswith(region),
            ))
            .order_by(EconomyIndicator.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _safe_analyze(
        self, region: str, period: str
    ) -> Optional[RegionDetail]:
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
        try:
            existing = await self.db.execute(
                select(EconomyIndicator).where(and_(
                    EconomyIndicator.region_code == region_code,
                    EconomyIndicator.period == period,
                ))
            )
            record = existing.scalar_one_or_none()

            if record:
                record.signal = signal
                record.confidence = confidence
                for key, value in indicators.items():
                    if hasattr(record, key):
                        setattr(record, key, value)
            else:
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
        if not all_indicators:
            return {k: None for k in V2_INDICATOR_KEYS}

        result = {}
        for key in V2_INDICATOR_KEYS:
            values = [ind.get(key) for ind in all_indicators if ind.get(key) is not None]
            result[key] = round(sum(values) / len(values), 2) if values else None
        return result

    @staticmethod
    def _generate_overview_summary(
        period: str, boom: int, normal: int, recession: int,
        total: int, national_avg: Dict,
    ) -> str:
        year = period[:4]
        month = period[4:6]

        if boom > recession and boom > normal:
            overall = "전반적으로 호황세를 보이고 있습니다"
        elif recession > boom and recession > normal:
            overall = "전반적으로 침체 양상을 보이고 있습니다"
        else:
            overall = "전반적으로 관망세가 지속되고 있습니다"

        highlights = []
        jr = national_avg.get("jeonse_ratio")
        if jr is not None:
            if jr >= 70:
                highlights.append(f"전국 평균 전세가율 {jr:.1f}%로 높은 수준")
            elif jr < 60:
                highlights.append(f"전국 평균 전세가율 {jr:.1f}%로 매매 강세")

        sic = national_avg.get("sale_index_change")
        if sic is not None:
            if sic > 0:
                highlights.append(f"매매가격지수 전월 대비 {sic:.2f}% 상승")
            elif sic < 0:
                highlights.append(f"매매가격지수 전월 대비 {abs(sic):.2f}% 하락")

        sd = national_avg.get("supply_demand")
        if sd is not None:
            if sd > 105:
                highlights.append(f"매매수급동향 {sd:.1f}으로 수요 우위")
            elif sd < 95:
                highlights.append(f"매매수급동향 {sd:.1f}으로 공급 우위")

        highlight_text = ", ".join(highlights) if highlights else "지표 집계 중"

        return (
            f"{year}년 {month}월 기준 전국 {total}개 주요 지역 부동산 시장은 {overall}. "
            f"호황 {boom}곳, 보통 {normal}곳, 침체 {recession}곳으로 나타났으며, "
            f"{highlight_text}."
        )
