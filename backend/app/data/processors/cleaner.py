"""
부동산 데이터 클리닝 모듈

수집된 원시 데이터의 결측치 처리, 이상치 제거, 타입 변환을 수행합니다.
"""

import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 가격 이상치 필터 기준 (만원 단위)
MIN_DEAL_AMOUNT = 100        # 100만원 이하 거래는 오류 데이터
MAX_DEAL_AMOUNT = 1_000_000  # 100억 이상 거래는 검토 필요 (오피스텔 등 예외)

# 면적 이상치 필터 (㎡)
MIN_AREA_SQM = 3.0    # 3㎡ 이하는 오류
MAX_AREA_SQM = 2000.0  # 2000㎡ 초과는 대형 건물

# 건축년도 범위
MIN_BUILT_YEAR = 1950
MAX_BUILT_YEAR = datetime.now().year + 2  # 분양 예정 포함


def normalize_region_code(code: str) -> str:
    """
    법정동 코드 정규화

    다양한 형식의 코드를 표준 형식으로 변환:
    - "11110" → "11110" (시군구, 5자리)
    - "1111010100" → "1111010100" (법정동, 10자리)
    - "11" → "11" (시도, 2자리)
    - "11 110" → "11110" (공백 제거)
    """
    if not code:
        return ""

    # 공백 제거
    cleaned = code.strip().replace(" ", "").replace("-", "")

    # 숫자만 추출
    numeric = re.sub(r"[^0-9]", "", cleaned)

    # 유효한 길이 확인 (2, 5, 10자리)
    if len(numeric) not in (2, 5, 10):
        logger.warning(f"Unusual region code length: {numeric} (original: {code})")

    return numeric


