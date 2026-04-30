# EV Battery Self-Healing Factory — 시스템 아키텍처

> EV 배터리팩 제조 공정의 **자율 복구 (Self-Healing)** 플랫폼.
> 사람이 대시보드를 보지 않아도 AI가 문제를 감지·진단·복구·학습하는 다크 팩토리 시스템.
>
> 본 문서는 **시스템의 책임·구성·동작 흐름**을 설명한다. 사상은 [VISION.md](VISION.md), 개발 가이드는 [CLAUDE.md](CLAUDE.md), 빠른 시작은 [README.md](README.md)에서 다룬다.

---

## 1. 시스템 한 줄 요약

```
센서 데이터 → AI가 이상을 감지 → 온톨로지로 원인 추적 → 자동 복구 → 결과를 학습 →
                                                      ↓
                                       다음 사이클이 더 똑똑해짐 (자가 진화)
```

전통적 모니터링 시스템이 "문제를 보여주는" 데서 그친다면, 이 플랫폼은 **문제 자체를 없애는 것**이 목표다. 대시보드는 *결과*를 검증하는 수단이지, *목적*이 아니다.

---

## 2. 핵심 설계 원칙

| # | 원칙 | 구체적 의미 |
|---|---|---|
| 1 | **자동 복구가 목적** | 모니터링은 수단. 사람이 안 봐도 시스템이 해결해야 함 |
| 2 | **온톨로지 = 공장의 두뇌** | 모든 공정 지식, 인과관계, 장애 이력을 그래프로 구조화 |
| 3 | **에이전트 협업** | 감지/진단/복구/검증을 전문 에이전트들이 분업 |
| 4 | **실패에서 성장** | 장애·오탐·잘못된 복구를 삭제하지 않고 학습 데이터로 축적 |
| 5 | **점진적 자율성** | L1(권고) → L2(반자율) → L3(자동) → L4(완전자율) 순서로 승격 |
| 6 | **Hybrid Agentic** | 빠른 감지·복구는 경량 규칙 에이전트, 복잡한 추론은 LLM이 담당 |
| 7 | **인과관계 추적** | 상관(correlation)이 아니라 인과(causation)를 명시적으로 추적 |

---

## 3. 자율성 단계 (현재 L3+)

| 단계 | 이름 | 사람의 역할 | AI의 역할 |
|---|---|---|---|
| L0 | 수동 공장 | 모든 판단/실행 | 없음 |
| L1 | 감시 공장 | 판단/실행 | 이상 감지·알람 |
| L2 | 지능 공장 | 승인/감독 | 진단·대응 권고 |
| **L3** | **자율 공장** | **예외 처리만** | **자동 진단·복구** ← 현재 |
| L4 | 다크 팩토리 | 전략 수립만 | 완전 자율 운영 + 자가 진화 |

현재 시스템은 **L3 자율 공장 + L4 Tier 2** 단계에 있다. 자동 인과 발견·자가 진화·LLM 오케스트레이션·CDT 시뮬레이션 기반 의사결정·예측 정확도 자기 보정까지 구현됨.

---

## 4. 전체 시스템 아키텍처

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         BROWSER (Next.js, port 3000)                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────────────┐ │
│  │ ProcessMap   │ │ EventLog     │ │ MetricsBar   │ │ Pre-verify Panel    │ │
│  │ (5 area cols)│ │ (실시간 로그)│ │ (수율/노드..)│ │ (시뮬레이션 + 임계)  │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └─────────────────────┘ │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────────────┐ │
│  │ HITL Queue   │ │ Incident     │ │ Predictive   │ │ Orchestrator Trace  │ │
│  │ (승인/거절)  │ │ Analysis     │ │ RUL Panel    │ │ (rule vs LLM 결정)  │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └─────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │  WebSocket: 30+ event types
                                      │  REST: /api/state, /api/init, ...
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      FastAPI BACKEND (port 8080)                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                       SelfHealingEngine                                 │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │ │
│  │  │ 자율 복구 루프 (7 페이즈)                                        │  │ │
│  │  │  SCENARIO → SENSE → DETECT → DIAGNOSE → PRE-VERIFY → RECOVER     │  │ │
│  │  │   → VERIFY → LEARN → PERIODIC                                    │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                         │ │
│  │  ┌─────────── 12 에이전트 ────────────┐  ┌─────── 메타 시스템 ──────┐  │ │
│  │  │ AnomalyDetector / RootCauseAnalyzer│  │ EvolutionAgent (자가진화) │  │ │
│  │  │ AutoRecoveryAgent / CausalReasoner │  │ LLMOrchestrator (Hybrid)  │  │ │
│  │  │ CorrelationAnalyzer / Cross-Invest │  │ CausalDiscoveryEngine     │  │ │
│  │  │ PredictiveAgent / WeibullRUL       │  │ ResilienceOrchestrator    │  │ │
│  │  │ NL Diagnoser / LLMAnalyst          │  │ ScenarioEngine            │  │ │
│  │  │ TraceabilityManager                │  │ Backtest Harness          │  │ │
│  │  └────────────────────────────────────┘  └───────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                  Kuzu Graph DB (5 계층 온톨로지)                        │ │
│  │  L1 공정 지식 │ L2 운영 │ L3 인과 │ L4 의사결정/RUL │ L5 학습/추적성   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      ▲                                       │
│                                      │                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │     Sensor Bridge (현재: Simulated, 향후: MQTT / OPC-UA / Sparkplug)   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. 5계층 온톨로지 (공장의 두뇌)

