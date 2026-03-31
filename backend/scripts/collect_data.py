#!/usr/bin/env python3
"""
부동산 데이터 수집 스크립트

공공데이터포털(국토부 실거래가 API) 및 네이버 부동산 크롤러를 통해
주요 지역 매물·거래 데이터를 수집하여 PostgreSQL에 저장합니다.

사용 예시:
    # 전체 지역, 전체 소스, 최근 3개월
    python scripts/collect_data.py --months 3 --source all

    # 서울·경기만, 공공API만
    python scripts/collect_data.py --regions 서울 경기 --source public

    # 특정 지역 네이버 크롤링만
    python scripts/collect_data.py --regions 부산 대구 --source naver --months 1
"""

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 프로젝트 루트를 sys.path에 추가 (backend/ 기준 실행 대응)
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.data.collectors import naver_crawler, public_api
from app.db.models import RealEstateListing, RealEstateTransaction

# ---------------------------------------------------------------------------
# 로깅 설정
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("collect_data")

# ---------------------------------------------------------------------------
# 지역 코드 매핑 (사용자 입력 → 법정동 시도 코드)
# ---------------------------------------------------------------------------
REGION_CODE_MAP: Dict[str, Tuple[str, str]] = {
    "서울": ("11", "서울특별시"),
    "경기": ("41", "경기도"),
    "인천": ("28", "인천광역시"),
    "부산": ("26", "부산광역시"),
    "대구": ("27", "대구광역시"),
    "대전": ("30", "대전광역시"),
    "광주": ("29", "광주광역시"),
    "울산": ("31", "울산광역시"),
    "세종": ("36", "세종특별자치시"),
    "강원": ("42", "강원특별자치도"),
    "충북": ("43", "충청북도"),
    "충남": ("44", "충청남도"),
    "전북": ("45", "전북특별자치도"),
    "전남": ("46", "전라남도"),
    "경북": ("47", "경상북도"),
    "경남": ("48", "경상남도"),
    "제주": ("50", "제주특별자치도"),
}

# 기본 수집 대상 지역 (9대 광역시도)
DEFAULT_REGIONS = ["서울", "경기", "인천", "부산", "대구", "대전", "광주", "울산", "세종"]


def build_year_months(months_back: int) -> List[str]:
    """
    현재 날짜로부터 N개월 이전까지의 연월 목록을 반환합니다.

    Args:
        months_back: 몇 개월 이전까지 수집할지

    Returns:
        ['202401', '202402', ...] 형식의 연월 리스트 (오래된 순)
    """
    today = date.today()
    result = []
    for i in range(months_back, 0, -1):
        # 현재 월에서 i개월 빼기
        year = today.year
        month = today.month - i
        while month <= 0:
            year -= 1
            month += 12
        result.append(f"{year:04d}{month:02d}")
    return result


