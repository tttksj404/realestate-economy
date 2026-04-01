"""
부동산 경제 지표 피처 엔지니어링 모듈

6개 핵심 지표를 계산하여 시장 상황을 수치화합니다.

지표 설명:
1. 저가 매물 비율: 시세 대비 5% 이상 저렴한 매물 비중 → 높을수록 침체 신호
2. 매물 증감률: 전월 대비 신규 매물 증감 → 증가하면 공급 증가 (침체 신호)
3. 호가/실거래가 괴리율: 호가와 실거래가 차이 → 클수록 거래 침체
4. 지역 가격지수 변동: 전월 대비 평균 거래가 변동 → 음수면 침체
5. 매물 소진 기간: 등록~거래 완료까지 평균 일수 → 길수록 침체
6. 전세가율: 매매가 대비 전세가 비율 → 높을수록 투자 리스크
"""

import logging
import statistics
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _get_period_dates(period: str) -> Tuple[date, date]:
    """
    YYYYMM 형식 기간을 시작일/종료일로 변환

    Args:
        period: "202503" 형식

    Returns:
        (시작일, 종료일) 튜플
    """
    year = int(period[:4])
    month = int(period[4:6])

    start = date(year, month, 1)
    # 월 마지막 날 계산
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)

    return start, end


def _get_prev_period(period: str) -> str:
    """
    전월 기간 반환

    Args:
        period: "202503" → "202502"
    """
    year = int(period[:4])
    month = int(period[4:6])

    if month == 1:
        return f"{year - 1}12"
    else:
        return f"{year}{str(month - 1).zfill(2)}"


def compute_low_price_listing_ratio(
    listings: List[Dict[str, Any]],
    region: str,
    period: str,
    discount_threshold: float = 0.05,
) -> Optional[float]:
    """
    저가 매물 비율 계산

    시세(= 해당 지역 동일 유형 매물 중앙값) 대비 discount_threshold 이상 저렴한
    매물의 비율을 반환합니다.

    Args:
        listings: 매물 데이터 리스트
        region: 지역 코드
        period: 분석 기준 연월
        discount_threshold: 저가 기준 (기본 5%)

    Returns:
        저가 매물 비율 (0.0 ~ 100.0, %)
    """
    region_listings = [
        l for l in listings
        if l.get("region_code", "").startswith(region)
        and l.get("listing_price") is not None
    ]

    if len(region_listings) < 3:
        logger.debug(f"Insufficient listings for low_price_ratio: {len(region_listings)}")
        return None

    prices = [l["listing_price"] for l in region_listings]
    median_price = statistics.median(prices)

    if median_price == 0:
        return None

    threshold_price = median_price * (1 - discount_threshold)
    low_price_count = sum(1 for p in prices if p <= threshold_price)

    ratio = (low_price_count / len(prices)) * 100
    return round(ratio, 2)


def compute_listing_count_change(
    current_listings: List[Dict[str, Any]],
    prev_listings: List[Dict[str, Any]],
    region: str,
) -> Optional[float]:
    """
    매물 증감률 계산

    전월 대비 현재월 매물 수 증감률

    Args:
        current_listings: 현재월 매물 리스트
        prev_listings: 전월 매물 리스트
        region: 지역 코드

    Returns:
        증감률 (%, 양수=증가, 음수=감소)
    """
    current_count = sum(
        1 for l in current_listings
        if l.get("region_code", "").startswith(region)
    )
    prev_count = sum(
        1 for l in prev_listings
        if l.get("region_code", "").startswith(region)
    )

    if prev_count == 0:
        logger.debug(f"No previous listings for region {region}")
        return None

    change_rate = ((current_count - prev_count) / prev_count) * 100
    return round(change_rate, 2)


def compute_price_gap_ratio(
    listings: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
    region: str,
) -> Optional[float]:
    """
    호가/실거래가 괴리율 계산

    (매물 호가 평균 - 실거래가 평균) / 실거래가 평균 × 100

    Args:
        listings: 매물 데이터 (호가 포함)
        transactions: 실거래가 데이터
        region: 지역 코드

    Returns:
        괴리율 (%, 양수=호가가 더 높음)
    """
    listing_prices = [
        l["listing_price"]
        for l in listings
        if l.get("region_code", "").startswith(region)
        and l.get("listing_price") is not None
    ]

    tx_amounts = [
        t["deal_amount"]
        for t in transactions
        if t.get("region_code", "").startswith(region)
        and t.get("deal_amount") is not None
    ]

    if not listing_prices or not tx_amounts:
        return None

    avg_listing = statistics.mean(listing_prices)
    avg_actual = statistics.mean(tx_amounts)

    if avg_actual == 0:
        return None

    gap_ratio = ((avg_listing - avg_actual) / avg_actual) * 100
    return round(gap_ratio, 2)


