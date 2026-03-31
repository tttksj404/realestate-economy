#!/bin/bash
# Claude Code 메모리를 iCloud에 연결하는 스크립트 (Mac)
# 사용법: bash setup-claude-memory.sh

ICLOUD_MEMORY="$HOME/Library/Mobile Documents/com~apple~CloudDocs/.claude-shared/projects/C--Users-SSAFY-iCloudDrive"
CLAUDE_MEMORY="$HOME/.claude/projects/C--Users-SSAFY-iCloudDrive/memory"

echo "Claude Code 메모리 iCloud 동기화 설정"
echo ""

# 1. iCloud 쪽 디렉토리 확인
mkdir -p "$ICLOUD_MEMORY"

# 2. 기존 memory 처리
if [ -L "$CLAUDE_MEMORY" ]; then
    echo "  이미 심볼릭 링크가 설정되어 있습니다."
    echo "  $CLAUDE_MEMORY -> $(readlink "$CLAUDE_MEMORY")"
    exit 0
fi

if [ -d "$CLAUDE_MEMORY" ]; then
    echo "  기존 메모리 파일을 iCloud로 복사..."
    cp -r "$CLAUDE_MEMORY"/* "$ICLOUD_MEMORY/" 2>/dev/null
    mv "$CLAUDE_MEMORY" "${CLAUDE_MEMORY}.bak"
fi

# 3. 프로젝트 디렉토리 확인
mkdir -p "$(dirname "$CLAUDE_MEMORY")"

# 4. 심볼릭 링크 생성
ln -s "$ICLOUD_MEMORY" "$CLAUDE_MEMORY"

if [ -d "$CLAUDE_MEMORY" ]; then
    echo "  OK 메모리 동기화 완료!"
    echo "  $CLAUDE_MEMORY -> $ICLOUD_MEMORY"
    echo ""
    echo "  메모리 파일:"
    ls "$CLAUDE_MEMORY" | sed 's/^/    - /'
else
    echo "  ERROR: 링크 생성 실패"
fi
