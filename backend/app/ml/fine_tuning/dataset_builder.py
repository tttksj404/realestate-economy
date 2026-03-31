"""
파인튜닝 데이터셋 빌더

EconomyIndicator DB 레코드로부터 LLM 파인튜닝용
instruction-response 쌍(JSONL)을 구성합니다.

데이터 증강(augment)을 통해 동일 지표에 대해
표현 방식을 다양화하여 학습 데이터 풍부도를 높입니다.
"""

import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EconomyIndicator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 경제 신호별 분석 문구 템플릿
# 각 신호(호황/보통/침체)에 대한 상세 해설 문단 후보군
# ---------------------------------------------------------------------------

_BOOM_INTROS = [
    "현재 해당 지역의 부동산 시장은 **호황** 국면을 보이고 있습니다.",
    "지표 종합 분석 결과, 시장은 **상승 사이클** 진입 신호를 명확히 발신하고 있습니다.",
    "주요 선행 지표가 일제히 긍정 방향을 가리키며 **매수 우위** 시장이 형성되었습니다.",
]
_NORMAL_INTROS = [
    "현재 해당 지역의 부동산 시장은 **보합/관망** 국면에 있습니다.",
    "지표들은 뚜렷한 방향성 없이 **횡보 흐름**을 나타내고 있습니다.",
    "매수·매도 세력이 균형을 이루며 **중립 국면**이 지속되고 있습니다.",
]
_RECESSION_INTROS = [
    "현재 해당 지역의 부동산 시장은 **침체** 국면에 진입했습니다.",
    "복수의 선행 지표가 하방 압력을 가리키며 **조정 국면**이 진행 중입니다.",
    "공급 과잉 및 수요 위축 신호가 동시에 확인되며 **매도 우위** 시장이 형성되었습니다.",
]

_SIGNAL_INTROS: Dict[str, List[str]] = {
    "호황": _BOOM_INTROS,
    "보통": _NORMAL_INTROS,
    "침체": _RECESSION_INTROS,
}

# 지표별 해설 문구 생성 헬퍼 (값 범위에 따른 자연어 표현)
def _describe_low_price_ratio(ratio: float) -> str:
    """저가 매물 비율 해설 — 높을수록 침체 신호"""
    if ratio < 5.0:
        return f"저가 매물 비율은 {ratio:.1f}%로 매우 낮아, 급매 압력이 거의 없습니다."
    elif ratio < 15.0:
        return f"저가 매물 비율이 {ratio:.1f}%로 보통 수준이며, 일부 급매물이 산재합니다."
    else:
        return f"저가 매물 비율이 {ratio:.1f}%로 높아, 시장에 급매 압력이 확산되고 있습니다."


def _describe_listing_change(change: float) -> str:
    """매물 증감률 해설 — 양수(공급 증가)일수록 침체 신호"""
    if change < -5.0:
        return f"전월 대비 매물이 {abs(change):.1f}% 감소하여, 공급 부족에 따른 가격 상승 압력이 존재합니다."
    elif change < 10.0:
        return f"매물 증감률은 {change:+.1f}%로 안정적인 공급 수준을 유지하고 있습니다."
    else:
        return f"전월 대비 매물이 {change:.1f}% 증가하여, 공급 과잉 우려가 커지고 있습니다."


def _describe_price_gap(gap: float) -> str:
    """호가·실거래가 괴리율 해설 — 높을수록 매도자 희망가격 버블 신호"""
    if gap < 2.0:
        return f"호가·실거래가 괴리율이 {gap:.1f}%로 낮아, 시장 가격이 현실 거래와 잘 부합합니다."
    elif gap < 8.0:
        return f"괴리율 {gap:.1f}%는 보통 수준으로, 매도자와 매수자 간 기대 격차가 소폭 존재합니다."
    else:
        return f"괴리율이 {gap:.1f}%로 높아, 매도자 호가가 실거래가를 크게 상회하며 거래 공백이 우려됩니다."


