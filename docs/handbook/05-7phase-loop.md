# Ch.05 7-Phase Loop — 자율 복구의 심장

← [04. Ontology](./04-ontology.md) | [목차](./00-toc.md) | 다음 → [06. Agents & Skills](./06-agents-skills.md)

---

## 5.1 한 줄 요약

```
SENSE → DETECT → DIAGNOSE → PRE-VERIFY → RECOVER → VERIFY → LEARN
```

각 페이즈는 `src/v4/phases/`의 단일 `.py` 파일. `engine.py`는 오케스트레이션만 담당. 페이즈를 추가/수정할 때 `engine.py`는 **거의 건드리지 않습니다**.

---

## 5.2 페이즈별 책임/입력/출력

### Phase 1 — SENSE (`phases/sense.py`)

**책임**: 가상 센서 56개에서 reading을 수집하고, 활성 시나리오에 따라 노이즈/드리프트 주입.

| 입력 | 출력 |
|---|---|
| 사이클 인덱스, 활성 시나리오 | `readings: dict[sensor_id → value]` |

핵심 모듈:
- `sensor_simulator.py` — 56 센서 (온도, 압력, 진동, 전류, ...)
- `scenarios.py` — 20 시나리오 + 가중 랜덤 활성화

---

### Phase 2 — DETECT (`phases/detect.py`)

**책임**: SPC 3-sigma + Western Electric 룰 + 고급 통계로 anomaly 후보 생성.

| 입력 | 출력 |
|---|---|
| readings | `anomaly_events: list[Anomaly]` |

검출 기법:
- **SPC 3-sigma** — 평균±3σ 이탈
- **Western Electric** — 연속 패턴 (예: 9점 같은 쪽)
- **CUSUM** — 누적합 변화
- **EWMA** — 지수가중 이동평균
- **EvolutionAgent의 anomaly_threshold_tuning 전략**이 임계값을 자가 조정 ([Ch.08](./08-slo-evolution-recurrence.md))

진화 임계가 너무 민감해지지 않도록 EvolutionAgent는 fitness EMA로 보정.

---

### Phase 3 — DIAGNOSE (`phases/diagnose.py`)

**책임**: anomaly의 root cause를 *온톨로지 역추적*으로 찾기. 필요 시 LLM 보강.

| 입력 | 출력 |
|---|---|
| anomaly_events | `rca_candidates: list[RCACandidate]` (top-K) |

내부 구조:
- `causal.py` — `CausalReasoner.diagnose()` — 그래프 traversal + FailureChain 매칭
- `correlation.py` — `CorrelationAnalyzer` — 상관 기반 보조 후보
- `correlation.py` — `CrossProcessInvestigator` — cross-step 영향 분석
- `llm_orchestrator.py` — 복잡도 따라 rule/LLM 분기. LLM 결과는 confidence cap 적용

점수 합산:
```
score = base_score + causal_score + history_score + pattern_score
       + (LLM이 활성화된 경우) llm_score (capped)
```

---

### Phase 4 — PRE-VERIFY (`phases/preverify.py`)

**책임**: 각 후보 액션을 *가상 적용*해 expected_delta 시뮬. 안전 등급별 임계 미달 시 자동 거절.

| 입력 | 출력 |
|---|---|
| rca_candidates + playbook | `validated_actions` + 거절 이유 |

핵심 함수:
- `simulate_action(engine, action)` — 단일 액션 시뮬. yield_rate 변화·success_prob·anomaly_resolution 예측
- `simulate_action_sequence(engine, actions)` — Markov 가정 액션 시퀀스 (최대 3 step). cumulative_success_prob, expected_delta_total 노출

안전 등급별 임계:
- A 등급 (고전압/레이저) — score 임계 가장 높음 (보수적)
- B 등급 (주의) — 중간
- C 등급 (일반) — 임계 낮음

임계값은 EvolutionAgent의 `preverify_threshold_tuning` 전략이 자가 보정. 60 iter ring buffer로 sparkline 가시화.

**Anti-recurrence 정책 적용**: 동일 시그니처 2회 이상 → 같은 액션 후순위, 3회 이상 → ESCALATE 강제. 단일 진실 [`recurrence.py`](../../src/v4/recurrence.py).

