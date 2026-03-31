# Task 05: Infra/DevOps — Docker 통합 + CI/CD + 환경 설정

## Goal
Docker Compose로 전체 서비스가 정상 기동되고, 개발/프로덕션 환경 설정이 완료되도록 한다.

## Tasks

### 1. Docker Compose 검증
- `docker-compose up --build` 실행하여 5개 서비스 모두 기동 확인
- 서비스 간 네트워크 통신 확인 (backend ↔ postgres, chromadb, redis)
- 볼륨 영속성 확인 (컨테이너 재시작 후 데이터 유지)
- Health check 동작 확인

### 2. Backend Dockerfile 개선
- Multi-stage build: 의존성 설치 레이어 캐싱
- ML 모델 다운로드 레이어 분리 (빌드 시간 단축)
- non-root 유저 실행 확인
- `.dockerignore` 추가 (tests, __pycache__, .git)

### 3. Frontend Dockerfile + Nginx 검증
- Multi-stage build: node build → nginx serve
- SPA 라우팅: 새로고침 시 404 안 나도록 try_files 확인
- `/api/` 프록시: backend 서비스로 정상 포워딩
- SSE 프록시: `proxy_buffering off` 확인 (스트리밍 응답)
- gzip 압축 동작

### 4. 환경변수 관리
- `.env.example` 모든 변수 문서화
- Docker 환경과 로컬 개발 환경 분리
- 시크릿 관리: API 키가 이미지에 포함되지 않도록 확인

### 5. 데이터베이스 초기화
- PostgreSQL 초기 스키마 자동 적용 (entrypoint 또는 init script)
- Alembic 마이그레이션이 컨테이너 시작 시 자동 실행되도록 설정
- 테스트 데이터 시드 스크립트

### 6. 스케줄러 설정
- APScheduler: 매일 06:00 데이터 수집 자동 실행
- 스케줄러가 backend 컨테이너 내에서 동작하도록 설정
- 로그 파일 볼륨 마운트

### 7. CI/CD (GitHub Actions)
- `.github/workflows/ci.yml`: lint, type check, test, build
- Backend: `ruff check`, `mypy`, `pytest`
- Frontend: `tsc --noEmit`, `npm run build`
- Docker build 테스트

## Files to Modify
- `docker-compose.yml`
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `frontend/nginx.conf`
- `.env.example`

## Files to Create
- `backend/.dockerignore`
- `frontend/.dockerignore`
- `backend/entrypoint.sh` (alembic upgrade + uvicorn)
- `.github/workflows/ci.yml`
- `backend/data/init/seed_data.sql` (optional)

## Acceptance Criteria
- [ ] `docker-compose up --build` → 5개 서비스 모두 healthy
- [ ] `curl http://localhost:8000/health` → {"status": "ok"}
- [ ] `curl http://localhost:3000` → React 앱 렌더링
- [ ] `curl http://localhost:3000/api/v1/economy/overview` → 백엔드 프록시 동작
- [ ] PostgreSQL 데이터 볼륨 영속성 확인
- [ ] GitHub Actions CI 파이프라인 통과
