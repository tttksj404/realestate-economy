"""
온비드(캠코/한국자산관리공사) 공매 물건 수집기

온비드 공공데이터 API를 통해 부동산 공매 정보를 수집합니다.
공매 물건 증가 = 부실채권 증가 = 경기 침체 시그널

API 문서: https://openapi.onbid.co.kr
- 물건 검색: /openapi/services/KamcoPblctCltrSvc/getKamcoPblctCltrList
"""

import asyncio
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

ONBID_BASE_URL = "https://openapi.onbid.co.kr/openapi/services"

# 물건 용도 코드 (부동산 관련)
PROPERTY_USAGE_CODES = {
    "0001": "아파트",
    "0002": "연립/다세대",
    "0003": "단독주택",
    "0004": "오피스텔",
    "0005": "상가",
    "0006": "토지",
    "0007": "공장",
}

# 시도 코드 → 지역명 매핑
SIDO_CODES = {
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


async def fetch_onbid_properties(
    region_code: str = "",
    property_type: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
) -> List[Dict[str, Any]]:
    """
    온비드 공매 물건 목록 조회

    Args:
        region_code: 시도 코드 (예: "11" = 서울)
        property_type: 물건 용도 코드
        start_date: 공매 시작일 (YYYYMMDD)
        end_date: 공매 종료일 (YYYYMMDD)
        page: 페이지 번호
        page_size: 페이지 크기

    Returns:
        공매 물건 리스트
    """
    if not settings.ONBID_API_KEY:
        logger.warning("ONBID_API_KEY가 설정되지 않았습니다.")
        return []

    params = {
        "serviceKey": settings.ONBID_API_KEY,
        "numOfRows": str(page_size),
        "pageNo": str(page),
    }

    if region_code:
        params["SIDO"] = region_code
    if property_type:
        params["CLTR_MNMT_NO_CD"] = property_type
    if start_date:
        params["DPSL_DT_FROM"] = start_date
    if end_date:
        params["DPSL_DT_TO"] = end_date

    url = f"{ONBID_BASE_URL}/KamcoPblctCltrSvc/getKamcoPblctCltrList"

    results = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

            root = ElementTree.fromstring(response.text)

            # 응답 코드 확인
            result_code = root.findtext(".//resultCode", "")
            if result_code != "00":
                result_msg = root.findtext(".//resultMsg", "알 수 없는 오류")
                logger.error("온비드 API 오류: %s - %s", result_code, result_msg)
                return []

            items = root.findall(".//item")
            for item in items:
                record = _parse_onbid_item(item, region_code)
                if record:
                    results.append(record)

            total_count = int(root.findtext(".//totalCount", "0"))
            logger.info(
                "온비드 공매 조회: region=%s, page=%d, 결과=%d건 (전체 %d건)",
                region_code, page, len(results), total_count,
            )

    except httpx.HTTPStatusError as e:
        logger.error("온비드 API HTTP 오류: %s", e)
    except httpx.TimeoutException:
        logger.error("온비드 API 타임아웃: region=%s", region_code)
    except ElementTree.ParseError as e:
        logger.error("온비드 API XML 파싱 오류: %s", e)
    except Exception as e:
        logger.error("온비드 API 예기치 않은 오류: %s", e, exc_info=True)

    return results


def _parse_onbid_item(item: ElementTree.Element, default_region: str = "") -> Optional[Dict[str, Any]]:
    """온비드 XML item을 딕셔너리로 파싱"""
    try:
        # 감정가 / 최저입찰가
        appraisal_price = _safe_float(item.findtext("APSL_ASES_AVG_AMT", "0"))
        min_bid_price = _safe_float(item.findtext("MIN_BID_AMT", "0"))

        # 물건 정보
        cltr_nm = item.findtext("CLTR_NM", "")  # 물건명
        cltr_no = item.findtext("CLTR_NO", "")  # 물건번호
        cltr_mnmt_no = item.findtext("CLTR_MNMT_NO", "")  # 물건관리번호

        # 용도 판별
        usage_cd = item.findtext("GOODS_NM_CD", "")
        property_type = PROPERTY_USAGE_CODES.get(usage_cd, "기타")

        # 지역 정보
        sido = item.findtext("SIDO", default_region)
        addr = item.findtext("LDNM_ADRS", "")  # 소재지

        # 면적
        area = _safe_float(item.findtext("TFAREA", "0"))

        # 공매 일정
        dpsl_dt = item.findtext("DPSL_DT", "")  # 처분일자
        pbct_dt = item.findtext("PBCT_DT", "")  # 공고일자

        # 유찰 횟수 (유찰이 많을수록 경기 침체 시그널)
        fail_cnt = _safe_int(item.findtext("PBCT_CNT", "0"))

        # 낙찰가율 (감정가 대비)
        bid_ratio = 0.0
        if appraisal_price and min_bid_price:
            bid_ratio = round(min_bid_price / appraisal_price * 100, 2)

        return {
            "cltr_no": cltr_no,
            "cltr_mnmt_no": cltr_mnmt_no,
            "cltr_nm": cltr_nm,
            "property_type": property_type,
            "region_code": sido,
            "address": addr,
            "appraisal_price": appraisal_price,  # 감정가 (만원)
            "min_bid_price": min_bid_price,  # 최저입찰가 (만원)
            "bid_ratio": bid_ratio,  # 낙찰가율 (%)
            "area_sqm": area,
            "disposal_date": dpsl_dt,
            "announcement_date": pbct_dt,
            "fail_count": fail_cnt,  # 유찰 횟수
            "source": "온비드",
        }
    except Exception as e:
        logger.warning("온비드 항목 파싱 실패: %s", e)
        return None


def _safe_float(value: str) -> float:
    """안전한 float 변환"""
    try:
        cleaned = value.replace(",", "").strip()
        return float(cleaned) if cleaned else 0.0
    except (ValueError, AttributeError):
        return 0.0


def _safe_int(value: str) -> int:
    """안전한 int 변환"""
    try:
        cleaned = value.replace(",", "").strip()
        return int(cleaned) if cleaned else 0
    except (ValueError, AttributeError):
        return 0


async def fetch_all_onbid_properties(
    regions: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    전체 지역 온비드 공매 물건 일괄 수집

    Args:
        regions: 시도 코드 리스트 (None이면 전체)
        start_date: 시작일 (YYYYMMDD)
        end_date: 종료일 (YYYYMMDD)

    Returns:
        전체 공매 물건 리스트
    """
    target_regions = regions or list(SIDO_CODES.keys())
    all_results: List[Dict[str, Any]] = []

    for region_code in target_regions:
        page = 1
        while True:
            items = await fetch_onbid_properties(
                region_code=region_code,
                start_date=start_date,
                end_date=end_date,
                page=page,
                page_size=100,
            )
            all_results.extend(items)

            if len(items) < 100:
                break
            page += 1
            await asyncio.sleep(0.5)  # rate limiting

        logger.info("온비드 %s 수집 완료: %d건", SIDO_CODES.get(region_code, region_code), len(all_results))

    return all_results
