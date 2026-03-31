#!/usr/bin/env python3
"""
벡터 DB 구축 스크립트

PostgreSQL의 EconomyIndicator 레코드를 요약 텍스트로 변환하고
DocumentEmbedder(sentence-transformers)로 임베딩하여
ChromaDB 벡터 스토어에 저장합니다.

이후 RAG 서비스에서 유사 지역·기간 분석 리포트를 검색하는 데 사용됩니다.

사용 예시:
    # 전체 데이터 벡터화
    python scripts/build_vectordb.py

    # 특정 지역만, 최근 6개월만
    python scripts/build_vectordb.py --regions 서울 경기 --months 6

    # 기존 컬렉션 초기화 후 재구축
    python scripts/build_vectordb.py --reset
"""

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 프로젝트 루트를 sys.path에 추가
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import EconomyIndicator
from app.db.vector_store import VectorStore

# ---------------------------------------------------------------------------
# 로깅 설정
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("build_vectordb")

# ---------------------------------------------------------------------------
# 지역 코드 매핑 (collect_data.py와 동일)
# ---------------------------------------------------------------------------
REGION_CODE_MAP: Dict[str, str] = {
    "서울": "11", "경기": "41", "인천": "28",
    "부산": "26", "대구": "27", "대전": "30",
    "광주": "29", "울산": "31", "세종": "36",
    "강원": "42", "충북": "43", "충남": "44",
    "전북": "45", "전남": "46", "경북": "47",
    "경남": "48", "제주": "50",
}

DEFAULT_REGIONS = list(REGION_CODE_MAP.keys())


def build_summary_text(indicator: EconomyIndicator) -> str:
    """
    EconomyIndicator 레코드를 자연어 요약 텍스트로 변환합니다.

    임베딩 품질을 높이기 위해 주요 지표와 경제 신호를 포함한
    한국어 설명 문장을 생성합니다.

    Args:
        indicator: EconomyIndicator ORM 객체

    Returns:
        임베딩용 요약 텍스트
    """
    # 기간 포맷
    period = indicator.period
    year = period[:4]
    month = period[4:6]
    period_str = f"{year}년 {month}월"

    # 지표값 안전 포맷 (None 대응)
    def fmt_pct(val: Optional[float], decimals: int = 1) -> str:
        return f"{val:.{decimals}f}%" if val is not None else "N/A"

    def fmt_days(val: Optional[float]) -> str:
        return f"{val:.0f}일" if val is not None else "N/A"

    # 신호 및 신뢰도
    signal = indicator.signal or "보통"
    confidence = indicator.confidence or 0.0
    conf_pct = f"{confidence * 100:.0f}%"

    # 경제 신호 해석 문구
    signal_desc = {
        "호황": "부동산 시장이 상승 사이클에 있으며 수요 우위 시장이 형성되어 있습니다.",
        "보통": "부동산 시장이 보합 국면으로 뚜렷한 방향성 없이 횡보하고 있습니다.",
        "침체": "부동산 시장이 하락 압력을 받고 있으며 공급 우위 또는 수요 위축이 진행 중입니다.",
    }.get(signal, "부동산 시장 동향을 분석합니다.")

    text = (
        f"{indicator.region_name} {period_str} 부동산 경제 분석 리포트.\n\n"
        f"경제 신호: {signal} (신뢰도 {conf_pct})\n"
        f"{signal_desc}\n\n"
        f"핵심 지표:\n"
        f"- 저가 매물 비율: {fmt_pct(indicator.low_price_listing_ratio)}"
        f" — 시세 대비 5% 이상 저렴한 급매물 비중\n"
        f"- 매물 증감률: {fmt_pct(indicator.listing_count_change, 2)}"
        f" — 전월 대비 신규 매물 증감\n"
        f"- 호가·실거래가 괴리율: {fmt_pct(indicator.price_gap_ratio)}"
        f" — 매도 희망가와 실거래가 차이\n"
        f"- 지역 가격지수 변동: {fmt_pct(indicator.regional_price_index, 2)}"
        f" — 전월 대비 평균 거래가 변화율\n"
        f"- 매물 소진 기간: {fmt_days(indicator.sale_speed)}"
        f" — 매물 등록부터 거래 완료까지 평균 기간\n"
        f"- 전세가율: {fmt_pct(indicator.jeonse_ratio)}"
        f" — 매매가 대비 전세가 비율\n"
    )
    return text


def build_metadata(indicator: EconomyIndicator) -> Dict[str, Any]:
    """
    ChromaDB 메타데이터 딕셔너리 구성 (필터링·검색에 활용)

    ChromaDB 메타데이터는 str/int/float/bool만 지원합니다.
    """
    return {
        "region_code": indicator.region_code,
        "region_name": indicator.region_name,
        "period": indicator.period,
        "signal": indicator.signal or "보통",
        "confidence": float(indicator.confidence) if indicator.confidence else 0.0,
        "low_price_listing_ratio": float(indicator.low_price_listing_ratio)
        if indicator.low_price_listing_ratio is not None else -1.0,
        "listing_count_change": float(indicator.listing_count_change)
        if indicator.listing_count_change is not None else 0.0,
        "price_gap_ratio": float(indicator.price_gap_ratio)
        if indicator.price_gap_ratio is not None else -1.0,
        "regional_price_index": float(indicator.regional_price_index)
        if indicator.regional_price_index is not None else 0.0,
        "sale_speed": float(indicator.sale_speed)
        if indicator.sale_speed is not None else -1.0,
        "jeonse_ratio": float(indicator.jeonse_ratio)
        if indicator.jeonse_ratio is not None else -1.0,
        "indicator_id": indicator.id,
    }


