"""
LLM 서비스 모듈

로컬 HuggingFace 모델을 통해 부동산 경제 분석 텍스트 생성 및
채팅 스트리밍 응답을 처리합니다.

지원 모델:
- beomi/Llama-3-Open-Ko-8B (기본, 한국어 특화)
- 기타 HuggingFace 호환 모델
"""

import asyncio
import logging
import threading
from typing import AsyncGenerator, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# 시스템 프롬프트: 부동산 경제 분석 전문가 페르소나
SYSTEM_PROMPT = """당신은 한국 부동산 시장 분석 전문가입니다.
국토교통부 실거래가 데이터, 매물 현황, 경제 지표를 종합하여
정확하고 유용한 부동산 시장 분석을 제공합니다.

분석 시 다음 원칙을 따릅니다:
1. 데이터 기반의 객관적 분석
2. 투자 위험 요소 명시
3. 지역별 특성 고려
4. 시장 신호 (호황/보통/침체) 명확한 근거 제시

투자 조언이 아닌 시장 현황 분석 정보를 제공함을 명시하세요."""


class LLMService:
    """
    로컬 LLM 서비스

    transformers 라이브러리를 통해 로컬 모델을 로드하고
    텍스트 생성 및 스트리밍을 처리합니다.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or settings.LLM_MODEL_PATH
        self._model = None
        self._tokenizer = None
        self._pipeline = None

    def _load_model(self):
        """모델 지연 로딩 (처음 사용 시 로드)"""
        if self._pipeline is not None:
            return self._pipeline

        try:
            import torch
            from transformers import (
                AutoModelForCausalLM,
                AutoTokenizer,
                TextIteratorStreamer,
                pipeline as hf_pipeline,
                BitsAndBytesConfig,
            )

            logger.info(f"Loading LLM: {self.model_path}")

            tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                trust_remote_code=True,
            )

            # 양자화 설정 (GPU 메모리 절약)
            use_quantization = False
            try:
                import bitsandbytes
                use_quantization = torch.cuda.is_available()
            except ImportError:
                pass

            if use_quantization:
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                )
                model = AutoModelForCausalLM.from_pretrained(
                    self.model_path,
                    quantization_config=quantization_config,
                    device_map="auto",
                    trust_remote_code=True,
                )
            else:
                device = "cuda" if torch.cuda.is_available() else "cpu"
                model = AutoModelForCausalLM.from_pretrained(
                    self.model_path,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    device_map="auto" if torch.cuda.is_available() else None,
                    trust_remote_code=True,
                )
                if not torch.cuda.is_available():
                    model = model.to(device)

            self._model = model
            self._tokenizer = tokenizer
            self._pipeline = hf_pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
            )

            logger.info("LLM loaded successfully.")
            return self._pipeline

        except Exception as e:
            logger.error(f"Failed to load LLM: {e}", exc_info=True)
            raise

    def _build_prompt(
        self,
        messages: List[Dict[str, str]],
        context: str = "",
    ) -> str:
        """
        메시지 목록과 RAG 컨텍스트로 LLM 입력 프롬프트 구성

        Llama-3 Chat 형식 (또는 일반 Instruct 형식) 사용
        """
        # 시스템 + 컨텍스트 구성
        system_content = SYSTEM_PROMPT
        if context:
            system_content += f"\n\n{context}"

        # 토크나이저가 chat_template을 지원하는지 확인
        if self._tokenizer and hasattr(self._tokenizer, "chat_template") and self._tokenizer.chat_template:
            full_messages = [{"role": "system", "content": system_content}] + messages
            try:
                prompt = self._tokenizer.apply_chat_template(
                    full_messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
                return prompt
            except Exception:
                pass

        # 폴백: 수동 Alpaca/Instruct 형식
        prompt_parts = [f"[시스템]\n{system_content}\n"]
        for msg in messages:
            role = "사용자" if msg["role"] == "user" else "AI"
            prompt_parts.append(f"[{role}]\n{msg['content']}\n")
        prompt_parts.append("[AI]\n")

        return "\n".join(prompt_parts)

    async def analyze(
        self,
        indicators: Dict,
        context: str,
        signal: str,
        region_name: str,
        period: str,
    ) -> str:
        """
        경제 지표 기반 분석 리포트 생성

        Args:
            indicators: 6개 경제 지표 딕셔너리
            context: RAG 검색 컨텍스트
            signal: 경제 신호 (호황/보통/침체)
            region_name: 지역명
            period: 분석 기간

        Returns:
            자연어 분석 리포트 문자열
        """
        # 지표를 자연어로 변환
        indicator_desc = self._indicators_to_text(indicators)

        messages = [
            {
                "role": "user",
                "content": (
                    f"{region_name} 지역의 {period} 부동산 시장을 분석해주세요.\n\n"
                    f"경제 신호: {signal}\n\n"
                    f"주요 지표:\n{indicator_desc}\n\n"
                    "위 데이터를 바탕으로 시장 상황, 원인 분석, "
                    "향후 전망을 3~5문단으로 설명해주세요."
                ),
            }
        ]

        result = await self._generate_async(messages, context)
        return result

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        context: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        LLM 스트리밍 채팅 응답 생성 (async generator)

        Args:
            messages: 대화 히스토리
            context: RAG 컨텍스트

        Yields:
            생성된 토큰 문자열
        """
        # 모델이 로드되지 않은 경우 폴백 응답 사용
        try:
            self._load_model()
        except Exception as e:
            logger.warning(f"LLM not available, using fallback: {e}")
            async for token in self._fallback_stream(messages, context):
                yield token
            return

        try:
            from transformers import TextIteratorStreamer

            prompt = self._build_prompt(messages, context)
            inputs = self._tokenizer(prompt, return_tensors="pt")

            # GPU 이동
            import torch
            device = next(self._model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}

            streamer = TextIteratorStreamer(
                self._tokenizer,
                skip_prompt=True,
                skip_special_tokens=True,
            )

            # 별도 스레드에서 생성 실행 (블로킹 방지)
            generation_kwargs = {
                **inputs,
                "streamer": streamer,
                "max_new_tokens": settings.LLM_MAX_NEW_TOKENS,
                "temperature": settings.LLM_TEMPERATURE,
                "top_p": settings.LLM_TOP_P,
                "do_sample": True,
                "repetition_penalty": 1.1,
            }

            thread = threading.Thread(
                target=self._model.generate,
                kwargs=generation_kwargs,
            )
            thread.start()

            # 스트리머에서 토큰 읽기
            loop = asyncio.get_event_loop()
            for token in streamer:
                yield token
                await asyncio.sleep(0)  # 이벤트 루프에 제어권 반환

            thread.join()

        except Exception as e:
            logger.error(f"LLM streaming error: {e}", exc_info=True)
            yield f"\n[오류: {str(e)}]"

    async def _generate_async(
        self,
        messages: List[Dict[str, str]],
        context: str = "",
    ) -> str:
        """비동기 텍스트 생성 (단일 응답)"""
        try:
            self._load_model()
        except Exception as e:
            return self._fallback_generate(messages, context)

        prompt = self._build_prompt(messages, context)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._pipeline(
                prompt,
                max_new_tokens=settings.LLM_MAX_NEW_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
                top_p=settings.LLM_TOP_P,
                do_sample=True,
                repetition_penalty=1.1,
                return_full_text=False,
            ),
        )

        if result and len(result) > 0:
            return result[0].get("generated_text", "")
        return ""

    def _fallback_generate(
        self,
        messages: List[Dict[str, str]],
        context: str,
    ) -> str:
        """
        LLM 미사용 시 폴백 텍스트 생성

        모델 로드 실패 시 지표 기반 템플릿 응답을 반환합니다.
        """
        last_msg = messages[-1]["content"] if messages else ""
        return (
            f"[LLM 모델 미사용 폴백 응답]\n\n"
            f"요청: {last_msg[:200]}\n\n"
            f"현재 LLM 모델을 로드할 수 없어 자동 생성된 응답입니다. "
            f"모델 경로({self.model_path})를 확인해주세요.\n\n"
            f"{'참고 컨텍스트가 있습니다.' if context else '참고 컨텍스트가 없습니다.'}"
        )

    async def _fallback_stream(
        self,
        messages: List[Dict[str, str]],
        context: str,
    ) -> AsyncGenerator[str, None]:
        """LLM 폴백 스트리밍 응답"""
        response = self._fallback_generate(messages, context)
        # 청크 단위로 나누어 스트리밍 흉내
        chunk_size = 10
        for i in range(0, len(response), chunk_size):
            yield response[i : i + chunk_size]
            await asyncio.sleep(0.01)

    async def interpret_macro(
        self,
        national_indicators: Dict,
        region_signals: List[Dict],
        period: str,
        context: str = "",
    ) -> str:
        """
        거시경제 해석 및 예측 리포트 생성

        전국 평균 지표 + 지역별 신호를 종합하여
        현재 경제 상황 진단과 단기 전망을 생성합니다.
        """
        indicator_text = self._indicators_to_text(national_indicators)

        signal_summary = []
        for rs in region_signals:
            signal_summary.append(f"  {rs['region_name']}: {rs['signal']} (신뢰도 {rs['confidence']:.0%})")
        signal_text = "\n".join(signal_summary) if signal_summary else "데이터 없음"

        messages = [
            {
                "role": "user",
                "content": (
                    f"{period[:4]}년 {period[4:6]}월 기준 한국 부동산 시장을 통해 거시경제 상황을 해석해주세요.\n\n"
                    f"## 전국 평균 지표\n{indicator_text}\n\n"
                    f"## 주요 지역별 신호\n{signal_text}\n\n"
                    "다음 관점에서 분석해주세요:\n"
                    "1. **현재 경제 상황 진단**: 6개 지표가 종합적으로 시사하는 거시경제 상태\n"
                    "2. **핵심 리스크**: 미분양 추이, 전세가율, 수급동향 등에서 감지되는 위험 신호\n"
                    "3. **지역별 온도 차이**: 수도권 vs 지방의 차별화 양상\n"
                    "4. **향후 1~3개월 전망**: 지표 추세 기반 단기 예측\n"
                    "5. **시사점**: 정책·금리·인구 등 거시 변수와의 연결\n\n"
                    "각 항목 2~3문장씩, 총 5개 항목으로 정리해주세요."
                ),
            }
        ]

        return await self._generate_async(messages, context)

    @staticmethod
    def _indicators_to_text(indicators: Dict) -> str:
        """V2 지표 딕셔너리를 사람이 읽기 쉬운 텍스트로 변환"""
        lines = []
        mapping = {
            "sale_index_change": ("매매가격지수 변동률", "%"),
            "jeonse_ratio": ("전세가율", "%"),
            "unsold_change": ("미분양 증감률", "%"),
            "tx_count_change": ("거래량 변동률", "%"),
            "supply_demand": ("매매수급동향", ""),
            "auction_change": ("공매 증감률", "%"),
        }
        for key, (label, unit) in mapping.items():
            value = indicators.get(key)
            if value is not None:
                lines.append(f"- {label}: {value:.2f}{unit}")
            else:
                lines.append(f"- {label}: 데이터 없음")
        return "\n".join(lines)