async def collect_public_api(
    db_session: AsyncSession,
    region_code: str,
    region_name: str,
    year_months: List[str],
) -> Dict[str, int]:
    """
    공공API(국토부 실거래가)에서 거래 데이터를 수집하여 DB에 저장합니다.

    Args:
        db_session: 비동기 DB 세션
        region_code: 시도 코드 (예: "11")
        region_name: 지역명 (예: "서울특별시")
        year_months: 수집할 연월 목록

    Returns:
        {"apartment": N, "villa": N, "officetel": N} 저장 건수
    """
    saved_counts = {"apartment": 0, "villa": 0, "officetel": 0}

    for ym in year_months:
        year = int(ym[:4])
        month = int(ym[4:6])
        logger.info(f"[공공API] {region_name} {ym} 수집 중...")

        try:
            # 아파트 실거래가 수집
            apt_trades = await public_api.fetch_apartment_trades(
                region_code=region_code, year=year, month=month
            )
            for trade in apt_trades:
                obj = RealEstateTransaction(
                    region_code=region_code,
                    region_name=region_name,
                    property_type="아파트",
                    deal_amount=trade.get("deal_amount", 0),
                    area_sqm=trade.get("area_sqm"),
                    deal_date=trade.get("deal_date"),
                    floor=trade.get("floor"),
                    built_year=trade.get("built_year"),
                    source="공공API",
                )
                db_session.add(obj)
            saved_counts["apartment"] += len(apt_trades)
            logger.debug(f"  아파트: {len(apt_trades)}건")

        except Exception as e:
            logger.warning(f"[공공API] {region_name} {ym} 아파트 수집 실패: {e}")

        try:
            # 연립다세대 실거래가 수집
            villa_trades = await public_api.fetch_villa_trades(
                region_code=region_code, year=year, month=month
            )
            for trade in villa_trades:
                obj = RealEstateTransaction(
                    region_code=region_code,
                    region_name=region_name,
                    property_type="빌라",
                    deal_amount=trade.get("deal_amount", 0),
                    area_sqm=trade.get("area_sqm"),
                    deal_date=trade.get("deal_date"),
                    floor=trade.get("floor"),
                    built_year=trade.get("built_year"),
                    source="공공API",
                )
                db_session.add(obj)
            saved_counts["villa"] += len(villa_trades)
            logger.debug(f"  빌라: {len(villa_trades)}건")

        except Exception as e:
            logger.warning(f"[공공API] {region_name} {ym} 빌라 수집 실패: {e}")

        try:
            # 오피스텔 실거래가 수집
            offi_trades = await public_api.fetch_officetel_trades(
                region_code=region_code, year=year, month=month
            )
            for trade in offi_trades:
                obj = RealEstateTransaction(
                    region_code=region_code,
                    region_name=region_name,
                    property_type="오피스텔",
                    deal_amount=trade.get("deal_amount", 0),
                    area_sqm=trade.get("area_sqm"),
                    deal_date=trade.get("deal_date"),
                    floor=trade.get("floor"),
                    built_year=trade.get("built_year"),
                    source="공공API",
                )
                db_session.add(obj)
            saved_counts["officetel"] += len(offi_trades)
            logger.debug(f"  오피스텔: {len(offi_trades)}건")

        except Exception as e:
            logger.warning(f"[공공API] {region_name} {ym} 오피스텔 수집 실패: {e}")

        # 연월별 중간 커밋 (롤백 범위 최소화)
        await db_session.flush()

    return saved_counts


async def collect_naver(
    db_session: AsyncSession,
    region_code: str,
    region_name: str,
) -> Dict[str, int]:
    """
    네이버 부동산 크롤러에서 현재 매물 데이터를 수집하여 DB에 저장합니다.

    Args:
        db_session: 비동기 DB 세션
        region_code: 시도 코드
        region_name: 지역명

    Returns:
        {"매매": N, "전세": N} 저장 건수
    """
    saved_counts = {"매매": 0, "전세": 0}
    today = date.today()

    logger.info(f"[네이버] {region_name} 매물 수집 중...")

    # 매매 매물 수집
    try:
        listings = await naver_crawler.fetch_listings(region_code=region_code)
        for item in listings:
            obj = RealEstateListing(
                region_code=region_code,
                region_name=region_name,
                property_type=item.get("property_type", "아파트"),
                listing_price=item.get("listing_price"),
                actual_price=item.get("actual_price"),
                jeonse_price=None,
                area_sqm=item.get("area_sqm"),
                floor=item.get("floor"),
                built_year=item.get("built_year"),
                listed_at=item.get("listed_at", today),
                source="네이버",
            )
            db_session.add(obj)
        saved_counts["매매"] += len(listings)
        logger.debug(f"  매매 매물: {len(listings)}건")

    except Exception as e:
        logger.warning(f"[네이버] {region_name} 매매 매물 수집 실패: {e}")

    # 전세 매물 수집
    try:
        jeonse_listings = await naver_crawler.fetch_jeonse_listings(region_code=region_code)
        for item in jeonse_listings:
            obj = RealEstateListing(
                region_code=region_code,
                region_name=region_name,
                property_type=item.get("property_type", "아파트"),
                listing_price=None,
                actual_price=None,
                jeonse_price=item.get("jeonse_price"),
                area_sqm=item.get("area_sqm"),
                floor=item.get("floor"),
                built_year=item.get("built_year"),
                listed_at=item.get("listed_at", today),
                source="네이버",
            )
            db_session.add(obj)
        saved_counts["전세"] += len(jeonse_listings)
        logger.debug(f"  전세 매물: {len(jeonse_listings)}건")

    except Exception as e:
        logger.warning(f"[네이버] {region_name} 전세 매물 수집 실패: {e}")

    await db_session.flush()
    return saved_counts


