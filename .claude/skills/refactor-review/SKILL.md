---
name: refactor-review
description: 4개 관점 멀티 에이전트로 코드 리팩토링 리뷰를 병렬 수행하고 합의 기반 우선순위로 1순위만 즉시 실행. 트리거 — "리팩토링 리뷰", "코드 정리", "다중 에이전트 리뷰", "/refactor-review", "/refactor-review [영역|파일]" 등
---

# Refactor-Review — 4관점 멀티 에이전트 리팩토링

코드 품질·silent failure·중복·타입 디자인 4개 관점을 **병렬**로 동시 분석한 뒤,
에이전트 간 **합의 우선순위**에 따라 1순위 변경을 즉시 실행한다.

## 핵심 원칙

- **4관점 강제 병렬 spawn**: 단일 메시지에서 4개 에이전트를 동시에 호출. 시야 다양화 ≠ 한 에이전트가 4역할.
- **합의 기반 선정**: 2개 이상 에이전트가 같은 항목을 1-2순위로 지목하면 **자동 1순위**.
- **단일 작은 변화**: 한 호출 = 한 리팩토링. P0만 실행, P1+는 후속 호출로.
- **회귀 가드**: 변경 전후 unit test + (있으면) backtest/타입체크 실행. 메트릭 악화 시 롤백.
- **솔루션 코드 금지**: 분석 에이전트는 file:line + 진단만. 솔루션 작성은 메인 모델이.

## 실행 인자

- 인자 없음: 최근 변경 (`git diff --stat`) + 핵심 모듈 자동 선정.
- `[영역]`: 특정 디렉토리 (예: `src/v4/`, `web/src/components/`).
- `[파일]`: 특정 파일 (예: `src/v4/causal.py`).

## 워크플로우 (필수 순서)

### Phase 1 — SCOPE (필수, 짧게)

1. `git status --short` + `git diff --stat HEAD~5..HEAD` — 최근 활동 영역 파악.
2. 인자 해석:
   - 인자 없음 → 최근 커밋된/uncommitted 파일 위주.
   - `[영역]` → 해당 디렉토리 모든 .py / .ts.
   - `[파일]` → 해당 파일 + 직접 import하는 파일 1차 이웃.
3. 분석 대상 표 출력:

| 파일 | LOC | 역할 |
|---|---|---|

### Phase 2 — 4-AGENT PARALLEL ANALYZE (필수)

**반드시 단일 메시지에서 4개 에이전트를 병렬 spawn.** 각 에이전트는 다른 관점·다른 우선순위 산출.

#### Agent A — Code Reviewer (`pr-review-toolkit:code-reviewer`)
- 역할: CLAUDE.md / 프로젝트 컨벤션 위반 + 단일 책임 원칙 + 매직 넘버 + 인터페이스 일관성.
- 입력: 분석 대상 파일 목록 + 최근 git diff.
- 요청: 우선순위별 리팩토링 제안, file:line 인용, 1순위 추천 + 트레이드오프 1줄.
- **중요**: 솔루션 코드 작성 금지.

#### Agent B — Silent-Failure Hunter (`pr-review-toolkit:silent-failure-hunter`)
- 역할: `try: ... except: pass` 패턴, 무시되는 반환값, 누락된 fallback alert, generic catch가 가리는 시스템 위험.
- 입력: 분석 대상 디렉토리 (디렉토리 단위 스캔이 효과적).
- 요청: 위험 silent failure top 5 (file:line) + 의도적 graceful degradation vs 진짜 silent 구분 + fix 난이도.
- **중요**: 솔루션 코드 작성 금지.

#### Agent C — Code Simplifier (`pr-review-toolkit:code-simplifier`)
- 역할: 중복 코드(DRY 위반), 긴 if-elif 체인, 중첩 try/except, 보일러플레이트, 매직 넘버 위치 불일치.
- 입력: 분석 대상 핵심 파일들 (LOC 기준 큰 파일 우선).
- 요청: 단순화 우선순위 top 5 + 중복 제거 기회(공통 함수 후보 명시) + 영향도(가독성/유지보수/테스트가능성).
- **중요**: 솔루션 코드 작성 금지.

#### Agent D — Type Design Analyzer (`pr-review-toolkit:type-design-analyzer`)
- 역할: dict-based 인터페이스의 invariant 누수, Optional 처리 불일치, enum 후보, 직렬화 비대칭, dataclass/TypedDict 도입 기회.
- 입력: 핵심 데이터 흐름 (incident/anomaly/diagnosis 등 도메인 dict들이 흐르는 파일).
- 요청: 타입 디자인 약점 top 5 + 정량 평가(encapsulation/invariant/usefulness/enforcement 0-10) + 도입 우선순위(Enum/dataclass/TypedDict/Pydantic).
- **중요**: 솔루션 코드 작성 금지.