각 계층은 그래프 DB의 노드/관계 타입 묶음으로 구현된다. 이전 계층 위에 새 계층이 쌓이는 구조.

### L1 — 공정 지식 (정적 도메인)

공장의 변하지 않는 구조와 사양.

| 노드 타입 | 의미 |
|---|---|
| ProcessArea | 5대 공정영역 (셀 어셈블리, 전장 조립, 냉각 시스템, 인클로저, 최합조립/검사) |
| ProcessStep | 31개 개별 공정 단계 (수율, OEE, 안전등급, 사이클 타임 등) |
| Equipment | 설비 (MTBF, MTTR, 투자비) |
| Material | 자재 (단가, 공급사, 리드타임) |
| QualitySpec | 품질 규격 (min/max 범위) |
| DefectMode | 결함 모드 (Severity/Occurrence/Detection → RPN) |
| AutomationPlan | 자동화 계획 |
| MaintenancePlan | 정비 계획 |

**관계 14종**: 공정 흐름(NEXT_STEP, FEEDS_INTO, PARALLEL_WITH, TRIGGERS_REWORK), 구조(BELONGS_TO, USES_EQUIPMENT, CONSUMES, REQUIRES_SPEC), 결함/정비(HAS_DEFECT, PREVENTS, PLANNED_UPGRADE, HAS_MAINTENANCE), 의존성(DEPENDS_ON), 검사(INSPECTS).

### L2 — 운영 (동적 이벤트)

매 사이클 발생하는 운영 데이터.

| 노드 | 의미 |
|---|---|
| SensorReading | 센서 측정값 (56개 가상 센서) |
| Alarm | 임계 초과 경보 |
| Incident | 자동 복구가 처리한 장애 사건 |
| RecoveryAction | 실행된 복구 액션 (action_type, parameter, old/new value) |

### L3 — 인과 추론

상관이 아닌 인과를 명시.

| 노드/관계 | 의미 |
|---|---|
| CausalRule | 인과 규칙 (cause_type → effect_type, strength) |
| AnomalyPattern | 시계열 패턴 (drift / spike / level_shift) |
| FailureChain | 학습된 장애 체인 (success_count, failure_count) |
| CAUSES / CORRELATES_WITH / MATCHED_BY / CHAIN_USES / HAS_CAUSE / HAS_PATTERN | 인과·매칭 관계 |

### L4 — 의사결정 + 예지정비

| 노드 | 의미 |
|---|---|
| ResponsePlaybook | (cause_type → action_type) 매핑, priority + active 플래그 |
| EscalationPolicy | HITL 에스컬레이션 정책 |
| RULEstimate | Weibull 생존분석 RUL 결과 (장비별 upsert) |

### L5 — 학습 + 추적성

| 노드 | 의미 |
|---|---|
| LearningRecord | EvolutionAgent의 메타 학습 사이클 결과 |
| StrategyMutation | 전략 파라미터 변형 이력 |
| ProductionBatch | 생산 배치 (Tesla/Samsung SDI 추적성 방식) |
| LotTrace | 자재 LOT 추적 |
| BatteryPassport | EU Battery Passport (2027 규제 대응) |

---

## 6. 자율 복구 루프 — 7 페이즈