async def main(
    regions: List[str],
    months: int,
    source: str,
) -> None:
    """
    메인 데이터 수집 루틴

    Args:
        regions: 수집 대상 지역명 리스트 (예: ["서울", "경기"])
        months: 몇 개월 이전 데이터까지 수집할지 (공공API)
        source: 수집 소스 ("public" | "naver" | "all")
    """
    # 지역 코드 매핑 검증
    region_pairs: List[Tuple[str, str]] = []
    for region in regions:
        if region not in REGION_CODE_MAP:
            logger.error(
                f"알 수 없는 지역: '{region}'. "
                f"지원 지역: {', '.join(REGION_CODE_MAP.keys())}"
            )
            sys.exit(1)
        region_pairs.append(REGION_CODE_MAP[region])

    # 수집 대상 연월 목록 생성
    year_months = build_year_months(months)
    logger.info(
        f"수집 시작 — 지역: {regions}, 소스: {source}, "
        f"기간: {year_months[0]}~{year_months[-1]} ({len(year_months)}개월)"
    )

    # DB 엔진 / 세션 팩토리 생성
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    SessionFactory = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False
    )

    total_stats: Dict[str, int] = {}
    start_time = datetime.now()

    async with SessionFactory() as session:
        for idx, (region_code, region_name) in enumerate(region_pairs, start=1):
            logger.info(
                f"[{idx}/{len(region_pairs)}] {region_name} ({region_code}) 처리 중..."
            )
            region_stats: Dict[str, int] = {}

            # 공공API 수집
            if source in ("public", "all"):
                try:
                    counts = await collect_public_api(
                        session, region_code, region_name, year_months
                    )
                    region_stats.update({f"공공__{k}": v for k, v in counts.items()})
                    logger.info(
                        f"  [공공API] {region_name} — "
                        f"아파트 {counts['apartment']}, 빌라 {counts['villa']}, "
                        f"오피스텔 {counts['officetel']}건 수집"
                    )
                except Exception as e:
                    logger.error(f"  [공공API] {region_name} 수집 오류: {e}")

            # 네이버 수집
            if source in ("naver", "all"):
                try:
                    counts = await collect_naver(session, region_code, region_name)
                    region_stats.update({f"네이버__{k}": v for k, v in counts.items()})
                    logger.info(
                        f"  [네이버] {region_name} — "
                        f"매매 {counts['매매']}, 전세 {counts['전세']}건 수집"
                    )
                except Exception as e:
                    logger.error(f"  [네이버] {region_name} 수집 오류: {e}")

            # 지역별 통계 누적
            for k, v in region_stats.items():
                total_stats[k] = total_stats.get(k, 0) + v

        # 전체 커밋
        await session.commit()
        logger.info("DB 커밋 완료")

    await engine.dispose()

    # 수집 결과 요약
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("=" * 60)
    logger.info("데이터 수집 완료")
    logger.info(f"소요 시간  : {elapsed:.1f}초")
    logger.info(f"대상 지역  : {', '.join(regions)}")
    logger.info("수집 건수  :")
    for k, v in sorted(total_stats.items()):
        logger.info(f"  {k}: {v:,}건")
    logger.info("=" * 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="부동산 데이터 수집기 — 공공API/네이버 데이터를 PostgreSQL에 저장",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python scripts/collect_data.py
  python scripts/collect_data.py --regions 서울 경기 --months 6
  python scripts/collect_data.py --source naver --regions 부산
  python scripts/collect_data.py --source public --months 12
        """,
    )
    parser.add_argument(
        "--regions",
        nargs="+",
        default=DEFAULT_REGIONS,
        metavar="REGION",
        help=f"수집 대상 지역 (기본값: {' '.join(DEFAULT_REGIONS)})",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=3,
        help="몇 개월 이전 데이터까지 수집할지 (기본값: 3, 공공API 전용)",
    )
    parser.add_argument(
        "--source",
        choices=["public", "naver", "all"],
        default="all",
        help="데이터 소스 선택: public(공공API) / naver(네이버) / all(모두, 기본값)",
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

    # 로그 레벨 적용
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    asyncio.run(
        main(
            regions=args.regions,
            months=args.months,
            source=args.source,
        )
    )
