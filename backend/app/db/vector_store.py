import logging
from typing import List, Optional

import chromadb
from chromadb import Collection
from chromadb.config import Settings as ChromaSettings

from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION_REALESTATE_ANALYSIS = "realestate_analysis"
COLLECTION_MARKET_REPORTS = "market_reports"


class EmbeddingFunction:
    def __init__(self, model_name: str = settings.EMBEDDING_MODEL_NAME):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model: %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded.")
        return self._model

    def __call__(self, input: List[str]) -> List[List[float]]:
        model = self._load_model()
        prefixed = [f"passage: {text}" for text in input]
        embeddings = model.encode(prefixed, normalize_embeddings=True)
        return embeddings.tolist()


class VectorStore:
    def __init__(self):
        if settings.CHROMADB_HOST:
            logger.info(
                "Using remote ChromaDB at %s:%s",
                settings.CHROMADB_HOST,
                settings.CHROMADB_PORT,
            )
            self.client = chromadb.HttpClient(
                host=settings.CHROMADB_HOST,
                port=settings.CHROMADB_PORT,
                settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
            )
        else:
            logger.info("Using local ChromaDB path: %s", settings.CHROMADB_PATH)
            self.client = chromadb.PersistentClient(
                path=settings.CHROMADB_PATH,
                settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
            )

        self.embedding_fn = EmbeddingFunction()
        self._collections: dict[str, Collection] = {}

    def init_collection(self) -> None:
        for name in [COLLECTION_REALESTATE_ANALYSIS, COLLECTION_MARKET_REPORTS]:
            collection = self.client.get_or_create_collection(
                name=name,
                embedding_function=self.embedding_fn,
                metadata={"hnsw:space": "cosine"},
            )
            self._collections[name] = collection
            logger.info("ChromaDB collection '%s' ready. Count: %s", name, collection.count())

    def _get_collection(self, name: str = COLLECTION_REALESTATE_ANALYSIS) -> Collection:
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
        collection = self._get_collection(collection_name)
        collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
        logger.info("Upserted %s documents into '%s'.", len(documents), collection_name)

    def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[dict] = None,
        collection_name: str = COLLECTION_REALESTATE_ANALYSIS,
    ) -> List[dict]:
        collection = self._get_collection(collection_name)

        if collection.count() == 0:
            logger.warning("Collection '%s' is empty. Returning empty results.", collection_name)
            return []

        query_params: dict = {
            "query_texts": [f"query: {query}"],
            "n_results": min(n_results, collection.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_params["where"] = where

        results = collection.query(**query_params)

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
        self.client.delete_collection(name)
        self._collections.pop(name, None)
        logger.warning("Collection '%s' deleted.", name)

    def get_collection_count(self, name: str = COLLECTION_REALESTATE_ANALYSIS) -> int:
        return self._get_collection(name).count()