def _parse_date(date_value: Any) -> Optional[date]:
    """
    다양한 날짜 형식을 date 객체로 변환

    지원 형식:
    - "2025-03-15", "2025.03.15", "20250315"
    - "2025년 3월 15일"
    """
    if date_value is None:
        return None

    if isinstance(date_value, date):
        return date_value

    date_str = str(date_value).strip()

    # 한국어 날짜 형식
    korean_match = re.match(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", date_str)
    if korean_match:
        y, m, d = korean_match.groups()
        return date(int(y), int(m), int(d))

    # 구분자 제거 후 파싱
    date_str_clean = re.sub(r"[-./]", "", date_str)

    formats_to_try = [
        ("%Y%m%d", 8),
        ("%Y%m", 6),
    ]

    for fmt, expected_len in formats_to_try:
        if len(date_str_clean) == expected_len:
            try:
                parsed = datetime.strptime(date_str_clean, fmt)
                return parsed.date()
            except ValueError:
                continue

    logger.debug(f"Could not parse date: {date_value}")
    return None


def _is_valid_price(price: Optional[float]) -> bool:
    """가격 유효성 검사"""
    if price is None:
        return True  # None은 결측치로 허용
    return MIN_DEAL_AMOUNT <= price <= MAX_DEAL_AMOUNT


def _is_valid_area(area: Optional[float]) -> bool:
    """면적 유효성 검사"""
    if area is None:
        return True
    return MIN_AREA_SQM <= area <= MAX_AREA_SQM


def _is_valid_built_year(year: Optional[int]) -> bool:
    """건축년도 유효성 검사"""
    if year is None:
        return True
    return MIN_BUILT_YEAR <= year <= MAX_BUILT_YEAR


def clean_transaction_data(raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    실거래가 데이터 클리닝

    처리 사항:
    1. 결측치: deal_amount 없는 레코드 제거
    2. 이상치: 가격 범위 벗어난 레코드 제거
    3. 타입 변환: 문자열 → 숫자/날짜
    4. 지역 코드 정규화

    Args:
        raw_data: 공공API에서 수집한 원시 거래 데이터

    Returns:
        정제된 거래 데이터 리스트
    """
    cleaned = []
    removed_count = 0

    for idx, record in enumerate(raw_data):
        try:
            # 거래금액 필수값 확인
            deal_amount = record.get("deal_amount")
            if deal_amount is None:
                removed_count += 1
                continue

            # 숫자 변환
            try:
                deal_amount = float(str(deal_amount).replace(",", "").strip())
            except (ValueError, TypeError):
                removed_count += 1
                continue

            # 가격 이상치 확인
            if not _is_valid_price(deal_amount):
                logger.debug(f"Invalid price filtered: {deal_amount} at record {idx}")
                removed_count += 1
                continue

            # 면적 처리
            area_sqm = record.get("area_sqm")
            if area_sqm is not None:
                try:
                    area_sqm = float(area_sqm)
                    if not _is_valid_area(area_sqm):
                        area_sqm = None
                except (ValueError, TypeError):
                    area_sqm = None

            # 건축년도 처리
            built_year = record.get("built_year")
            if built_year is not None:
                try:
                    built_year = int(built_year)
                    if not _is_valid_built_year(built_year):
                        built_year = None
                except (ValueError, TypeError):
                    built_year = None

            # 층수 처리
            floor = record.get("floor")
            if floor is not None:
                try:
                    floor = int(floor)
                    if floor < 0 or floor > 200:
                        floor = None
                except (ValueError, TypeError):
                    floor = None

            # 날짜 파싱
            deal_date = _parse_date(record.get("deal_date"))

            # 지역 코드 정규화
            region_code = normalize_region_code(record.get("region_code", ""))

            cleaned.append(
                {
                    "region_code": region_code,
                    "region_name": str(record.get("region_name", record.get("dong_name", ""))),
                    "property_type": str(record.get("property_type", "기타")),
                    "deal_amount": deal_amount,
                    "area_sqm": area_sqm,
                    "deal_date": deal_date,
                    "floor": floor,
                    "built_year": built_year,
                    "source": str(record.get("source", "공공API")),
                }
            )

        except Exception as e:
            logger.warning(f"Error processing transaction record {idx}: {e}")
            removed_count += 1
            continue

    logger.info(
        f"Transaction cleaning complete: {len(cleaned)} valid, {removed_count} removed "
        f"(total={len(raw_data)})"
    )
    return cleaned


def clean_listing_data(raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    매물 데이터 클리닝

    처리 사항:
    1. 결측치: listing_price 없는 레코드 처리 (제거하지 않고 None 유지)
    2. 이상치: 비정상 가격/면적 필터링
    3. 타입 변환 및 정규화

    Args:
        raw_data: 네이버/공공API에서 수집한 원시 매물 데이터

    Returns:
        정제된 매물 데이터 리스트
    """
    cleaned = []
    removed_count = 0

    for idx, record in enumerate(raw_data):
        try:
            # listing_price 처리 (없어도 유지하되 이상치는 제거)
            listing_price = record.get("listing_price")
            if listing_price is not None:
                try:
                    listing_price = float(str(listing_price).replace(",", "").strip())
                    if not _is_valid_price(listing_price):
                        listing_price = None
                except (ValueError, TypeError):
                    listing_price = None

            # 전세가 처리
            jeonse_price = record.get("jeonse_price")
            if jeonse_price is not None:
                try:
                    jeonse_price = float(str(jeonse_price).replace(",", "").strip())
                    if not _is_valid_price(jeonse_price):
                        jeonse_price = None
                except (ValueError, TypeError):
                    jeonse_price = None

            # 실거래 참고가 처리
            actual_price = record.get("actual_price")
            if actual_price is not None:
                try:
                    actual_price = float(str(actual_price).replace(",", "").strip())
                    if not _is_valid_price(actual_price):
                        actual_price = None
                except (ValueError, TypeError):
                    actual_price = None

            # 가격 정보가 전혀 없으면 제외
            if listing_price is None and jeonse_price is None and actual_price is None:
                removed_count += 1
                continue

            # 면적 처리
            area_sqm = record.get("area_sqm")
            if area_sqm is not None:
                try:
                    area_sqm = float(area_sqm)
                    if not _is_valid_area(area_sqm):
                        area_sqm = None
                except (ValueError, TypeError):
                    area_sqm = None

            # 건축년도 처리
            built_year = record.get("built_year")
            if built_year is not None:
                try:
                    built_year = int(built_year)
                    if not _is_valid_built_year(built_year):
                        built_year = None
                except (ValueError, TypeError):
                    built_year = None

            # 층수 처리
            floor = record.get("floor")
            if floor is not None:
                try:
                    floor = int(floor)
                    if floor < 0 or floor > 200:
                        floor = None
                except (ValueError, TypeError):
                    floor = None

            # 등록일 파싱
            listed_at = _parse_date(record.get("listed_at"))

            # 지역 코드 정규화
            region_code = normalize_region_code(record.get("region_code", ""))

            cleaned.append(
                {
                    "region_code": region_code,
                    "region_name": str(record.get("region_name", "")),
                    "property_type": str(record.get("property_type", "기타")),
                    "listing_price": listing_price,
                    "actual_price": actual_price,
                    "jeonse_price": jeonse_price,
                    "area_sqm": area_sqm,
                    "floor": floor,
                    "built_year": built_year,
                    "listed_at": listed_at,
                    "source": str(record.get("source", "네이버")),
                }
            )

        except Exception as e:
            logger.warning(f"Error processing listing record {idx}: {e}")
            removed_count += 1
            continue

    logger.info(
        f"Listing cleaning complete: {len(cleaned)} valid, {removed_count} removed "
        f"(total={len(raw_data)})"
    )
    return cleaned
