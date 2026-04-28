# Ch.09 Development — 새 코드 추가 절차

← [08. SLO · Evolution · Recurrence](./08-slo-evolution-recurrence.md) | [목차](./00-toc.md) | 다음 → [10. Glossary](./10-glossary.md)

---

이 챕터는 본 저장소에 직접 기여할 때 따를 절차/규칙을 모았습니다. [`CLAUDE.md`](../../CLAUDE.md)의 개발 가이드를 신규 합류자에게 풀어쓴 버전입니다.

---

## 9.1 황금 규칙 5 (반드시 외울 것)

1. **측정→분석→개선→검증** 순서. 측정 없이 코드 수정 🔴 금지
2. **단일 작은 변화** — 한 PR = 한 가지 개선
3. **이전 버전과 비교** — 결과는 JSON으로 `results/`에 기록
4. **회귀 가드 백테스트** — 변경 전후 모두 실행
5. **온톨로지 쿼리 우선** — 판단 로직 하드코딩 🔴 금지

---

## 9.2 새 v3 에이전트 추가 (5 단계)

### 단계 1 — `BaseAgent` 상속 클래스 작성

`src/v3/agents.py`:

```python
class MyNewAgent(BaseAgent):
    ROLE = "MyNewAgent"

    def observe(self, conn) -> dict:
        # 그래프 쿼리로 현재 상태 관찰
        return {"some_metric": ...}

    def propose(self, observation) -> list[Proposal]:
        # 자기 영역 개선안 생성
        return [Proposal(
            agent_name=self.name,
            skill_name="some_skill",
            params={...},
            justification="..."
        )]

    def critique(self, proposal: Proposal) -> dict:
        # 다른 에이전트 제안 비평
        return {"issues": [], "suggestions": []}

    def vote(self, proposal: Proposal) -> float:
        # -1 (반대) ~ 1 (찬성)
        return 0.7
```

### 단계 2 — `create_agents()`에 등록

같은 파일의 `create_agents()` 끝에:

```python
agents.append(MyNewAgent())
```

### 단계 3 — (필요 시) 새 스킬 추가

`src/v3/skills.py`:

```python
def skill_my_new_skill(conn, params, counters):
    # idempotent하게 스키마 확장
    try:
        conn.execute("CREATE NODE TABLE NewNode ...")
    except Exception:
        pass
    # 그래프 갱신
    conn.execute("MERGE (n:NewNode {id: $id}) ...", {"id": params["id"]})
    counters["my_new_skill_calls"] += 1
```

`create_skill_registry()`에 등록:

```python
registry["my_new_skill"] = skill_my_new_skill
```

### 단계 4 — 테스트 (수동 검증)

```bash
./run.sh v3
```

CLI 출력에서 본인 에이전트의 trust_score 변동 확인.

### 단계 5 — VISION 정합성 체크

본인 에이전트가 다음 중 어느 9 원칙을 구현하는지 PR 설명에 명시:
- 9.1 온톨로지 = 두뇌
- 9.2 인과 추적
- ...

---

## 9.3 새 v4 페이즈 또는 페이즈 로직 수정

### 새 페이즈 추가 (드물지만)

1. `src/v4/phases/my_phase.py` 생성. 단일 함수 export
2. `src/v4/engine.py`의 `run_cycle()`에 한 줄 import + 호출
3. snapshot에 새 결과 직렬화하려면 `_engine_state.py:snapshot()` 수정

### 기존 페이즈 수정

🟢 **모범**:
- 그 페이즈 파일만 수정
- HITL 정책 변경 → `_engine_hitl.py`만 수정
- anti-recurrence 정책 변경 → `recurrence.py`만 수정

🔴 **금지**:
- `engine.py`에 비즈니스 로직 추가
- 페이즈 간 직접 호출 (반드시 engine을 통해)

---

## 9.4 새 시나리오 추가

`src/v4/scenarios.py`의 `Scenario(...)` 리스트에 추가:

```python
Scenario(
    id="SCN-021",
    name="my new scenario",
    severity="MEDIUM",  # HIGH / MEDIUM / LOW
    affected_steps=["PS-203"],
    sensors_affected={"vibration_pump_1": {"drift": 0.05}},
    duration_iters=10,
)
```

가중 랜덤이 자동으로 새 시나리오를 활성화 카운트와 함께 균형 잡음.

---

## 9.5 새 진화 전략 추가

`src/v4/evolution_agent.py`의 `_register_strategies()`:

```python
def _my_mutate(...):
    # 변형 함수
    ...

self.strategies.append(StrategyRecord(
    name="my_strategy",
    mutate_fn=_my_mutate,
    cooldown_iters=5,
    ...
))
```

EvolutionTimeline (frontend)이 자동으로 sparkline 추가.

---

