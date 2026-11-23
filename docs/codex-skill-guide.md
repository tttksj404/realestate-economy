# Codex 스킬·지침 가이드 — realestate-economy

> 생성일 2026-11-23. Codex 작업 폴더 `~/Desktop/2학기/_gh_audit/work/realestate-economy`에서 이 레포를 다룰 때 적용되는 지침과 자주 쓰는 스킬이다.
> 전체 목록(사용자 스킬 66개, 플러그인 스킬, 모든 작업 폴더 맵)은 `tttksj404/codex-global-skills`의 `docs/codex-skill-usage-guide.md`에 있다.

## 적용 지침

| 지침 | 언제 | 내용 |
|---|---|---|
| 전역 `~/.codex/AGENTS.md` | 모든 작업 | 한국어 답변, 직접 수행·검증, 결과/검증/남은 리스크 보고, 복잡한 작업은 `codex-fablize` 자동 승격 |
| 레포 `AGENTS.md`·`CLAUDE.md` | 이 레포 작업 시작 시 | 백엔드(FastAPI) API·데이터 파이프라인·AI 서비스·ML 파인튜닝 위치와 경제 신호 로직, 실행 명령 |
| `codex-tasks/` | Codex 작업 지시서 실행 | 작업 단위 명세 |

## 이 레포에서 주로 쓰는 스킬

"언제 쓰나"는 각 `SKILL.md`의 description 원문이다.

| 스킬 | 언제 쓰나 (SKILL.md description) |
|---|---|
| `codex-fablize` | Use when the user asks for fablize, codex-fablize, gpt55-fablize (legacy name), Fable-style, Fable5-style, or to make Codex work like Fable — on any Codex model, not only GPT-5.5. Applies only transferable workflow: inspect first, finish multi-step work, checkpoint evidence, investigate systematically, observe rendered artifacts, verify before done, and separate implementation from audit roles. Does not clone Clau... |
| `ui-ux-pro-max` | UI/UX design intelligence for web and mobile. Searchable local database with 50+ styles, 161 color palettes, 57 font pairings, 161 product types, 99 UX guidelines, and 25 chart types across 10 stacks (React, Next.js, Vue, Svelte, SwiftUI, React Native, Flutter, Tailwind, shadcn/ui, and HTML/CSS). Use when designing, building, or reviewing UI: pages, components, color schemes, typography, layout, accessibility, ani... |
| `playwright` | Use when the task requires automating a real browser from the terminal (navigation, form filling, snapshots, screenshots, data extraction, UI-flow debugging) via `playwright-cli` or the bundled wrapper script. |
| `jupyter-notebook` | Use when the user asks to create, scaffold, or edit Jupyter notebooks (`.ipynb`) for experiments, explorations, or tutorials; prefer the bundled templates and run the helper script `new_notebook.py` to generate a clean starting notebook. |
| `security-best-practices` | Perform language and framework specific security best-practice reviews and suggest improvements. Trigger only when the user explicitly requests security best practices guidance, a security review/report, or secure-by-default coding help. Trigger only for supported languages (python, javascript/typescript, go). Do not trigger for general code review, debugging, or non-security tasks. |
