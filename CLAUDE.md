# CLAUDE.md — realestate-economy 프로젝트

## 프로젝트 개요

부동산 매물/거래/공매 데이터로 거시경제 상황을 AI가 판단하는 서비스.
핵심: 저가 매물 급증 + 공매 증가 → 경기 침체 시그널.

## 새 PC 세팅 (iCloud 동기화 후)

```powershell
# Windows
cd C:\Users\{USER}\iCloudDrive\realestate-economy
powershell -ExecutionPolicy Bypass -File setup.ps1
```

```bash
# Mac
cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/realestate-economy
bash setup.sh
```

이것만 하면 Python venv + Node modules + Docker 인프라 + DB 마이그레이션까지 완료.

## iCloud로 동기화되는 것 / 안 되는 것

### 동기화됨 (코드 + 설정)
- 모든 소스 코드 (backend/, frontend/)
- `.env` (API 키 포함 — 기기 간 공유)
- `docker-compose.yml`, `Dockerfile`
- `setup.ps1`, `setup.sh` (부트스트랩)
- `AGENTS.md`, `CLAUDE.md`

### 동기화 안 됨 (기기별 재생성 필요 → setup 스크립트가 처리)
- `backend/.venv/` (Python 가상환경)
- `frontend/node_modules/`
- Docker volumes (postgres_data, chromadb_data 등)
- `.git/` (GitHub에서 별도 관리)

## 기술 스택

- **Backend**: FastAPI + Python 3.11
- **Frontend**: React 18 + TypeScript + Vite + Tailwind
- **DB**: PostgreSQL 15, ChromaDB (벡터), Redis (캐시)
- **AI**: Llama 3.1 8B (QLoRA), multilingual-e5-large (임베딩)
- **Infra**: Docker Compose

## 데이터 소스

| 소스 | API 키 환경변수 | 용도 |
|------|----------------|------|
| 국토부 아파트 매매 | `PUBLIC_DATA_API_KEY_APT` | 실거래가 |
| 국토부 단독/다가구 | `PUBLIC_DATA_API_KEY_SMALL` | 실거래가 |
| 국토부 연립다세대 | `PUBLIC_DATA_API_KEY_TOGETHER` | 실거래가 |
| 국토부 오피스텔 | `PUBLIC_DATA_API_KEY_OFFICE` | 실거래가 |
| 온비드(캠코) 공매 | `ONBID_API_KEY` | 공매 물건 |

## 주요 명령어

```bash
# 전체 Docker 기동
docker compose up --build

# 로컬 개발 (백엔드)
cd backend && .venv/Scripts/activate  # Windows
cd backend && source .venv/bin/activate  # Mac
uvicorn app.main:app --reload --port 8000

# 로컬 개발 (프론트엔드)
cd frontend && npm run dev

# 데이터 수집
cd backend && python scripts/collect_data.py --months 3 --source all

# 벡터DB 구축 (RAG)
cd backend && python scripts/build_vectordb.py

# 파인튜닝 (GPU 필요)
cd backend && python scripts/fine_tune.py --epochs 3

# 테스트
cd backend && pytest tests/ -v
cd frontend && npm test
```

## 파이프라인 실행 순서

1. `setup.ps1` 또는 `setup.sh` (환경 구축)
2. `scripts/collect_data.py --months 6` (데이터 수집)
3. `scripts/build_vectordb.py` (RAG용 벡터DB)
4. `scripts/fine_tune.py` (LLM 파인튜닝 — GPU 필요)
5. `uvicorn app.main:app` (서비스 시작)

## 디렉토리 구조

```
backend/
  app/
    api/v1/          — economy, regions, chat 엔드포인트
    data/collectors/  — public_api.py (국토부), onbid_api.py (온비드)
    data/processors/  — cleaner, feature_engineer, embedder
    services/         — economy_analyzer, rag_service, llm_service
    ml/fine_tuning/   — dataset_builder, trainer, evaluator
    db/               — models, database, vector_store
  scripts/            — collect_data, build_vectordb, fine_tune
  tests/              — pytest 테스트
frontend/
  src/pages/          — Dashboard, RegionDetail, Chat
  src/components/     — 차트, 테이블, 지표카드, 챗
```

## 경제 판단 로직

6개 지표 → 규칙 기반 1차 판단 → RAG 컨텍스트 → LLM 최종 분석

| 지표 | 침체 기준 |
|------|----------|
| 저가매물비율 | > 40% |
| 매물증감률 | > 20% |
| 호가괴리율 | > 15% |
| 가격지수변동 | < -5% |
| 매물소진기간 | > 90일 |
| 전세가율 | > 80% |
| 공매물건수 (온비드) | 급증 시 침체 |
