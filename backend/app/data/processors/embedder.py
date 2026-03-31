"""
임베딩 생성 모듈

sentence-transformers의 multilingual-e5-large 모델을 사용하여
부동산 분석 문서를 벡터화합니다.

multilingual-e5 모델 사용 시:
- 검색 쿼리: "query: {text}" prefix 사용
- 저장 문서: "passage: {text}" prefix 사용
"""

import logging
from typing import List, Optional, Union

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


class DocumentEmbedder:
    """
    문서 임베딩 생성기

    sentence-transformers의 multilingual-e5-large 모델을 사용하며
    지연 로딩(lazy loading)을 통해 메모리 효율을 높입니다.

    사용 예시:
        embedder = DocumentEmbedder()
        vector = embedder.embed_text("서울 강남구 아파트 시장 분석")
        vectors = embedder.embed_documents(["문서1", "문서2"])
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: int = 32,
    ):
        """
        Args:
            model_name: 사용할 모델명 (기본: settings.EMBEDDING_MODEL_NAME)
            device: 추론 디바이스 ("cpu", "cuda", "mps" 등, None이면 자동 감지)
            batch_size: 배치 처리 크기
        """
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self.device = device
        self.batch_size = batch_size
        self._model = None

    def _load_model(self):
        """모델 지연 로딩 (첫 사용 시 로드)"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                import torch

                # 디바이스 자동 감지
                if self.device is None:
                    if torch.cuda.is_available():
                        self.device = "cuda"
                    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                        self.device = "mps"
                    else:
                        self.device = "cpu"

                logger.info(
                    f"Loading embedding model: {self.model_name} on device: {self.device}"
                )
                self._model = SentenceTransformer(
                    self.model_name,
                    device=self.device,
                )
                logger.info(
                    f"Embedding model loaded. Embedding dim: {self._model.get_sentence_embedding_dimension()}"
                )
            except ImportError as e:
                logger.error(f"sentence-transformers not installed: {e}")
                raise
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise

        return self._model

    @property
    def embedding_dim(self) -> int:
        """임베딩 벡터 차원 수"""
        model = self._load_model()
        return model.get_sentence_embedding_dimension()

    def embed_text(
        self,
        text: str,
        is_query: bool = False,
    ) -> List[float]:
        """
        단일 텍스트 임베딩

        Args:
            text: 임베딩할 텍스트
            is_query: True이면 "query: " prefix, False이면 "passage: " prefix

        Returns:
            float 리스트 (임베딩 벡터)
        """
        model = self._load_model()

        # multilingual-e5 prefix 적용
        prefix = "query: " if is_query else "passage: "
        prefixed_text = f"{prefix}{text}"

        embedding = model.encode(
            prefixed_text,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embedding.tolist()

    def embed_documents(
        self,
        documents: List[str],
        show_progress: bool = False,
    ) -> List[List[float]]:
        """
        복수 문서 배치 임베딩

        Args:
            documents: 임베딩할 텍스트 문서 리스트
            show_progress: 진행률 표시 여부

        Returns:
            각 문서의 임베딩 벡터 리스트 (n_docs × embedding_dim)
        """
        if not documents:
            return []

        model = self._load_model()

        # "passage: " prefix 일괄 적용
        prefixed_docs = [f"passage: {doc}" for doc in documents]

        embeddings = model.encode(
            prefixed_docs,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=show_progress,
        )

        return embeddings.tolist()

    def embed_queries(self, queries: List[str]) -> List[List[float]]:
        """
        검색 쿼리 배치 임베딩 (query prefix 사용)

        Args:
            queries: 검색 쿼리 리스트

        Returns:
            쿼리 임베딩 벡터 리스트
        """
        if not queries:
            return []

        model = self._load_model()
        prefixed_queries = [f"query: {q}" for q in queries]

        embeddings = model.encode(
            prefixed_queries,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return embeddings.tolist()

    def compute_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float],
    ) -> float:
        """
        두 임베딩 벡터의 코사인 유사도 계산

        Args:
            embedding1: 첫 번째 임베딩 벡터
            embedding2: 두 번째 임베딩 벡터

        Returns:
            코사인 유사도 (-1.0 ~ 1.0, normalize된 경우 0.0 ~ 1.0)
        """
        arr1 = np.array(embedding1)
        arr2 = np.array(embedding2)

        norm1 = np.linalg.norm(arr1)
        norm2 = np.linalg.norm(arr2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(arr1, arr2) / (norm1 * norm2))

    def create_document_text(
        self,
        region_name: str,
        period: str,
        signal: str,
        indicators: dict,
        analysis_text: str,
    ) -> str:
        """
        부동산 분석 결과를 임베딩용 문서 텍스트로 변환

        Args:
            region_name: 지역명
            period: 분석 기간
            signal: 경제 신호 (호황/보통/침체)
            indicators: 6개 지표 딕셔너리
            analysis_text: 분석 리포트 텍스트

        Returns:
            임베딩에 최적화된 문서 텍스트
        """
        indicator_text = (
            f"저가매물비율: {indicators.get('low_price_listing_ratio', 'N/A')}%, "
            f"매물증감률: {indicators.get('listing_count_change', 'N/A')}%, "
            f"호가괴리율: {indicators.get('price_gap_ratio', 'N/A')}%, "
            f"가격지수변동: {indicators.get('regional_price_index', 'N/A')}%, "
            f"매물소진기간: {indicators.get('sale_speed', 'N/A')}일, "
            f"전세가율: {indicators.get('jeonse_ratio', 'N/A')}%"
        )

        return (
            f"[{region_name}] {period} 부동산 경제 분석\n"
            f"경제 신호: {signal}\n"
            f"핵심 지표: {indicator_text}\n"
            f"분석 내용: {analysis_text}"
        )
