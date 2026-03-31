"""
네이버 부동산 매물 수집기

네이버 부동산 비공개 API를 통해 매물 목록 수집
엔드포인트: https://new.land.naver.com/api/articles

주의: 네이버 부동산 API는 공개 API가 아니며 Rate Limit 준수 필요
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# 네이버 부동산 API 베이스 URL
NAVER_LAND_API_BASE = "https://new.land.naver.com/api"
ARTICLES_URL = f"{NAVER_LAND_API_BASE}/articles"

# 지역 코드 변환 (법정동 코드 → 네이버 cortarNo)
# 네이버는 자체 지역 코드 체계 사용
NAVER_CORTAR_MAP = {
    "11": "1100000000",   # 서울
    "26": "2600000000",   # 부산
    "27": "2700000000",   # 대구
    "28": "2800000000",   # 인천
    "29": "2900000000",   # 광주
    "30": "3000000000",   # 대전
    "31": "3100000000",   # 울산
    "36": "3600000000",   # 세종
    "41": "4100000000",   # 경기
    "42": "4200000000",   # 강원
    "43": "4300000000",   # 충북
    "44": "4400000000",   # 충남
    "45": "4500000000",   # 전북
    "46": "4600000000",   # 전남
    "47": "4700000000",   # 경북
    "48": "4800000000",   # 경남
    "50": "5000000000",   # 제주
}

# 매물 유형 코드 매핑
PROPERTY_TYPE_MAP = {
    "APT": "아파트",
    "ABYG": "아파트분양권",
    "OPST": "오피스텔",
    "VL": "빌라",
    "DDDGG": "단독/다가구",
}

# 요청 헤더 (네이버 부동산 웹 클라이언트 모사)
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://new.land.naver.com/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}


def _get_cortar_no(region_code: str) -> Optional[str]:
    """법정동 코드를 네이버 cortarNo로 변환"""
    # 시도 코드 (앞 2자리) 기준 매핑
    sido_code = region_code[:2]
    return NAVER_CORTAR_MAP.get(sido_code)


def _parse_article(article: Dict[str, Any], region_code: str) -> Dict[str, Any]:
    """
    네이버 부동산 매물 원본 데이터 파싱

    Args:
        article: API 응답의 개별 매물 항목
        region_code: 요청에 사용한 지역 코드

    Returns:
        정규화된 매물 딕셔너리
    """
    # 가격 파싱 (네이버는 억/만원 혼합 표기)
    def parse_naver_price(price_str: Optional[str]) -> Optional[float]:
        """'7억5000' → 75000 (만원 단위)"""
        if not price_str:
            return None
        try:
            price_str = price_str.replace(",", "").strip()
            if "억" in price_str:
                parts = price_str.split("억")
                eok = float(parts[0]) * 10000
                man = float(parts[1]) if parts[1] else 0
                return eok + man
            else:
                return float(price_str)
        except (ValueError, IndexError):
            return None

    # 매물 유형 변환
    article_type = article.get("realEstateTypeCode", "")
    property_type = PROPERTY_TYPE_MAP.get(article_type, article_type)

    return {
        "region_code": region_code,
        "region_name": article.get("cortarAddress", ""),
        "property_type": property_type,
        "listing_price": parse_naver_price(article.get("dealOrWarrantPrc")),
        "jeonse_price": parse_naver_price(article.get("warrantyPrice")),
        "area_sqm": float(article.get("area2", 0)) if article.get("area2") else None,
        "floor": int(article.get("floorInfo", "0").split("/")[0]) if article.get("floorInfo") else None,
        "article_name": article.get("articleName"),
        "article_no": article.get("articleNo"),
        "naver_url": f"https://new.land.naver.com/articles/{article.get('articleNo')}",
        "source": "네이버",
    }


async def fetch_listings(
    region_code: str,
    property_types: Optional[List[str]] = None,
    max_pages: int = 5,
) -> List[Dict[str, Any]]:
    """
    네이버 부동산 매물 목록 수집

    Args:
        region_code: 법정동 시도 코드 (2자리, 예: "11" = 서울)
        property_types: 수집할 매물 유형 리스트 (기본: ["APT", "VL", "OPST"])
        max_pages: 최대 페이지 수 (rate limit 방지)

    Returns:
        매물 딕셔너리 리스트
    """
    if property_types is None:
        property_types = ["APT", "VL", "OPST"]

    cortar_no = _get_cortar_no(region_code)
    if not cortar_no:
        logger.warning(f"No cortarNo mapping for region_code: {region_code}")
        return []

    all_listings = []

    async with httpx.AsyncClient(
        headers=DEFAULT_HEADERS,
        timeout=20.0,
        follow_redirects=True,
    ) as client:
        for rlet_type in property_types:
            page = 1
            while page <= max_pages:
                params = {
                    "cortarNo": cortar_no,
                    "order": "rank",
                    "realEstateType": rlet_type,
                    "tradeType": "",
                    "tag": ":::::::::",
                    "rentPriceMin": 0,
                    "rentPriceMax": 900000000,
                    "priceMin": 0,
                    "priceMax": 900000000,
                    "areaMin": 0,
                    "areaMax": 900000000,
                    "oldBuildYears": "",
                    "recentlyBuildYears": "",
                    "minHouseHoldCount": "",
                    "maxHouseHoldCount": "",
                    "showArticle": "false",
                    "sameAddressGroup": "false",
                    "minMaintenanceCost": "",
                    "maxMaintenanceCost": "",
                    "page": page,
                    "perPage": 20,
                }

                try:
                    resp = await client.get(ARTICLES_URL, params=params)

                    # 네이버 API는 인증 없이 접근 시 403 반환 가능
                    if resp.status_code == 403:
                        logger.warning(
                            f"Naver API returned 403 for region={region_code}, type={rlet_type}. "
                            "Consider adding authentication headers."
                        )
                        break

                    resp.raise_for_status()
                    data = resp.json()

                except httpx.HTTPStatusError as e:
                    logger.error(f"Naver API HTTP error: {e.response.status_code} for {rlet_type}")
                    break
                except httpx.RequestError as e:
                    logger.error(f"Naver API request error: {e}")
                    break
                except ValueError as e:
                    logger.error(f"Naver API JSON parse error: {e}")
                    break

                articles = data.get("articleList", [])
                if not articles:
                    logger.debug(f"No more articles for type={rlet_type} at page={page}")
                    break

                for article in articles:
                    parsed = _parse_article(article, region_code)
                    all_listings.append(parsed)

                # 페이지네이션 처리
                total_count = data.get("totalCount", 0)
                if page * 20 >= total_count:
                    break

                page += 1
                # Rate limit 방지: 요청 간 대기
                await asyncio.sleep(0.5)

    logger.info(
        f"Fetched {len(all_listings)} listings from Naver for region={region_code}"
    )
    return all_listings


async def fetch_jeonse_listings(
    region_code: str,
    property_types: Optional[List[str]] = None,
    max_pages: int = 5,
) -> List[Dict[str, Any]]:
    """
    네이버 부동산 전세 매물 수집 (전세가율 계산용)

    Args:
        region_code: 법정동 시도 코드
        property_types: 매물 유형 리스트
        max_pages: 최대 페이지 수

    Returns:
        전세 매물 딕셔너리 리스트 (trade_type="전세")
    """
    if property_types is None:
        property_types = ["APT", "VL"]

    cortar_no = _get_cortar_no(region_code)
    if not cortar_no:
        return []

    all_listings = []

    async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=20.0) as client:
        for rlet_type in property_types:
            page = 1
            while page <= max_pages:
                params = {
                    "cortarNo": cortar_no,
                    "order": "rank",
                    "realEstateType": rlet_type,
                    "tradeType": "B1",  # B1 = 전세
                    "tag": ":::::::::",
                    "rentPriceMin": 0,
                    "rentPriceMax": 900000000,
                    "priceMin": 0,
                    "priceMax": 900000000,
                    "areaMin": 0,
                    "areaMax": 900000000,
                    "page": page,
                    "perPage": 20,
                }

                try:
                    resp = await client.get(ARTICLES_URL, params=params)
                    if resp.status_code == 403:
                        break
                    resp.raise_for_status()
                    data = resp.json()
                except (httpx.HTTPError, ValueError) as e:
                    logger.error(f"Naver jeonse API error: {e}")
                    break

                articles = data.get("articleList", [])
                if not articles:
                    break

                for article in articles:
                    parsed = _parse_article(article, region_code)
                    parsed["trade_type"] = "전세"
                    all_listings.append(parsed)

                total_count = data.get("totalCount", 0)
                if page * 20 >= total_count:
                    break

                page += 1
                await asyncio.sleep(0.5)

    return all_listings
