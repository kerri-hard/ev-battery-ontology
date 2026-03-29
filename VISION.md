# 다크 팩토리를 향한 제조 AIOps 플랫폼

## 1. 제품 비전

> **제조 공정에서 문제가 발생하면 AI가 원인을 진단하고, 스스로 복구하며, 동일 장애가 재발하지 않도록 학습하는 — 사람이 불을 켤 필요 없는 공장, 다크 팩토리(Dark Factory)를 만든다.**

이 프로젝트는 **제조공정 온톨로지(Knowledge Graph) + 멀티 에이전트 AIOps + 디지털 트윈**을 결합하여, 공장이 스스로 문제를 감지→진단→복구→학습하는 자율 제조 시스템을 구현한다.

---

## 2. 학술 기반: 왜 이 접근이 유효한가

이 프로젝트의 아키텍처는 2024~2026년 최신 연구에 근거한다.

### 2.1 Knowledge Graph + Digital Twin 융합

> *"The combination of knowledge graphs and digital twins allows increased self-awareness by capitalizing on semantics stored in the KG, enabling tasks such as predictive maintenance and anomaly detection."*
> — Digital Twin Meets Knowledge Graph for Intelligent Manufacturing Processes (Sensors, 2024)

**다층 Knowledge Graph 아키텍처** (Nature Scientific Reports, 2024)는 세 계층으로 제조 지식을 구조화한다:
- **Concept Layer**: 공정/장비/자재/품질의 관계를 지식 네트워크로 구축
- **Model Layer**: 디지털과 물리적 파라미터를 정렬
- **Decision Layer**: 실시간 데이터 기반 의사결정

→ **본 프로젝트의 L1~L4 온톨로지 계층 구조가 이 아키텍처와 정확히 일치한다.**

### 2.2 Hybrid Agentic AI + Multi-Agent System

> *"The convergence of Agentic AI and Multi-Agent Systems enables a new paradigm for intelligent decision-making — LLM-based agents provide strategic orchestration and adaptive reasoning, complemented by rule-based agents performing domain-specific tasks on the edge."*
> — Hybrid Agentic AI and Multi-Agent Systems in Smart Manufacturing (NAMRC 2026)

**SOMN (Self-organizing Machine Network)** (ASME MSEC 2025)는 지능적 기계 에이전트가 실시간으로 자율 재편성하여 장애에 대한 레질리언스를 확보한다.

→ **본 프로젝트의 6종 전문 에이전트 토론 시스템이 이 패러다임을 구현한다.**

### 2.3 Knowledge Graph 기반 Root Cause Analysis

> *"Knowledge-graph-driven fault diagnosis leverages ontology models integrating textual features from production line components with expert insights, increasing the efficiency of fault diagnosis."*
> — Knowledge-Graph-Driven Fault Diagnosis Methods for Intelligent Production Lines (Sensors, 2025)

**Causal AI** (Databricks, 2025)는 인과관계 그래프를 통해 증상이 아닌 진짜 원인을 식별한다. **Neurosymbolic 접근** (CausalTrace, 2025)은 신경망과 지식 그래프를 결합하여 설명 가능한 진단을 제공한다.

→ **본 프로젝트의 RootCauseAnalyzer가 온톨로지 경로 역추적으로 이를 구현한다.**

### 2.4 LLM 기반 자율 예지정비 에이전트

> *"An autonomous agent powered by LLMs automates predictive modeling for fault diagnosis and RUL prediction, processing natural language queries and autonomously configuring AI models with iterative optimization."*
> — Toward Autonomous LLM-Based AI Agents for Predictive Maintenance (Applied Sciences, 2025)

**FD-LLM** (Advanced Engineering Informatics, 2025)은 대형 언어 모델을 장비 고장 진단에 특화시켜, 비정형 정비 기록에서도 원인을 추론한다.

→ **본 프로젝트의 다음 단계: LLM 에이전트가 온톨로지를 자연어로 쿼리하여 진단하는 것.**

### 2.5 자가 진화 에이전트 (Self-Evolving Agents)