def compute_regional_price_index(
    current_transactions: List[Dict[str, Any]],
    prev_transactions: List[Dict[str, Any]],
    region: str,
) -> Optional[float]:
    """
    지역 가격지수 변동 계산

    전월 대비 현재월 평균 거래가 변동률

    Args:
        current_transactions: 현재월 실거래가 데이터
        prev_transactions: 전월 실거래가 데이터
        region: 지역 코드

    Returns:
        가격지수 변동률 (%, 양수=상승, 음수=하락)
    """
    current_amounts = [
        t["deal_amount"]
        for t in current_transactions
        if t.get("region_code", "").startswith(region)
        and t.get("deal_amount") is not None
    ]

    prev_amounts = [
        t["deal_amount"]
        for t in prev_transactions
        if t.get("region_code", "").startswith(region)
        and t.get("deal_amount") is not None
    ]

    if not current_amounts or not prev_amounts:
        return None

    # 면적 보정: ㎡당 단가로 비교 (면적 데이터 있는 경우)
    current_per_sqm = []
    for t in current_transactions:
        if t.get("region_code", "").startswith(region) and t.get("deal_amount") and t.get("area_sqm"):
            current_per_sqm.append(t["deal_amount"] / t["area_sqm"])

    prev_per_sqm = []
    for t in prev_transactions:
        if t.get("region_code", "").startswith(region) and t.get("deal_amount") and t.get("area_sqm"):
            prev_per_sqm.append(t["deal_amount"] / t["area_sqm"])

    if current_per_sqm and prev_per_sqm:
        current_avg = statistics.mean(current_per_sqm)
        prev_avg = statistics.mean(prev_per_sqm)
    else:
        current_avg = statistics.mean(current_amounts)
        prev_avg = statistics.mean(prev_amounts)

    if prev_avg == 0:
        return None

    change_rate = ((current_avg - prev_avg) / prev_avg) * 100
    return round(change_rate, 2)


def compute_sale_speed(
    listings: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
    region: str,
    period: str,
) -> Optional[float]:
    """
    매물 소진 기간 계산 (일)

    매물 등록일부터 거래 완료까지 평균 일수를 추정합니다.
    직접적인 매칭이 어렵기 때문에, 당월 거래 완료 건수 대비
    잔여 매물 수를 통해 소진 기간을 역산합니다.

    공식: 소진 기간 = (잔여 매물 수 / 당월 거래 건수) × 30일

    Args:
        listings: 현재 매물 리스트
        transactions: 당월 실거래가 리스트
        region: 지역 코드
        period: 분석 기준 연월

    Returns:
        매물 소진 기간 (일)
    """
    region_listings = [
        l for l in listings
        if l.get("region_code", "").startswith(region)
    ]

    start, end = _get_period_dates(period)
    region_transactions = [
        t for t in transactions
        if t.get("region_code", "").startswith(region)
        and t.get("deal_date") is not None
        and start <= t["deal_date"] <= end
    ]

    if not region_transactions:
        return None

    listing_count = len(region_listings)
    tx_count = len(region_transactions)

    if tx_count == 0:
        return None

    # 소진 기간 = 잔여 매물 수 / 월간 거래 수 × 30일
    sale_speed = (listing_count / tx_count) * 30
    return round(sale_speed, 1)


