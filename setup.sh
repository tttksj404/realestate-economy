#!/bin/bash
# realestate-economy 부트스트랩 스크립트 (Mac/Linux)
# iCloudDrive만 있으면 어느 PC에서든 전체 환경 구축
#
# 사용법: bash setup.sh

set -e
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

echo "========================================"
echo " realestate-economy 환경 설정"
echo "========================================"
echo ""

# -----------------------------------------------------------
# 1. 필수 도구 확인
# -----------------------------------------------------------
echo "[1/6] 필수 도구 확인..."
MISSING=()

command -v python3 &>/dev/null && echo "  OK Python: $(python3 --version)" || MISSING+=("Python 3.11+")
command -v node &>/dev/null && echo "  OK Node.js: $(node --version)" || MISSING+=("Node.js 20+")
command -v docker &>/dev/null && echo "  OK Docker: $(docker --version)" || MISSING+=("Docker Desktop")
command -v git &>/dev/null && echo "  OK Git: $(git --version)" || MISSING+=("Git")

if [ ${#MISSING[@]} -gt 0 ]; then
    echo ""
    echo "  누락된 도구:"
    for m in "${MISSING[@]}"; do echo "    - $m"; done
    echo "  위 도구를 설치한 후 다시 실행해주세요."
    exit 1
fi

# -----------------------------------------------------------
# 2. .env 확인
# -----------------------------------------------------------
echo ""
echo "[2/6] 환경변수 확인..."
if [ -f ".env" ]; then
    echo "  OK .env 파일 존재"
else
    echo "  ERROR: .env 파일 없음 — API 키를 .env에 입력해주세요"
    exit 1
fi

# -----------------------------------------------------------
# 3. Python 가상환경 + 의존성
# -----------------------------------------------------------
echo ""
echo "[3/6] Python 백엔드 설정..."
if [ ! -d "backend/.venv" ]; then
    echo "  가상환경 생성 중..."
    python3 -m venv backend/.venv
fi
echo "  의존성 설치 중..."
backend/.venv/bin/pip install -q -r backend/requirements.txt 2>/dev/null || echo "  WARNING: 일부 패키지 설치 실패"
echo "  OK Python 의존성 설치 완료"

# -----------------------------------------------------------
# 4. Node.js 프론트엔드 의존성
# -----------------------------------------------------------
echo ""
echo "[4/6] 프론트엔드 설정..."
cd frontend
[ ! -d "node_modules" ] && npm install --silent 2>/dev/null
echo "  OK 프론트엔드 의존성 설치 완료"
cd "$PROJECT_ROOT"

# -----------------------------------------------------------
# 5. Docker 인프라 기동
# -----------------------------------------------------------
echo ""
echo "[5/6] Docker 인프라 기동..."
docker info &>/dev/null || { echo "  Docker Desktop을 먼저 시작해주세요."; exit 1; }
docker compose up -d postgres redis chromadb
echo "  OK PostgreSQL + Redis + ChromaDB 기동 완료"

# -----------------------------------------------------------
# 6. DB 마이그레이션
# -----------------------------------------------------------
echo ""
echo "[6/6] DB 마이그레이션..."
sleep 3  # postgres 준비 대기
cd backend
.venv/bin/python -m alembic upgrade head 2>/dev/null && echo "  OK DB 테이블 생성 완료" || echo "  WARNING: 마이그레이션 실패"
cd "$PROJECT_ROOT"

# -----------------------------------------------------------
echo ""
echo "========================================"
echo " 설정 완료!"
echo "========================================"
echo ""
echo "서비스 시작:"
echo "  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload"
echo "  cd frontend && npm run dev"
echo ""
echo "데이터 수집:"
echo "  cd backend && .venv/bin/python scripts/collect_data.py --months 3"
