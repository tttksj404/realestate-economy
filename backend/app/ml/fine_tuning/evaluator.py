"""
파인튜닝 모델 평가기

파인튜닝된 모델(또는 병합 모델)을 테스트 데이터셋에 대해 평가하고
경제 신호 분류 정확도, 텍스트 품질(ROUGE) 등의 메트릭을 계산합니다.

평가 항목:
- 경제 신호 분류 정확도: 호황/보통/침체 3-class classification
- ROUGE-1/2/L: 분석 텍스트 생성 품질
- 레이턴시: 추론 속도
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 경제 신호 레이블
SIGNAL_LABELS = ["호황", "보통", "침체"]


@dataclass
class EvaluationResult:
    """개별 샘플 평가 결과"""
    instruction: str
    expected_signal: str
    predicted_signal: str
    expected_response: str
    predicted_response: str
    signal_correct: bool
    rouge1: float
    rouge2: float
    rougeL: float
    latency_ms: float


@dataclass
class EvaluationReport:
    """전체 평가 리포트"""
    model_path: str
    test_dataset_path: str
    evaluated_at: str
    total_samples: int
    signal_accuracy: float
    signal_accuracy_per_class: Dict[str, float]
    avg_rouge1: float
    avg_rouge2: float
    avg_rougeL: float
    avg_latency_ms: float
    p95_latency_ms: float
    confusion_matrix: Dict[str, Dict[str, int]]
    sample_results: List[Dict[str, Any]] = field(default_factory=list)


class ModelEvaluator:
    """
    파인튜닝 모델 평가기

    1. evaluate()        : 모델 로드 → 추론 → 결과 수집
    2. compute_metrics() : 정확도, ROUGE 계산
    3. generate_report() : 평가 리포트 저장
    """

    # 시스템 프롬프트 (훈련 시와 동일하게 유지)
    SYSTEM_PROMPT = (
        "당신은 부동산 경제 분석 전문가입니다. "
        "제시된 부동산 지표를 바탕으로 해당 지역의 경제상황을 전문적으로 분석하고 "
        "시장 신호와 투자 시사점을 제공하세요."
    )

    def __init__(
        self,
        max_new_tokens: int = 512,
        temperature: float = 0.1,
        top_p: float = 0.9,
    ):
        """
        Args:
            max_new_tokens: 생성 최대 토큰 수
            temperature: 샘플링 온도 (낮을수록 결정론적)
            top_p: nucleus sampling p값
        """
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.model = None
        self.tokenizer = None
        self._results: List[EvaluationResult] = []

    def evaluate(
        self,
        model_path: str,
        test_dataset_path: str,
        max_samples: Optional[int] = None,
        use_4bit: bool = False,
    ) -> List[EvaluationResult]:
        """
        파인튜닝된 모델을 테스트 데이터셋에 대해 평가합니다.

        Args:
            model_path: 평가할 모델 경로 (병합 모델 또는 LoRA 어댑터)
            test_dataset_path: JSONL 테스트 데이터셋 경로
            max_samples: 최대 평가 샘플 수 (None이면 전체)
            use_4bit: 4비트 양자화 사용 여부 (메모리 절감)

        Returns:
            EvaluationResult 리스트
        """
        # 모델 로드
        self._load_model(model_path, use_4bit=use_4bit)

        # 테스트 데이터셋 로드
        test_data = self._load_jsonl(test_dataset_path)
        if max_samples is not None:
            test_data = test_data[:max_samples]

        logger.info(f"평가 시작 — 샘플 수: {len(test_data)}")

        results: List[EvaluationResult] = []

        for idx, sample in enumerate(test_data, start=1):
            if idx % 10 == 0:
                logger.info(f"평가 진행: {idx}/{len(test_data)}")

            instruction = sample.get("instruction", "")
            expected_response = sample.get("response", "")

            # 기대 신호 추출: response에서 "**판단: X**" 패턴 파싱
            expected_signal = self._extract_signal(expected_response)

            # 모델 추론
            start_time = time.perf_counter()
            predicted_response = self._generate(instruction)
            latency_ms = (time.perf_counter() - start_time) * 1000

            # 예측 신호 추출
            predicted_signal = self._extract_signal(predicted_response)

            # ROUGE 계산
            rouge1, rouge2, rougeL = self._compute_rouge(
                expected_response, predicted_response
            )

            result = EvaluationResult(
                instruction=instruction,
                expected_signal=expected_signal,
                predicted_signal=predicted_signal,
                expected_response=expected_response,
                predicted_response=predicted_response,
                signal_correct=(expected_signal == predicted_signal),
                rouge1=rouge1,
                rouge2=rouge2,
                rougeL=rougeL,
                latency_ms=latency_ms,
            )
            results.append(result)

        self._results = results
        logger.info(f"평가 완료 — {len(results)}건 처리")
        return results

    def compute_metrics(
        self, results: Optional[List[EvaluationResult]] = None
    ) -> Dict[str, Any]:
        """
        평가 결과로부터 종합 메트릭을 계산합니다.

        Args:
            results: 평가 결과 리스트 (None이면 마지막 evaluate() 결과 사용)

        Returns:
            메트릭 딕셔너리:
            - signal_accuracy: 전체 신호 분류 정확도
            - signal_accuracy_per_class: 클래스별 정확도
            - confusion_matrix: 혼동 행렬
            - avg_rouge1/2/L: 평균 ROUGE 스코어
            - avg_latency_ms: 평균 추론 시간
            - p95_latency_ms: 95 퍼센타일 추론 시간
        """
        if results is None:
            results = self._results

        if not results:
            raise ValueError("평가 결과가 없습니다. evaluate()를 먼저 실행하세요.")

        # 경제 신호 분류 정확도
        total = len(results)
        correct = sum(1 for r in results if r.signal_correct)
        signal_accuracy = correct / total if total > 0 else 0.0

        # 클래스별 정확도 계산
        per_class: Dict[str, Dict[str, int]] = {
            label: {"correct": 0, "total": 0} for label in SIGNAL_LABELS
        }
        for r in results:
            if r.expected_signal in per_class:
                per_class[r.expected_signal]["total"] += 1
                if r.signal_correct:
                    per_class[r.expected_signal]["correct"] += 1

        signal_accuracy_per_class = {
            label: (
                stats["correct"] / stats["total"]
                if stats["total"] > 0 else 0.0
            )
            for label, stats in per_class.items()
        }

        # 혼동 행렬 (expected → predicted 카운트)
        confusion: Dict[str, Dict[str, int]] = {
            label: {other: 0 for other in SIGNAL_LABELS}
            for label in SIGNAL_LABELS
        }
        for r in results:
            exp = r.expected_signal if r.expected_signal in SIGNAL_LABELS else "보통"
            pred = r.predicted_signal if r.predicted_signal in SIGNAL_LABELS else "보통"
            confusion[exp][pred] += 1

        # ROUGE 평균
        avg_rouge1 = sum(r.rouge1 for r in results) / total
        avg_rouge2 = sum(r.rouge2 for r in results) / total
        avg_rougeL = sum(r.rougeL for r in results) / total

        # 레이턴시 통계
        latencies = sorted(r.latency_ms for r in results)
        avg_latency = sum(latencies) / total
        p95_idx = int(0.95 * total)
        p95_latency = latencies[min(p95_idx, total - 1)]

        metrics = {
            "total_samples": total,
            "signal_accuracy": signal_accuracy,
            "signal_accuracy_per_class": signal_accuracy_per_class,
            "confusion_matrix": confusion,
            "avg_rouge1": avg_rouge1,
            "avg_rouge2": avg_rouge2,
            "avg_rougeL": avg_rougeL,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
        }

        logger.info(
            f"메트릭 계산 완료 — 신호 정확도: {signal_accuracy:.1%}, "
            f"ROUGE-L: {avg_rougeL:.4f}, 평균 레이턴시: {avg_latency:.1f}ms"
        )
        return metrics

    def generate_report(
        self,
        output_path: str,
        model_path: str = "",
        test_dataset_path: str = "",
        results: Optional[List[EvaluationResult]] = None,
        include_samples: bool = True,
        max_sample_records: int = 50,
    ) -> EvaluationReport:
        """
        평가 리포트를 JSON 파일로 생성합니다.

        Args:
            output_path: 리포트 저장 경로 (*.json)
            model_path: 평가 모델 경로 (기록용)
            test_dataset_path: 테스트 데이터셋 경로 (기록용)
            results: 평가 결과 (None이면 마지막 evaluate() 결과 사용)
            include_samples: 개별 샘플 결과 포함 여부
            max_sample_records: 저장할 최대 샘플 수

        Returns:
            EvaluationReport 객체
        """
        if results is None:
            results = self._results

        metrics = self.compute_metrics(results)

        # 샘플 결과 직렬화 (선택적, 용량 제한)
        sample_records: List[Dict[str, Any]] = []
        if include_samples:
            for r in results[:max_sample_records]:
                sample_records.append({
                    "instruction": r.instruction[:300] + "..." if len(r.instruction) > 300 else r.instruction,
                    "expected_signal": r.expected_signal,
                    "predicted_signal": r.predicted_signal,
                    "signal_correct": r.signal_correct,
                    "expected_response_preview": r.expected_response[:200],
                    "predicted_response_preview": r.predicted_response[:200],
                    "rouge1": round(r.rouge1, 4),
                    "rouge2": round(r.rouge2, 4),
                    "rougeL": round(r.rougeL, 4),
                    "latency_ms": round(r.latency_ms, 1),
                })

        report = EvaluationReport(
            model_path=model_path,
            test_dataset_path=test_dataset_path,
            evaluated_at=datetime.now().isoformat(),
            total_samples=metrics["total_samples"],
            signal_accuracy=round(metrics["signal_accuracy"], 4),
            signal_accuracy_per_class={
                k: round(v, 4)
                for k, v in metrics["signal_accuracy_per_class"].items()
            },
            avg_rouge1=round(metrics["avg_rouge1"], 4),
            avg_rouge2=round(metrics["avg_rouge2"], 4),
            avg_rougeL=round(metrics["avg_rougeL"], 4),
            avg_latency_ms=round(metrics["avg_latency_ms"], 1),
            p95_latency_ms=round(metrics["p95_latency_ms"], 1),
            confusion_matrix=metrics["confusion_matrix"],
            sample_results=sample_records,
        )

        # JSON 저장
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with output_file.open("w", encoding="utf-8") as f:
            json.dump(asdict(report), f, ensure_ascii=False, indent=2)

        logger.info(f"평가 리포트 저장 완료: {output_path}")

        # 콘솔 요약 출력
        self._print_summary(report)
        return report

    # ------------------------------------------------------------------
    # 내부 유틸리티
    # ------------------------------------------------------------------

    def _load_model(self, model_path: str, use_4bit: bool = False) -> None:
        """모델 및 토크나이저 로드"""
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        except ImportError as e:
            raise ImportError("transformers 패키지가 필요합니다.") from e

        logger.info(f"모델 로드: {model_path} (4bit={use_4bit})")

        model_kwargs: Dict[str, Any] = {
            "device_map": "auto",
            "trust_remote_code": True,
        }

        if use_4bit:
            # 추론 전용 4비트 양자화
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )
            model_kwargs["quantization_config"] = bnb_config
        else:
            model_kwargs["torch_dtype"] = torch.float16

        self.model = AutoModelForCausalLM.from_pretrained(model_path, **model_kwargs)
        self.model.eval()

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path, trust_remote_code=True
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        logger.info("모델 로드 완료")

    def _generate(self, instruction: str) -> str:
        """
        단일 instruction에 대해 모델 추론 실행

        Llama-3 chat 포맷으로 입력을 구성하여 응답을 생성합니다.
        """
        try:
            import torch
        except ImportError:
            return ""

        # 채팅 포맷 구성
        prompt = (
            "<|begin_of_text|>"
            "<|start_header_id|>system<|end_header_id|>\n"
            f"{self.SYSTEM_PROMPT}<|eot_id|>"
            "<|start_header_id|>user<|end_header_id|>\n"
            f"{instruction}<|eot_id|>"
            "<|start_header_id|>assistant<|end_header_id|>\n"
        )

        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=1024,
        ).to(self.model.device)

        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                do_sample=(self.temperature > 0),
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        # 입력 부분 제거, 응답만 디코딩
        generated_ids = output_ids[0][inputs["input_ids"].shape[-1]:]
        response = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        return response.strip()

    def _extract_signal(self, response_text: str) -> str:
        """
        응답 텍스트에서 경제 신호(호황/보통/침체)를 추출합니다.

        "**판단: 호황**" 또는 "판단: 침체" 등의 패턴을 탐색합니다.
        """
        import re

        # 마크다운 볼드 패턴: **판단: X**
        bold_pattern = r'\*\*판단:\s*([호황보통침체]+)\*\*'
        match = re.search(bold_pattern, response_text)
        if match:
            return match.group(1).strip()

        # 일반 패턴: "판단: X"
        plain_pattern = r'판단:\s*([호황보통침체]+)'
        match = re.search(plain_pattern, response_text)
        if match:
            return match.group(1).strip()

        # 키워드 직접 탐색 (우선순위: 호황 > 침체 > 보통)
        for signal in SIGNAL_LABELS:
            if signal in response_text:
                return signal

        logger.debug(f"신호 추출 실패: {response_text[:100]}")
        return "보통"  # 기본값

    def _compute_rouge(
        self, reference: str, hypothesis: str
    ) -> Tuple[float, float, float]:
        """
        ROUGE-1, ROUGE-2, ROUGE-L 스코어를 계산합니다.

        rouge_score 패키지가 없을 경우 간단한 토큰 오버랩으로 폴백합니다.
        """
        try:
            from rouge_score import rouge_scorer
            scorer = rouge_scorer.RougeScorer(
                ["rouge1", "rouge2", "rougeL"], use_stemmer=False
            )
            scores = scorer.score(reference, hypothesis)
            return (
                scores["rouge1"].fmeasure,
                scores["rouge2"].fmeasure,
                scores["rougeL"].fmeasure,
            )
        except ImportError:
            # 폴백: 단순 토큰 F1
            r1 = self._token_f1(reference, hypothesis, n=1)
            r2 = self._token_f1(reference, hypothesis, n=2)
            return r1, r2, r1  # ROUGE-L 근사값으로 ROUGE-1 사용

    def _token_f1(self, reference: str, hypothesis: str, n: int = 1) -> float:
        """단순 n-gram 겹침 F1 (rouge_score 폴백용)"""
        def get_ngrams(text: str, n: int) -> List[tuple]:
            tokens = text.split()
            return [tuple(tokens[i: i + n]) for i in range(len(tokens) - n + 1)]

        ref_ngrams = get_ngrams(reference, n)
        hyp_ngrams = get_ngrams(hypothesis, n)

        if not ref_ngrams or not hyp_ngrams:
            return 0.0

        ref_set = set(ref_ngrams)
        hyp_set = set(hyp_ngrams)
        overlap = len(ref_set & hyp_set)

        precision = overlap / len(hyp_set) if hyp_set else 0.0
        recall = overlap / len(ref_set) if ref_set else 0.0

        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    def _load_jsonl(self, path: str) -> List[Dict[str, Any]]:
        """JSONL 파일 로드"""
        records = []
        with open(path, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning(f"JSONL 파싱 오류 (line {lineno}): {e}")
        return records

    def _print_summary(self, report: EvaluationReport) -> None:
        """평가 결과 콘솔 요약 출력"""
        bar = "=" * 60
        print(f"\n{bar}")
        print("  모델 평가 리포트 요약")
        print(bar)
        print(f"  모델 경로    : {report.model_path}")
        print(f"  평가 일시    : {report.evaluated_at}")
        print(f"  평가 샘플 수 : {report.total_samples}건")
        print(f"\n  [경제 신호 분류 정확도]")
        print(f"  전체 정확도  : {report.signal_accuracy:.1%}")
        for label, acc in report.signal_accuracy_per_class.items():
            print(f"  {label:4s} 정확도 : {acc:.1%}")
        print(f"\n  [혼동 행렬] (행=실제, 열=예측)")
        header = "       " + "  ".join(f"{lbl:4s}" for lbl in SIGNAL_LABELS)
        print(f"  {header}")
        for actual_lbl in SIGNAL_LABELS:
            row = "  ".join(
                f"{report.confusion_matrix[actual_lbl].get(pred_lbl, 0):4d}"
                for pred_lbl in SIGNAL_LABELS
            )
            print(f"  {actual_lbl:4s} | {row}")
        print(f"\n  [ROUGE 스코어]")
        print(f"  ROUGE-1      : {report.avg_rouge1:.4f}")
        print(f"  ROUGE-2      : {report.avg_rouge2:.4f}")
        print(f"  ROUGE-L      : {report.avg_rougeL:.4f}")
        print(f"\n  [추론 레이턴시]")
        print(f"  평균         : {report.avg_latency_ms:.1f}ms")
        print(f"  P95          : {report.p95_latency_ms:.1f}ms")
        print(f"{bar}\n")
