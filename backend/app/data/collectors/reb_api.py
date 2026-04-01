"""
한국부동산원 R-ONE 부동산통계 API 수집기

API 문서: https://www.reb.or.kr/r-one/portal/openapi/openApiDevPage.do
인증키 발급: https://www.reb.or.kr/r-one/portal/openapi/openApiIntroPage.do

주요 통계표:
- A_2024_00178: (월) 지역별 매매지수_아파트
- A_2024_00182: (월) 지역별 전세지수_아파트
- A_2024_00188: (월) 지역별 매매 평균가격_아파트
- A_2024_00192: (월) 지역별 전세 평균가격_아파트
- T237973129847263: 미분양주택현황
- T244183132827305: (주) 매매가격지수
- T247713133046872: (주) 전세가격지수
- T248163133074619: (주) 매매수급동향
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://www.reb.or.kr/r-one/openapi"

# 통계표 ID
STAT_APT_SALE_INDEX_MONTHLY = "A_2024_00178"
STAT_APT_JEONSE_INDEX_MONTHLY = "A_2024_00182"
STAT_APT_SALE_AVG_PRICE = "A_2024_00188"
STAT_APT_JEONSE_AVG_PRICE = "A_2024_00192"
STAT_UNSOLD_HOUSING = "T237973129847263"
STAT_WEEKLY_SALE_INDEX = "T244183132827305"
STAT_WEEKLY_JEONSE_INDEX = "T247713133046872"
STAT_WEEKLY_SUPPLY_DEMAND = "T248163133074619"

# R-ONE CLS_FULLNM → 지역코드 매핑
REGION_CLS_MAP = {
    "전국": "00",
    "서울": "11",
    "부산": "26",
    "대구": "27",
    "인천": "28",
    "광주": "29",
    "대전": "30",
    "울산": "31",
    "세종": "36",
    "경기": "41",
    "수도권": "SU",
    "지방": "LO",
}


async def _fetch_reb_data(
    statbl_id: str,
    dtacycle_cd: str,
    wrttime: str,
    p_size: int = 300,
) -> List[Dict[str, Any]]:
    """
    R-ONE API 공통 호출

    Args:
        statbl_id: 통계표 ID
        dtacycle_cd: 데이터 주기 (MM, WK, YY 등)
        wrttime: 조회 기간 (YYYYMM 또는 YYYYWW)
        p_size: 페이지 크기

    Returns:
        row 데이터 리스트
    """
    if not settings.KOREA_REAL_ESTATE_KEY:
        logger.warning("KOREA_REAL_ESTATE_KEY not set, skipping R-ONE API")
        return []

    params = {
        "KEY": settings.KOREA_REAL_ESTATE_KEY,
        "STATBL_ID": statbl_id,
        "DTACYCLE_CD": dtacycle_cd,
        "WRTTIME_IDTFR_ID": wrttime,
        "Type": "json",
        "pSize": p_size,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(f"{BASE_URL}/SttsApiTblData.do", params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"R-ONE API HTTP error: {e.response.status_code} for {statbl_id}")
            return []
        except httpx.RequestError as e:
            logger.error(f"R-ONE API request error: {e}")
            return []

    try:
        data = resp.json()
        tbl = data.get("SttsApiTblData", [])
        if len(tbl) < 2:
            return []

        head = tbl[0].get("head", [])
        if head and len(head) > 1:
            result = head[1].get("RESULT", {})
            if result.get("CODE") != "INFO-000":
                logger.warning(f"R-ONE API warning: {result}")
                return []

        return tbl[1].get("row", [])
    except Exception as e:
        logger.error(f"R-ONE API parse error: {e}")
        return []


def _extract_region_code(cls_fullnm: str) -> Optional[str]:
    """CLS_FULLNM에서 지역코드 추출 (예: '서울>도심권' → '11')"""
    if not cls_fullnm:
        return None
    top_region = cls_fullnm.split(">")[0].strip()
    # '계' 제거 (미분양: '서울>계' → '서울')
    top_region = top_region.replace(">계", "").strip()
    return REGION_CLS_MAP.get(top_region)


async def fetch_apt_sale_index(period: str) -> List[Dict[str, Any]]:
    """
    (월) 아파트 매매가격지수 조회

    Args:
        period: YYYYMM (예: "202601")

    Returns:
        [{"region_code": "11", "region_name": "서울", "value": 129.7, "period": "2026년 1월"}, ...]
    """
    rows = await _fetch_reb_data(STAT_APT_SALE_INDEX_MONTHLY, "MM", period)
    results = []
    for row in rows:
        region_code = _extract_region_code(row.get("CLS_FULLNM", ""))
        if region_code and row.get("ITM_NM") == "지수":
            results.append({
                "region_code": region_code,
                "region_name": row.get("CLS_FULLNM", "").split(">")[0],
                "sale_index": float(row["DTA_VAL"]) if row.get("DTA_VAL") is not None else None,
                "period": row.get("WRTTIME_DESC", period),
            })
    logger.info(f"Fetched {len(results)} apt sale index records for {period}")
    return results


async def fetch_apt_jeonse_index(period: str) -> List[Dict[str, Any]]:
    """(월) 아파트 전세가격지수 조회"""
    rows = await _fetch_reb_data(STAT_APT_JEONSE_INDEX_MONTHLY, "MM", period)
    results = []
    for row in rows:
        region_code = _extract_region_code(row.get("CLS_FULLNM", ""))
        if region_code and row.get("ITM_NM") == "지수":
            results.append({
                "region_code": region_code,
                "region_name": row.get("CLS_FULLNM", "").split(">")[0],
                "jeonse_index": float(row["DTA_VAL"]) if row.get("DTA_VAL") is not None else None,
                "period": row.get("WRTTIME_DESC", period),
            })
    logger.info(f"Fetched {len(results)} apt jeonse index records for {period}")
    return results


async def fetch_apt_avg_prices(period: str) -> List[Dict[str, Any]]:
    """
    (월) 아파트 매매/전세 평균가격 조회

    매매 + 전세를 합쳐서 전세가율 계산 가능하도록 반환
    """
    sale_rows = await _fetch_reb_data(STAT_APT_SALE_AVG_PRICE, "MM", period)
    jeonse_rows = await _fetch_reb_data(STAT_APT_JEONSE_AVG_PRICE, "MM", period)

    # 매매 평균가 취합
    sale_map: Dict[str, float] = {}
    for row in sale_rows:
        region_code = _extract_region_code(row.get("CLS_FULLNM", ""))
        if region_code and row.get("DTA_VAL") is not None:
            sale_map[region_code] = float(row["DTA_VAL"])

    # 전세 평균가 취합
    jeonse_map: Dict[str, float] = {}
    for row in jeonse_rows:
        region_code = _extract_region_code(row.get("CLS_FULLNM", ""))
        if region_code and row.get("DTA_VAL") is not None:
            jeonse_map[region_code] = float(row["DTA_VAL"])

    results = []
    for region_code in sale_map:
        sale_avg = sale_map.get(region_code)
        jeonse_avg = jeonse_map.get(region_code)
        jeonse_ratio = None
        if sale_avg and jeonse_avg and sale_avg > 0:
            jeonse_ratio = round((jeonse_avg / sale_avg) * 100, 2)

        results.append({
            "region_code": region_code,
            "sale_avg_price": sale_avg,
            "jeonse_avg_price": jeonse_avg,
            "jeonse_ratio": jeonse_ratio,
            "period": period,
        })

    logger.info(f"Fetched {len(results)} avg price records for {period}")
    return results


async def fetch_unsold_housing(period: str) -> List[Dict[str, Any]]:
    """
    (월) 미분양주택현황 조회

    Returns:
        [{"region_code": "11", "region_name": "서울", "unsold_count": 914, "period": ...}, ...]
    """
    rows = await _fetch_reb_data(STAT_UNSOLD_HOUSING, "MM", period)
    results = []
    for row in rows:
        cls = row.get("CLS_FULLNM", "")
        # '서울>계' 패턴에서 시도 단위만 추출
        if ">계" not in cls and "계" not in row.get("CLS_NM", ""):
            continue
        top_region = cls.split(">")[0].strip()
        region_code = REGION_CLS_MAP.get(top_region)
        if region_code and row.get("DTA_VAL") is not None:
            results.append({
                "region_code": region_code,
                "region_name": top_region,
                "unsold_count": int(float(row["DTA_VAL"])),
                "period": row.get("WRTTIME_DESC", period),
            })
    logger.info(f"Fetched {len(results)} unsold housing records for {period}")
    return results


async def fetch_weekly_supply_demand(period: str) -> List[Dict[str, Any]]:
    """
    (주) 매매수급동향 조회

    100 초과: 수요 > 공급 (호황)
    100 미만: 공급 > 수요 (침체)

    Args:
        period: YYYYWW 형식 (예: "202613" = 2026년 13주차)
    """
    rows = await _fetch_reb_data(STAT_WEEKLY_SUPPLY_DEMAND, "WK", period)
    results = []
    seen = set()
    for row in rows:
        region_code = _extract_region_code(row.get("CLS_FULLNM", ""))
        if region_code and region_code not in seen and row.get("DTA_VAL") is not None:
            seen.add(region_code)
            results.append({
                "region_code": region_code,
                "region_name": row.get("CLS_FULLNM", "").split(">")[0],
                "supply_demand_index": float(row["DTA_VAL"]),
                "date": row.get("WRTTIME_DESC", ""),
            })
    logger.info(f"Fetched {len(results)} supply-demand records for {period}")
    return results


async def fetch_all_reb_monthly(period: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    R-ONE 월간 데이터 일괄 수집

    Args:
        period: YYYYMM

    Returns:
        {
            "sale_index": [...],
            "jeonse_index": [...],
            "avg_prices": [...],
            "unsold": [...],
        }
    """
    import asyncio

    sale_idx, jeonse_idx, avg_prices, unsold = await asyncio.gather(
        fetch_apt_sale_index(period),
        fetch_apt_jeonse_index(period),
        fetch_apt_avg_prices(period),
        fetch_unsold_housing(period),
    )

    return {
        "sale_index": sale_idx,
        "jeonse_index": jeonse_idx,
        "avg_prices": avg_prices,
        "unsold": unsold,
    }