def compute_jeonse_ratio(
    transactions: List[Dict[str, Any]],
    jeonse_listings: List[Dict[str, Any]],
    region: str,
) -> Optional[float]:
    """
    전세가율 계산 (%)

    (전세가 평균 / 매매가 평균) × 100

    70% 이상: 갭투자 위험 높음
    60~70%: 정상 범위
    60% 미만: 매매 강세 (호황 신호)

    Args:
        transactions: 매매 실거래가 데이터
        jeonse_listings: 전세 매물 데이터
        region: 지역 코드

    Returns:
        전세가율 (%, 0~100)
    """
    sale_amounts = [
        t["deal_amount"]
        for t in transactions
        if t.get("region_code", "").startswith(region)
        and t.get("deal_amount") is not None
    ]

    jeonse_prices = [
        l.get("jeonse_price") or l.get("listing_price")
        for l in jeonse_listings
        if l.get("region_code", "").startswith(region)
        and (l.get("jeonse_price") or l.get("listing_price")) is not None
    ]

    if not sale_amounts or not jeonse_prices:
        return None

    avg_sale = statistics.mean(sale_amounts)
    avg_jeonse = statistics.mean(jeonse_prices)

    if avg_sale == 0:
        return None

    ratio = (avg_jeonse / avg_sale) * 100
    return round(min(ratio, 100.0), 2)  # 100% 상한 처리


def compute_all_indicators(
    region: str,
    period: str,
    current_listings: List[Dict[str, Any]],
    prev_listings: List[Dict[str, Any]],
    current_transactions: List[Dict[str, Any]],
    prev_transactions: List[Dict[str, Any]],
    jeonse_listings: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Optional[float]]:
    """
    6개 핵심 지표 전체 계산 (레거시 — 매물 데이터 기반)

    매물(호가) 데이터가 없으면 대부분 None 반환.
    R-ONE 기반 compute_all_indicators_v2를 사용 권장.
    """
    logger.info(f"Computing all indicators (legacy) for region={region}, period={period}")

    if jeonse_listings is None:
        jeonse_listings = [
            l for l in current_listings
            if l.get("jeonse_price") is not None
        ]

    indicators = {
        "low_price_listing_ratio": compute_low_price_listing_ratio(
            current_listings, region, period
        ),
        "listing_count_change": compute_listing_count_change(
            current_listings, prev_listings, region
        ),
        "price_gap_ratio": compute_price_gap_ratio(
            current_listings, current_transactions, region
        ),
        "regional_price_index": compute_regional_price_index(
            current_transactions, prev_transactions, region
        ),
        "sale_speed": compute_sale_speed(
            current_listings, current_transactions, region, period
        ),
        "jeonse_ratio": compute_jeonse_ratio(
            current_transactions, jeonse_listings, region
        ),
    }

    return indicators


# =============================================================================
# V2 지표: R-ONE 공식 통계 + 국토부 실거래 + 온비드 공매 기반
# =============================================================================


def compute_sale_index_change(
    current_index: Optional[float],
    prev_index: Optional[float],
) -> Optional[float]:
    """
    매매가격지수 변동률 (R-ONE 공식 지수 기반)

    전월 대비 변동률 = (당월지수 - 전월지수) / 전월지수 × 100
    양수 = 상승, 음수 = 하락
    """
    if current_index is None or prev_index is None or prev_index == 0:
        return None
    return round(((current_index - prev_index) / prev_index) * 100, 3)


def compute_jeonse_ratio_v2(
    sale_avg: Optional[float],
    jeonse_avg: Optional[float],
) -> Optional[float]:
    """
    전세가율 (R-ONE 공식 평균가격 기반)

    전세가율 = 전세평균가 / 매매평균가 × 100
    높을수록 갭투자 위험, 매매 약세
    """
    if sale_avg is None or jeonse_avg is None or sale_avg == 0:
        return None
    return round((jeonse_avg / sale_avg) * 100, 2)


def compute_unsold_change(
    current_unsold: Optional[int],
    prev_unsold: Optional[int],
) -> Optional[float]:
    """
    미분양 증감률

    전월 대비 미분양 주택 수 변동률
    양수 = 미분양 증가 (침체), 음수 = 미분양 감소 (호황)
    """
    if current_unsold is None or prev_unsold is None or prev_unsold == 0:
        return None
    return round(((current_unsold - prev_unsold) / prev_unsold) * 100, 2)


def compute_tx_count_change(
    current_count: int,
    prev_count: int,
) -> Optional[float]:
    """
    거래량 변동률 (국토부 실거래 건수 기반)

    전월 대비 실거래 건수 변동률
    양수 = 거래 증가 (호황), 음수 = 거래 감소 (침체)
    """
    if prev_count == 0:
        return None
    return round(((current_count - prev_count) / prev_count) * 100, 2)


