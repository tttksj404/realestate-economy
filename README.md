# Real Estate Economy Service

부동산 매물/거래/공매 데이터로 거시경제 상황을 AI가 판단하는 서비스.

**핵심 가설:** 저가 매물 급증 + 공매 증가 = 경기 침체 시그널

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI, Python 3.11, SQLAlchemy (async) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Database | PostgreSQL 15, ChromaDB (vector), Redis (cache) |
| AI/ML | Llama 3.1 8B (QLoRA), multilingual-e5-large |
| Infra | Docker Compose |

## Quick Start (Development)

```bash
# 1. Clone
git clone https://github.com/tttksj404/realestate-economy.git
cd realestate-economy

# 2. Environment
cp .env.example .env
# Edit .env — fill in API keys (data.go.kr, onbid)

# 3. Run
docker compose up --build

# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs
```

## Production Deployment

```bash
# 1. Set required env vars
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
export CORS_ORIGINS=https://yourdomain.com
export DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/realestate
# ... set all vars in .env.example

# 2. Run with production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Production Checklist

- [ ] `SECRET_KEY` — strong random string
- [ ] `API_KEY` — set to protect endpoints (optional, empty = no auth)
- [ ] `CORS_ORIGINS` — your frontend domain
- [ ] `DATABASE_URL` — production PostgreSQL
- [ ] `PUBLIC_DATA_API_KEY_*` — 국토부 API keys from [data.go.kr](https://www.data.go.kr)
- [ ] `ONBID_API_KEY` — 온비드 API key from [openapi.onbid.co.kr](https://openapi.onbid.co.kr)
- [ ] `POSTGRES_PASSWORD` — change default
- [ ] `WEB_CONCURRENCY=2` — uvicorn workers (2-4 recommended)
- [ ] HTTPS termination via reverse proxy (Caddy, nginx, ALB)

## Data Pipeline

```bash
# Initial data collection (6 months)
cd backend
python scripts/collect_data.py --months 6 --source all

# Build RAG vector database
python scripts/build_vectordb.py

# Fine-tune LLM (GPU required, 16GB+ VRAM)
python scripts/fine_tune.py --epochs 3
```

Daily collection runs automatically at 06:00 KST via the built-in scheduler.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/economy/overview` | National economy summary |
| GET | `/api/v1/economy/{region}` | Regional analysis |
| GET | `/api/v1/regions` | Supported regions list |
| GET | `/api/v1/regions/{region}/listings` | Property listings |
| GET | `/api/v1/regions/{region}/prices` | Price trends |
| POST | `/api/v1/chat` | AI chat (SSE streaming) |
| GET | `/health` | Health check |

When `API_KEY` is set, include `X-API-Key` header in requests.

## Environment Variables

See [`.env.example`](.env.example) for all available variables with descriptions.

## Development

```bash
# Backend (local)
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (local)
cd frontend && npm install && npm run dev

# Tests
cd backend && pytest -v
cd frontend && npm test
```

## Architecture

```
User → React SPA → nginx → FastAPI
                              ├── PostgreSQL (listings, transactions, indicators)
                              ├── ChromaDB (RAG vector store)
                              ├── Redis (response cache)
                              └── Llama 3.1 8B (economy analysis)
```

6 indicators → rule-based signal → RAG context → LLM final analysis

| Indicator | Recession Threshold |
|-----------|-------------------|
| Low-price listing ratio | > 40% |
| Listing count change | > 20% |
| Ask-deal price gap | > 15% |
| Price index change | < -5% |
| Days on market | > 90 days |
| Jeonse ratio | > 80% |