---

### Phase 5 — RECOVER (`phases/recover.py`)

**책임**: 검증된 액션을 실제 적용. HITL 게이트 통과 필요.

| 입력 | 출력 |
|---|---|
| validated_actions | applied_actions or hitl_pending |

HITL 게이트 ([`_engine_hitl.py`](../../src/v4/_engine_hitl.py)):
- 안전등급 A: 항상 HITL
- 안전등급 B + medium_requires_history=true: 과거 매칭 history 있을 때만 자동
- 안전등급 C: 자동 진행
- min_confidence 미달: HITL
- high_risk_threshold 초과: HITL

운영자는 Healing 페이지의 SelectedIncidentCard에서 **Approve/Reject inline** 가능.

실 적용 채널:
- `protocol_bridge.py:OPCUABridge` — OPC-UA via asyncua
- `protocol_bridge.py:SimulatedBridge` — 시뮬레이션 (기본)
- `protocol_bridge.py:SparkplugBBridge` — Eclipse Tahu (선택)

---

### Phase 6 — VERIFY (`phases/verify.py`)

**책임**: 사후 yield/OEE 측정, 예측 정확도(sign_accuracy, MAE) 추적.

| 입력 | 출력 |
|---|---|
| applied_actions + post-readings | verify_result + accuracy metrics |

이 결과로 PRE-VERIFY 시뮬 모델의 캘리브레이션 추적. ECE/Brier 계산은 backtest에서.

---

### Phase 7 — LEARN (`phases/learn.py`)

**책임**: incident 영속화, FailureChain 매칭 링크, recurrence_tracker 갱신, L3 그래프 강화.

| 입력 | 출력 |
|---|---|
| 페이즈 1-6 모든 결과 | Incident node 영속, FailureChain 강화 |

학습 동작:
1. `Incident` 노드 추가 (Cypher CREATE)
2. 매칭된 `FailureChain`이 있으면 `MATCHED_BY` 관계 + success_count 증가
3. 새 인과 발견 시 `CausalRule` 후보로 보내기 (CausalDiscoveryEngine은 7 iter마다 실행)
4. `recurrence_tracker`에 시그니처 카운트 추가

---

### Periodic (`phases/periodic.py`)

7 페이즈와 별개로 주기적으로 실행되는 작업:

| 작업 | 주기 | 모듈 |
|---|---|---|
| **CausalDiscovery** (Granger F-test) | 7 iter | `causal_discovery.py` |
| **EvolutionAgent cycle** | 5 iter | `evolution_agent.py` |
| **LLM analyst 사이클 분석** | 가변 | `llm_analyst.py` |

---

## 5.3 사이클 종료 후 무엇이 영속되는가

[`_engine_state.py:snapshot()`](../../src/v4/_engine_state.py)이 다음을 `results/self_healing_v4_latest.json`에 직렬화:

- `healing` — incidents, recurrence_kpis, hitl_history
- `preverify` — accuracy (mae, sign_accuracy), thresholds_history (60 iter)
- `recurrence` — 시그니처 카운트
- `phase4` — evolution_agent.cycle_count, strategy fitness
- `slo` — per-step / per-area / global SLI + violations

이 파일을 backtest가 replay해서 회귀를 검증.

---

## 5.4 페이즈를 추가/수정할 때

🟢 **모범**:
- 신규 페이즈 = `phases/` 새 파일. `engine.py`에 한 줄 import + 호출
- 기존 페이즈 변경 = 그 파일만 수정 + 같은 파일에 unit test (가능 시)

🔴 **금지**:
- `engine.py`에 비즈니스 로직 추가
- 페이즈 간 직접 호출 (반드시 engine을 통해)
- `_engine_state.py` 외 다른 곳에서 snapshot 직접 수정

---

## 5.5 다음 → 누가 이 페이즈들을 돌리는가

지금까지는 *동작*. 다음은 v3의 *멀티 에이전트 토론* — 7-페이즈가 운영(v4)이라면 v3는 그 *온톨로지를 빌드*하는 회의입니다.

---

← [04. Ontology](./04-ontology.md) | [목차](./00-toc.md) | 다음 → [06. Agents & Skills](./06-agents-skills.md)