### Phase 3 — SYNTHESIZE (필수)

4개 결과를 통합한 합의 우선순위 매트릭스:

| 우선순위 | 제안 | 합의 (몇 명) | 난이도 | 영향 |
|---|---|---|---|---|

규칙:
- **2명 이상 1-2순위로 지목**한 항목 → P0
- **1명만 critical**로 지목 + 다른 에이전트가 인접 영역 지목 → P1
- **L 난이도 + big bang risk** (예: dataclass 전체 도입) → P3 (다음 호출로 미루기)
- 같은 file:line이 여러 에이전트에서 다른 각도로 언급 → **반드시** P0 후보

### Phase 4 — PROPOSE (필수)

P0 1개 + 백업 옵션 1-2개를 표로 제시. 사용자 결정 대기.

> **그 다음 멈추고 사용자 승인 대기.** 자동 진행 금지. (단, "자동" / "전부 다" 같은 명시적 승인이 들어오면 P0만 실행.)

### Phase 5 — IMPLEMENT P0 (사용자 승인 후, 1개만)

원칙:
- 신규 helper / module 추출 시 `src/<adjacent>/<feature>.py` 패턴 (`v4/recurrence.py` 사례 참조).
- 기존 호출처는 위임만 남기고 슬림화 (예: 19줄 → 3줄).
- private symbol cross-module import → 공개 API로 승격 (예: `_RECUR_DEMOTE_AT` → `RECUR_DEMOTE_AT`).
- 단위 테스트는 `PYTHONPATH=src python3 -B -c "..."`로 즉시 작성·실행.
- TypeScript는 `cd web && npx tsc --noEmit`.

### Phase 6 — VERIFY (필수)

1. **Unit smoke**: 추출한 helper의 핵심 invariant를 PYTHONPATH=src python3 -c로 직접 검증.
2. **E2E smoke**: 호출처가 동일 외부 동작을 보이는지 1개 시나리오 통과.
3. **Regression** (해당시): backtest / 빌드 / 타입체크 재실행. 핵심 메트릭 변화 ±5% 이내 확인.
4. 비교 표 출력:

| 검증 항목 | Before | After | 판정 |
|---|---|---|---|

성공 기준 충족 여부:
- ✅ **충족**: 다음 후보(P1) 1줄 요약 후 종료.
- ❌ **미충족**: 즉시 롤백 (`git checkout -- <files>` 또는 Edit 역적용) + 가설 분석.
- ⚠️ **부분**: 어떤 부분이 됐고 안 됐는지 명시.

### Phase 7 — COMMIT 제안

변경이 의미 있으면 커밋 메시지 초안. 사용자가 "커밋해" 등으로 명시할 때만 실제 커밋.
P0+P1+...을 한 커밋에 묶지 말 것 — 각 P단위로 별도 commit.

## 분석 대상 선정 기본값

`Phase 1`에서 인자 없음 시:
1. uncommitted 변경된 파일 (`git diff --stat`)
2. 직전 5개 커밋에서 변경된 파일 (중복 제거)
3. 위 파일들이 import하는 1차 이웃 (해당 모듈 핵심 파일 1-2개)

LOC > 500줄 파일은 자동으로 Code Simplifier에게 우선 입력.

## Anti-pattern 금지

- ❌ 4명 다 같은 프롬프트로 호출 (시야 다양화 실패)
- ❌ 분석 에이전트에게 솔루션 코드까지 작성시키기 (역할 분리 위반)
- ❌ P0~P3을 한꺼번에 적용 (블래스트 반경 폭발)
- ❌ "리팩토링 같으니 안전" 가정 — 회귀 가드 생략
- ❌ Big bang dataclass / Pydantic 도입을 P0로 (multi-step 작업이라 별도 사이클로)
- ❌ 4-에이전트 결과를 단순 나열 (합의 분석이 핵심)

## 좋은 사이클 vs 나쁜 사이클

**좋은 사이클** (실제 사례):
- 4명 spawn → 3명이 `_update_recurrence_tracker` 중복을 1순위로 지목 → P0 자동 결정 → `v4/recurrence.py` 신규 모듈로 추출 → unit + E2E test 통과 → backtest regression 없음 → 커밋

**나쁜 사이클**:
- 4명 spawn → 4명 다 다른 1순위 제시 → 메인 모델이 자의적으로 선택 → 회귀 검증 없이 적용 → 다른 메트릭 악화 → 그래도 커밋

## 참고 자료

- harness-improve 스킬 (자매 사이클): `.claude/skills/harness-improve/SKILL.md`
- pr-review-toolkit 에이전트 정의 (시스템 레벨)
- CLAUDE.md — 프로젝트 컨벤션 source of truth
