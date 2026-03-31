"""
RAG (Retrieval-Augmented Generation) 서비스

ChromaDB에서 관련 부동산 분석 문서를 검색하여
LLM 프롬프트 컨텍스트를 구성합니다.
"""

import logging
from typing import List, Optional

from app.config import settings
from app.db.vector_store import VectorStore, COLLECTION_REALESTATE_ANALYSIS

logger = logging.getLogger(__name__)


class RAGService:
    """
    RAG 서비스

    사용자 쿼리 + 지역 정보를 기반으로 ChromaDB에서
    유사한 과거 분석 사례를 검색하여 LLM 컨텍스트를 구성합니다.

    컨텍스트 구성 전략:
    1. 동일 지역 최신 분석 (높은 가중치)
    2. 유사 지표 패턴의 타 지역 사례
    3. 관련 시장 리포트
    """

    def __init__(self):
        self.vector_store = VectorStore()
        self.top_k = settings.RAG_TOP_K
        self.similarity_threshold = settings.RAG_SIMILARITY_THRESHOLD

    async def retrieve(
        self,
        query: str,
        region: Optional[str] = None,
        indicators: Optional[dict] = None,
        collection_name: str = COLLECTION_REALESTATE_ANALYSIS,
    ) -> str:
        """
        RAG 컨텍스트 검색 및 구성

        Args:
            query: 사용자 질의 텍스트
            region: 분석 대상 지역 코드 (지정 시 해당 지역 우선 검색)
            indicators: 현재 계산된 경제 지표 (보강 검색에 활용)
            collection_name: 검색 대상 컬렉션

        Returns:
            LLM 프롬프트에 삽입할 컨텍스트 문자열
        """
        retrieved_docs = []

        # 1단계: 지역 특화 검색 (지역이 지정된 경우)
        if region:
            region_docs = self._search_by_region(
                query=query,
                region=region,
                n_results=3,
                collection_name=collection_name,
            )
            retrieved_docs.extend(region_docs)

        # 2단계: 의미 유사도 기반 전체 검색 (잔여 슬롯 채우기)
        remaining_slots = self.top_k - len(retrieved_docs)
        if remaining_slots > 0:
            # 지표 정보를 보강 쿼리로 추가
            enriched_query = self._build_enriched_query(query, region, indicators)
            global_docs = self._search_global(
                query=enriched_query,
                n_results=remaining_slots + 2,  # 여유분 검색 후 필터링
                collection_name=collection_name,
            )

            # 이미 포함된 문서 중복 제거
            existing_ids = {doc["id"] for doc in retrieved_docs}
            for doc in global_docs:
                if doc["id"] not in existing_ids and len(retrieved_docs) < self.top_k:
                    # 유사도 임계값 필터링 (distance가 낮을수록 유사)
                    if doc.get("distance", 1.0) <= (1.0 - self.similarity_threshold):
                        retrieved_docs.append(doc)
                        existing_ids.add(doc["id"])

        if not retrieved_docs:
            logger.info(f"No relevant documents found for query: {query[:100]}")
            return ""

        # 컨텍스트 문자열 구성
        context = self._build_context_string(retrieved_docs)
        logger.info(f"RAG context built with {len(retrieved_docs)} documents ({len(context)} chars)")
        return context

    def _search_by_region(
        self,
        query: str,
        region: str,
        n_results: int,
        collection_name: str,
    ) -> List[dict]:
        """지역 코드 필터를 적용한 검색"""
        try:
            # ChromaDB where 필터: region_code가 region으로 시작하는 문서
            # 주의: ChromaDB는 startsWith 미지원, 정확히 일치하는 코드 사용
            where_filter = {"region_code": {"$eq": region}}

            docs = self.vector_store.search(
                query=query,
                n_results=n_results,
                where=where_filter,
                collection_name=collection_name,
            )
            return docs
        except Exception as e:
            logger.warning(f"Region-specific search failed: {e}")
            return []

    def _search_global(
        self,
        query: str,
        n_results: int,
        collection_name: str,
    ) -> List[dict]:
        """전체 컬렉션 검색 (지역 필터 없음)"""
        try:
            docs = self.vector_store.search(
                query=query,
                n_results=n_results,
                collection_name=collection_name,
            )
            return docs
        except Exception as e:
            logger.warning(f"Global search failed: {e}")
            return []

    def _build_enriched_query(
        self,
        original_query: str,
        region: Optional[str],
        indicators: Optional[dict],
    ) -> str:
        """
        원본 쿼리에 지역/지표 정보를 보강하여 검색 정확도 향상

        Args:
            original_query: 원본 사용자 쿼리
            region: 지역 코드
            indicators: 경제 지표 딕셔너리

        Returns:
            보강된 검색 쿼리 텍스트
        """
        parts = [original_query]

        if region:
            parts.append(f"지역: {region}")

        if indicators:
            # 주요 지표만 추가
            if indicators.get("signal"):
                parts.append(f"시장신호: {indicators['signal']}")
            if indicators.get("jeonse_ratio") is not None:
                jr = indicators["jeonse_ratio"]
                if jr >= 70:
                    parts.append("전세가율 높음 갭투자 위험")
                elif jr < 60:
                    parts.append("전세가율 낮음 매매 강세")
            if indicators.get("listing_count_change") is not None:
                lcc = indicators["listing_count_change"]
                if lcc > 10:
                    parts.append("매물 급증 공급 과잉")
                elif lcc < -10:
                    parts.append("매물 감소 공급 부족")

        return " ".join(parts)

    def _build_context_string(self, docs: List[dict]) -> str:
        """
        검색된 문서들을 LLM 프롬프트용 컨텍스트 텍스트로 변환

        Args:
            docs: 검색 결과 문서 리스트 (id, document, metadata, distance 포함)

        Returns:
            포맷된 컨텍스트 문자열
        """
        context_parts = [
            "=== 참고 자료 (RAG 검색 결과) ===\n"
        ]

        for i, doc in enumerate(docs, start=1):
            metadata = doc.get("metadata", {})
            region_name = metadata.get("region_name", "")
            period = metadata.get("period", "")
            signal = metadata.get("signal", "")
            source_type = metadata.get("source_type", "분석 리포트")

            header = f"[참고 {i}]"
            if region_name or period:
                header += f" {region_name} {period}"
            if signal:
                header += f" (신호: {signal})"
            header += f" - {source_type}"

            context_parts.append(f"{header}\n{doc.get('document', '')}\n")

        context_parts.append("=== 참고 자료 끝 ===\n")
        return "\n".join(context_parts)

    async def add_analysis_to_store(
        self,
        region_code: str,
        region_name: str,
        period: str,
        signal: str,
        indicators: dict,
        analysis_text: str,
        doc_id: Optional[str] = None,
    ) -> str:
        """
        분석 결과를 벡터 스토어에 저장

        향후 유사 시장 상황 검색에 활용됩니다.

        Args:
            region_code: 지역 코드
            region_name: 지역명
            period: 분석 기간
            signal: 경제 신호
            indicators: 지표 데이터
            analysis_text: 분석 리포트 텍스트
            doc_id: 문서 ID (미입력 시 자동 생성)

        Returns:
            저장된 문서 ID
        """
        from app.data.processors.embedder import DocumentEmbedder

        embedder = DocumentEmbedder()
        doc_text = embedder.create_document_text(
            region_name=region_name,
            period=period,
            signal=signal,
            indicators=indicators,
            analysis_text=analysis_text,
        )

        if doc_id is None:
            doc_id = f"{region_code}_{period}_{signal}"

        metadata = {
            "region_code": region_code,
            "region_name": region_name,
            "period": period,
            "signal": signal,
            "source_type": "AI분석",
        }
        # 지표 메타데이터 추가
        for k, v in indicators.items():
            if v is not None:
                metadata[k] = float(v)

        self.vector_store.add_documents(
            documents=[doc_text],
            metadatas=[metadata],
            ids=[doc_id],
        )

        logger.info(f"Analysis stored in vector store: {doc_id}")
        return doc_id
