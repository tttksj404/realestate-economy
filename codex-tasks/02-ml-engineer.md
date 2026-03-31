# Task 02: ML Engineer — RAG + 파인튜닝 파이프라인 구현 완성

## Goal
RAG 파이프라인과 LLM 파인튜닝 파이프라인이 end-to-end로 동작하도록 완성한다.

## Tasks

### 1. 임베딩 서비스 검증 (`processors/embedder.py`)
- `intfloat/multilingual-e5-large` 모델 로딩 테스트
- 한국어 부동산 텍스트 임베딩 품질 확인
- 배치 임베딩 성능 최적화 (GPU 사용 시)

### 2. ChromaDB 벡터 스토어 완성 (`db/vector_store.py`)
- 컬렉션 초기화 및 문서 추가 테스트
- 메타데이터 필터링 (지역별, 기간별) 동작 확인
- 유사도 검색 결과 품질 검증
- 중복 문서 처리 (upsert) 확인

### 3. RAG 서비스 개선 (`services/rag_service.py`)
- 검색 쿼리 최적화: 지역명 + 지표 키워드 조합
- 컨텍스트 윈도우 크기 제한 (LLM 토큰 한도 고려)
- 검색 결과 랭킹: relevance score 기반 상위 N개 선택
- 프롬프트 템플릿 최적화 (한국어, 부동산 도메인)

### 4. LLM 서비스 안정화 (`services/llm_service.py`)
- 모델 로딩 실패 시 fallback (규칙 기반 응답)
- 4bit 양자화 로딩 검증
- SSE 스트리밍 안정성 (TextIteratorStreamer)
- 응답 형식 강제: JSON structured output 또는 마크다운 구조

### 5. 파인튜닝 데이터셋 구축 (`ml/fine_tuning/dataset_builder.py`)
- 시드 데이터 50건 생성 (다양한 지역/시나리오)
- augmentation으로 500건까지 확장
- train/val/test split (80/10/10)
- 데이터 품질 검증 스크립트

### 6. 파인튜닝 실행 검증 (`ml/fine_tuning/trainer.py`)
- QLoRA 설정 파라미터 최적화
- 학습 로그 (loss, eval metrics) 확인
- 체크포인트 저장 및 모델 병합 검증
- VRAM 사용량 프로파일링 (16GB 기준)

### 7. 시드 데이터 파일 생성
- `backend/data/seed/economy_analysis_seed.jsonl` — 50건의 시드 학습 데이터

## Files to Modify
- `backend/app/db/vector_store.py`
- `backend/app/data/processors/embedder.py`
- `backend/app/services/rag_service.py`
- `backend/app/services/llm_service.py`
- `backend/app/ml/fine_tuning/dataset_builder.py`
- `backend/app/ml/fine_tuning/trainer.py`

## Files to Create
- `backend/data/seed/economy_analysis_seed.jsonl`
- `backend/tests/test_rag.py`
- `backend/tests/test_llm_service.py`
- `backend/tests/test_fine_tuning.py`

## Acceptance Criteria
- [ ] ChromaDB에 문서 추가 → 검색 → 관련 문서 반환 확인
- [ ] RAG: "서울 빌라 매물 증가" 질문 → 관련 컨텍스트 검색
- [ ] LLM: 지표 데이터 입력 → 경제상황 분석 텍스트 생성
- [ ] SSE 스트리밍으로 토큰 단위 응답 전송
- [ ] 시드 데이터 50건 JSONL 생성
- [ ] 파인튜닝 1 epoch 실행 → 모델 저장 성공 (dry-run)