> *"Self-evolving agents represent a new paradigm bridging foundation models and lifelong agentic systems — agents that improve their own capabilities over time through experience."*
> — A Comprehensive Survey of Self-Evolving AI Agents (2025)

Gartner 예측: 2028년까지 기업 애플리케이션의 33%가 자율 에이전트를 포함하고, 15%의 업무 의사결정이 자동화될 것.

→ **본 프로젝트의 신뢰도 기반 자가 학습 메커니즘이 이 방향을 선도한다.**

---

## 3. 핵심 아키텍처: Cognitive Digital Twin

최신 연구의 핵심 개념인 **Cognitive Digital Twin (CDT)**을 채택한다. CDT는 단순한 가상 복제본이 아니라, 온톨로지(지식) + 센서(인식) + AI 에이전트(추론/행동)가 결합된 **인지 능력을 가진 디지털 트윈**이다.

```
┌─────────────────────────────────────────────────────────────────────┐
│                   Cognitive Digital Twin 아키텍처                     │
│                                                                      │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│   │  Physical     │    │  Knowledge    │    │  Cognitive    │          │
│   │  Twin         │◄──►│  Graph        │◄──►│  Agents       │          │
│   │  (센서/PLC)   │    │  (온톨로지)    │    │  (AI 에이전트) │          │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
│          │                   │                    │                   │
│          ▼                   ▼                    ▼                   │
│   실시간 데이터 흐름    인과관계 추론       자율 의사결정            │
│   센서값, 알람, 상태    경로 탐색, RCA     감지→진단→복구→학습      │
│                                                                      │
│   ┌──────────────────────────────────────────────────────┐          │
│   │              자율 복구 루프 (Self-Healing Loop)        │          │
│   │                                                       │          │
│   │   SENSE → DETECT → DIAGNOSE → RECOVER → VERIFY       │          │
│   │     ↑                                        │        │          │
│   │     └──────────── LEARN ◄────────────────────┘        │          │
│   └──────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
```

### 기존 접근 vs CDT 접근

| 구분 | 기존 스마트 팩토리 | 본 프로젝트 (CDT) |
|------|-------------------|-------------------|
| 데이터 모델 | 관계형 DB + 대시보드 | **온톨로지 Knowledge Graph** |
| 이상 감지 | 규칙 기반 임계값 | **SPC + 통계적 이상탐지 + 인과추론** |
| 원인 분석 | 사람이 수동으로 | **온톨로지 경로 역추적 자동 RCA** |
| 대응 | 사람이 판단/실행 | **에이전트 토론 → 자동 복구** |
| 학습 | 없음 (매번 처음부터) | **장애 이력 축적 → 동일 장애 즉시 대응** |
| 진화 | 수동 업데이트 | **자가 진화 에이전트 (신뢰도 학습)** |

---

## 4. 온톨로지 = Cognitive 계층 구조

### 4.1 현재 구현된 계층

| 계층 | 역할 | 노드 타입 | 상태 |
|------|------|----------|------|
| **L1. 공정 지식** | 정적 구조/관계 | ProcessArea, ProcessStep, Equipment, Material, QualitySpec, DefectMode, AutomationPlan, MaintenancePlan | **구현됨** (8타입, 14관계) |
| **L2. 실시간 상태** | 센서/알람/장애 | SensorReading, Alarm, Incident, RecoveryAction | **구현됨** (4타입, 6관계) |

### 4.2 연구 기반 확장 계획

| 계층 | 근거 논문 | 추가 노드 타입 | 추가 관계 |
|------|----------|--------------|----------|
| **L3. 인과 추론** | KG-Driven Fault Diagnosis (2025), CausalTrace (2025) | CausalRule, AnomalyPattern, FailureChain | CAUSES, CORRELATES_WITH, PREDICTS, PRECEDES |
| **L4. 의사결정** | Hybrid Agentic AI (NAMRC 2026), Autonomous LLM Agent (2025) | ResponsePlaybook, EscalationPolicy, OptimizationGoal | TRIGGERS_ACTION, ESCALATES_TO, OPTIMIZES |
| **L5. 자가 진화** | Self-Evolving Agents Survey (2025) | AgentCapability, LearningRecord, StrategyMutation | EVOLVED_FROM, VALIDATED_BY, SUPERSEDES |

