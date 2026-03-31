# Claude Code 메모리를 iCloud에 연결하는 스크립트
# 어느 PC에서든 동일한 메모리를 공유할 수 있도록 Junction 링크 생성
#
# 사용법: powershell -ExecutionPolicy Bypass -File setup-claude-memory.ps1

$iCloudMemory = "$env:USERPROFILE\iCloudDrive\.claude-shared\projects\C--Users-SSAFY-iCloudDrive"
$claudeMemory = "$env:USERPROFILE\.claude\projects\C--Users-SSAFY-iCloudDrive\memory"

Write-Host "Claude Code 메모리 iCloud 동기화 설정" -ForegroundColor Cyan
Write-Host ""

# 1. iCloud 쪽 디렉토리 확인
if (-not (Test-Path $iCloudMemory)) {
    Write-Host "  iCloud 메모리 디렉토리 생성 중..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $iCloudMemory -Force | Out-Null
}

# 2. 기존 memory 디렉토리 처리
if (Test-Path $claudeMemory) {
    $item = Get-Item $claudeMemory
    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        Write-Host "  이미 Junction이 설정되어 있습니다." -ForegroundColor Green
        Write-Host "  $claudeMemory -> $iCloudMemory" -ForegroundColor Gray
        exit 0
    }

    # 기존 파일을 iCloud로 복사 (기존 내용 보존)
    Write-Host "  기존 메모리 파일을 iCloud로 복사..." -ForegroundColor Yellow
    Copy-Item -Path "$claudeMemory\*" -Destination $iCloudMemory -Force -Recurse 2>$null

    # 백업 후 삭제
    $backup = "${claudeMemory}.bak"
    if (Test-Path $backup) { Remove-Item -Recurse -Force $backup }
    Rename-Item $claudeMemory "${claudeMemory}.bak"
}

# 3. Claude 프로젝트 디렉토리 확인
$claudeProjectDir = Split-Path $claudeMemory -Parent
if (-not (Test-Path $claudeProjectDir)) {
    New-Item -ItemType Directory -Path $claudeProjectDir -Force | Out-Null
}

# 4. Junction 생성
Write-Host "  Junction 생성 중..." -ForegroundColor Yellow
cmd /c "mklink /J `"$claudeMemory`" `"$iCloudMemory`""

if (Test-Path $claudeMemory) {
    Write-Host ""
    Write-Host "  OK 메모리 동기화 완료!" -ForegroundColor Green
    Write-Host "  $claudeMemory -> $iCloudMemory" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  메모리 파일:" -ForegroundColor White
    Get-ChildItem $claudeMemory | ForEach-Object { Write-Host "    - $($_.Name)" -ForegroundColor Gray }
} else {
    Write-Host "  ERROR: Junction 생성 실패" -ForegroundColor Red
}
