---
name: harness-improve
description: VISION.md에 따른 시스템 개선 한 사이클을 멀티 에이전트 하네스 엔지니어링으로 진행. 측정→분석→제안→구현→검증. 트리거 — "하네스 사이클 돌려", "비전 보고 개선", "다음 사이클 진행해", "/harness-improve", "/harness-improve [영역]" 등
---

# Harness-Improve — 비전 정합 멀티 에이전트 개선 사이클

VISION.md(다크 팩토리 5단계 로드맵 + 9가지 설계 철학)에 비추어 시스템을 한 사이클 개선한다.
*반드시 측정→분석→제안→구현→검증 순서를 지킨다.* 측정 없이 코드 수정 금지.

## 핵심 원칙 (CLAUDE.md 하네스 루프 규약)

- **측정→분석→개선→검증**: 짐작 금지. 데이터로 결정.
- **단일 작은 변화**: 한 사이클 = 한 가지 개선. 여러 개 묶지 말 것.
- **수렴 조건**: 직전 사이클 대비 핵심 메트릭 0.3%p 미만 변화면 정리/문서로 마무리.
- **회귀 가드**: 변경 전후 모두 backtest 실행. drift_warnings 늘어나면 롤백.
- **비전 우선순위**: 자동복구(9.4) > 학습(9.5) > 점진적 자율(9.6) > 인과추적(9.2) > Hybrid(9.3).

## 실행 인자

- 인자 없음: 모든 영역 전체 GAP 스캔.
- `[영역]`: 특정 영역만 (예: `preverify`, `recurrence`, `ui`, `scenarios`, `playbook`, `evolution`).

## 워크플로우 (필수 순서)

### Phase 1 — MEASURE (필수)

병렬로 다음을 수집:

1. **Latest snapshot 읽기**: `results/self_healing_v4_latest.json`에서 incidents, recurrence_kpis, preverify metrics 추출. 없으면 짧은 시뮬 실행 (5-10 iter).
2. **Backtest 실행** (있는 스냅샷 기준): `python scripts/backtest.py --snapshot results/self_healing_v4_latest.json` 결과의 ECE/Brier/drift_warnings 수집.
3. **Git 최근 커밋 5개**: 무엇이 직전에 변경됐는지 파악 (`git log --oneline -5`).

수집 후 표로 정리:

| 지표 | 현재값 | 목표/벤치마크 | 상태 |
|---|---|---|---|

### Phase 2 — MULTI-AGENT ANALYZE (필수, 병렬 수행)

**반드시 다음 3개 에이전트를 단일 메시지에서 병렬 spawn**하여 시야를 다양화한다:

#### Agent A — Vision Reviewer (subagent_type: general-purpose)
- 역할: VISION.md §6 (5단계 로드맵), §7 (GAP 분석), §9 (설계 철학) 읽고 현재 시스템과 대조.
- 입력으로 Phase 1 측정 결과 전달.
- 출력: "비전과 가장 동떨어진 영역 top 3" + 각각의 비전 근거 인용.

#### Agent B — Codebase Auditor (subagent_type: Explore, thoroughness: medium)
- 역할: 측정에서 stuck 또는 낮은 메트릭의 *기술적 원인* 추적.
- 코드를 읽고 "왜 이 메트릭이 나쁜가" 가설 3-5개.
- 출력: 가설 + 관련 파일 경로 + 변경 난이도 추정.

#### Agent C — Recent Activity Reviewer (subagent_type: general-purpose)
- 역할: 최근 git log 5건 + 커밋 메시지의 "다음 사이클 후보"로 적힌 항목 추출.
- 출력: 이전에 본인이 약속했지만 아직 안 한 작업 리스트.

3개 결과를 통합해 GAP 매트릭스 작성:

| GAP 영역 | 비전 근거 (A) | 기술적 원인 (B) | 직전 사이클 약속 (C) | 종합 우선순위 |
|---|---|---|---|---|

### Phase 3 — PROPOSE (필수)

**2-3개 옵션**을 제안하되 각각 다음 4개 항목 포함:

| 옵션 | 무엇을 바꿀 것인가 | 예상 변화 메트릭 | 측정 가능한 성공 기준 | 예상 작업 분량 |
|---|---|---|---|---|

**1순위 추천**을 명확히 표시 + 트레이드오프 1줄.

> **그 다음 반드시 멈추고 사용자 결정 대기.** 자동 진행 금지. 인자 없는 호출도 항상 사용자 승인 후 진행.

### Phase 4 — IMPLEMENT (사용자 승인 후)

원칙:
- TaskCreate로 sub-task 3-5개 분해.
- 한 번에 한 파일 수정 → 즉시 검증.
- Python: `PYTHONPATH=src python3 -c "..."`로 import 검증.
- TypeScript: `cd web && npx tsc --noEmit`.
- 큰 클래스/모듈 새로 만들기보다 기존 파일 수정 우선.

### Phase 5 — VERIFY (필수)

Phase 1과 동일한 측정 재실행. **반드시 비교 표 출력**:

| 지표 | Before | After | Δ | 비전 정합성 |
|---|---:|---:|---|---|

성공 기준 충족 여부 판정:
- ✅ **충족**: 다음 사이클 후보 3개 제시 후 종료.
- ❌ **미충족**: 가설 분석 + 롤백 옵션 제시.
- ⚠️ **부분 충족**: 어떤 부분이 됐고 안 됐는지 명시.

### Phase 6 — COMMIT 제안

변경이 의미 있으면 커밋 메시지 초안 작성. 사용자가 "커밋해" 등으로 명시할 때만 실제 커밋.

## 도메인별 측정 도구 빠른 참조

- **자율 복구 메트릭**: `engine.get_state()['healing']['recurrence_kpis']`
- **PRE-VERIFY 정확도**: `engine.get_state()['preverify']` (mae, sign_accuracy)
- **반복 시그니처**: `engine.recurrence_tracker` 또는 state['recurrence']
- **Evolution 사이클**: `state['phase4']['evolution_agent']['cycle_count']`
- **Backtest**: `scripts/backtest.py`
- **Research loop**: `python src/v4/research_loop.py` (긴 사이클, 신중히)

## Anti-pattern 금지 사항

- ❌ 측정 없이 "이게 좋아 보여서" 코드 수정
- ❌ 한 커밋에 여러 비독립 변경 묶기
- ❌ "Backwards compat을 위해" 옛 코드 유지하는 dead branch
- ❌ 사이클 끝났다 선언하면서 검증 단계 생략
- ❌ Phase 5 결과가 부정적인데 결과를 미화

## 좋은 사이클 vs 나쁜 사이클 예시

**좋은 사이클** (최근 commit 9e83956 참고):
- 측정으로 repeat_rate 46.2% 발견 → 가설 (옵션 부족) → 시나리오/플레이북/sim 동시 변경 → 측정 후 40.6% 확인 → 커밋

**나쁜 사이클**:
- 측정 없이 "preverify 임계값 올리면 좋겠다" → 임계값 변경 → 다른 메트릭 어떻게 됐는지 확인 안 함 → 커밋

## 참고 문서

- [VISION.md](../../../VISION.md) — 5단계 로드맵, 9가지 설계 철학, 7장 GAP 분석
- [ARCHITECTURE.md](../../../ARCHITECTURE.md) — 7-페이즈 자율 복구 루프, 모듈 맵
- [CLAUDE.md](../../../CLAUDE.md) — 개발 가이드, 하네스 루프 규약
