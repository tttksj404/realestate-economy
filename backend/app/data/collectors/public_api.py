"""
공공데이터포털 국토교통부 실거래가 API 수집기

API 문서 (유형별 별도 인증키 사용):
- 아파트 매매 실거래가 (apt): https://www.data.go.kr/data/15058747/openapi.do
- 단독/다가구 매매 (small): https://www.data.go.kr/data/15058022/openapi.do
- 연립다세대 매매 (together): https://www.data.go.kr/data/15058038/openapi.do
- 오피스텔 매매 (office): https://www.data.go.kr/data/15058452/openapi.do
"""

import logging
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# 공공데이터포털 베이스 URL
BASE_URL = "https://apis.data.go.kr/1613000"

# API 엔드포인트 (유형별)
APARTMENT_TRADE_URL = f"{BASE_URL}/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"         # 아파트 (apt)
DETACHED_TRADE_URL = f"{BASE_URL}/RTMSDataSvcSHTrade/getRTMSDataSvcSHTrade"            # 단독/다가구 (small)
VILLA_TRADE_URL = f"{BASE_URL}/RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade"               # 연립다세대 (together)
OFFICETEL_TRADE_URL = f"{BASE_URL}/RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade"       # 오피스텔 (office)

# 한 번에 가져올 최대 건수
DEFAULT_NUM_OF_ROWS = 1000


def _parse_xml_response(xml_text: str) -> List[Dict[str, Any]]:
    """
    공공API XML 응답 파싱

    응답 구조:
    <response>
      <header><resultCode>00</resultCode>...</header>
      <body>
        <items>
          <item>...</item>
        </items>
        <totalCount>N</totalCount>
      </body>
    </response>
    """
    try:
        root = ET.fromstring(xml_text)

        # 응답 코드 확인
        result_code = root.findtext(".//resultCode", default="")
        if result_code != "00":
            result_msg = root.findtext(".//resultMsg", default="Unknown error")
            logger.error(f"API error: {result_code} - {result_msg}")
            return []

        items = root.findall(".//item")
        records = []
        for item in items:
            record = {}
            for child in item:
                record[child.tag] = child.text.strip() if child.text else None
            records.append(record)

        return records

    except ET.ParseError as e:
        logger.error(f"XML parse error: {e}. Response snippet: {xml_text[:500]}")
        return []


