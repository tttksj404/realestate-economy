# AGENTS.md — Codex Context

## Project Overview

부동산 매물 데이터를 분석하여 거시경제 상황을 AI가 추론하는 웹 서비스.
핵심 가설: 저가 부동산(빌라 등) 매물 급증 → 경기 침체 시그널.

## Architecture

- **Backend**: FastAPI (Python 3.11) — `backend/`
- **Frontend**: React 18 + TypeScript + Vite — `frontend/`
- **Database**: PostgreSQL 15 (async via asyncpg)
- **Vector Store**: ChromaDB
- **LLM**: Llama 3.1 8B (QLoRA fine-tuned)
- **Embedding**: intfloat/multilingual-e5-large
- **Infra**: Docker Compose (5 services)

## Key Files

### Backend Entry
- `backend/app/main.py` — FastAPI app with lifespan, CORS, v1 router
- `backend/app/config.py` — pydantic-settings, all env vars

### API Endpoints (`backend/app/api/v1/`)
- `economy.py` — GET /economy/overview, GET /economy/{region}
- `regions.py` — GET /regions, GET /regions/{region}/listings, GET /regions/{region}/prices
- `chat.py` — POST /chat (SSE streaming)

### Data Pipeline (`backend/app/data/`)
- `collectors/public_api.py` — 국토부 공공데이터포털 API (실거래가)
- `collectors/naver_crawler.py` — 네이버 부동산 매물 크롤링
- `processors/cleaner.py` — 데이터 정제, 이상치 제거
- `processors/feature_engineer.py` — 6개 경제 지표 계산
- `processors/embedder.py` — sentence-transformers 임베딩

### AI Services (`backend/app/services/`)
- `economy_analyzer.py` — 규칙 기반 + RAG + LLM 경제상황 판단
- `rag_service.py` — ChromaDB 검색 → 컨텍스트 구성
- `llm_service.py` — Llama 모델 로드, 추론, 스트리밍

### ML Pipeline (`backend/app/ml/fine_tuning/`)
- `dataset_builder.py` — 학습 데이터 구축 (DB → instruction-response pairs)
- `trainer.py` — QLoRA 파인튜닝 (peft + trl)
- `evaluator.py` — 모델 평가 (accuracy, ROUGE)

### Database (`backend/app/db/`)
- `database.py` — async SQLAlchemy engine + session
- `models.py` — RealEstateListing, RealEstateTransaction, EconomyIndicator
- `vector_store.py` — ChromaDB wrapper

### Frontend (`frontend/src/`)
- `pages/Dashboard.tsx` — 전국 경제상황 대시보드
- `pages/RegionDetail.tsx` — 지역별 상세 분석
- `pages/Chat.tsx` — AI 채팅 인터페이스
- `components/` — EconomyIndicator, PriceChart, ListingTable, RegionMap, ChatMessage

### Scripts (`backend/scripts/`)
- `collect_data.py` — 데이터 수집 CLI
- `build_vectordb.py` — 벡터DB 구축
- `fine_tune.py` — 파인튜닝 실행

## Data Models (DB)

### RealEstateListing
매물 정보: region_code, property_type(아파트/빌라/오피스텔), listing_price, actual_price, jeonse_price, area_sqm, source(공공API/네이버)

### RealEstateTransaction
실거래 정보: region_code, property_type, deal_amount, area_sqm, deal_date

### EconomyIndicator
경제 지표: region_code, period, low_price_listing_ratio, listing_count_change, price_gap_ratio, regional_price_index, sale_speed, jeonse_ratio, signal(호황/보통/침체), confidence

## Economy Signal Logic

6개 지표 → 가중 점수 → signal 판단:
- low_price_listing_ratio > 40% → 침체 시그널
- listing_count_change > 20% → 매도 압력
- price_gap_ratio > 15% → 가격 조정기
- regional_price_index < -5% → 지역 경기 위축
- sale_speed > 90일 → 수요 감소
- jeonse_ratio > 80% → 갭투자 위험

규칙 기반 1차 판단 → RAG 컨텍스트 보강 → LLM 최종 분석

## Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev  # port 5173, proxies /api to :8000

# Data Collection
cd backend
python scripts/collect_data.py --months 3 --source all

# Vector DB Build
python scripts/build_vectordb.py

# Fine-tuning
python scripts/fine_tune.py --epochs 3

# Docker (full stack)
docker-compose up --build
```

## Environment Variables

See `.env.example` for all required variables. Key ones:
- `PUBLIC_DATA_API_KEY` — 공공데이터포털 API 인증키
- `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` — 네이버 API
- `DATABASE_URL` — PostgreSQL connection string
- `LLM_MODEL_PATH` — 파인튜닝된 모델 경로

## Testing

- Backend: `pytest` with `httpx.AsyncClient`
- Frontend: `npm test` (vitest)
- E2E: `docker-compose up` → verify all endpoints respond

## Korean Domain Terms

- 실거래가 = actual transaction price
- 호가 = asking price (listed price)
- 전세 = jeonse (lump-sum lease deposit)
- 전세가율 = jeonse-to-sale price ratio
- 매물 = property listing
- 빌라 = villa (low-rise multi-family housing)
- 다세대 = multi-family housing
- 오피스텔 = officetel (mixed residential/commercial)
- 호황 = economic boom
- 침체 = economic downturn/slump
- 법정동코드 = legal district code
