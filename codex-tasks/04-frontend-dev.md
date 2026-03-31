# Task 04: Frontend Dev — 대시보드 UI 완성 및 API 연동

## Goal
React 프론트엔드가 백엔드 API와 올바르게 연동되어 완성된 대시보드를 제공하도록 한다.

## Tasks

### 1. 빌드 검증
- `npm install` → `npm run build` 에러 없이 통과
- TypeScript 타입 에러 모두 해결
- 개발 서버 `npm run dev` 정상 기동

### 2. Dashboard 페이지 완성 (`pages/Dashboard.tsx`)
- API 연동: useEconomyOverview() 훅으로 실제 데이터 표시
- 로딩 상태: 스켈레톤 UI
- 에러 상태: 에러 메시지 + 재시도 버튼
- 반응형: 모바일/태블릿/데스크탑 레이아웃

### 3. RegionDetail 페이지 완성 (`pages/RegionDetail.tsx`)
- 가격 차트: Recharts 라인 차트에 실제 데이터 바인딩
- 매물 테이블: 정렬, 필터링, 페이지네이션 동작
- 6개 지표 카드: 수치 + 트렌드 화살표 + 설명 텍스트
- AI 분석 요약 섹션: 마크다운 렌더링

### 4. Chat 페이지 완성 (`pages/Chat.tsx`)
- SSE 스트리밍: 토큰 단위로 메시지 렌더링
- 추천 질문 칩: 클릭 시 자동 전송
- 대화 히스토리 유지 (클라이언트 상태)
- 입력 중 로딩 인디케이터

### 5. 컴포넌트 개선
- `EconomyIndicator.tsx`: 신호등 색상 애니메이션, 수치 카운트업
- `PriceChart.tsx`: 툴팁 한국어 포맷, 천 단위 쉼표
- `ListingTable.tsx`: 빈 상태 UI, 가격 포맷 (억/만원)
- `RegionMap.tsx`: hover 효과, 클릭 네비게이션
- `ChatMessage.tsx`: 코드 블록, 볼드, 리스트 마크다운 지원

### 6. 공통 UI
- 다크 테마 일관성 확인
- 사이드바 네비게이션 active 상태
- 404 페이지
- 글로벌 에러 바운더리

### 7. 테스트
- 컴포넌트 렌더링 테스트 (vitest + @testing-library/react)
- API 훅 테스트 (MSW mock)

## Files to Modify
- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/pages/RegionDetail.tsx`
- `frontend/src/pages/Chat.tsx`
- `frontend/src/components/*.tsx` (all components)
- `frontend/src/api/client.ts`
- `frontend/src/hooks/*.ts`
- `frontend/src/App.tsx`

## Files to Create
- `frontend/src/pages/NotFound.tsx`
- `frontend/src/components/ErrorBoundary.tsx`
- `frontend/src/components/Skeleton.tsx`
- `frontend/src/__tests__/Dashboard.test.tsx`
- `frontend/src/__tests__/Chat.test.tsx`

## Acceptance Criteria
- [ ] `npm run build` 에러 없이 성공
- [ ] Dashboard: 9개 지역 신호등 카드 렌더링
- [ ] RegionDetail: 가격 차트 + 매물 테이블 + 지표 카드 표시
- [ ] Chat: SSE 스트리밍으로 AI 응답 토큰 단위 렌더링
- [ ] 반응형: 모바일 375px에서 레이아웃 깨짐 없음
- [ ] 다크 테마 일관성