## 9.6 새 프론트엔드 컴포넌트

### 단계 1 — 디렉토리/파일

```
web/src/components/myfeature/MyComponent.tsx
```

### 단계 2 — 보일러플레이트

```tsx
'use client';

import { useEngine } from '@/context/EngineContext';
import GlassCard from '@/components/common/GlassCard';

export default function MyComponent() {
  const { state } = useEngine();
  return (
    <GlassCard>
      <div className="ds-label">My Component</div>
      <div className="ds-body">{state.healing.iteration}</div>
    </GlassCard>
  );
}
```

### 단계 3 — 새 WebSocket 이벤트가 필요하면

1. `web/src/types/index.ts`에 인터페이스 추가
2. `web/src/hooks/reducers.ts`에 핸들러 추가
3. 백엔드 `event_bus.py`에서 이벤트 발행

### 단계 4 — 페이지에 dispatch

`web/src/app/page.tsx`의 view 분기에 추가.

### 단계 5 — 디자인 토큰 사용

`ds-heading`, `ds-label`, `ds-body`, `ds-caption` + `pill-success/warning/danger/info` + `glass`. 🔴 임의 폰트 크기 (`text-[7px]` 같은 magic font) 추가 금지.

severity 색은 `common/severityColors.ts`의 매핑만 사용.

---

## 9.7 새 페이지 추가

1. `types/index.ts`의 `ViewKey`에 추가
2. `useHarnessEngine.ts`의 `setView` 처리 (자동)
3. `Sidebar.tsx`의 `NAV_ITEMS`에 추가 (icon, key, desc)
4. `PageIntent.tsx`의 `PAGE_META`에 추가 (한 질문 + accent)
5. `app/page.tsx`의 view dispatch에 추가
6. `KeyboardShortcuts.tsx`에 단축키 (`g X`)

---

## 9.8 회귀 가드 (PR 전 필수)

### 단계 1 — 시뮬 실행

```bash
./run.sh dev
# 적어도 30 사이클 돌려 snapshot 갱신
```

### 단계 2 — 백테스트

```bash
python scripts/backtest.py --snapshot results/self_healing_v4_latest.json
```

### 단계 3 — 게이트 통과 확인

| 메트릭 | 임계 |
|---|---|
| `decision_match_rate` | ≥ 0.55 |
| `brier_score` | ≤ 0.10 |
| `ECE` | ≤ 0.30 |
| `drift_warnings` | ≤ 5 |

위반 시 변경 롤백 또는 가설 분석.

### 단계 4 — TypeScript 컴파일

```bash
cd web && npx tsc --noEmit
```

### 단계 5 — Python import 검증

```bash
PYTHONPATH=src python3 -c "from v4.engine import SelfHealingEngine; print('ok')"
```

---

## 9.9 커밋 / PR 가이드

### 커밋 메시지

본 저장소 표기 (직전 커밋 5개 참고):

```
[영역] 한 줄 요약 — 핵심 변경 + 측정 결과

(필요 시 본문)

근거: VISION §X.X / measurement
```

### PR 설명에 포함할 것

- **무엇을 바꿨나** (1-3 줄)
- **왜** (VISION 9 원칙 중 어느 것)
- **측정 Before/After** (표)
- **회귀 가드 결과** (백테스트 통과 스크린샷 또는 출력)

---

## 9.10 자주 만나는 함정

| 증상 | 원인 | 해결 |
|---|---|---|
| Kuzu schema 오류 | 이전 실행의 schema 잔재 | DB 디렉토리 삭제 후 재실행 |
| WebSocket reconnect loop | 백엔드 죽음 | 8080 포트 확인. `lsof -i :8080` |
| LLM token 소진 에러 | API key quota | 오프라인 폴백 자동 동작. 또는 cache 사용 |
| Snapshot file lock | 동시 실행 두 개 | `pkill -f "uvicorn"` 후 한 번만 실행 |
| Bytecode cache stale | `__pycache__` 잔재 | `rm -rf src/v4/__pycache__` 후 `python3 -B` |

---

## 9.11 하네스 스킬 활용

`.claude/skills/`:

- **`/harness-improve`** — 비전 정합 멀티 에이전트 개선 사이클. 측정→분석→제안→구현→검증 자동
- **`/refactor-review`** — 4관점 리팩토링 리뷰. P0 1건만 즉시 실행

새 기능 추가가 아니라 *코드 정리* 라면 `/refactor-review`가 적절.

---

## 9.12 다음 → 용어 사전

코드 작업 중 만나는 모든 약어/용어를 [Ch.10 Glossary](./10-glossary.md)에 정리.

---

← [08. SLO · Evolution · Recurrence](./08-slo-evolution-recurrence.md) | [목차](./00-toc.md) | 다음 → [10. Glossary](./10-glossary.md)
