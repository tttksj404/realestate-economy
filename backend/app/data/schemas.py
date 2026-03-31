from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────
# 매물 / 거래 응답 스키마
# ─────────────────────────────────────────────────────────────

class ListingResponse(BaseModel):
    """부동산 매물 현황 응답"""

    id: int
    region_code: str = Field(description="법정동 코드")
    region_name: str = Field(description="지역명")
    property_type: str = Field(description="매물 유형 (아파트/빌라/오피스텔)")
    listing_price: Optional[float] = Field(None, description="호가 (만원)")
    actual_price: Optional[float] = Field(None, description="실거래 참고가 (만원)")
    jeonse_price: Optional[float] = Field(None, description="전세가 (만원)")
    area_sqm: Optional[float] = Field(None, description="전용면적 (㎡)")
    floor: Optional[int] = Field(None, description="층수")
    built_year: Optional[int] = Field(None, description="건축연도")
    listed_at: Optional[date] = Field(None, description="매물 등록일")
    source: str = Field(description="데이터 출처 (공공API/네이버)")

    model_config = {"from_attributes": True}


class TransactionResponse(BaseModel):
    """실거래가 내역 응답"""

    id: int
    region_code: str = Field(description="법정동 코드")
    region_name: str = Field(description="지역명")
    property_type: str = Field(description="매물 유형")
    deal_amount: float = Field(description="거래금액 (만원)")
    area_sqm: Optional[float] = Field(None, description="전용면적 (㎡)")
    deal_date: Optional[date] = Field(None, description="거래일자")
    floor: Optional[int] = Field(None, description="층수")
    built_year: Optional[int] = Field(None, description="건축연도")
    source: str = Field(description="데이터 출처")

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────
# 경제 지표 스키마
# ─────────────────────────────────────────────────────────────

class IndicatorData(BaseModel):
    """6개 핵심 경제 지표 데이터"""

    low_price_listing_ratio: Optional[float] = Field(
        None, description="저가 매물 비율 (%): 시세 대비 5% 이상 저렴한 매물 비중"
    )
    listing_count_change: Optional[float] = Field(
        None, description="매물 증감률 (%): 전월 대비 신규 매물 증감"
    )
    price_gap_ratio: Optional[float] = Field(
        None, description="호가/실거래가 괴리율 (%)"
    )
    regional_price_index: Optional[float] = Field(
        None, description="지역 가격지수 변동 (%): 전월 대비"
    )
    sale_speed: Optional[float] = Field(
        None, description="매물 소진 기간 (일)"
    )
    jeonse_ratio: Optional[float] = Field(
        None, description="전세가율 (%)"
    )


class RegionSignal(BaseModel):
    """지역별 경제 신호 요약"""

    region_code: str
    region_name: str
    signal: Literal["호황", "보통", "침체"]
    confidence: float = Field(ge=0.0, le=1.0, description="신호 신뢰도")
    indicators: IndicatorData


class RegionDetail(BaseModel):
    """지역 상세 경제 분석 결과"""

    region_code: str
    region_name: str
    period: str = Field(description="분석 기준 연월 (YYYYMM)")
    signal: Literal["호황", "보통", "침체"]
    confidence: float = Field(ge=0.0, le=1.0)
    indicators: IndicatorData
    analysis_report: str = Field(description="LLM 생성 자연어 분석 리포트")
    rag_context_count: int = Field(description="참조한 RAG 문서 수")
    generated_at: datetime = Field(description="분석 생성 시각")


class EconomyOverview(BaseModel):
    """전국 경제 상황 요약"""

    period: str = Field(description="분석 기준 연월")
    total_regions: int = Field(description="분석 지역 수")
    boom_count: int = Field(description="호황 지역 수")
    normal_count: int = Field(description="보통 지역 수")
    recession_count: int = Field(description="침체 지역 수")
    national_avg_indicators: IndicatorData = Field(description="전국 평균 지표")
    regions: List[RegionSignal] = Field(description="지역별 신호 목록")
    summary: str = Field(description="전국 경제 상황 요약 텍스트")
    generated_at: datetime


# ─────────────────────────────────────────────────────────────
# 채팅 스키마
# ─────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    """단일 채팅 메시지"""

    role: Literal["user", "assistant", "system"] = Field(description="메시지 역할")
    content: str = Field(description="메시지 내용", min_length=1)


class ChatRequest(BaseModel):
    """채팅 요청"""

    messages: List[ChatMessage] = Field(
        description="대화 히스토리 (최신 메시지 마지막)",
        min_length=1,
    )
    region: Optional[str] = Field(
        None,
        description="분석 대상 지역 코드 (지정 시 해당 지역 중심 RAG)",
        example="11",
    )
    stream: bool = Field(default=True, description="SSE 스트리밍 여부")


class ChatResponse(BaseModel):
    """채팅 응답 (비스트리밍 시 사용)"""

    response: str = Field(description="AI 응답 텍스트")
    context_used: bool = Field(description="RAG 컨텍스트 사용 여부")
    rag_document_count: int = Field(description="참조 문서 수")
    region: Optional[str] = Field(None, description="분석 지역")