def _describe_price_index(index: float) -> str:
    """지역 가격지수 변동 해설"""
    if index > 1.0:
        return f"지역 가격지수가 전월 대비 {index:+.2f}% 상승하며 상승 모멘텀이 유지되고 있습니다."
    elif index > -1.0:
        return f"가격지수 변동은 {index:+.2f}%로 거의 보합 수준입니다."
    else:
        return f"가격지수가 {index:.2f}% 하락하여 실질적인 가격 조정이 진행 중입니다."


def _describe_sale_speed(days: float) -> str:
    """매물 소진 기간 해설 — 짧을수록 호황 신호"""
    if days < 30.0:
        return f"평균 매물 소진 기간이 {days:.0f}일로 매우 짧아, 수요가 공급을 빠르게 흡수하고 있습니다."
    elif days < 90.0:
        return f"매물 소진 기간 {days:.0f}일은 보통 수준으로, 시장 유동성이 적정하게 유지됩니다."
    else:
        return f"매물 소진 기간이 {days:.0f}일로 길어, 수요 부진과 거래 침체가 지속되고 있습니다."


def _describe_jeonse_ratio(ratio: float) -> str:
    """전세가율 해설 — 높을수록 갭투자 위험, 매매 침체 신호"""
    if ratio < 55.0:
        return f"전세가율이 {ratio:.1f}%로 낮아 갭투자 위험이 제한적이며 매매 시장에 안정감이 있습니다."
    elif ratio < 75.0:
        return f"전세가율 {ratio:.1f}%는 보통 수준이나 추가 상승 시 갭투자 부담이 커질 수 있습니다."
    else:
        return f"전세가율이 {ratio:.1f}%로 높아 역전세 위험 및 매매가 하락 압력이 잠재합니다."


def _build_instruction(
    region_name: str,
    period: str,
    low_price: float,
    listing_change: float,
    price_gap: float,
    price_index: float,
    sale_speed: float,
    jeonse: float,
) -> str:
    """
    LLM 입력 instruction 구성

    LEET 지문 형식처럼 구조화된 지표 테이블을 포함합니다.
    """
    # 기간 포맷: '202401' → '2024년 01월'
    year = period[:4]
    month = period[4:6]
    period_str = f"{year}년 {month}월"

    return (
        "다음 부동산 지표를 분석하여 경제상황을 판단하세요.\n\n"
        f"지역: {region_name}\n"
        f"기간: {period_str}\n"
        f"저가매물비율: {low_price:.1f}%\n"
        f"매물증감률: {listing_change:+.1f}%\n"
        f"호가괴리율: {price_gap:.1f}%\n"
        f"가격지수변동: {price_index:+.2f}%\n"
        f"매물소진기간: {sale_speed:.0f}일\n"
        f"전세가율: {jeonse:.1f}%"
    )


def _build_response(
    signal: str,
    confidence: float,
    region_name: str,
    period: str,
    low_price: float,
    listing_change: float,
    price_gap: float,
    price_index: float,
    sale_speed: float,
    jeonse: float,
    intro_override: Optional[str] = None,
) -> str:
    """
    LLM 출력 response 구성

    각 지표별 해설 + 종합 결론을 마크다운 형식으로 작성합니다.
    """
    year = period[:4]
    month = period[4:6]

    # 신호별 도입 문구 (증강 시 다양화)
    intros = _SIGNAL_INTROS.get(signal, _NORMAL_INTROS)
    intro = intro_override if intro_override else intros[0]

    # 신뢰도 퍼센트 변환
    conf_pct = round(confidence * 100, 1)

    # 지표별 해설 조합
    indicator_lines = "\n".join([
        f"- {_describe_low_price_ratio(low_price)}",
        f"- {_describe_listing_change(listing_change)}",
        f"- {_describe_price_gap(price_gap)}",
        f"- {_describe_price_index(price_index)}",
        f"- {_describe_sale_speed(sale_speed)}",
        f"- {_describe_jeonse_ratio(jeonse)}",
    ])

    # 신호별 투자 시사점
    if signal == "호황":
        implication = (
            "전반적으로 수요가 공급을 초과하며 가격 상승 사이클이 진행 중입니다. "
            "신중한 매수 타이밍 검토가 유효하나, 단기 급등에 따른 조정 가능성도 염두에 두어야 합니다."
        )
    elif signal == "침체":
        implication = (
            "공급 과잉과 수요 위축이 겹치며 가격 하방 압력이 지속될 것으로 예상됩니다. "
            "매수 진입보다는 관망 또는 분할 접근 전략이 적절하며, 저가 매물 선별 기회를 모색할 수 있습니다."
        )
    else:
        implication = (
            "시장은 뚜렷한 방향성 없이 횡보하고 있으며, 정책 변화나 외부 충격에 민감하게 반응할 수 있습니다. "
            "추가 지표 모니터링과 함께 신중한 관망이 권고됩니다."
        )

    response = (
        f"## 경제상황 분석\n\n"
        f"**판단: {signal}** (신뢰도: {conf_pct}%)\n\n"
        f"### {region_name} {year}년 {month}월 지표 해설\n\n"
        f"{intro}\n\n"
        f"{indicator_lines}\n\n"
        f"### 종합 시사점\n\n"
        f"{implication}"
    )
    return response