### 4.3 인과 추론 계층 (L3) — 다음 핵심 개선

연구에 따르면, **Causal AI**가 기존 상관관계 분석보다 진짜 원인을 찾는 데 훨씬 효과적이다. 현재 RootCauseAnalyzer는 경로 거리 기반이지만, 다음과 같이 개선해야 한다:

```
현재:  PS-203 수율 하락 → 경로 탐색 → "장비 MTBF 초과" (거리 기반 순위)

개선:  PS-203 수율 하락
       → CausalRule: "크림핑 압력 부족 ─[CAUSES]→ 접촉 불량 ─[CAUSES]→ 수율 하락"
       → FailureChain: 과거 동일 패턴 3회 확인 (신뢰도 92%)
       → AnomalyPattern: 직전 15분간 전류 센서 2σ 이상 연속
       → 진짜 원인: "크림핑 프레스 실린더 마모" (인과관계 기반, 경로 기반 아님)
```

---

## 5. 에이전트 아키텍처 진화 방향

### 5.1 현재 에이전트 (v3 + v4)

| 티어 | 에이전트 | 역할 | 구현 상태 |
|------|---------|------|----------|
| **온톨로지 개선** | ProcessAnalyst, QualityEngineer, MaintenanceEngineer, AutomationArchitect, SupplyChainAnalyst, SafetyAuditor | 토론으로 온톨로지 구조 개선 | 구현됨 |
| **자율 복구** | AnomalyDetector, RootCauseAnalyzer, AutoRecoveryAgent | 감지→진단→복구 | 구현됨 |

### 5.2 연구 기반 추가 에이전트

| 에이전트 | 근거 | 역할 |
|---------|------|------|
| **CausalReasoner** | CausalTrace (2025), Causal AI (Databricks) | 인과관계 그래프 기반 근본 원인 추론. 상관관계가 아닌 인과관계로 진단 |
| **PredictiveAgent** | Autonomous LLM for PdM (2025), FD-LLM (2025) | 장비 잔여수명(RUL) 예측 + 선제적 정비 스케줄링 |
| **ResilienceOrchestrator** | SOMN (ASME 2025) | 장비 고장 시 대체 경로 자동 활성화, 생산 라인 자율 재편성 |
| **NaturalLanguageDiagnoser** | FD-LLM (2025), LLM Planning Agent (2025) | 비정형 정비 기록/작업자 보고서에서 원인 추론 |
| **EvolutionAgent** | Self-Evolving Agents Survey (2025) | 에이전트 전략 자체를 변형/테스트/승격하는 메타 에이전트 |

### 5.3 Hybrid Agentic 아키텍처 (NAMRC 2026 기반)

```
┌─────────────────────────────────────────────────┐
│              Orchestration Layer                  │
│         (LLM — 전략적 추론, 적응적 판단)          │
├─────────────────────────────────────────────────┤
│              Edge Agent Layer                     │
│    (Rule-based + Small LM — 빠른 도메인 태스크)   │
│                                                   │
│  [AnomalyDetector] [CausalReasoner] [Recovery]   │
│  [Predictive]      [Resilience]     [Safety]     │
├─────────────────────────────────────────────────┤
│              Knowledge Layer                      │
│         (온톨로지 Knowledge Graph — Kuzu)          │
│                                                   │
│  L1:공정지식  L2:실시간상태  L3:인과추론  L4:의사결정│
└─────────────────────────────────────────────────┘
```

NAMRC 2026 논문의 핵심 인사이트: **LLM은 전략적 오케스트레이션에, 경량 에이전트는 에지에서 빠른 실행에** 각각 사용해야 한다. 모든 것을 LLM으로 하면 느리고, 모든 것을 규칙으로 하면 유연하지 않다.

---

## 6. 다크 팩토리 5단계 로드맵