def _safe_float(value: Optional[str]) -> Optional[float]:
    """문자열을 float으로 변환 (콤마 제거, 공백 처리)"""
    if value is None:
        return None
    try:
        return float(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _safe_int(value: Optional[str]) -> Optional[int]:
    """문자열을 int로 변환"""
    if value is None:
        return None
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        return None


async def fetch_apartment_trades(
    region_code: str,
    year_month: str,
    page_no: int = 1,
) -> List[Dict[str, Any]]:
    """
    국토부 아파트 매매 실거래가 조회

    Args:
        region_code: 법정동 시군구코드 (5자리, 예: "11110" = 서울 종로구)
        year_month: 조회 연월 (YYYYMM, 예: "202503")
        page_no: 페이지 번호 (기본: 1)

    Returns:
        거래 내역 리스트. 각 항목:
        {
            "deal_amount": float,   # 거래금액 (만원)
            "area_sqm": float,      # 전용면적
            "deal_date": str,       # 거래일 (YYYY-MM-DD)
            "floor": int,
            "built_year": int,
            "apt_name": str,        # 아파트명
            "region_code": str,
            "property_type": str,   # 항상 "아파트"
        }
    """
    params = {
        "serviceKey": settings.PUBLIC_DATA_API_KEY_APT,
        "LAWD_CD": region_code,
        "DEAL_YMD": year_month,
        "numOfRows": DEFAULT_NUM_OF_ROWS,
        "pageNo": page_no,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(APARTMENT_TRADE_URL, params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Apartment trade API HTTP error: {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Apartment trade API request error: {e}")
            return []

    raw_items = _parse_xml_response(resp.text)
    result = []

    for item in raw_items:
        # 거래일 조합: 년 + 월 + 일
        year = item.get("년", "")
        month = str(item.get("월", "")).zfill(2)
        day = str(item.get("일", "")).zfill(2)
        deal_date = f"{year}-{month}-{day}" if year else None

        result.append(
            {
                "deal_amount": _safe_float(item.get("거래금액")),
                "area_sqm": _safe_float(item.get("전용면적")),
                "deal_date": deal_date,
                "floor": _safe_int(item.get("층")),
                "built_year": _safe_int(item.get("건축년도")),
                "apt_name": item.get("아파트"),
                "region_code": region_code,
                "dong_name": item.get("법정동"),
                "property_type": "아파트",
                "source": "공공API",
            }
        )

    logger.info(
        f"Fetched {len(result)} apartment trades for region={region_code}, period={year_month}"
    )
    return result


async def fetch_villa_trades(
    region_code: str,
    year_month: str,
    page_no: int = 1,
) -> List[Dict[str, Any]]:
    """
    국토부 연립다세대(빌라) 매매 실거래가 조회

    Args:
        region_code: 법정동 시군구코드 (5자리)
        year_month: 조회 연월 (YYYYMM)
        page_no: 페이지 번호

    Returns:
        거래 내역 리스트 (아파트와 동일 구조, property_type="빌라")
    """
    params = {
        "serviceKey": settings.PUBLIC_DATA_API_KEY_TOGETHER,
        "LAWD_CD": region_code,
        "DEAL_YMD": year_month,
        "numOfRows": DEFAULT_NUM_OF_ROWS,
        "pageNo": page_no,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(VILLA_TRADE_URL, params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Villa trade API HTTP error: {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Villa trade API request error: {e}")
            return []

    raw_items = _parse_xml_response(resp.text)
    result = []

    for item in raw_items:
        year = item.get("년", "")
        month = str(item.get("월", "")).zfill(2)
        day = str(item.get("일", "")).zfill(2)
        deal_date = f"{year}-{month}-{day}" if year else None

        result.append(
            {
                "deal_amount": _safe_float(item.get("거래금액")),
                "area_sqm": _safe_float(item.get("전용면적")),
                "deal_date": deal_date,
                "floor": _safe_int(item.get("층")),
                "built_year": _safe_int(item.get("건축년도")),
                "building_name": item.get("연립다세대"),
                "region_code": region_code,
                "dong_name": item.get("법정동"),
                "property_type": "빌라",
                "source": "공공API",
            }
        )

    logger.info(
        f"Fetched {len(result)} villa trades for region={region_code}, period={year_month}"
    )
    return result


async def fetch_detached_trades(
    region_code: str,
    year_month: str,
    page_no: int = 1,
) -> List[Dict[str, Any]]:
    """
    국토부 단독/다가구 매매 실거래가 조회

    Args:
        region_code: 법정동 시군구코드 (5자리)
        year_month: 조회 연월 (YYYYMM)
        page_no: 페이지 번호

    Returns:
        거래 내역 리스트 (property_type="단독다가구")
    """
    params = {
        "serviceKey": settings.PUBLIC_DATA_API_KEY_SMALL,
        "LAWD_CD": region_code,
        "DEAL_YMD": year_month,
        "numOfRows": DEFAULT_NUM_OF_ROWS,
        "pageNo": page_no,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(DETACHED_TRADE_URL, params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Detached trade API HTTP error: {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Detached trade API request error: {e}")
            return []

    raw_items = _parse_xml_response(resp.text)
    result = []

    for item in raw_items:
        year = item.get("년", "")
        month = str(item.get("월", "")).zfill(2)
        day = str(item.get("일", "")).zfill(2)
        deal_date = f"{year}-{month}-{day}" if year else None

        result.append(
            {
                "deal_amount": _safe_float(item.get("거래금액")),
                "area_sqm": _safe_float(item.get("대지면적") or item.get("연면적")),
                "deal_date": deal_date,
                "floor": None,  # 단독주택은 층 정보 없음
                "built_year": _safe_int(item.get("건축년도")),
                "building_name": item.get("주택유형"),
                "region_code": region_code,
                "dong_name": item.get("법정동"),
                "property_type": "단독다가구",
                "source": "공공API",
            }
        )

    logger.info(
        f"Fetched {len(result)} detached trades for region={region_code}, period={year_month}"
    )
    return result


async def fetch_officetel_trades(
    region_code: str,
    year_month: str,
    page_no: int = 1,
) -> List[Dict[str, Any]]:
    """
    국토부 오피스텔 매매 실거래가 조회

    Args:
        region_code: 법정동 시군구코드 (5자리)
        year_month: 조회 연월 (YYYYMM)
        page_no: 페이지 번호

    Returns:
        거래 내역 리스트 (property_type="오피스텔")
    """
    params = {
        "serviceKey": settings.PUBLIC_DATA_API_KEY_OFFICE,
        "LAWD_CD": region_code,
        "DEAL_YMD": year_month,
        "numOfRows": DEFAULT_NUM_OF_ROWS,
        "pageNo": page_no,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(OFFICETEL_TRADE_URL, params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Officetel trade API HTTP error: {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Officetel trade API request error: {e}")
            return []

    raw_items = _parse_xml_response(resp.text)
    result = []

    for item in raw_items:
        year = item.get("년", "")
        month = str(item.get("월", "")).zfill(2)
        day = str(item.get("일", "")).zfill(2)
        deal_date = f"{year}-{month}-{day}" if year else None

        result.append(
            {
                "deal_amount": _safe_float(item.get("거래금액")),
                "area_sqm": _safe_float(item.get("전용면적")),
                "deal_date": deal_date,
                "floor": _safe_int(item.get("층")),
                "built_year": _safe_int(item.get("건축년도")),
                "building_name": item.get("단지"),
                "region_code": region_code,
                "dong_name": item.get("법정동"),
                "property_type": "오피스텔",
                "source": "공공API",
            }
        )

    logger.info(
        f"Fetched {len(result)} officetel trades for region={region_code}, period={year_month}"
    )
    return result


async def fetch_all_trades(
    region_code: str,
    year_month: str,
) -> List[Dict[str, Any]]:
    """
    모든 유형의 실거래가를 한 번에 수집

    아파트 + 빌라 + 오피스텔 합산 반환
    """
    import asyncio

    apt, detached, villa, officetel = await asyncio.gather(
        fetch_apartment_trades(region_code, year_month),
        fetch_detached_trades(region_code, year_month),
        fetch_villa_trades(region_code, year_month),
        fetch_officetel_trades(region_code, year_month),
    )

    all_trades = apt + detached + villa + officetel
    logger.info(
        f"Total {len(all_trades)} trades fetched for region={region_code}, period={year_month}"
    )
    return all_trades
