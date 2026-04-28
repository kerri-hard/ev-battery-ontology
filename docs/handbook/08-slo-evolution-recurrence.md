# Ch.08 SLO · Evolution · Recurrence — 측정·진화·방지

← [07. Features](./07-features.md) | [목차](./00-toc.md) | 다음 → [09. Development](./09-development.md)

---

이 챕터는 시스템이 **자기 자신을 측정하고, 학습하고, 같은 실수를 반복하지 않게 하는** 세 매커니즘을 다룹니다.

---

## 8.1 SLO/SLI — 신뢰 약속의 측정

### 8.1.1 왜 SLI가 필요한가

운영자에게 *"시스템이 잘 동작하는가?"* 묻는 답은 항상 모호합니다. 5 SLI는 그 모호함을 *측정 가능한 약속*으로 바꿉니다.

### 8.1.2 5 SLI 카탈로그 (코드 진실)

[`src/v4/_engine_state.py:SLO_TARGETS`](../../src/v4/_engine_state.py)이 단일 진실 출처:

| SLI | 식 | target | higher_is_better | 의미 |
|---|---|---|---|---|
| `auto_recovery_rate` | auto_recovered / total_incidents | **0.95** | ✓ | 99% 자동 복구 비전 (9.4) |
| `p95_recovery_latency` | recovery_time_sec p95 | **0.05s** | ✗ | 빠른 회복 |
| `yield_compliance` | yield_rate ≥ 0.99 인 step 비율 | **0.95** | ✓ | 수율 약속 |
| `hitl_rate` | hitl_required / total_incidents | **0.05** | ✗ | 사람 개입 최소화 |
| `repeat_rate` | 재발 incidents / total | **0.25** | ✗ | 학습 SLI (9.5) |

### 8.1.3 측정 단위: per-step / per-area / global

`_engine_state.py`의 3 함수:

```
_compute_per_step_sli  → ProcessStep 단위 (31 step = 31 microservice)
_compute_per_area_sli  → ProcessArea 단위 (5 영역)
_compute_global_sli    → 시스템 전체
```

**31 step = 31 microservice** 비유는 SRE 워크플로 그대로 도입한 핵심:
- 각 step은 자기 SLO를 가진 독립 서비스
- 위반 발생 시 affected_steps drill-down으로 해당 microservice 즉시 확인

### 8.1.4 위반 처리 흐름

```
SLI 임계 위반 감지
    ↓ _compute_slo_violations
SLOViolation 객체 생성
    ↓ event_bus
WebSocket: slo_violation 이벤트
    ↓ NotificationCenter
Toast 알림 → 클릭 → SLO 페이지 + selectedSloKey set
    ↓ SLOViolationAlert
affected_steps 클릭 → Healing 페이지
```

### 8.1.5 Error Budget

`SLOKpiRibbon`의 budget gauge — `1 - SLI / target` 비율. 0%가 되면 모든 freeze.

---

## 8.2 Evolution — 8 진화 전략

### 8.2.1 EvolutionAgent 한 줄 요약

> **시스템이 자기 자신의 동작 파라미터를 가우시안 변형으로 시도하고, fitness가 좋아지면 승격, 나빠지면 롤백하는 자가 진화 메커니즘.**

진실 출처: [`src/v4/evolution_agent.py`](../../src/v4/evolution_agent.py). 5 iter마다 1 cycle.

### 8.2.2 8 전략 명단

| # | 전략 | 무엇을 변형 |
|---|---|---|
| 1 | `anomaly_threshold_tuning` | DETECT 페이즈의 SPC 임계 |
| 2 | `causal_rule_derivation` | 새 CausalRule 후보 derive |
| 3 | `correlation_expansion` | 상관 분석 lookback window |
| 4 | `playbook_optimization` | RECOVER 페이즈의 액션 우선순위 |
| 5 | `scenario_difficulty` | 시나리오 난이도 곡선 (research_loop) |
| 6 | `causal_strength_calibration` | CausalRule.strength 보정 |
| 7 | `causal_discovery` | Granger F-test 트리거 (7 iter마다) |
| 8 | `preverify_threshold_tuning` | PRE-VERIFY 안전등급 임계 |

각각 `StrategyRecord(name, mutate_fn, ...)`로 등록.

### 8.2.3 fitness 추적 (EMA)

각 전략은 EMA(exponential moving average) fitness를 가집니다:

```python
fitness_new = α × current_metric + (1-α) × fitness_old
```

α는 전략별 다름. 보통 0.2-0.3.

승격 조건:
- fitness > threshold + 쿨다운 시간 경과 → 변형 적용
- fitness 악화 → 롤백 + 쿨다운 증가

### 8.2.4 frontend 가시화

