from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RealEstateListing(Base):
    """
    부동산 매물 현황 테이블

    공공API 및 네이버 부동산 크롤링을 통해 수집된 현재 매물 정보
    """

    __tablename__ = "real_estate_listings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 지역 정보 (법정동 코드)
    region_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    region_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # 매물 유형: 아파트/빌라/오피스텔
    property_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # 가격 정보 (단위: 만원)
    listing_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)    # 호가
    actual_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)     # 실거래가 참고
    jeonse_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)     # 전세가

    # 물건 정보
    area_sqm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)   # 전용면적 (㎡)
    floor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)       # 층
    built_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 건축연도

    # 매물 등록일
    listed_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)

    # 데이터 출처: 공공API / 네이버
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="공공API")

    # 메타
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RealEstateTransaction(Base):
    """
    부동산 실거래가 테이블

    국토교통부 실거래가 공개시스템 API에서 수집된 실제 거래 내역
    """

    __tablename__ = "real_estate_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 지역 정보
    region_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    region_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # 매물 유형
    property_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # 거래금액 (단위: 만원)
    deal_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)

    # 물건 정보
    area_sqm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deal_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    floor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    built_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 데이터 출처
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="공공API")

    # 메타
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EconomyIndicator(Base):
    """
    부동산 경제 지표 테이블

    지역별/기간별 계산된 6개 핵심 지표 및 AI 경제 신호
    """

    __tablename__ = "economy_indicators"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 지역 정보
    region_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    region_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # 분석 기준 연월 (YYYYMM)
    period: Mapped[str] = mapped_column(String(6), nullable=False, index=True)

    # 6개 핵심 지표
    low_price_listing_ratio: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="저가 매물 비율 (%): 시세 대비 5% 이상 저렴한 매물 비중"
    )
    listing_count_change: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="매물 증감률 (%): 전월 대비 신규 매물 증감"
    )
    price_gap_ratio: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="호가/실거래가 괴리율 (%): 호가와 실거래가 차이"
    )
    regional_price_index: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="지역 가격지수 변동 (%): 전월 대비 평균 거래가 변동"
    )
    sale_speed: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="매물 소진 기간 (일): 등록~거래 완료까지 평균 일수"
    )
    jeonse_ratio: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="전세가율 (%): 매매가 대비 전세가 비율"
    )

    # 경제 신호 판정: 호황/보통/침체
    signal: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True, index=True, comment="경제 신호: 호황/보통/침체"
    )
    # 신호 신뢰도 (0.0 ~ 1.0)
    confidence: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="신호 신뢰도 (0.0~1.0)"
    )

    # 메타
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