매 사이클마다 다음 페이즈가 순차 실행된다 (현재 1 사이클 ≈ 1초). 페이즈별로 WebSocket 이벤트가 발행되어 프론트엔드에서 실시간 시각화.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ⓪ SCENARIO    4 사이클마다 무작위로 장애 시나리오 주입 (테스트 데이터)   │
├─────────────────────────────────────────────────────────────────────────┤
│  ① SENSE       센서 readings 수집 + 정상범위 이탈 카운트                 │
│                + 센서 간 Pearson 상관 (CORRELATES_WITH 영구 저장)         │
├─────────────────────────────────────────────────────────────────────────┤
│  ② DETECT      SPC (3σ + Western Electric) + 고급 감지 (Matrix Profile  │
│                + Isolation Forest)로 이상 탐지. 임계 초과 시 Alarm 노드. │
├─────────────────────────────────────────────────────────────────────────┤
│  ③ DIAGNOSE    경로 기반 RCA (장비/자재/결함모드/상류/검사) +            │
│                인과 체인 역추적 + LLM 오케스트레이터 (복잡도>0.5만 호출)  │
│                + 교차 원인 (CrossProcessInvestigator: 상관+온톨로지 검증) │
├─────────────────────────────────────────────────────────────────────────┤
│  ④ PRE-VERIFY  ★ NEW (CDT 시뮬레이션 기반 의사결정)                       │
│                각 후보 액션을 적용 전에 시뮬레이션:                        │
│                  score = expected_delta × confidence × (1 − risk)        │
│                  expected_delta = (new_value − old_value) × success_prob │
│                안전등급 A에서 score < 임계값 → 자동 거절 (HITL 강제)      │
├─────────────────────────────────────────────────────────────────────────┤
│  ⑤ RECOVER     선택된 액션을 실제 적용. 실패 시 지수 백오프 재시도        │
│                (최대 3회, base 0.05초). 모두 실패 시 ResilienceOrchest-  │
│                rator가 PARALLEL_WITH 대체 경로 탐색·활성화.              │
├─────────────────────────────────────────────────────────────────────────┤
│  ⑥ VERIFY      복구 후 yield_rate 재측정 → improvement 판정.              │
│                예측치(PRE-VERIFY)와 비교하여 정확도 누적.                  │
│                + Weibull RUL 추정 → RULEstimate 노드 upsert.              │
│                + PredictiveAgent로 P1/P2 장비 우선순위 계산.              │
├─────────────────────────────────────────────────────────────────────────┤
│  ⑦ LEARN       에이전트 지식 업데이트:                                    │
│                  - AnomalyDetector recovery_feedback 누적                │
│                  - RootCauseAnalyzer cause_history 누적                  │
│                  - AutoRecoveryAgent success_history 누적                │
│                  - CausalReasoner FailureChain 추가/강도 보정             │
│                + Incident 노드 생성 + L3 관계 강화 (HAS_CAUSE, HAS_PATTERN)│
├─────────────────────────────────────────────────────────────────────────┤
│  ⑧ PERIODIC    주기적 메타 작업:                                          │
│                  - 3 사이클: causal calibration (Bayesian replay)        │
│                  - 5 사이클: playbook mutation, scenario 난이도 적응,    │
│                              causal discovery (Granger), Evolution cycle │
│                  - 매 사이클: traceability batch, event bus, LLM 분석     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. PRE-VERIFY 게이트 (CDT 핵심)

> **의도**: 액션을 실행하기 *전에* 그 결과를 시뮬레이션한다. 안전등급이 높은 공정에서 위험한 액션이 자동 실행되는 것을 차단.

### 7.1 시뮬레이션 점수 계산

각 후보 액션에 대해 다음을 계산한다:

| 변수 | 의미 | 산출 방법 |
|---|---|---|
| param_delta | 액션이 만들 yield/OEE 변화량 | 플레이북의 adjustment 값 (또는 new − old) |
| success_prob | 그 액션이 성공할 확률 | 과거 (action_type, cause_type) 성공률 (이력 < 2건이면 confidence) |
| expected_delta | 기댓값 | param_delta × success_prob |
| risk_factor | 위험도 계수 | LOW=0.1, MEDIUM=0.3, HIGH=0.6, CRITICAL=0.9 |
| **score** | **선택 점수** | **expected_delta × confidence × (1 − risk_factor)** |

가장 높은 score의 액션이 선택된다.

### 7.2 안전등급별 거절 임계값

| 안전등급 | 의미 | 기본 임계값 |
|---|---|---:|
| A | 위험 (고전압/레이저) | 1e-4 (엄격) |
| B | 주의 | 0.0 |
| C | 일반 | -1e-3 (관대) |

best score가 임계값 미만이면 → **자동 거절 → HITL 큐로 직행**.