def compute_supply_demand_score(
    supply_demand_index: Optional[float],
) -> Optional[float]:
    """
    매매수급동향 점수 (R-ONE 주간 수급지수)

    원본: 0~200, 100 = 균형
    변환: 100 초과 = 수요 우위 (호황), 100 미만 = 공급 우위 (침체)
    그대로 반환 (100 기준으로 해석)
    """
    if supply_demand_index is None:
        return None
    return round(supply_demand_index, 2)


def compute_auction_change(
    current_auction_count: int,
    prev_auction_count: int,
) -> Optional[float]:
    """
    공매 물건 증감률 (온비드 데이터)

    전월 대비 공매 물건 수 변동률
    양수 = 공매 증가 (침체), 음수 = 공매 감소 (호황)
    """
    if prev_auction_count == 0:
        return None
    return round(((current_auction_count - prev_auction_count) / prev_auction_count) * 100, 2)


def compute_all_indicators_v2(
    region: str,
    period: str,
    reb_data: Dict[str, Any],
    prev_reb_data: Dict[str, Any],
    current_tx_count: int,
    prev_tx_count: int,
    current_auction_count: int = 0,
    prev_auction_count: int = 0,
) -> Dict[str, Optional[float]]:
    """
    V2 지표 체계: R-ONE 공식 통계 기반 6개 핵심 지표

    Args:
        region: 지역 코드 (2자리)
        period: YYYYMM
        reb_data: R-ONE 당월 데이터 (fetch_all_reb_monthly 결과)
        prev_reb_data: R-ONE 전월 데이터
        current_tx_count: 당월 실거래 건수
        prev_tx_count: 전월 실거래 건수
        current_auction_count: 당월 공매 건수
        prev_auction_count: 전월 공매 건수

    Returns:
        {
            "sale_index_change": 매매가격지수 변동률 (%),
            "jeonse_ratio": 전세가율 (%),
            "unsold_change": 미분양 증감률 (%),
            "tx_count_change": 거래량 변동률 (%),
            "supply_demand": 매매수급동향 (지수),
            "auction_change": 공매 증감률 (%),
        }
    """
    logger.info(f"Computing V2 indicators for region={region}, period={period}")

    # R-ONE 데이터에서 해당 지역 추출
    def _find_region(items: List[Dict], key: str) -> Optional[float]:
        for item in items:
            if item.get("region_code") == region:
                return item.get(key)
        return None

    # 매매지수 변동률
    cur_sale_idx = _find_region(reb_data.get("sale_index", []), "sale_index")
    prev_sale_idx = _find_region(prev_reb_data.get("sale_index", []), "sale_index")

    # 전세가율
    avg_price = None
    for item in reb_data.get("avg_prices", []):
        if item.get("region_code") == region:
            avg_price = item
            break

    # 미분양
    cur_unsold = _find_region(reb_data.get("unsold", []), "unsold_count")
    prev_unsold = _find_region(prev_reb_data.get("unsold", []), "unsold_count")

    # 수급동향 (최신 주간)
    supply_demand = _find_region(reb_data.get("supply_demand", []), "supply_demand_index")

    indicators = {
        "sale_index_change": compute_sale_index_change(cur_sale_idx, prev_sale_idx),
        "jeonse_ratio": avg_price.get("jeonse_ratio") if avg_price else None,
        "unsold_change": compute_unsold_change(
            int(cur_unsold) if cur_unsold is not None else None,
            int(prev_unsold) if prev_unsold is not None else None,
        ),
        "tx_count_change": compute_tx_count_change(current_tx_count, prev_tx_count),
        "supply_demand": compute_supply_demand_score(supply_demand),
        "auction_change": compute_auction_change(current_auction_count, prev_auction_count),
    }

    logger.info(
        f"V2 Indicators for {region}/{period}: "
        f"sale_idx_chg={indicators['sale_index_change']}, "
        f"jeonse_ratio={indicators['jeonse_ratio']}, "
        f"unsold_chg={indicators['unsold_change']}, "
        f"tx_count_chg={indicators['tx_count_change']}, "
        f"supply_demand={indicators['supply_demand']}, "
        f"auction_chg={indicators['auction_change']}"
    )

    return indicators
