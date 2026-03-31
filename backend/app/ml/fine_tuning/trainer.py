"""
QLoRA 파인튜닝 트레이너

4비트 양자화(BitsAndBytesConfig) + LoRA(PEFT) + SFTTrainer(TRL)를 사용하여
Llama-3.1-8B-Instruct 기반 부동산 경제 분석 특화 모델을 파인튜닝합니다.

하드웨어 요구사항:
- GPU VRAM: 최소 16GB (4비트 양자화 기준)
- RAM: 32GB 이상 권장
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FineTuner:
    """
    QLoRA 파인튜닝 오케스트레이터

    1. setup_model()    : 4비트 양자화된 베이스 모델 로드
    2. setup_lora()     : LoRA 어댑터 설정
    3. train()          : SFTTrainer로 학습 실행
    4. merge_and_save() : LoRA 가중치를 베이스 모델에 병합하여 저장
    """

    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.lora_config = None
        self.base_model_name: Optional[str] = None

    def setup_model(
        self,
        base_model: str = "meta-llama/Llama-3.1-8B-Instruct",
        use_flash_attention: bool = False,
    ) -> None:
        """
        4비트 양자화(NF4)로 베이스 모델 및 토크나이저 로드

        Args:
            base_model: HuggingFace 모델 ID 또는 로컬 경로
            use_flash_attention: FlashAttention-2 사용 여부 (CUDA Ampere+ 필요)
        """
        try:
            import torch
            from transformers import (
                AutoModelForCausalLM,
                AutoTokenizer,
                BitsAndBytesConfig,
            )
        except ImportError as e:
            raise ImportError(
                "transformers, bitsandbytes 패키지가 필요합니다. "
                "pip install transformers bitsandbytes 를 실행하세요."
            ) from e

        logger.info(f"베이스 모델 로드 시작: {base_model}")
        self.base_model_name = base_model

        # 4비트 NF4 양자화 설정
        # NF4(Normal Float 4): 정규분포 가정하의 최적 4비트 데이터 타입
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,                          # 4비트 양자화 활성화
            bnb_4bit_quant_type="nf4",                  # NF4 타입 사용
            bnb_4bit_compute_dtype=torch.bfloat16,      # 계산은 bfloat16으로
            bnb_4bit_use_double_quant=True,             # 이중 양자화로 메모리 추가 절감
        )

        # 모델 로드 키워드 인자 구성
        model_kwargs: Dict[str, Any] = {
            "quantization_config": bnb_config,
            "device_map": "auto",           # GPU/CPU 자동 배치
            "trust_remote_code": True,
            "torch_dtype": torch.bfloat16,
        }

        if use_flash_attention:
            model_kwargs["attn_implementation"] = "flash_attention_2"
            logger.info("FlashAttention-2 활성화")

        self.model = AutoModelForCausalLM.from_pretrained(
            base_model,
            **model_kwargs,
        )
        # 추론 모드 해제 및 그래디언트 체크포인트 준비
        self.model.config.use_cache = False
        self.model.enable_input_require_grads()

        # 토크나이저 로드
        self.tokenizer = AutoTokenizer.from_pretrained(
            base_model,
            trust_remote_code=True,
            padding_side="right",   # Llama 계열은 right padding
        )
        # pad_token이 없는 경우 eos_token으로 대체
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        logger.info(f"모델 로드 완료 — 파라미터 수: {self._count_parameters():,}")

    def setup_lora(
        self,
        r: int = 16,
        lora_alpha: int = 32,
        target_modules: Optional[List[str]] = None,
        lora_dropout: float = 0.05,
        bias: str = "none",
        task_type: str = "CAUSAL_LM",
    ) -> None:
        """
        LoRA(Low-Rank Adaptation) 어댑터 설정

        Args:
            r: LoRA 랭크 (높을수록 표현력↑ 메모리↑, 보통 8~64)
            lora_alpha: LoRA 스케일링 계수 (보통 r의 2배)
            target_modules: LoRA 적용 대상 모듈명 리스트 (None이면 기본값 사용)
            lora_dropout: 드롭아웃 비율 (과적합 방지)
            bias: 바이어스 학습 방법 ("none"|"all"|"lora_only")
            task_type: PEFT 태스크 타입
        """
        try:
            from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
        except ImportError as e:
            raise ImportError(
                "peft 패키지가 필요합니다. pip install peft 를 실행하세요."
            ) from e

        if self.model is None:
            raise RuntimeError("setup_model()을 먼저 호출하세요.")

        # Llama 계열 기본 타깃 모듈: 어텐션 프로젝션 레이어
        if target_modules is None:
            target_modules = ["q_proj", "k_proj", "v_proj", "o_proj"]

        logger.info(
            f"LoRA 설정 — r={r}, alpha={lora_alpha}, "
            f"target_modules={target_modules}, dropout={lora_dropout}"
        )

        # 4비트 양자화 모델을 LoRA 학습에 맞게 준비
        # gradient_checkpointing=True: 메모리 절감 (속도와 트레이드오프)
        self.model = prepare_model_for_kbit_training(
            self.model,
            use_gradient_checkpointing=True,
        )

        self.lora_config = LoraConfig(
            r=r,
            lora_alpha=lora_alpha,
            target_modules=target_modules,
            lora_dropout=lora_dropout,
            bias=bias,
            task_type=TaskType.CAUSAL_LM,
        )

        # 모델에 LoRA 어댑터 적용
        self.model = get_peft_model(self.model, self.lora_config)

        # 학습 가능한 파라미터 비율 출력
        trainable, total = self._count_trainable_parameters()
        logger.info(
            f"LoRA 적용 완료 — 학습 가능 파라미터: {trainable:,} / {total:,} "
            f"({100 * trainable / total:.2f}%)"
        )

    def train(
        self,
        dataset_path: str,
        output_dir: str,
        epochs: int = 3,
        batch_size: int = 4,
        lr: float = 2e-4,
        max_seq_length: int = 2048,
        gradient_accumulation_steps: int = 4,
        warmup_ratio: float = 0.03,
        weight_decay: float = 0.001,
        save_steps: int = 100,
        logging_steps: int = 10,
        eval_split: float = 0.05,
    ) -> Dict[str, Any]:
        """
        SFTTrainer로 QLoRA 파인튜닝 실행

        Args:
            dataset_path: JSONL 학습 데이터셋 경로
            output_dir: 체크포인트 및 최종 모델 저장 디렉토리
            epochs: 학습 에폭 수
            batch_size: 배치 사이즈 (GPU당)
            lr: 학습률
            max_seq_length: 최대 시퀀스 길이 (토큰)
            gradient_accumulation_steps: 그래디언트 누적 스텝
            warmup_ratio: 워밍업 비율
            weight_decay: L2 정규화 계수
            save_steps: 체크포인트 저장 주기
            logging_steps: 로그 출력 주기
            eval_split: 검증 세트 분할 비율

        Returns:
            학습 결과 메트릭 딕셔너리
        """
        try:
            from datasets import Dataset
            from trl import SFTConfig, SFTTrainer
        except ImportError as e:
            raise ImportError(
                "trl, datasets 패키지가 필요합니다. "
                "pip install trl datasets 를 실행하세요."
            ) from e

        if self.model is None or self.tokenizer is None:
            raise RuntimeError("setup_model()과 setup_lora()를 먼저 호출하세요.")

        logger.info(f"학습 데이터셋 로드: {dataset_path}")

        # JSONL 데이터셋 로드
        raw_data = self._load_jsonl(dataset_path)
        if not raw_data:
            raise ValueError(f"데이터셋이 비어 있습니다: {dataset_path}")

        # instruction + response를 Llama-3 chat 포맷으로 변환
        formatted = [self._format_chat(item) for item in raw_data]
        hf_dataset = Dataset.from_list([{"text": t} for t in formatted])

        # 검증 세트 분리
        if eval_split > 0:
            split = hf_dataset.train_test_split(test_size=eval_split, seed=42)
            train_dataset = split["train"]
            eval_dataset = split["test"]
            logger.info(
                f"학습: {len(train_dataset)}건, 검증: {len(eval_dataset)}건"
            )
        else:
            train_dataset = hf_dataset
            eval_dataset = None

        # 출력 디렉토리 생성
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # SFTConfig 설정
        sft_config = SFTConfig(
            output_dir=output_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            gradient_accumulation_steps=gradient_accumulation_steps,
            gradient_checkpointing=True,
            optim="paged_adamw_32bit",      # 메모리 효율적인 AdamW 변형
            learning_rate=lr,
            weight_decay=weight_decay,
            lr_scheduler_type="cosine",     # 코사인 학습률 스케줄러
            warmup_ratio=warmup_ratio,
            max_seq_length=max_seq_length,
            dataset_text_field="text",
            packing=False,                  # 시퀀스 패킹 비활성화
            save_strategy="steps",
            save_steps=save_steps,
            save_total_limit=3,             # 최근 3개 체크포인트만 보관
            evaluation_strategy="steps" if eval_dataset else "no",
            eval_steps=save_steps if eval_dataset else None,
            logging_steps=logging_steps,
            logging_dir=os.path.join(output_dir, "logs"),
            fp16=False,
            bf16=True,                      # bfloat16으로 학습 (Ampere GPU 권장)
            report_to="none",               # wandb/tensorboard 미사용 (선택 변경 가능)
            load_best_model_at_end=True if eval_dataset else False,
            metric_for_best_model="eval_loss" if eval_dataset else None,
            group_by_length=True,           # 유사 길이 시퀀스 묶기 (패딩 최소화)
        )

        trainer = SFTTrainer(
            model=self.model,
            tokenizer=self.tokenizer,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            args=sft_config,
        )

        logger.info(
            f"학습 시작 — epochs={epochs}, batch_size={batch_size}, lr={lr}"
        )
        train_result = trainer.train()

        # 최종 모델 저장 (LoRA 어댑터만)
        final_adapter_path = os.path.join(output_dir, "final_adapter")
        trainer.save_model(final_adapter_path)
        self.tokenizer.save_pretrained(final_adapter_path)
        logger.info(f"LoRA 어댑터 저장 완료: {final_adapter_path}")

        metrics = {
            "train_loss": train_result.training_loss,
            "train_runtime": train_result.metrics.get("train_runtime", 0),
            "train_samples_per_second": train_result.metrics.get(
                "train_samples_per_second", 0
            ),
            "total_steps": train_result.global_step,
            "epochs": epochs,
            "output_dir": output_dir,
            "adapter_path": final_adapter_path,
        }
        logger.info(f"학습 완료 — 최종 loss: {metrics['train_loss']:.4f}")
        return metrics

    def merge_and_save(
        self,
        output_dir: str,
        adapter_path: Optional[str] = None,
        merged_model_name: str = "merged_model",
        push_to_hub: bool = False,
        hub_repo_id: Optional[str] = None,
    ) -> str:
        """
        LoRA 가중치를 베이스 모델에 병합하여 완전한 모델로 저장

        병합된 모델은 추론 시 PEFT 라이브러리 없이 직접 로드 가능합니다.

        Args:
            output_dir: 학습 출력 디렉토리
            adapter_path: 어댑터 경로 (None이면 output_dir/final_adapter 사용)
            merged_model_name: 병합 모델 저장 디렉토리명
            push_to_hub: HuggingFace Hub 업로드 여부
            hub_repo_id: Hub 레포지토리 ID (push_to_hub=True 시 필요)

        Returns:
            병합된 모델 저장 경로
        """
        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        except ImportError as e:
            raise ImportError("transformers, peft 패키지가 필요합니다.") from e

        if adapter_path is None:
            adapter_path = os.path.join(output_dir, "final_adapter")

        if not Path(adapter_path).exists():
            raise FileNotFoundError(f"어댑터 경로를 찾을 수 없습니다: {adapter_path}")

        merged_path = os.path.join(output_dir, merged_model_name)
        Path(merged_path).mkdir(parents=True, exist_ok=True)

        logger.info(f"베이스 모델 재로드 (병합용, fp16): {self.base_model_name}")

        # 병합은 fp16 풀 정밀도로 수행 (4비트 양자화 없이)
        base_model = AutoModelForCausalLM.from_pretrained(
            self.base_model_name,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )

        logger.info(f"LoRA 어댑터 로드: {adapter_path}")
        peft_model = PeftModel.from_pretrained(base_model, adapter_path)

        logger.info("LoRA 가중치 병합 시작 (merge_and_unload)...")
        merged_model = peft_model.merge_and_unload()

        # 병합 모델 저장
        merged_model.save_pretrained(merged_path, safe_serialization=True)

        # 토크나이저도 함께 저장
        tokenizer = AutoTokenizer.from_pretrained(adapter_path, trust_remote_code=True)
        tokenizer.save_pretrained(merged_path)

        logger.info(f"병합 모델 저장 완료: {merged_path}")

        if push_to_hub:
            if not hub_repo_id:
                raise ValueError("push_to_hub=True 시 hub_repo_id를 지정하세요.")
            logger.info(f"HuggingFace Hub 업로드: {hub_repo_id}")
            merged_model.push_to_hub(hub_repo_id, safe_serialization=True)
            tokenizer.push_to_hub(hub_repo_id)
            logger.info("Hub 업로드 완료")

        # 메모리 해제
        del peft_model, base_model
        try:
            import gc
            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

        return merged_path

    # ------------------------------------------------------------------
    # 내부 유틸리티 메서드
    # ------------------------------------------------------------------

    def _format_chat(self, sample: Dict[str, Any]) -> str:
        """
        instruction-response 쌍을 Llama-3 chat 포맷으로 변환

        Llama-3 Instruct 포맷:
        <|begin_of_text|><|start_header_id|>system<|end_header_id|>
        {system}<|eot_id|>
        <|start_header_id|>user<|end_header_id|>
        {user}<|eot_id|>
        <|start_header_id|>assistant<|end_header_id|>
        {assistant}<|eot_id|>
        """
        system_prompt = (
            "당신은 부동산 경제 분석 전문가입니다. "
            "제시된 부동산 지표를 바탕으로 해당 지역의 경제상황을 전문적으로 분석하고 "
            "시장 신호와 투자 시사점을 제공하세요."
        )
        instruction = sample.get("instruction", "")
        response = sample.get("response", "")

        text = (
            "<|begin_of_text|>"
            "<|start_header_id|>system<|end_header_id|>\n"
            f"{system_prompt}<|eot_id|>"
            "<|start_header_id|>user<|end_header_id|>\n"
            f"{instruction}<|eot_id|>"
            "<|start_header_id|>assistant<|end_header_id|>\n"
            f"{response}<|eot_id|>"
        )
        return text

    def _load_jsonl(self, path: str) -> List[Dict[str, Any]]:
        """JSONL 파일 로드"""
        import json

        records = []
        with open(path, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning(f"JSONL 파싱 실패 (line {lineno}): {e}")
        return records

    def _count_parameters(self) -> int:
        """전체 모델 파라미터 수 반환"""
        if self.model is None:
            return 0
        return sum(p.numel() for p in self.model.parameters())

    def _count_trainable_parameters(self) -> tuple:
        """(학습 가능 파라미터 수, 전체 파라미터 수) 반환"""
        if self.model is None:
            return 0, 0
        trainable = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in self.model.parameters())
        return trainable, total