### 7.3 자기 진화 (Strategy 8)

EvolutionAgent가 5 사이클마다 임계값 자체를 튜닝한다.

```
┌─ 측정 ─┐    ┌─ 분석 ──────────────────┐    ┌─ 개선 ─────────────┐
│        │    │                          │    │                     │
│ 예측 vs │ → │ sign_accuracy < 0.6     │ →  │ TIGHTEN             │
│ 실측    │    │ → 시뮬레이션 신뢰도 낮음│    │ (임계값 +20%)       │
│ 비교    │    │                          │    │                     │
│        │    │ sign_accuracy > 0.85    │ →  │ LOOSEN              │
│ MAE,   │    │ + reject_rate > 5%       │    │ (임계값 −20%)       │
│ sign   │    │ → 너무 보수적            │    │ (자율성 회복)       │
│ match  │    │                          │    │                     │
│        │    │ 그 외 → HOLD            │    │ 변경 없음           │
└────────┘    └──────────────────────────┘    └─────────────────────┘
                                                       │
                                              ┌────────▼────────┐
                                              │ 검증            │
                                              │ 다음 사이클의   │
                                              │ accuracy 측정 → │
                                              │ 또 fitness 신호 │
                                              └─────────────────┘
```

각 안전등급별로 별도 bound가 적용되어 runaway 방지.

---

## 8. Backtest 하네스 (회귀 가드)

> **의도**: 모델/플레이북 변경이 과거 결정과 어떻게 다른지 측정해 회귀를 차단.

CLI: 저장된 incident snapshot을 현재 모델로 replay.

| 산출 메트릭 | 의미 |
|---|---|
| decision_match_rate | 현재 모델 top-action vs 기록된 action 일치율 |
| confidence_brier | Brier score (낮을수록 calibrated) — 신뢰도 ≈ 실제 성공률 |
| confidence_ece | Expected Calibration Error (10-bin) |
| preverify_reject_rate | PRE-VERIFY가 거절했을 incident 비율 |
| per_action_breakdown | action_type별 (count, match_rate, reject_rate) |
| drift_warnings | 회귀 경고 — 과거 성공한 action을 현재 모델이 다른 것으로 바꾸는 케이스 |

운영 시나리오:
- 새 플레이북/규칙 추가 후 backtest 실행
- drift_warnings가 N건 이상이면 사람이 검토 후 머지
- 향후 GitHub Actions PR 게이트로 자동화 예정

---

## 9. 에이전트 분업 (12종 + 메타 5종)

### 9.1 자율 복구 에이전트 (12종)

각 에이전트는 단일 책임 원칙을 지킨다. 판단은 온톨로지 쿼리 기반(하드코딩 금지). 모든 행동/결과는 온톨로지에 기록.

| 에이전트 | 페이즈 | 주요 책임 |
|---|---|---|
| **AnomalyDetector** | DETECT | SPC + Western Electric 룰로 통계적 이상 감지 |
| **AdvancedAnomalyDetector** | DETECT | CUSUM + Matrix Profile + Isolation Forest 보강 |
| **RootCauseAnalyzer** | DIAGNOSE | 온톨로지 7개 경로(장비/자재/결함모드/상류/검사 등) 역추적 |
| **CausalReasoner** | DIAGNOSE | CausalRule 체인 + FailureChain 패턴 매칭으로 신뢰도 가중 |
| **CorrelationAnalyzer** | SENSE | 센서 간 Pearson + 시차 상관 → CORRELATES_WITH 저장 |
| **CrossProcessInvestigator** | DIAGNOSE | 상관 + 온톨로지 경로 교차 검증으로 숨겨진 의존성 추적 |
| **AutoRecoveryAgent** | RECOVER | 플레이북 기반 자동 복구 + 성공률 학습 + 자기 변형 |
| **ResilienceOrchestrator** | RECOVER | PARALLEL_WITH 대체 경로 탐색·활성화 |
| **PredictiveAgent** | VERIFY | 미해결 인시던트 가중 RUL v1.1 |
| **WeibullRULEstimator** | VERIFY | Weibull 생존분석 기반 RUL + RULEstimate 노드 upsert |
| **NaturalLanguageDiagnoser** | route_intent | 자연어 질의 기반 진단 요약 |
| **LLMAnalyst** | PERIODIC | 인시던트별 LLM 심층 분석 (캐시 + fallback 템플릿) |

### 9.2 메타 시스템 (5종)

