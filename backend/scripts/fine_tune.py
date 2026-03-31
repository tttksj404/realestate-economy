#!/usr/bin/env python3
"""
QLoRA 파인튜닝 실행 스크립트

1. DB에서 EconomyIndicator 레코드를 수집하여 JSONL 데이터셋 생성
2. 데이터 증강으로 학습 데이터 풍부도 향상
3. QLoRA(4비트 양자화 + LoRA) 파인튜닝 실행
4. 모델 평가 및 리포트 생성
5. LoRA 가중치 병합 후 최종 모델 저장

사용 예시:
    # 기본 설정 (Llama-3.1-8B, 3 에폭)
    python scripts/fine_tune.py

    # 커스텀 설정
    python scripts/fine_tune.py --base-model beomi/Llama-3-Open-Ko-8B \\
        --output-dir ./ft_output/ko-llama --epochs 5 --batch-size 2

    # 데이터셋만 빌드
    python scripts/fine_tune.py --dataset-only --output-dir ./ft_data

    # 기존 데이터셋으로 학습만 실행
    python scripts/fine_tune.py --skip-build --dataset-path ./ft_data/train.jsonl
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# 프로젝트 루트를 sys.path에 추가
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.ml.fine_tuning.dataset_builder import DatasetBuilder
from app.ml.fine_tuning.evaluator import ModelEvaluator
from app.ml.fine_tuning.trainer import FineTuner

# ---------------------------------------------------------------------------
# 로깅 설정
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("fine_tune")


async def build_dataset(
    output_dir: Path,
    num_variations: int = 2,
    min_confidence: float = 0.5,
    eval_split: float = 0.1,
) -> tuple[str, str]:
    """
    DB에서 데이터셋을 구축하고 train/test JSONL로 저장합니다.

    Args:
        output_dir: 데이터셋 저장 디렉토리
        num_variations: 증강 변형 수
        min_confidence: 최소 신뢰도 필터
        eval_split: 테스트셋 분리 비율

    Returns:
        (train_path, test_path) 튜플
    """
    import random

    logger.info("데이터셋 빌드 시작")

    # DB 연결
    engine = create_async_engine(
        settings.DATABASE_URL, echo=False, pool_pre_ping=True
    )
    SessionFactory = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False
    )

    builder = DatasetBuilder(min_confidence=min_confidence)

    # DB에서 원본 데이터셋 구축
    async with SessionFactory() as session:
        raw_dataset = await builder.build_from_db(session)

    await engine.dispose()

    if not raw_dataset:
        logger.error("DB에서 수집된 EconomyIndicator 레코드가 없습니다.")
        logger.error(
            "먼저 scripts/collect_data.py를 실행하여 데이터를 수집하고,\n"
            "경제 신호(signal) 및 신뢰도(confidence)가 계산된 레코드가 있어야 합니다."
        )
        sys.exit(1)

    logger.info(f"원본 데이터셋: {len(raw_dataset)}건")

    # 데이터 증강
    augmented = builder.augment_with_variations(
        raw_dataset, num_variations=num_variations
    )
    logger.info(f"증강 후 데이터셋: {len(augmented)}건")

    # 통계 출력
    stats = builder.get_statistics(augmented)
    logger.info(f"신호 분포: {stats['signal_distribution']}")
    logger.info(f"지역 분포: {stats['region_distribution']}")

    # Train/Test 분리 (랜덤 셔플 후 분리)
    rng = random.Random(42)
    rng.shuffle(augmented)

    split_idx = int(len(augmented) * (1 - eval_split))
    train_data = augmented[:split_idx]
    test_data = augmented[split_idx:]

    # 저장
    output_dir.mkdir(parents=True, exist_ok=True)
    train_path = str(output_dir / "train.jsonl")
    test_path = str(output_dir / "test.jsonl")

    saved_train = builder.save_dataset(train_data, train_path, include_meta=True)
    saved_test = builder.save_dataset(test_data, test_path, include_meta=True)

    logger.info(
        f"데이터셋 저장 완료 — 훈련: {saved_train}건 ({train_path}), "
        f"테스트: {saved_test}건 ({test_path})"
    )
    return train_path, test_path


def run_training(
    train_path: str,
    output_dir: str,
    base_model: str,
    epochs: int,
    batch_size: int,
    lr: float,
    lora_r: int,
    lora_alpha: int,
    max_seq_length: int,
) -> dict:
    """
    QLoRA 파인튜닝 실행

    Args:
        train_path: 학습 데이터셋 경로
        output_dir: 모델 저장 경로
        base_model: 베이스 모델 ID
        epochs: 학습 에폭
        batch_size: 배치 크기
        lr: 학습률
        lora_r: LoRA 랭크
        lora_alpha: LoRA 알파
        max_seq_length: 최대 시퀀스 길이

    Returns:
        학습 결과 메트릭 딕셔너리
    """
    logger.info("=" * 60)
    logger.info("QLoRA 파인튜닝 시작")
    logger.info(f"  베이스 모델  : {base_model}")
    logger.info(f"  출력 디렉토리: {output_dir}")
    logger.info(f"  에폭         : {epochs}")
    logger.info(f"  배치 크기    : {batch_size}")
    logger.info(f"  학습률       : {lr}")
    logger.info(f"  LoRA r       : {lora_r}")
    logger.info(f"  LoRA alpha   : {lora_alpha}")
    logger.info("=" * 60)

    tuner = FineTuner()

    # 모델 및 LoRA 설정
    tuner.setup_model(base_model=base_model)
    tuner.setup_lora(
        r=lora_r,
        lora_alpha=lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )

    # 학습 실행
    train_metrics = tuner.train(
        dataset_path=train_path,
        output_dir=output_dir,
        epochs=epochs,
        batch_size=batch_size,
        lr=lr,
        max_seq_length=max_seq_length,
    )

    logger.info(f"학습 완료 — loss: {train_metrics['train_loss']:.4f}")

    # LoRA 가중치 병합
    logger.info("LoRA 가중치 병합 시작...")
    merged_path = tuner.merge_and_save(output_dir=output_dir)
    train_metrics["merged_model_path"] = merged_path

    return train_metrics


def run_evaluation(
    model_path: str,
    test_dataset_path: str,
    output_dir: str,
    max_samples: Optional[int] = None,
) -> dict:
    """
    파인튜닝된 모델 평가 실행

    Args:
        model_path: 평가할 모델 경로 (병합 모델 권장)
        test_dataset_path: 테스트 데이터셋 JSONL 경로
        output_dir: 리포트 저장 디렉토리
        max_samples: 최대 평가 샘플 수

    Returns:
        평가 메트릭 딕셔너리
    """
    logger.info(f"모델 평가 시작: {model_path}")

    evaluator = ModelEvaluator(
        max_new_tokens=512,
        temperature=0.1,  # 평가 시 낮은 온도로 결정론적 생성
    )

    # 평가 실행
    results = evaluator.evaluate(
        model_path=model_path,
        test_dataset_path=test_dataset_path,
        max_samples=max_samples,
    )

    # 메트릭 계산
    metrics = evaluator.compute_metrics(results)

    # 리포트 생성
    report_path = str(Path(output_dir) / "evaluation_report.json")
    report = evaluator.generate_report(
        output_path=report_path,
        model_path=model_path,
        test_dataset_path=test_dataset_path,
        results=results,
        include_samples=True,
    )

    logger.info(f"평가 리포트 저장: {report_path}")
    return metrics


def save_run_summary(
    output_dir: str,
    args: argparse.Namespace,
    train_metrics: Optional[dict],
    eval_metrics: Optional[dict],
) -> None:
    """
    전체 실행 요약을 JSON으로 저장합니다.
    """
    summary = {
        "run_at": datetime.now().isoformat(),
        "config": {
            "base_model": args.base_model,
            "output_dir": args.output_dir,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "lr": args.lr,
            "lora_r": args.lora_r,
            "lora_alpha": args.lora_alpha,
        },
        "train_metrics": train_metrics,
        "eval_metrics": eval_metrics,
    }

    summary_path = Path(output_dir) / "run_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info(f"실행 요약 저장: {summary_path}")


async def main(args: argparse.Namespace) -> None:
    """파인튜닝 전체 파이프라인 실행"""
    output_dir = Path(args.output_dir)
    data_dir = output_dir / "data"

    train_metrics = None
    eval_metrics = None

    # 1단계: 데이터셋 빌드
    if not args.skip_build:
        train_path, test_path = await build_dataset(
            output_dir=data_dir,
            num_variations=args.augment_variations,
            min_confidence=args.min_confidence,
            eval_split=args.eval_split,
        )
    else:
        # 기존 데이터셋 사용
        if not args.dataset_path:
            logger.error("--skip-build 사용 시 --dataset-path를 지정해야 합니다.")
            sys.exit(1)
        train_path = args.dataset_path
        # 테스트셋은 동일 디렉토리의 test.jsonl 탐색
        test_path_candidate = str(Path(args.dataset_path).parent / "test.jsonl")
        test_path = test_path_candidate if Path(test_path_candidate).exists() else args.dataset_path
        logger.info(f"기존 데이터셋 사용 — 훈련: {train_path}")

    # 데이터셋만 빌드하고 종료
    if args.dataset_only:
        logger.info("--dataset-only 옵션: 데이터셋 빌드 후 종료")
        return

    # 2단계: QLoRA 파인튜닝
    model_output_dir = str(output_dir / "model")
    train_metrics = run_training(
        train_path=train_path,
        output_dir=model_output_dir,
        base_model=args.base_model,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        max_seq_length=args.max_seq_length,
    )

    # 3단계: 평가 (병합된 최종 모델 기준)
    if not args.skip_eval:
        merged_model_path = train_metrics.get(
            "merged_model_path", str(Path(model_output_dir) / "merged_model")
        )
        eval_dir = str(output_dir / "eval")

        eval_metrics = run_evaluation(
            model_path=merged_model_path,
            test_dataset_path=test_path,
            output_dir=eval_dir,
            max_samples=args.eval_max_samples,
        )

        logger.info(
            f"평가 완료 — 신호 정확도: {eval_metrics['signal_accuracy']:.1%}, "
            f"ROUGE-L: {eval_metrics['avg_rougeL']:.4f}"
        )
    else:
        logger.info("--skip-eval 옵션: 평가 단계 건너뜀")

    # 4단계: 실행 요약 저장
    save_run_summary(
        output_dir=str(output_dir),
        args=args,
        train_metrics=train_metrics,
        eval_metrics=eval_metrics,
    )

    logger.info("=" * 60)
    logger.info("파인튜닝 파이프라인 완료")
    logger.info(f"출력 디렉토리: {output_dir}")
    logger.info("=" * 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="부동산 경제 분석 LLM QLoRA 파인튜닝 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 전체 파이프라인 (데이터 빌드 + 학습 + 평가)
  python scripts/fine_tune.py --output-dir ./ft_output

  # 커스텀 베이스 모델
  python scripts/fine_tune.py --base-model beomi/Llama-3-Open-Ko-8B --epochs 5

  # 데이터셋만 생성
  python scripts/fine_tune.py --dataset-only --output-dir ./ft_data

  # 기존 데이터셋으로 학습만
  python scripts/fine_tune.py --skip-build --dataset-path ./ft_data/data/train.jsonl

  # 학습 후 평가 건너뜀
  python scripts/fine_tune.py --skip-eval
        """,
    )

    # 모델 설정
    model_group = parser.add_argument_group("모델 설정")
    model_group.add_argument(
        "--base-model",
        default="meta-llama/Llama-3.1-8B-Instruct",
        help="파인튜닝 베이스 모델 ID 또는 로컬 경로 (기본값: Llama-3.1-8B-Instruct)",
    )
    model_group.add_argument(
        "--output-dir",
        default="./ft_output",
        help="출력 디렉토리 (체크포인트, 모델, 리포트 저장, 기본값: ./ft_output)",
    )

    # 학습 하이퍼파라미터
    train_group = parser.add_argument_group("학습 하이퍼파라미터")
    train_group.add_argument(
        "--epochs", type=int, default=3, help="학습 에폭 수 (기본값: 3)"
    )
    train_group.add_argument(
        "--batch-size", type=int, default=4, dest="batch_size",
        help="GPU당 배치 크기 (기본값: 4, 메모리 부족 시 2로 낮추세요)"
    )
    train_group.add_argument(
        "--lr", type=float, default=2e-4, help="학습률 (기본값: 2e-4)"
    )
    train_group.add_argument(
        "--max-seq-length", type=int, default=2048, dest="max_seq_length",
        help="최대 시퀀스 길이 토큰 수 (기본값: 2048)"
    )

    # LoRA 설정
    lora_group = parser.add_argument_group("LoRA 설정")
    lora_group.add_argument(
        "--lora-r", type=int, default=16, dest="lora_r",
        help="LoRA 랭크 r (기본값: 16, 높을수록 표현력↑ 메모리↑)"
    )
    lora_group.add_argument(
        "--lora-alpha", type=int, default=32, dest="lora_alpha",
        help="LoRA 스케일 알파 (기본값: 32, 보통 r의 2배)"
    )

    # 데이터셋 설정
    data_group = parser.add_argument_group("데이터셋 설정")
    data_group.add_argument(
        "--dataset-only", action="store_true", default=False,
        help="데이터셋 빌드만 수행하고 종료"
    )
    data_group.add_argument(
        "--skip-build", action="store_true", default=False,
        help="데이터셋 빌드 건너뜀 (기존 데이터셋 사용)"
    )
    data_group.add_argument(
        "--dataset-path", default=None,
        help="--skip-build 시 사용할 기존 학습 데이터셋 경로"
    )
    data_group.add_argument(
        "--augment-variations", type=int, default=2, dest="augment_variations",
        help="원본 1건당 데이터 증강 변형 수 (기본값: 2)"
    )
    data_group.add_argument(
        "--min-confidence", type=float, default=0.5, dest="min_confidence",
        help="파인튜닝 사용 최소 신뢰도 (기본값: 0.5)"
    )
    data_group.add_argument(
        "--eval-split", type=float, default=0.1, dest="eval_split",
        help="테스트셋 분리 비율 (기본값: 0.1 = 10%%)"
    )

    # 평가 설정
    eval_group = parser.add_argument_group("평가 설정")
    eval_group.add_argument(
        "--skip-eval", action="store_true", default=False,
        help="평가 단계 건너뜀"
    )
    eval_group.add_argument(
        "--eval-max-samples", type=int, default=None, dest="eval_max_samples",
        help="최대 평가 샘플 수 (기본값: 전체)"
    )

    # 로그 레벨
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="로그 레벨 (기본값: INFO)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    asyncio.run(main(args))
