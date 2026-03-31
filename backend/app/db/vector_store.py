import logging
from typing import List, Optional

import chromadb
from chromadb import Collection
from chromadb.config import Settings as ChromaSettings

from app.config import settings

logger = logging.getLogger(__name__)

# ChromaDB 컬렉션 이름 상수
COLLECTION_REALESTATE_ANALYSIS = "realestate_analysis"
COLLECTION_MARKET_REPORTS = "market_reports"


class EmbeddingFunction:
    """
    ChromaDB용 sentence-transformers 임베딩 함수

    multilingual-e5-large 모델 사용 (한국어 최적화)
    """

    def __init__(self, model_name: str = settings.EMBEDDING_MODEL_NAME):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        """지연 로딩: 첫 사용 시 모델 로드"""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded.")
        return self._model

    def __call__(self, input: List[str]) -> List[List[float]]:
        """ChromaDB EmbeddingFunction 인터페이스 구현"""
        model = self._load_model()
        # multilingual-e5 모델은 "query: " / "passage: " prefix 사용
        prefixed = [f"passage: {text}" for text in input]
        embeddings = model.encode(prefixed, normalize_embeddings=True)
        return embeddings.tolist()


class VectorStore:
    """
    ChromaDB 벡터 스토어 래퍼

    부동산 분석 리포트, 시장 동향 문서를 벡터화하여 저장/검색
    """

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.CHROMADB_PATH,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )
        self.embedding_fn = EmbeddingFunction()
        self._collections: dict[str, Collection] = {}

    def init_collection(self) -> None:
        """기본 컬렉션 초기화"""
        for name in [COLLECTION_REALESTATE_ANALYSIS, COLLECTION_MARKET_REPORTS]:
            collection = self.client.get_or_create_collection(
                name=name,
                embedding_function=self.embedding_fn,
                metadata={"hnsw:space": "cosine"},
            )
            self._collections[name] = collection
            logger.info(f"ChromaDB collection '{name}' ready. Count: {collection.count()}")

    def _get_collection(self, name: str = COLLECTION_REALESTATE_ANALYSIS) -> Collection:
        """컬렉션 인스턴스 반환 (없으면 초기화)"""
        if name not in self._collections:
            self._collections[name] = self.client.get_or_create_collection(
                name=name,
                embedding_function=self.embedding_fn,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[name]

    def add_documents(
        self,
        documents: List[str],
        metadatas: List[dict],
        ids: List[str],
        collection_name: str = COLLECTION_REALESTATE_ANALYSIS,
    ) -> None:
        """
        문서 벡터화 후 컬렉션에 저장

        Args:
            documents: 원본 텍스트 문서 리스트
            metadatas: 각 문서의 메타데이터 (region_code, period, signal 등)
            ids: 문서 고유 ID 리스트
            collection_name: 대상 컬렉션 이름
        """
        collection = self._get_collection(collection_name)

        # 기존 ID 중복 방지: upsert 방식 사용
        collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )
        logger.info(f"Upserted {len(documents)} documents into '{collection_name}'.")

    def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[dict] = None,
        collection_name: str = COLLECTION_REALESTATE_ANALYSIS,
    ) -> List[dict]:
        """
        유사도 검색

        Args:
            query: 검색 쿼리 텍스트
            n_results: 반환할 최대 결과 수
            where: 메타데이터 필터 (예: {"region_code": {"$eq": "11"}})
            collection_name: 검색 대상 컬렉션

        Returns:
            [{
                "id": str,
                "document": str,
                "metadata": dict,
                "distance": float,
            }]
        """
        collection = self._get_collection(collection_name)

        if collection.count() == 0:
            logger.warning(f"Collection '{collection_name}' is empty. Returning empty results.")
            return []

        # multilingual-e5 query prefix 적용
        query_with_prefix = f"query: {query}"

        query_params: dict = {
            "query_texts": [query_with_prefix],
            "n_results": min(n_results, collection.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_params["where"] = where

        results = collection.query(**query_params)

        # 결과 정규화
        output = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                output.append(
                    {
                        "id": doc_id,
                        "document": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i],
                    }
                )
        return output

    def delete_collection(self, name: str) -> None:
        """컬렉션 삭제 (주의: 영구 삭제)"""
        self.client.delete_collection(name)
        self._collections.pop(name, None)
        logger.warning(f"Collection '{name}' deleted.")

    def get_collection_count(self, name: str = COLLECTION_REALESTATE_ANALYSIS) -> int:
        """컬렉션 문서 수 반환"""
        return self._get_collection(name).count()