전체 루프 위에서 동작하는 거버넌스/메타 컴포넌트.

| 컴포넌트 | 역할 |
|---|---|
| **EvolutionAgent** | 8개 전략의 fitness 추적 + 파라미터 변형/승격/쿨다운. 매 5 사이클마다 |
| **LLMOrchestrator** | 복잡도 점수로 rule vs LLM 경로 자동 분기. Anthropic / OpenAI 지원 |
| **CausalDiscoveryEngine** | Granger F-test + 조건부 독립성 가지치기 → 새 CausalRule 자동 승격 |
| **ScenarioEngine** | 장애 시나리오 주입 + 적응형 난이도 + cascading delay |
| **TraceabilityManager** | ProductionBatch / LotTrace / BatteryPassport (EU 규제 대응) |

### 9.3 에이전트 분석 파이프라인 예시

```
PS-203 (와이어 하네스) 수율 이상 발생
   │
   ├─→ AnomalyDetector ───── 3σ 위반 감지 (신뢰도 0.85)
   │
   ├─→ RootCauseAnalyzer ─── 경로 후보 5개:
   │                          {장비 MTBF 위험, 자재 공급 이상, 결함 모드, ...}
   │
   ├─→ CausalReasoner ────── 인과 체인 매칭:
   │                          실린더 마모 → 압력 부족 → 접촉 불량 → 수율 하락
   │                          (FailureChain 매칭, history_matched=True)
   │
   ├─→ CorrelationAnalyzer ─ 발견된 상관:
   │                          PS-103 진동 ↔ PS-203 온도 r=0.82
   │
   └─→ CrossProcessInvestigator → 진짜 원인은 상류 PS-103
                                   (스태킹 머신 진동이 하류로 전파)

   ↓
PRE-VERIFY 시뮬레이션:
   - EQUIPMENT_RESET PS-103 (안전등급 B): score=0.0006 ✓ 선택
   - ADJUST_PARAMETER PS-203:           score=0.0002 (대안)
   - INCREASE_INSPECTION PS-203:        score=0.0000 (대안)

   ↓
RECOVER → VERIFY:
   PS-103 OEE 0.82 → 0.84
   PS-203 yield 0.97 → 0.992 (예측 0.991, 실측 0.992 → MAE 0.001)

   ↓
LEARN:
   - FailureChain success_count++
   - CausalRule "실린더 마모 → 압력 부족" strength 보정
   - PRE-VERIFY accuracy_history에 sign_match=True 추가
```

---

## 10. 백엔드 모듈 맵 (책임만)

코드 디렉토리는 책임 중심으로 분리되어 있다.

```
src/v4/
├── engine.py                  ← SelfHealingEngine 클래스 (오케스트레이터)
│                                __init__, initialize, 페이즈 호출, intent routing
│
├── _engine_state.py           ← StateMixin: get_state, L3 trend, KPI 계산
├── _engine_hitl.py            ← HITLMixin: 승인/거절, 정책 업데이트, 감사 로그
│
├── phases/                    ← 7 페이즈 + 주기 작업
│   ├── sense.py               ← 센서 수집 + 상관분석
│   ├── detect.py              ← SPC + 고급 이상 감지
│   ├── diagnose.py            ← RCA + 인과 + LLM 오케스트레이션
│   ├── preverify.py           ← ★ CDT 시뮬레이션 + 임계값 거절
│   ├── recover.py             ← 액션 실행 + 백오프 + 대체경로 + HITL 큐
│   ├── verify.py              ← yield 검증 + RUL + 예측 정확도 누적
│   ├── learn.py               ← 에이전트 학습 + Incident 저장 + L3 강화
│   └── periodic.py            ← 5/3 사이클 메타 작업 + LLM 배치
│
├── healing/                   ← 자율 복구 에이전트 4종
│   ├── playbook.py            ← RECOVERY_PLAYBOOK 상수 + HITL 게이트
│   ├── detector.py            ← AnomalyDetector
│   ├── rca.py                 ← RootCauseAnalyzer
│   ├── recovery.py            ← AutoRecoveryAgent
│   └── orchestrator.py        ← ResilienceOrchestrator
│
├── analyst/                   ← LLMAnalyst 패키지
│   ├── client.py              ← OpenAI 호출 + 캐시 + fallback
│   ├── prompts.py             ← system/user 프롬프트 + 한국어 라벨
│   ├── fallback.py            ← API 미사용 시 템플릿 요약
│   ├── scoring.py             ← confidence breakdown + 참여 에이전트 식별
│   └── cache.py               ← LRU + TTL
│
├── research/                  ← 연구→개선→테스트→검증 자동 사이클 (CLI)
│   ├── metrics.py             ← MetricsCollector + 수렴/회귀 판정
│   ├── strategies.py          ← 6 개선 전략
│   ├── simulation.py          ← N회 자율 복구 시뮬레이션
│   └── db_setup.py            ← Kuzu DB 부트스트랩
│
├── causal.py                  ← CausalReasoner + L3 스키마 + 시드
├── causal_discovery.py        ← Granger 인과 자동 발견
├── correlation.py             ← CorrelationAnalyzer + CrossProcessInvestigator
├── decision_layer.py          ← L4 ResponsePlaybook + EscalationPolicy
├── advanced_detection.py      ← Matrix Profile + Isolation Forest
├── weibull_rul.py             ← Weibull 생존분석 + RULEstimate sync
├── traceability.py            ← L5 추적성 (Batch/Lot/BatteryPassport)
├── event_bus.py               ← pub/sub 이벤트 버스
├── protocol_bridge.py         ← SimulatedBridge + MQTTBridge 인터페이스
├── learning_layer.py          ← L5 LearningRecord + StrategyMutation 저장
├── llm_orchestrator.py        ← Hybrid Agentic 라우터
├── llm_agents.py              ← PredictiveAgent + NaturalLanguageDiagnoser
├── evolution_agent.py         ← 자가 진화 메타 에이전트 (8 전략)
├── scenarios.py               ← 장애 시나리오 라이브러리 + 적응형 난이도
├── sensor_simulator.py        ← 56개 가상 센서 + L2 스키마
└── backtest.py                ← Backtest 하네스 (회귀 가드)
```

