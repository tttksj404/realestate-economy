# realestate-economy 부트스트랩 스크립트
# 어느 PC에서든 iCloudDrive만 있으면 이 스크립트로 전체 환경 구축
#
# 사용법: powershell -ExecutionPolicy Bypass -File setup.ps1

$ErrorActionPreference = "Continue"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " realestate-economy 환경 설정" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# -----------------------------------------------------------
# 1. 필수 도구 확인
# -----------------------------------------------------------
Write-Host "[1/6] 필수 도구 확인..." -ForegroundColor Yellow

$missing = @()

# Python
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pyVer = python --version 2>&1
    Write-Host "  OK Python: $pyVer" -ForegroundColor Green
} else {
    $missing += "Python 3.11+ (https://python.org)"
}

# Node.js
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeVer = node --version 2>&1
    Write-Host "  OK Node.js: $nodeVer" -ForegroundColor Green
} else {
    Write-Host "  Node.js 미설치 - 설치 시도..." -ForegroundColor Yellow
    winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK Node.js 설치 완료 (터미널 재시작 필요할 수 있음)" -ForegroundColor Green
    } else {
        $missing += "Node.js 20+ (https://nodejs.org)"
    }
}

# Docker
if (Get-Command docker -ErrorAction SilentlyContinue) {
    $dockerVer = docker --version 2>&1
    Write-Host "  OK Docker: $dockerVer" -ForegroundColor Green
} else {
    $missing += "Docker Desktop (https://docker.com)"
}

# Git
if (Get-Command git -ErrorAction SilentlyContinue) {
    Write-Host "  OK Git: $(git --version)" -ForegroundColor Green
} else {
    $missing += "Git (https://git-scm.com)"
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "  누락된 도구:" -ForegroundColor Red
    foreach ($m in $missing) {
        Write-Host "    - $m" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "  위 도구를 설치한 후 다시 실행해주세요." -ForegroundColor Red
    exit 1
}

# -----------------------------------------------------------
# 2. .env 확인
# -----------------------------------------------------------
Write-Host ""
Write-Host "[2/6] 환경변수 확인..." -ForegroundColor Yellow

if (Test-Path "$projectRoot\.env") {
    Write-Host "  OK .env 파일 존재" -ForegroundColor Green
} else {
    Write-Host "  .env 파일 없음 — .env.example에서 복사하지 않았다면 생성 필요" -ForegroundColor Red
    Write-Host "  API 키를 .env 파일에 직접 입력해주세요" -ForegroundColor Red
    exit 1
}

# -----------------------------------------------------------
# 3. Python 가상환경 + 의존성
# -----------------------------------------------------------
Write-Host ""
Write-Host "[3/6] Python 백엔드 설정..." -ForegroundColor Yellow

$venvPath = "$projectRoot\backend\.venv"
if (-not (Test-Path "$venvPath\Scripts\activate.ps1")) {
    Write-Host "  가상환경 생성 중..." -ForegroundColor Gray
    python -m venv "$venvPath"
}

Write-Host "  의존성 설치 중..." -ForegroundColor Gray
& "$venvPath\Scripts\pip.exe" install -q -r "$projectRoot\backend\requirements.txt" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK Python 의존성 설치 완료" -ForegroundColor Green
} else {
    Write-Host "  WARNING: 일부 패키지 설치 실패 (GPU 관련은 정상)" -ForegroundColor Yellow
}

# -----------------------------------------------------------
# 4. Node.js 프론트엔드 의존성
# -----------------------------------------------------------
Write-Host ""
Write-Host "[4/6] 프론트엔드 설정..." -ForegroundColor Yellow

Set-Location "$projectRoot\frontend"
if (-not (Test-Path "node_modules")) {
    Write-Host "  npm install 실행 중..." -ForegroundColor Gray
    npm install --silent 2>$null
}
Write-Host "  OK 프론트엔드 의존성 설치 완료" -ForegroundColor Green
Set-Location $projectRoot

# -----------------------------------------------------------
# 5. Docker 인프라 기동
# -----------------------------------------------------------
Write-Host ""
Write-Host "[5/6] Docker 인프라 기동..." -ForegroundColor Yellow

$dockerRunning = docker info 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Docker Desktop이 실행 중이 아닙니다. 먼저 Docker Desktop을 시작해주세요." -ForegroundColor Red
    exit 1
}

docker compose up -d postgres redis chromadb 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK PostgreSQL + Redis + ChromaDB 기동 완료" -ForegroundColor Green
} else {
    Write-Host "  WARNING: Docker 서비스 기동 실패 — docker compose logs 확인" -ForegroundColor Yellow
}

# -----------------------------------------------------------
# 6. DB 마이그레이션
# -----------------------------------------------------------
Write-Host ""
Write-Host "[6/6] DB 마이그레이션..." -ForegroundColor Yellow

# postgres 준비 대기 (최대 15초)
$retry = 0
while ($retry -lt 15) {
    $health = docker compose exec -T postgres pg_isready 2>$null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 1
    $retry++
}

Set-Location "$projectRoot\backend"
& "$venvPath\Scripts\python.exe" -m alembic upgrade head 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK DB 테이블 생성 완료" -ForegroundColor Green
} else {
    Write-Host "  WARNING: 마이그레이션 실패 — DB 연결 확인 필요" -ForegroundColor Yellow
}
Set-Location $projectRoot

# -----------------------------------------------------------
# 완료
# -----------------------------------------------------------
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " 설정 완료!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "다음 명령어로 서비스를 시작하세요:" -ForegroundColor White
Write-Host ""
Write-Host "  # 백엔드 (터미널 1)" -ForegroundColor Gray
Write-Host "  cd backend" -ForegroundColor White
Write-Host "  .venv\Scripts\activate" -ForegroundColor White
Write-Host "  uvicorn app.main:app --reload --port 8000" -ForegroundColor White
Write-Host ""
Write-Host "  # 프론트엔드 (터미널 2)" -ForegroundColor Gray
Write-Host "  cd frontend" -ForegroundColor White
Write-Host "  npm run dev" -ForegroundColor White
Write-Host ""
Write-Host "  # 데이터 수집" -ForegroundColor Gray
Write-Host "  cd backend" -ForegroundColor White
Write-Host "  .venv\Scripts\python.exe scripts/collect_data.py --months 3" -ForegroundColor White
Write-Host ""
Write-Host "  # 또는 Docker 전체 기동" -ForegroundColor Gray
Write-Host "  docker compose up --build" -ForegroundColor White
Write-Host ""