| 단계 | 이름 | 사람의 역할 | AI의 역할 | 상태 |
|------|------|-----------|----------|------|
| **L0** | 수동 공장 | 모든 판단/실행 | 없음 | |
| **L1** | 감시 공장 | 판단/실행 | 이상 감지, 알람 | |
| **L2** | 지능 공장 | 승인/감독 | 진단, 대응 권고 | |
| **L3** | 자율 공장 | 예외 처리만 | 자동 진단/복구 | **현재** |
| **L4** | 다크 팩토리 | 전략 수립만 | 완전 자율 운영 + 자가 진화 | 목표 |

### Phase 1: 공정 지식 + 에이전트 토론 (완료)
- 온톨로지 L1 (8 노드타입, 14 관계타입)
- 6종 에이전트 토론 시스템 (신뢰도 가중 투표)
- 수율 87.15% → 91.47%, 완성도 37.2 → 80.9

### Phase 2: 자율 복구 시뮬레이션 (완료)
- 온톨로지 L2 (SensorReading, Alarm, Incident, RecoveryAction)
- 3종 복구 에이전트 (AnomalyDetector, RootCauseAnalyzer, AutoRecoveryAgent)
- 56개 가상 센서, 24건 자동 복구 (복구율 100%)
- 수율 → 93.14%

### Phase 3: 인과 추론 계층 (다음)
- 온톨로지 L3 (CausalRule, AnomalyPattern, FailureChain)
- CausalReasoner 에이전트 추가
- 인과관계 기반 RCA (경로 기반 → 인과 기반 전환)
- 장애 패턴 DB 축적 → 동일 장애 즉시 대응

### Phase 4: LLM 에이전트 통합
- PredictiveAgent (RUL 예측)
- NaturalLanguageDiagnoser (자연어 쿼리 진단)
- Hybrid 아키텍처: LLM 오케스트레이션 + 에지 경량 에이전트
- MQTT/OPC-UA 실제 센서 연동

### Phase 5: 다크 팩토리
- ResilienceOrchestrator (생산 라인 자율 재편성)
- EvolutionAgent (에이전트 전략 자가 진화)
- 디지털 트윈 시뮬레이션 기반 의사결정
- 다공장 연합 온톨로지

---

## 7. 현재 GAP 분석 (연구 기준)

| 역량 | 현재 수준 | 최신 연구 수준 | 상태 |
|------|----------|-------------|------|
| **원인 분석** | CausalReasoner + 인과 체인 역추적 | Causal AI 기반 RCA | **구현됨** (L3 계층) |
| **장애 패턴 학습** | FailureChain 패턴 매칭 + 성공률 추적 | 패턴 DB + 자동 대응 | **구현됨** |
| **공정 간 상관분석** | CorrelationAnalyzer (Pearson + lag) + CrossProcessInvestigator | 다변량 시계열 상관 | **구현됨** |
| **예지정비** | PredictiveAgent (RUL 기반) | RUL 예측 + 선제적 스케줄링 | **구현됨** |
| **자연어 인터페이스** | NaturalLanguageDiagnoser | LLM 온톨로지 쿼리 | **구현됨** |
| **HITL 안전장치** | 신뢰도/위험도 기반 에스컬레이션 | Human-in-the-Loop | **구현됨** |
| **라인 재편성** | 미구현 | 자율 기계 네트워크 재편성 (SOMN) | 다음 단계 |
| **에이전트 자가 진화** | 신뢰도 조정 | 전략 자체를 변형/테스트/승격 | 다음 단계 |

### 신규 구현: 공정 간 상관분석 (Cross-Process Correlation)