---

## 11. 프론트엔드 모듈 맵 (책임만)

```
web/src/
├── app/page.tsx               ← Dashboard 컴포지션 (panel 레이아웃)
│
├── hooks/
│   ├── useHarnessEngine.ts    ← WebSocket 연결 + reducer 디스패치
│   └── reducers/              ← 이벤트 핸들러 (도메인별 분리)
│       ├── lifecycleEvents.ts ← connected/state/initialized/loop_*/paused
│       ├── v3Events.ts        ← phase/observe/propose/debate/apply/evaluate/learn
│       ├── healingEvents.ts   ← sense/detect/diagnose/recover/verify/learn_healing
│       ├── hitlEvents.ts      ← HITL queue/resolve/policy_update
│       └── intelligenceEvents.ts  ← preverify/orchestrator/causal/evolution/...
│
├── context/EngineContext.tsx  ← React Context Provider
├── types/index.ts             ← 모든 TypeScript 인터페이스
│
└── components/
    ├── layout/                ← Header / Sidebar
    ├── process/               ← ProcessMap (5 area columns)
    ├── graph/                 ← OntologyGraph + L3Panels + 위치 추적 hook
    ├── preverify/             ← ★ PreverifyPanel (시뮬레이션 + 임계값)
    ├── issues/                ← LiveIssuePanel + IncidentAnalysis
    ├── agents/                ← AgentList + TrustBar
    ├── debate/                ← DebatePanel + VoteResults
    ├── metrics/               ← MetricsBar + SidebarMetrics
    ├── charts/                ← Sparkline / SVGLine / SVGBar (외부 라이브러리 없음)
    ├── controls/              ← ControlPanel + PhaseIndicator
    └── common/                ← GlassCard / Badge / EventLog / ConnectionDot
```

---

## 12. 데이터 흐름 — 단일 사이클 추적

