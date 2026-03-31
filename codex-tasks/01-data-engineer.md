# Task 01: Data Engineer — 데이터 수집/정제 파이프라인 검증 및 보완

## Goal
`backend/app/data/` 의 데이터 수집기와 정제 로직이 실제로 동작하도록 검증하고, 누락된 부분을 보완한다.

## Tasks

### 1. 공공데이터포털 API 수집기 보완 (`collectors/public_api.py`)
- XML 응답 파싱이 실제 API 응답 구조와 맞는지 확인
- 국토부 실거래가 API의 실제 필드명으로 매핑 수정 (참고: https://www.data.go.kr 의 국토교통부_아파트매매 실거래 상세 자료)
- 에러 핸들링: API 일일 호출 한도 초과, 빈 응답, 타임아웃 처리
- 지역코드(법정동코드 5자리) 매핑 테이블 추가

### 2. 네이버 부동산 크롤러 보완 (`collectors/naver_crawler.py`)
- 네이버 부동산 API의 실제 엔드포인트/헤더 확인 및 수정
- 매물 유형별(아파트, 빌라, 오피스텔) 필터링 파라미터 정확히 설정
- Rate limiting: 요청 간격 조절 (429 방지)
- 크롤링 차단 대응: User-Agent 로테이션, 재시도 로직

### 3. 데이터 정제 로직 테스트 (`processors/cleaner.py`)
- 실제 수집 데이터로 clean_transaction_data, clean_listing_data 실행
- 이상치 기준값이 현실적인지 검증 (예: 아파트 가격 범위)
- 날짜 포맷 변환이 API 응답의 실제 포맷과 일치하는지 확인

### 4. 피처 엔지니어링 검증 (`processors/feature_engineer.py`)
- 각 compute_* 함수의 SQL 쿼리가 올바른지 확인
- 빈 데이터일 때 ZeroDivisionError 등 예외 처리
- 샘플 데이터로 지표 계산 결과가 합리적인지 검증

### 5. 테스트 작성
- `backend/tests/test_collectors.py` — API 수집기 unit test (mock 응답)
- `backend/tests/test_processors.py` — 정제/피처 엔지니어링 test
- 테스트 실행: `cd backend && pytest tests/ -v`

## Files to Modify
- `backend/app/data/collectors/public_api.py`
- `backend/app/data/collectors/naver_crawler.py`
- `backend/app/data/processors/cleaner.py`
- `backend/app/data/processors/feature_engineer.py`
- `backend/app/data/schemas.py` (필요시)

## Files to Create
- `backend/tests/__init__.py`
- `backend/tests/test_collectors.py`
- `backend/tests/test_processors.py`
- `backend/tests/conftest.py` (fixtures)

## Acceptance Criteria
- [ ] 공공API mock 응답으로 수집기 테스트 통과
- [ ] 네이버 크롤러 mock 응답으로 테스트 통과
- [ ] 정제 함수에 실제 형태 데이터 넣었을 때 정상 출력
- [ ] 6개 피처 계산 함수 모두 테스트 통과
- [ ] `pytest tests/ -v` 전체 통과