```
예시: PS-203(하네스 제작) 수율 하락 발생

기존 분석: PS-203만 분석 → "크림핑 압력 이상" (단일 원인)

상관분석 결과:
  PS-103(셀 스태킹) 진동 ↔ PS-203 온도: r=0.82 (상류 진동이 하류에 전파)
  PS-104(레이저 용접) 온도 ↔ PS-203 온도: r=0.78 (열 전파)
  → 진짜 원인: 상류 PS-103의 스태킹 머신 진동 이상이 하류 공정으로 전파

다단계 진단:
  ① AnomalyDetector: PS-203 수율 이상 감지
  ② RootCauseAnalyzer: 경로 역추적 → 장비 MTBF 후보
  ③ CausalReasoner: 인과 체인 역추적 → 실린더 마모 → 압력 부족 → 접촉 불량
  ④ CrossProcessInvestigator: 상관분석 → PS-103 진동 이상이 근본 원인
  → 4개 에이전트의 분석을 종합하여 신뢰도 가중 최종 진단
```

### 에이전트 분석 파이프라인

```
장애 감지
  │
  ├─→ AnomalyDetector ────── SPC 통계적 이상 감지
  │                           3-sigma, Western Electric, 임계값 초과
  │
  ├─→ RootCauseAnalyzer ──── 온톨로지 경로 역추적
  │                           장비/자재/결함모드/상류/검사 7경로
  │
  ├─→ CausalReasoner ─────── 인과관계 체인 역추적
  │                           CausalRule 체인 + FailureChain 패턴 매칭
  │
  ├─→ CorrelationAnalyzer ── 센서 간 Pearson/시차 상관
  │                           107개 공정 간 상관관계 발견
  │
  └─→ CrossProcessInvestigator ── 상관 + 온톨로지 교차 검증
                                   상류/하류/숨겨진 의존성 추적
```

### 1순위 개선: 인과 추론 계층 (L3) — 구현 완료

```python
# 이전: 경로 거리 기반 순위
candidates.sort(key=lambda x: -x["confidence"])

# 현재: 인과관계 + 상관관계 + 학습 기반 복합 점수
# final = base(0.55) + causal_chain(0.25) + history_match(0.20) + pattern_link(0.12)
# + 교차 원인 분석(상관관계 r > 0.6이면 추가 후보)
```

### 구현된 인과 체인 예시

```
CausalRule 15개, CAUSES 관계 10개:
  실린더 마모 ─[CAUSES]→ 압력 부족 ─[CAUSES]→ 접촉 불량 ─[CAUSES]→ 수율 하락
  냉각 이상 ─[CAUSES]→ 온도 상승 ─[CAUSES]→ 코팅 불량 ─[CAUSES]→ 수율 하락
  자재 로트변경 ─[CAUSES]→ 특성 편차 ─[CAUSES]→ 공정 변동 ─[CAUSES]→ 수율 하락
  전류 이상 ─[CAUSES]→ 용접 불량 ─[CAUSES]→ 접합 강도 저하 ─[CAUSES]→ 수율 하락
  베어링 마모 ─[CAUSES]→ 진동 증가 ─[CAUSES]→ 가공 정밀도 저하 ─[CAUSES]→ 수율 하락

FailureChain 8+개: 실제 복구 경험이 자동 축적
  동일 장애 재발 시 패턴 매칭 → 즉시 올바른 복구 선택

Correlation 107+개: 공정 간 센서 상관관계 발견
  CORRELATES_WITH 관계로 온톨로지에 영구 저장
```
# 3. AnomalyPattern 노드: 시계열 패턴 (연속 drift, 급격한 spike 등)
# 4. 신뢰도 = 인과관계 강도 × 과거 확인 횟수 × 패턴 유사도
```

### 2순위 개선: 장애 이력 구조화

현재 Incident 노드에 문자열로 저장하지만, 구조화된 FailureChain으로 전환:
```
Incident ─[CAUSED_BY]→ CausalRule ─[HAS_PATTERN]→ AnomalyPattern
                                   ─[RESOLVED_BY]→ RecoveryAction
                                   ─[RECURRENCE_OF]→ 이전 Incident