```
1. SCENARIO 페이즈
   → ScenarioEngine.tick() → activate_random()
   → 'scenario_activated' WS 이벤트 발행

2. SENSE 페이즈
   → SensorSimulator.generate_readings() → 56개 readings
   → store_readings() → SensorReading 노드 생성
   → CorrelationAnalyzer.ingest() + analyze_all()
   → 'sense_done' + 'correlation_found' WS 이벤트

3. DETECT 페이즈
   → AnomalyDetector.update() + detect()
   → AdvancedDetector 보강
   → check_alarms() → Alarm 노드 생성
   → 'detect_done' WS 이벤트
   (이상 없으면 'all_clear' 후 사이클 종료)

4. DIAGNOSE 페이즈 (이상별)
   → RootCauseAnalyzer.analyze() → 후보 5경로
   → CausalReasoner.analyze() → 인과 체인 + FailureChain 매칭
   → LLMOrchestrator.decide_path() → 복잡도 > 0.5면 LLM 호출
   → CrossProcessInvestigator.investigate()
   → 'diagnose_done' WS 이벤트

5. PRE-VERIFY 페이즈 ★
   → 후보 액션마다 simulate_action() → score
   → 안전등급별 임계값으로 거절 판정
   → engine._latest_preverify_predictions에 저장 (verify에서 회수)
   → 'preverify_done' WS 이벤트

6. RECOVER 페이즈
   → 거절된 plan은 즉시 HITL 큐 → 'recover_pending_hitl' WS 이벤트
   → 선택된 액션 실행 with backoff
   → 모두 실패 시 ResilienceOrchestrator.activate_alternate()
   → 'recover_done' WS 이벤트

7. VERIFY 페이즈
   → AutoRecovery.verify_recovery() → post_yield 측정
   → _record_preverify_accuracy() → predicted vs actual 비교
   → WeibullRUL.estimate() + sync_to_ontology()
   → 'verify_done' (+ 'rul_critical' if P1/P2) WS 이벤트

8. LEARN 페이즈
   → 4종 에이전트 .learn() 호출 (knowledge_updates)
   → Incident 노드 생성 + healing_history 추가
   → L3 관계 강화 (HAS_CAUSE, HAS_PATTERN, MATCHED_BY)
   → 'learn_done_healing' + 'learning_record_created' WS 이벤트

9. PERIODIC 페이즈 (조건부)
   → 3 사이클: causal calibration → 'causal_calibrated'
   → 5 사이클: playbook mutation → 'playbook_mutated'
   → 5 사이클: scenario adapt → 'scenario_difficulty_adapted'
   → 5 사이클: causal discovery → 'causal_discovery_done'
   → 5 사이클: evolution cycle → 'evolution_cycle_done'
   → 매 사이클: traceability batch + event bus + LLM 배치 분석
```

각 WS 이벤트는 `web/src/hooks/reducers/` 의 핸들러 맵에서 처리되어 React 상태를 갱신한다.

---

## 13. HITL (Human-In-The-Loop) 정책 + 안전 가드

### 13.1 자동 vs HITL 결정

```
복구 액션이 다음 중 하나에 해당하면 → HITL 큐로 에스컬레이션:
  ① confidence < min_confidence (안전등급 A는 자동 0.65로 강제)
  ② risk_level >= high_risk_threshold (HIGH/CRITICAL)
  ③ medium_requires_history=True 이고 risk >= MEDIUM 인데 과거 이력 매칭 없음
  ④ ★ PRE-VERIFY가 거절 (score < 안전등급 임계값)
```

### 13.2 HITL 정책 자체도 운영 중 변경 가능

- 운영자: 승인/거절만 가능
- Supervisor: 정책 파라미터(min_confidence 등) 변경 가능
- 모든 변경은 audit 로그 + JSON 영속화

### 13.3 LLM 안전 가드

안전등급 A 공정에서 LLM 가설은 confidence가 강제로 0.59 이하로 cap → 자동 실행 차단, HITL 강제. `'llm_hypothesis_guarded'` 이벤트 발행.

---

## 14. 자가 진화 메커니즘 (EvolutionAgent)

8개 전략을 등록하여 매 5 사이클마다 fitness를 측정하고 개선을 시도한다.

| # | 전략 | fitness 신호 | 변형 대상 |
|---|---|---|---|
| 1 | anomaly_threshold_tuning | false_positive_rate | AnomalyDetector.window_size |
| 2 | causal_rule_derivation | 신규 규칙 수 | (도출만, 변형 없음) |
| 3 | correlation_expansion | 발견 상관 수 | CorrelationAnalyzer.threshold |
| 4 | playbook_optimization | 저성과 액션 수 | (식별만) |
| 5 | scenario_difficulty | 복구율 | ScenarioEngine 난이도 |
| 6 | causal_strength_calibration | 보정된 규칙 수 | CausalRule.strength |
| 7 | causal_discovery | 승격된 규칙 수 | (Granger 트리거) |
| 8 | **preverify_threshold_tuning ★** | **sign_accuracy** | **engine.preverify_thresholds** |

각 전략은 자체 fitness, 시도 횟수, 개선 횟수, best_params를 추적한다. 저성과 전략은 cooldown 후 비활성화. 결과는 LearningRecord 노드로 영속화 (재시작 시 복원).

---

## 15. 운영 시나리오

### 15.1 평상시 운영 (사람 개입 없음)