class DatasetBuilder:
    """
    EconomyIndicator DB 레코드 → 파인튜닝 데이터셋 빌더

    1. build_from_db()   : DB에서 지표 레코드를 쿼리하여 원본 데이터셋 생성
    2. augment_with_variations() : 동일 지표를 다양한 표현으로 증강
    3. save_dataset()    : JSONL 파일로 저장
    4. load_dataset()    : JSONL 파일 로드
    """

    # 파인튜닝에 사용할 최소 신뢰도 (낮은 품질 데이터 필터링)
    MIN_CONFIDENCE: float = 0.5

    # 증강 시 지표 값에 추가하는 노이즈 범위 (±)
    AUGMENT_NOISE = {
        "low_price": 1.5,       # ±1.5%p
        "listing_change": 2.0,  # ±2.0%p
        "price_gap": 1.0,       # ±1.0%p
        "price_index": 0.3,     # ±0.3%p
        "sale_speed": 5.0,      # ±5일
        "jeonse": 1.5,          # ±1.5%p
    }

    def __init__(self, min_confidence: float = MIN_CONFIDENCE):
        self.min_confidence = min_confidence

    async def build_from_db(self, db_session: AsyncSession) -> List[Dict[str, Any]]:
        """
        DB에서 EconomyIndicator 레코드를 조회하여 데이터셋 생성

        Args:
            db_session: SQLAlchemy 비동기 세션

        Returns:
            instruction-response 쌍의 리스트
        """
        logger.info("DB에서 EconomyIndicator 레코드 조회 시작")

        # 신호 및 신뢰도가 존재하는 레코드만 조회 (파인튜닝 타깃)
        stmt = select(EconomyIndicator).where(
            EconomyIndicator.signal.isnot(None),
            EconomyIndicator.confidence.isnot(None),
            EconomyIndicator.confidence >= self.min_confidence,
            # 6개 지표가 모두 존재하는 레코드만 사용
            EconomyIndicator.low_price_listing_ratio.isnot(None),
            EconomyIndicator.listing_count_change.isnot(None),
            EconomyIndicator.price_gap_ratio.isnot(None),
            EconomyIndicator.regional_price_index.isnot(None),
            EconomyIndicator.sale_speed.isnot(None),
            EconomyIndicator.jeonse_ratio.isnot(None),
        ).order_by(EconomyIndicator.period.desc(), EconomyIndicator.region_name)

        result = await db_session.execute(stmt)
        records: List[EconomyIndicator] = result.scalars().all()

        logger.info(f"조회된 레코드 수: {len(records)}")

        dataset: List[Dict[str, Any]] = []
        skipped = 0

        for rec in records:
            try:
                sample = self._record_to_sample(rec)
                dataset.append(sample)
            except Exception as e:
                logger.warning(f"레코드 변환 실패 (id={rec.id}): {e}")
                skipped += 1

        logger.info(f"데이터셋 생성 완료 — 총 {len(dataset)}건, 스킵 {skipped}건")
        return dataset

    def _record_to_sample(self, rec: EconomyIndicator) -> Dict[str, Any]:
        """
        EconomyIndicator 레코드 → instruction/response 딕셔너리 변환
        """
        # 안전하게 float 캐스팅 (Numeric 타입 대응)
        low_price = float(rec.low_price_listing_ratio)      # 저가 매물 비율
        listing_change = float(rec.listing_count_change)    # 매물 증감률
        price_gap = float(rec.price_gap_ratio)              # 호가괴리율
        price_index = float(rec.regional_price_index)       # 가격지수 변동
        sale_speed = float(rec.sale_speed)                  # 매물 소진 기간
        jeonse = float(rec.jeonse_ratio)                    # 전세가율
        confidence = float(rec.confidence)

        instruction = _build_instruction(
            region_name=rec.region_name,
            period=rec.period,
            low_price=low_price,
            listing_change=listing_change,
            price_gap=price_gap,
            price_index=price_index,
            sale_speed=sale_speed,
            jeonse=jeonse,
        )

        response = _build_response(
            signal=rec.signal,
            confidence=confidence,
            region_name=rec.region_name,
            period=rec.period,
            low_price=low_price,
            listing_change=listing_change,
            price_gap=price_gap,
            price_index=price_index,
            sale_speed=sale_speed,
            jeonse=jeonse,
        )

        return {
            "instruction": instruction,
            "response": response,
            # 메타 정보 (평가·디버깅용, 학습에는 미포함)
            "_meta": {
                "region_code": rec.region_code,
                "region_name": rec.region_name,
                "period": rec.period,
                "signal": rec.signal,
                "confidence": confidence,
                "source": "db",
            },
        }

    def augment_with_variations(
        self,
        dataset: List[Dict[str, Any]],
        num_variations: int = 2,
        seed: int = 42,
    ) -> List[Dict[str, Any]]:
        """
        데이터 증강: 각 샘플에 대해 지표 값에 미세 노이즈를 더하고
        서술 문체를 다양화하여 복수의 변형 샘플을 생성합니다.

        Args:
            dataset: build_from_db()에서 반환된 원본 데이터셋
            num_variations: 원본 1건당 생성할 변형 수
            seed: 재현성을 위한 랜덤 시드

        Returns:
            원본 + 변형 샘플이 합쳐진 데이터셋
        """
        rng = random.Random(seed)
        augmented: List[Dict[str, Any]] = list(dataset)  # 원본 보존

        logger.info(
            f"데이터 증강 시작 — 원본 {len(dataset)}건 × 변형 {num_variations}개"
        )

        for sample in dataset:
            meta = sample.get("_meta", {})
            if not meta:
                continue

            signal = meta["signal"]
            confidence = meta["confidence"]
            region_name = meta["region_name"]
            period = meta["period"]

            # instruction에서 지표 값을 역파싱하여 노이즈 적용
            raw_values = self._parse_instruction_values(sample["instruction"])
            if raw_values is None:
                continue

            intros = _SIGNAL_INTROS.get(signal, _NORMAL_INTROS)

            for var_idx in range(num_variations):
                # 지표 값에 가우시안 노이즈 추가 (신호 방향 유지를 위해 소폭 노이즈)
                noisy = self._apply_noise(raw_values, rng)

                # 도입 문구 순환 (다양성 확보)
                intro = intros[(var_idx + 1) % len(intros)]

                new_instruction = _build_instruction(
                    region_name=region_name,
                    period=period,
                    **noisy,
                )
                new_response = _build_response(
                    signal=signal,
                    confidence=confidence,
                    region_name=region_name,
                    period=period,
                    intro_override=intro,
                    **noisy,
                )

                augmented.append({
                    "instruction": new_instruction,
                    "response": new_response,
                    "_meta": {
                        **meta,
                        "source": f"augmented_v{var_idx + 1}",
                    },
                })

        logger.info(f"증강 완료 — 총 {len(augmented)}건 (원본 {len(dataset)} + 증강 {len(augmented) - len(dataset)})")
        return augmented

    def _parse_instruction_values(
        self, instruction: str
    ) -> Optional[Dict[str, float]]:
        """
        instruction 문자열에서 6개 지표 수치를 파싱합니다.

        Returns:
            {"low_price": ..., "listing_change": ..., ...} 또는 실패 시 None
        """
        try:
            lines = instruction.strip().split("\n")
            values: Dict[str, float] = {}
            key_map = {
                "저가매물비율": "low_price",
                "매물증감률": "listing_change",
                "호가괴리율": "price_gap",
                "가격지수변동": "price_index",
                "매물소진기간": "sale_speed",
                "전세가율": "jeonse",
            }
            for line in lines:
                for kor_key, eng_key in key_map.items():
                    if line.startswith(kor_key + ":"):
                        raw = line.split(":")[1].strip()
                        # 단위 제거 ('%', '일')
                        raw = raw.replace("%", "").replace("일", "").strip()
                        values[eng_key] = float(raw)
            if len(values) == 6:
                return values
            return None
        except Exception:
            return None

    def _apply_noise(
        self, values: Dict[str, float], rng: random.Random
    ) -> Dict[str, float]:
        """지표 값에 정규분포 노이즈를 추가합니다."""
        noise_cfg = self.AUGMENT_NOISE
        noisy = {
            "low_price": max(0.0, values["low_price"] + rng.gauss(0, noise_cfg["low_price"])),
            "listing_change": values["listing_change"] + rng.gauss(0, noise_cfg["listing_change"]),
            "price_gap": max(0.0, values["price_gap"] + rng.gauss(0, noise_cfg["price_gap"])),
            "price_index": values["price_index"] + rng.gauss(0, noise_cfg["price_index"]),
            "sale_speed": max(1.0, values["sale_speed"] + rng.gauss(0, noise_cfg["sale_speed"])),
            "jeonse": max(0.0, min(100.0, values["jeonse"] + rng.gauss(0, noise_cfg["jeonse"]))),
        }
        return noisy

    def save_dataset(
        self,
        dataset: List[Dict[str, Any]],
        output_path: str,
        include_meta: bool = False,
    ) -> int:
        """
        데이터셋을 JSONL 형식으로 저장합니다.

        Args:
            dataset: instruction-response 딕셔너리 리스트
            output_path: 저장 경로 (*.jsonl)
            include_meta: _meta 필드 포함 여부 (기본 False — 학습용에서 제외)

        Returns:
            저장된 레코드 수
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        written = 0
        with path.open("w", encoding="utf-8") as f:
            for sample in dataset:
                # 학습용 데이터에서 _meta 제거 (선택)
                record: Dict[str, Any] = {
                    "instruction": sample["instruction"],
                    "response": sample["response"],
                }
                if include_meta and "_meta" in sample:
                    record["_meta"] = sample["_meta"]

                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1

        logger.info(f"데이터셋 저장 완료: {output_path} ({written}건)")
        return written

    def load_dataset(self, path: str) -> List[Dict[str, Any]]:
        """
        JSONL 파일에서 데이터셋을 로드합니다.

        Args:
            path: JSONL 파일 경로

        Returns:
            instruction-response 딕셔너리 리스트
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"데이터셋 파일을 찾을 수 없습니다: {path}")

        dataset: List[Dict[str, Any]] = []
        with file_path.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    dataset.append(record)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSONL 파싱 실패 (line {lineno}): {e}")

        logger.info(f"데이터셋 로드 완료: {path} ({len(dataset)}건)")
        return dataset

    def get_statistics(self, dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        데이터셋 통계 반환 (신호 분포, 지역 분포 등)
        """
        from collections import Counter

        signal_counter: Counter = Counter()
        region_counter: Counter = Counter()
        sources: Counter = Counter()

        for sample in dataset:
            meta = sample.get("_meta", {})
            if meta:
                signal_counter[meta.get("signal", "unknown")] += 1
                region_counter[meta.get("region_name", "unknown")] += 1
                sources[meta.get("source", "unknown")] += 1

        return {
            "total": len(dataset),
            "signal_distribution": dict(signal_counter),
            "region_distribution": dict(region_counter),
            "source_distribution": dict(sources),
        }
