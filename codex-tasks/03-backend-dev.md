# Task 03: Backend Dev — API 엔드포인트 + DB 통합 완성

## Goal
FastAPI 엔드포인트가 DB와 서비스 레이어를 통해 올바르게 동작하도록 완성한다.

## Tasks

### 1. DB 마이그레이션 실행
- `alembic revision --autogenerate -m "initial tables"` 로 초기 마이그레이션 생성
- `alembic upgrade head` 로 테이블 생성 확인
- PostgreSQL 연결 테스트 (asyncpg)

### 2. Economy API 완성 (`api/v1/economy.py`)
- `GET /economy/overview`: EconomyAnalyzer.get_overview() 연동
- `GET /economy/{region}`: 지역별 상세 분석 반환
- 캐싱: Redis로 분석 결과 캐싱 (TTL 1시간)
- 응답 스키마 검증 (EconomyOverview, RegionDetail)

### 3. Regions API 완성 (`api/v1/regions.py`)
- `GET /regions`: 9개 광역시도 목록 (하드코딩 또는 DB)
- `GET /regions/{region}/listings`: 페이지네이션, 필터링 (property_type, price_range)
- `GET /regions/{region}/prices`: 기간별 가격 추이 집계 쿼리
- 쿼리 최적화: 인덱스 추가, N+1 방지

### 4. Chat API 완성 (`api/v1/chat.py`)
- `POST /chat`: RAGService + LLMService 연동
- SSE 스트리밍 응답 (event: token, event: done)
- 대화 히스토리 관리 (세션 기반 또는 request body)
- 에러 시 graceful degradation (LLM 없으면 규칙 기반 응답)

### 5. 미들웨어 추가
- Request logging 미들웨어
- Rate limiting (slowapi 또는 커스텀)
- Error handler: 일관된 에러 응답 포맷

### 6. API 테스트 작성
- `pytest` + `httpx.AsyncClient` 사용
- 모든 엔드포인트 happy path + error case 테스트
- DB fixture: 테스트용 샘플 데이터 insert

## Files to Modify
- `backend/app/api/v1/economy.py`
- `backend/app/api/v1/regions.py`
- `backend/app/api/v1/chat.py`
- `backend/app/api/v1/router.py`
- `backend/app/main.py`
- `backend/app/services/economy_analyzer.py`

## Files to Create
- `backend/alembic/versions/001_initial_tables.py` (auto-generated)
- `backend/tests/test_api_economy.py`
- `backend/tests/test_api_regions.py`
- `backend/tests/test_api_chat.py`
- `backend/tests/conftest.py` (DB fixtures)

## Acceptance Criteria
- [ ] `alembic upgrade head` 성공 (PostgreSQL에 3개 테이블 생성)
- [ ] `GET /api/v1/economy/overview` → 200 + 올바른 JSON 구조
- [ ] `GET /api/v1/regions/11110/listings?page=1&size=10` → 페이지네이션 동작
- [ ] `POST /api/v1/chat` → SSE 스트림으로 토큰 수신
- [ ] `GET /health` → {"status": "ok"}
- [ ] `pytest tests/test_api_*.py -v` 전체 통과