1. 백엔드 + 프론트 띄움 (`./run.sh dev`)
2. 자율 복구 루프가 계속 돌면서 매 사이클 페이즈 실행
3. 운영자는 대시보드를 *모니터링하지 않아도* 시스템이 자동 처리
4. PRE-VERIFY 임계값은 자기 진화하며 점차 최적화

### 15.2 HITL 개입 (예외 상황)

1. PRE-VERIFY가 거절 OR 정책 게이트 발동 → HITL 큐에 적재
2. 운영자가 `PreverifyPanel` 또는 HITL 패널에서 알림 확인
3. 승인 또는 거절 → 시스템이 즉시 처리

### 15.3 모델 변경 시

1. 새 플레이북/규칙 추가 (코드/데이터 변경)
2. 현재 시스템에서 incident 스냅샷 저장 (`results/self_healing_v4_latest.json`)
3. `python scripts/backtest.py --snapshot ...` 실행
4. drift_warnings 검토 → 회귀 없으면 머지
5. 재시작 → EvolutionAgent가 LearningRecord에서 자동 복원

### 15.4 신규 공정 추가

1. `data/graph_data.json`에 ProcessStep / Equipment 추가
2. 시드 스크립트(`research/db_setup.py`) 재실행
3. 시스템 자동으로 새 공정에 대해 학습 시작
4. FailureChain이 18+개 쌓이면 동일 패턴 즉시 매칭

---

## 16. 측정 가능한 운영 지표

대시보드와 `get_state()` API로 실시간 노출:

| 지표 | 의미 | 현재 (참고치) |
|---|---|---|
| recovery_rate | 자동 복구 성공률 | 100% |
| matched_chain_rate | FailureChain 매칭률 | 90%+ |
| repeat_incident_rate | 재발률 | 낮을수록 좋음 |
| line_yield | 라인 수율 | 베이스라인 87.15% → 91.47% |
| sign_accuracy_recent (PRE-VERIFY) | 시뮬레이션 방향 정확도 | 자기 보정 중 |
| mae_recent | 시뮬레이션 yield 예측 오차 | 0.005 (0.5%p) |
| auto_reject_rate | PRE-VERIFY 자동 거절률 | 임계값에 따라 변동 |
| confidence_brier (Backtest) | 신뢰도 calibration | 낮을수록 좋음 |

---

## 17. 기술 스택

| 영역 | 사용 기술 | 비고 |
|---|---|---|
| Knowledge Graph | Kuzu (임베디드) | Cypher 쿼리, 프로토타이핑용 |
| Backend | FastAPI + uvicorn (port 8080) | WebSocket + REST |
| Frontend | Next.js 14 + TypeScript (strict) + Tailwind | 외부 차트 라이브러리 없음 (커스텀 SVG) |
| State | useReducer + React Context | 외부 상태 라이브러리 없음 |
| Anomaly Detection | NumPy + scikit-learn | SPC + Matrix Profile + Isolation Forest |
| Causal Inference | scipy + Granger F-test | 자체 구현 |
| LLM | Anthropic / OpenAI (선택) | LRU+TTL 캐시 + fallback 템플릿 |
| Predictive | scipy.stats Weibull + lifelines (옵션) | RULEstimate 노드 sync |
| 추적성 | EU Battery Passport 스키마 | 2027 규제 대응 |
| 프로토콜 | SimulatedBridge / MQTTBridge | 향후 OPC-UA + Sparkplug B |

---

## 18. 미구현 / 다음 사이클 후보

| 항목 | 상태 | 우선순위 |
|---|---|---|
| Backtest CI 게이트 | 미구현 (CLI는 동작) | 높음 |
| Multi-step PRE-VERIFY | 단일 액션만 | 중간 |
| Counterfactual replay ("안 했다면?") | 미구현 | 중간 |
| Threshold 진화 sparkline | 현재값만 표시 | 낮음 |
| 실제 OPC-UA 연동 | **구현 완료** (asyncua sync client + node read/write, `protocol_bridge.py:OPCUABridge`) — 실 PLC 통합 테스트는 별도 | 중간 |
| 다공장 연합 온톨로지 | 단일 공장 | 낮음 (Phase 5) |
| Transformer RUL | Weibull로 강화 | 낮음 |

---

## 19. 참고 문서

- [VISION.md](VISION.md) — 사상, 5단계 로드맵, 학술 근거
- [CLAUDE.md](CLAUDE.md) — 개발 가이드 (에이전트 하네스 주입용)
- [README.md](README.md) — 빠른 시작
