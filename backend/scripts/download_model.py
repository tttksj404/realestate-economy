#!/usr/bin/env python3
"""
LLM 및 임베딩 모델 사전 다운로드

Docker 컨테이너 빌드 후 첫 실행 전에 모델을 미리 다운로드합니다.
GPU 컨테이너 안에서 실행:

    docker compose -f docker-compose.yml -f docker-compose.gpu.yml \
        run --rm backend python scripts/download_model.py

또는 로컬에서:
    python scripts/download_model.py
"""

import argparse
import logging
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("download_model")


def download_llm(model_id: str) -> None:
    """LLM 모델 다운로드 (4bit 양자화용 베이스)"""
    logger.info(f"Downloading LLM: {model_id}")

    from transformers import AutoModelForCausalLM, AutoTokenizer

    logger.info("  Downloading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    logger.info(f"  Tokenizer ready: {tokenizer.__class__.__name__}")

    logger.info("  Downloading model weights (this may take 10-20 minutes)...")
    try:
        import torch
        from transformers import BitsAndBytesConfig

        if torch.cuda.is_available():
            # 4bit 양자화로 로드 테스트
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )
            model = AutoModelForCausalLM.from_pretrained(
                model_id,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
            )
            vram = torch.cuda.memory_allocated() / 1024**3
            logger.info(f"  Model loaded (4bit) — VRAM usage: {vram:.1f} GB")
            del model
            torch.cuda.empty_cache()
        else:
            # CPU only — weights만 다운로드 (로드는 안 함)
            from huggingface_hub import snapshot_download
            snapshot_download(model_id)
            logger.info("  Model weights downloaded (CPU mode, not loaded)")

    except Exception as e:
        logger.warning(f"  Full model load failed ({e}), downloading weights only...")
        from huggingface_hub import snapshot_download
        snapshot_download(model_id)

    logger.info(f"  LLM download complete: {model_id}")


def download_embedding(model_id: str) -> None:
    """임베딩 모델 다운로드"""
    logger.info(f"Downloading embedding model: {model_id}")

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_id)
    # 테스트 인코딩
    test = model.encode(["테스트 문장입니다"])
    logger.info(f"  Embedding ready: dim={test.shape[1]}")
    del model

    logger.info(f"  Embedding download complete: {model_id}")


def main():
    parser = argparse.ArgumentParser(description="모델 사전 다운로드")
    parser.add_argument(
        "--llm",
        default="beomi/Llama-3-Open-Ko-8B",
        help="LLM 모델 ID (기본값: beomi/Llama-3-Open-Ko-8B)",
    )
    parser.add_argument(
        "--embedding",
        default="intfloat/multilingual-e5-large",
        help="임베딩 모델 ID (기본값: intfloat/multilingual-e5-large)",
    )
    parser.add_argument(
        "--skip-llm", action="store_true", help="LLM 다운로드 건너뜀"
    )
    parser.add_argument(
        "--skip-embedding", action="store_true", help="임베딩 다운로드 건너뜀"
    )
    args = parser.parse_args()

    if not args.skip_embedding:
        download_embedding(args.embedding)

    if not args.skip_llm:
        download_llm(args.llm)

    logger.info("All models downloaded successfully!")


if __name__ == "__main__":
    main()