async def load_indicators(
    db_session: AsyncSession,
    region_codes: Optional[List[str]] = None,
    months_back: Optional[int] = None,
) -> List[EconomyIndicator]:
    """
    PostgreSQL에서 EconomyIndicator 레코드를 로드합니다.

    Args:
        db_session: 비동기 DB 세션
        region_codes: 필터링할 시도 코드 목록 (None이면 전체)
        months_back: 최근 N개월 데이터만 로드 (None이면 전체)

    Returns:
        EconomyIndicator 리스트
    """
    conditions = []

    # 지역 필터
    if region_codes:
        conditions.append(EconomyIndicator.region_code.in_(region_codes))

    # 기간 필터 (YYYYMM 문자열 비교)
    if months_back is not None:
        today = date.today()
        # N개월 이전 연월 계산
        year = today.year
        month = today.month - months_back
        while month <= 0:
            year -= 1
            month += 12
        from_period = f"{year:04d}{month:02d}"
        conditions.append(EconomyIndicator.period >= from_period)
        logger.info(f"기간 필터: {from_period} 이후")

    stmt = select(EconomyIndicator)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(EconomyIndicator.period.desc(), EconomyIndicator.region_name)

    result = await db_session.execute(stmt)
    indicators = result.scalars().all()
    logger.info(f"EconomyIndicator 로드 완료: {len(indicators)}건")
    return list(indicators)


async def main(
    regions: Optional[List[str]],
    months: Optional[int],
    reset: bool,
    batch_size: int,
) -> None:
    """
    벡터 DB 구축 메인 루틴

    Args:
        regions: 대상 지역 목록 (None이면 전체)
        months: 최근 N개월 데이터만 처리
        reset: True이면 기존 컬렉션 삭제 후 재구축
        batch_size: ChromaDB 배치 업서트 크기
    """
    # 지역 코드 변환
    region_codes: Optional[List[str]] = None
    if regions:
        region_codes = []
        for r in regions:
            if r not in REGION_CODE_MAP:
                logger.error(
                    f"알 수 없는 지역: '{r}'. 지원 지역: {', '.join(REGION_CODE_MAP.keys())}"
                )
                sys.exit(1)
            region_codes.append(REGION_CODE_MAP[r])

    # DB 엔진 / 세션 팩토리
    engine = create_async_engine(
        settings.DATABASE_URL, echo=False, pool_pre_ping=True
    )
    SessionFactory = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False
    )

    # 벡터 스토어 초기화
    vector_store = VectorStore()

    if reset:
        logger.warning("기존 벡터 DB 컬렉션 삭제 중...")
        try:
            vector_store.delete_collection()
            logger.info("컬렉션 삭제 완료")
        except Exception as e:
            logger.warning(f"컬렉션 삭제 실패 (존재하지 않을 수 있음): {e}")

    # 컬렉션 초기화
    vector_store.init_collection()
    logger.info("ChromaDB 컬렉션 초기화 완료")

    # DB에서 지표 로드
    async with SessionFactory() as session:
        indicators = await load_indicators(
            session, region_codes=region_codes, months_back=months
        )

    await engine.dispose()

    if not indicators:
        logger.warning("처리할 EconomyIndicator 레코드가 없습니다.")
        return

    # 배치 단위로 임베딩 및 벡터 스토어 저장
    total = len(indicators)
    stored = 0
    skipped = 0

    logger.info(f"벡터화 시작 — 총 {total}건, 배치 크기 {batch_size}")

    for batch_start in range(0, total, batch_size):
        batch = indicators[batch_start: batch_start + batch_size]

        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []

        for ind in batch:
            try:
                doc_text = build_summary_text(ind)
                meta = build_metadata(ind)
                # 문서 고유 ID: region_code + period + indicator_id
                doc_id = f"{ind.region_code}_{ind.period}_{ind.id}"

                documents.append(doc_text)
                metadatas.append(meta)
                ids.append(doc_id)

            except Exception as e:
                logger.warning(f"문서 변환 실패 (id={ind.id}): {e}")
                skipped += 1

        if documents:
            try:
                vector_store.add_documents(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids,
                )
                stored += len(documents)
                logger.info(
                    f"  배치 저장: {batch_start + 1}~{min(batch_start + batch_size, total)} / {total}"
                )
            except Exception as e:
                logger.error(f"배치 저장 실패 (배치 시작={batch_start}): {e}")
                skipped += len(documents)

    # 최종 집계
    final_count = vector_store.get_collection_count()

    logger.info("=" * 60)
    logger.info("벡터 DB 구축 완료")
    logger.info(f"  총 대상   : {total}건")
    logger.info(f"  저장 완료 : {stored}건")
    logger.info(f"  스킵      : {skipped}건")
    logger.info(f"  컬렉션 총 : {final_count}건")
    logger.info(f"  저장 경로 : {settings.CHROMADB_PATH}")
    logger.info("=" * 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="벡터 DB 구축 — EconomyIndicator → ChromaDB 임베딩 저장",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python scripts/build_vectordb.py
  python scripts/build_vectordb.py --regions 서울 경기 --months 12
  python scripts/build_vectordb.py --reset
  python scripts/build_vectordb.py --batch-size 100
        """,
    )
    parser.add_argument(
        "--regions",
        nargs="+",
        default=None,
        metavar="REGION",
        help="처리할 지역 목록 (기본값: 전체 지역)",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=None,
        help="최근 N개월 데이터만 처리 (기본값: 전체 기간)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        default=False,
        help="기존 ChromaDB 컬렉션을 삭제하고 새로 구축",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        dest="batch_size",
        help="ChromaDB 배치 업서트 크기 (기본값: 50)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="로그 레벨 (기본값: INFO)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    asyncio.run(
        main(
            regions=args.regions,
            months=args.months,
            reset=args.reset,
            batch_size=args.batch_size,
        )
    )