`learning/EvolutionTimeline.tsx`가 8 전략의 fitness sparkline을 시계열로 보여줌. 어느 전략이 시스템 개선에 기여하고 있는지 한눈에 파악.

### 8.2.5 PRE-VERIFY 임계 자가 보정 예

8번 `preverify_threshold_tuning` 전략은 다음을 자가 학습:

```
prediction_accuracy 낮음 → 임계 보수적으로 (사이클 후 측정으로 보정)
prediction_accuracy 높음 → 임계 공격적으로 (자동화율 증대)
```

`thresholds_history`(60 iter ring)이 `_engine_state.py:snapshot()`에 영속. PreverifyPanel의 ThresholdSparklines가 A/B/C 3색으로 가시화.

---

## 8.3 Anti-recurrence — 반복 방지 정책

### 8.3.1 왜 anti-recurrence인가

같은 root cause로 incident가 반복되면 *학습 실패*입니다. VISION §9.5 (실패에서 성장)의 직접 구현.

### 8.3.2 단일 진실 모듈

[`src/v4/recurrence.py`](../../src/v4/recurrence.py)에 단 하나의 진실:

```python
RECUR_DEMOTE_AT = 2     # 2회 이상 → 시도된 액션 후순위
RECUR_ESCALATE_AT = 3   # 3회 이상 + 후보 소진 → ESCALATE 강제

def incident_signature(step_id, anomaly_type, top_cause) -> str
def update_tracker(tracker, signature) -> int
```

production(`learn.py`), replay(`backtest.py`), preverify(`preverify.py`) **세 곳 모두 같은 헬퍼 사용** — 정책 변경 시 한 곳만 수정.

### 8.3.3 시그니처 = (step_id, anomaly_type, top_cause)

같은 step에서, 같은 종류 anomaly가, 같은 root cause로 발생하면 같은 시그니처. 카운터 증가.

### 8.3.4 흐름

```
incident 발생
    ↓
시그니처 계산 → tracker[sig] += 1
    ↓
preverify에서 같은 시그니처 액션 체크
    ↓
count >= RECUR_DEMOTE_AT → 대안 액션 우선
    ↓
count >= RECUR_ESCALATE_AT && 모든 대안 소진 → HITL ESCALATE
```

### 8.3.5 frontend 가시화

`learning/FailureChainExplorer.tsx`가 시그니처별 카운트 표시. 자주 반복되는 패턴 = 학습이 막힌 영역 → 운영자가 직접 검토 필요.

---

## 8.4 세 매커니즘의 연결

```
Evolution (자기 변형)
    ↓ 임계/규칙/플레이북 자가 보정
SLO (자기 측정)
    ↓ 위반 감지
Anti-recurrence (자기 검증)
    ↓ 같은 실수 반복 차단
└──────── 다 같이 9.5 "실패에서 성장" 구현
```

세 매커니즘은 분리 모듈이지만 모두 한 흐름:
- Evolution이 *시도*
- SLO가 *측정*
- Anti-recurrence가 *학습 실패 회피*

---

## 8.5 Backtest — 회귀 가드

세 매커니즘 모두 *측정 + 영속화* 가 핵심이라 backtest로 회귀 검증 가능:

```bash
python scripts/backtest.py --snapshot results/self_healing_v4_latest.json
```

게이트 ([`scripts/backtest_ci_guard.py`](../../scripts/backtest_ci_guard.py)):

| 메트릭 | 임계 | 환경변수 override |
|---|---|---|
| `decision_match_rate` | ≥ 0.55 | `BACKTEST_MIN_DECISION_MATCH` |
| `brier_score` | ≤ 0.10 | `BACKTEST_MAX_BRIER` |
| `ECE` | ≤ 0.30 | `BACKTEST_MAX_ECE` |
| `drift_warnings` | ≤ 5 | `BACKTEST_MAX_DRIFT` |

GitHub Actions [`.github/workflows/backtest.yml`](../../.github/workflows/backtest.yml)이 PR마다 자동 실행.

### Counterfactual replay

`backtest.py:_compute_counterfactuals` — 만약 다른 액션을 골랐다면 yield_delta가 어땠을까?

```
action_value = chosen_delta - baseline_delta
```

양수면 RCA 결정이 가치 있었음. 음수면 회귀 의심.

---

## 8.6 다음 → 직접 코드를 추가하기

지금까지 *측정*과 *학습*의 매커니즘을 이해했습니다. 다음 챕터는 *어떻게 새 코드를 추가하는가* — 새 에이전트, 새 페이지, 새 페이즈, 새 스킬.

---

← [07. Features](./07-features.md) | [목차](./00-toc.md) | 다음 → [09. Development](./09-development.md)