```

---

## 8. 기술 스택

| 구성요소 | 현재 | 연구 기반 확장 방향 |
|---------|------|-------------------|
| Knowledge Graph | Kuzu (임베디드) | + Causal inference engine |
| 백엔드 | FastAPI + WebSocket | + MQTT/OPC-UA 브로커 |
| 프론트엔드 | Next.js 14 + TypeScript | 유지 |
| 에이전트 | Python rule-based | + Claude Agent SDK (LLM 오케스트레이션) |
| 이상 감지 | SPC (3-sigma) | + Temporal pattern learning |
| 원인 분석 | 경로 탐색 | + Causal Bayesian Network |
| 예지정비 | 정적 MTBF | + RUL 예측 (LSTM/Transformer) |

---

## 9. 설계 철학

### 9.1 Cognitive Digital Twin
온톨로지는 단순한 데이터 저장소가 아니라 **인지 능력을 가진 디지털 트윈의 두뇌**다. 에이전트가 온톨로지를 탐색하는 것은 인간 전문가가 공장을 이해하는 방식과 같다.

### 9.2 인과관계가 핵심
상관관계(correlation)가 아니라 **인과관계(causation)**를 추적해야 진짜 원인을 찾을 수 있다. "A 다음에 B가 발생했다"가 아니라 "A가 B를 유발했다"를 온톨로지에 명시한다.

### 9.3 Hybrid Agentic — LLM + 경량 에이전트
모든 것을 LLM으로 하지 않는다. 빠른 감지/복구는 경량 규칙 에이전트가, 복잡한 추론/전략은 LLM이 담당하는 **하이브리드 구조**가 최적이다.

### 9.4 자동 복구가 목적, 모니터링은 수단
대시보드를 보는 것이 아니라 **대시보드를 볼 필요가 없는 것**이 목표다.

### 9.5 실패에서 성장하는 시스템
모든 장애는 삭제하지 않고 FailureChain으로 구조화하여, 같은 상황이 재발하면 즉시 올바른 대응을 선택한다.

### 9.6 점진적 자율성
검증된 패턴만 자동화하고, 미확인 패턴은 사람에게 에스컬레이션한다. 충분한 데이터가 쌓인 후에만 자율 수준을 승격한다.

---

## 10. 참고 문헌

| 번호 | 논문/자료 | 핵심 인사이트 | 본 프로젝트 적용 |
|------|----------|-------------|----------------|
| 1 | Digital Twin Meets Knowledge Graph (Sensors, 2024) | KG+DT 융합으로 예지정비 강화 | L1~L2 온톨로지 계층 |
| 2 | Multi-Layer KG for Manufacturing (Nature Sci.Rep., 2024) | Concept/Model/Decision 3계층 KG | L1~L4 계층 구조 |
| 3 | Hybrid Agentic AI + MAS (NAMRC, 2026) | LLM 오케스트레이션 + 에지 에이전트 | 에이전트 아키텍처 |
| 4 | Self-organizing Machine Network (ASME MSEC, 2025) | 기계 에이전트의 자율 재편성 | ResilienceOrchestrator |
| 5 | Agentic AI for Predictive Maintenance (Applied Sci., 2025) | LLM 기반 자율 예지정비 | PredictiveAgent |
| 6 | KG-Driven Fault Diagnosis (Sensors, 2025) | 온톨로지 기반 장애 진단 | RootCauseAnalyzer |
| 7 | CausalTrace Neurosymbolic (arXiv, 2025) | 인과 추론 + 설명 가능 AI | CausalReasoner |
| 8 | FD-LLM for Equipment Diagnosis (Adv.Eng.Inf., 2025) | LLM 특화 장비 진단 | NaturalLanguageDiagnoser |
| 9 | Self-Evolving Agents Survey (2025) | 에이전트 자가 진화 패러다임 | EvolutionAgent |
| 10 | Causal AI for Manufacturing RCA (Databricks, 2025) | 인과 AI로 진짜 원인 식별 | L3 인과 추론 계층 |
| 11 | Ontology-Based DT for Maintenance (Springer, 2025) | 온톨로지 기반 정비 디지털 트윈 | L1 온톨로지 설계 |
| 12 | Autonomous LLM for PHM (Machines, 2025) | LLM이 예측 모델을 자율 구성 | Phase 4 LLM 통합 |
