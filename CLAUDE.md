# EV Battery Pack 제조 AIOps 플랫폼 — 개발 가이드

## 프로젝트 개요

제조공정 온톨로지 + AIOps로 **문제 감지 → 자동 진단 → PRE-VERIFY → 자동 복구 → 학습**하는 자율 제조 시스템(다크 팩토리) 플랫폼.

**현재 단계: L3 자율 공장 + L4 Tier 2** — 자동 인과 발견·자가 진화·LLM 오케스트레이션·CDT 시뮬레이션·예측 정확도 자기 보정 구현됨.

**참조 문서**:
- [`VISION.md`](VISION.md) — 다크 팩토리 방향성, 5단계 로드맵, 9가지 설계 철학
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — 시스템 동작/모듈 맵/7-페이즈 루프
- 본 문서(CLAUDE.md) — 개발 가이드 (에이전트 하네스 주입용)

## 핵심 원칙

1. **자동 복구가 목적**: 대시보드가 아니라 "사람이 안 봐도 AI가 해결"이 목표
2. **온톨로지 = 공장의 두뇌**: 모든 공정 지식, 인과관계, 장애 이력은 그래프로 구조화
3. **에이전트 협업**: 감지/진단/복구/검증을 전문 에이전트들이 분업
4. **실패에서 성장**: 장애·오탐·잘못된 복구를 삭제하지 않고 학습 데이터로 축적 (anti-recurrence)
5. **점진적 자율성**: L1(권고) → L2(반자율) → L3(자동) → L4(완전자율) 순서로 승격
6. **Hybrid Agentic**: 빠른 경량 규칙 에이전트 + 복잡 추론 LLM
7. **인과 추적**: 상관관계가 아니라 인과를 명시적으로 추적

## 자율 복구 루프 (7 페이즈)

```
SENSE → DETECT → DIAGNOSE → PRE-VERIFY → RECOVER → VERIFY → LEARN
```

각 페이즈는 `src/v4/phases/`에 분리되어 있으며 `src/v4/engine.py`가 오케스트레이션만 담당.

- **SENSE** (`sense.py`): 56 가상 센서에서 reading 수집, 시나리오 활성화
- **DETECT** (`detect.py`): SPC 3-sigma + Western Electric + advanced (CUSUM/EWMA)
- **DIAGNOSE** (`diagnose.py`): 인과 그래프 역추적 RCA + LLM 보강 + cross-cause
- **PRE-VERIFY** (`preverify.py`): 액션을 가상 적용해 expected_delta 시뮬, score < 안전등급별 임계 시 자동 거절. anti-recurrence 정책 적용 (`v4/recurrence.py`)
- **RECOVER** (`recover.py`): 검증된 액션 실제 실행 + HITL 게이트
- **VERIFY** (`verify.py`): 사후 yield/OEE 측정, 예측 정확도 추적
- **LEARN** (`learn.py`): Incident 영속화, FailureChain 매칭 링크, recurrence_tracker 갱신, L3 그래프 강화

## 프로젝트 구조

```
ev-battery-ontology/
├── VISION.md                 # 비전·로드맵·9 설계 철학
├── ARCHITECTURE.md           # 시스템 동작/모듈 맵
├── CLAUDE.md                 # 본 파일 — 개발 가이드
├── README.md                 # 빠른 시작
├── server.py                 # FastAPI 백엔드 (WebSocket + REST API, port 8080)
├── serve.py                  # 정적 HTML 대시보드 서버
├── run.sh                    # 실행 스크립트
├── requirements.txt          # kuzu, fastapi, uvicorn, scipy, numpy, ...
├── scripts/
│   ├── backtest.py           # Backtest CLI — snapshot replay + 회귀 게이트
│   └── generate_*.py         # 보고서/PPT 생성 유틸
├── src/
│   ├── harness_v3.py         # v3 배치 하네스 엔트리포인트
│   ├── v3/                   # 멀티 에이전트 토론 시스템 (온톨로지 개선)
│   │   ├── agents.py         # 6 전문 에이전트 + Moderator
│   │   ├── skills.py         # 14 스킬 레지스트리
│   │   ├── harness.py        # 배치 루프
│   │   └── engine.py         # 실시간 엔진 (WebSocket)
│   └── v4/                   # 자율 복구 + L3-L4 (확장 후)
│       ├── engine.py         # SelfHealingEngine — v3 위에 7-페이즈 루프
│       ├── _engine_state.py  # get_state, snapshot 영속화 (preverify/recurrence/phase4 포함)
│       ├── _engine_hitl.py   # HITL 정책/게이트
│       ├── phases/           # SENSE/DETECT/DIAGNOSE/PREVERIFY/RECOVER/VERIFY/LEARN/PERIODIC
│       ├── healing/          # detector, rca, recovery, playbook, orchestrator (회복탄력성)
│       ├── analyst/          # LLM analyst — client/cache/prompts/scoring/fallback
│       ├── research/         # research_loop 시뮬레이션·전략 탐색
│       ├── recurrence.py     # anti-recurrence 정책 단일 진실 소스 (RECUR_DEMOTE_AT 등)
│       ├── causal.py         # L3 CausalReasoner + FailureChain 매칭
│       ├── causal_discovery.py # Granger 인과 + 조건부 독립성 자동 발견
│       ├── correlation.py    # CorrelationAnalyzer + CrossProcessInvestigator
│       ├── scenarios.py      # 시나리오 엔진 (장애 주입)
│       ├── sensor_simulator.py # 56 가상 센서
│       ├── advanced_detection.py # CUSUM, EWMA
│       ├── llm_orchestrator.py # Hybrid Agentic — 복잡도 기반 rule/LLM 분기
│       ├── llm_agents.py     # PredictiveAgent, NaturalLanguageDiagnoser
│       ├── llm_analyst.py    # 사이클 후 분석 LLM (배치)
│       ├── decision_layer.py # L4 정책/HITL 결정 레이어
│       ├── learning_layer.py # L5 LearningRecord 영속화
│       ├── evolution_agent.py # 자가 진화 — 8 전략 fitness 추적/변형/승격
│       ├── healing_agents.py # AnomalyDetector, RootCauseAnalyzer, AutoRecoveryAgent, ResilienceOrchestrator
│       ├── traceability.py   # ProductionBatch ↔ Incident 추적
│       ├── weibull_rul.py    # Weibull-기반 RUL 추정
│       ├── protocol_bridge.py # OPC-UA / Sparkplug B (현재 SimulatedBridge)
│       ├── event_bus.py      # 사이클 이벤트 발행
│       ├── backtest.py       # BacktestRunner — anti-recurrence 인지 replay
│       └── research_loop.py  # 전략 6종 + 자가 진화 사이클
├── web/                      # Next.js 14 + TypeScript + Tailwind CSS 프론트엔드
│   └── src/
│       ├── app/page.tsx
│       ├── types/index.ts    # 모든 인터페이스
│       ├── hooks/useHarnessEngine.ts # WebSocket + useReducer (모든 데이터 흐름)
│       ├── context/EngineContext.tsx
│       └── components/
│           ├── layout/       # Header, Sidebar, MainContent
│           ├── process/      # ProcessMap, AreaColumn, StepNode
│           ├── graph/        # 온톨로지 force-directed SVG
│           ├── issues/       # 실시간 이슈 패널
│           ├── agents/       # AgentList, TrustBar
│           ├── debate/       # DebatePanel, VoteResults
│           ├── metrics/      # MetricsBar, SidebarMetrics
│           ├── charts/       # SparklineChart, SVGLineChart, SVGBarChart
│           ├── controls/     # ControlPanel, PhaseIndicator
│           ├── preverify/    # PreverifyPanel — 시뮬레이션 게이트 + 임계값 진화
│           ├── autonomy/     # AutonomyPanel + RecurrencePanel
│           └── common/       # GlassCard, Badge, EventLog, ConnectionDot
├── data/
│   └── graph_data.json       # 원본 제조 데이터 (5 공정영역, 31 스텝)
├── results/                  # 사이클 결과 JSON (snapshot, evolution_state, causal_discovery_state, backtest_report)
├── dashboards/               # HTML 대시보드 (독립 실행)
└── .claude/skills/           # 프로젝트 스킬
    ├── harness-improve/      # 비전 정합 멀티 에이전트 개선 사이클
    └── refactor-review/      # 4관점 멀티 에이전트 리팩토링 리뷰
```

## 온톨로지 스키마 (L1-L3 통합, 현재)

### L1-L2 노드 (8종)
- `ProcessArea` — 5 공정영역 (PA-100~500)
- `ProcessStep` — 31 공정 단계 (yield_rate/oee/sigma_level/safety_level)
- `Equipment` — 설비 (mtbf_hours/mttr_hours)
- `Material` — 자재 (cost/supplier/lead_time_days)
- `QualitySpec` — 품질 규격
- `DefectMode` — 결함 모드 (severity/occurrence/detection/rpn)
- `AutomationPlan` — 자동화 계획
- `MaintenancePlan` — 정비 계획

### L3 노드 (인과 추론, `causal.py`/`causal_discovery.py`)
- `CausalRule` — 인과 규칙 (cause_type/effect_type/strength/confirmation_count)
- `AnomalyPattern` — 이상 패턴 (drift/spike/oscillation/level_shift/variance_increase)
- `FailureChain` — 과거 확인된 원인→증상 체인 (success_count/fail_count/avg_recovery_sec)
- `Incident` — 장애 이력 (id/step_id/root_cause/recovery_action/resolved/timestamp)

### L4 노드 (정책/거버넌스, `decision_layer.py`)
- `EscalationPolicy` — HITL 정책
- `RecoveryAction` — 적용된 액션 이력
- `ProductionBatch` — 트레이서빌리티 단위
- `RULEstimate` — Weibull RUL 추정

### 관계 (L1~L4 통합, 약 20종)
- 공정 흐름: `NEXT_STEP`, `FEEDS_INTO`, `PARALLEL_WITH`, `TRIGGERS_REWORK`
- 구조: `BELONGS_TO`, `USES_EQUIPMENT`, `CONSUMES`, `REQUIRES_SPEC`
- L2 확장: `HAS_DEFECT`, `PREVENTS`, `PLANNED_UPGRADE`, `HAS_MAINTENANCE`, `DEPENDS_ON`, `INSPECTS`
- L3: `CAUSES` (CausalRule→CausalRule), `HAS_CAUSE`, `HAS_PATTERN`, `MATCHED_BY` (Incident→FailureChain), `CHAIN_USES`, `PREDICTS`
- L4: `ESCALATES_TO`, `RESOLVED_BY`, `HAS_INCIDENT`, `BATCH_INCIDENT`

## 제조 도메인 컨텍스트

- **제품**: EV 배터리팩 (96셀 파우치, 리튬이온)
- **5대 공정영역**: 셀 어셈블리(PA-100) → 전장 조립(PA-200) → 냉각 시스템(PA-300) → 인클로저(PA-400) → 최합조립/검사(PA-500)
- **주요 병목**: 와이어 하네스 제작(PS-203, 수율 0.98), 표면 처리/코팅(PS-404, 수율 0.988)
- **핵심 자재**: 리튬이온 파우치 셀(SK On), BMS PCB(LG이노텍), 쿨링 플레이트(삼성SDI)
- **안전 등급**: A(위험-고전압/레이저), B(주의), C(일반) — PRE-VERIFY 임계가 등급별로 다름

## 개발시 유의사항

### 온톨로지 확장
- 새 노드/관계 추가 전 기존 타입으로 표현 가능한지 검토
- 관계명은 동사형으로 의미 명확하게 (`RELATED_TO` 같은 모호한 관계 금지)
- 속성은 정량적 (측정 가능한 값)
- VISION.md의 L1~L4 구조에 맞춰 확장

### 하네스 루프 확장
- **반드시 측정→분석→개선→검증** 사이클 준수 (`/harness-improve` 스킬 사용 권장)
- 수렴 조건 명확히 정의 (v2 기준: 개선률 0.3%p 이하시 종료)
- 결과는 JSON으로 기록 (`results/`)
- 이전 버전과의 비교 메트릭 포함
- 회귀 가드: 변경 전후 backtest 실행 (`scripts/backtest.py`)

### 자율 복구 시스템 확장 (v4)
- 페이즈 로직은 `src/v4/phases/`에 분리. `engine.py`는 오케스트레이션만.
- 상태 영속화는 `_engine_state.py`로 일원화 (snapshot에 preverify/recurrence/phase4 모두 포함)
- HITL 정책 변경은 `_engine_hitl.py`에 한정
- anti-recurrence 정책 변경은 `recurrence.py`만 수정 (production·replay 모두 동기)

### 에이전트 개발
- 단일 책임 원칙: 한 에이전트 = 한 역할
- 판단은 온톨로지 쿼리 기반 (하드코딩 금지)
- 모든 행동/결과는 온톨로지에 기록
- 판단 불가시 에스컬레이션 (상위 에이전트 또는 사람)

### 그래프 DB
- Kuzu (임베디드)
- Cypher 쿼리 (`conn.execute()`)
- DB 경로 설정 가능하게 (하드코딩 금지)
- 스키마 확장은 `try: ... except: pass`로 idempotent하게 (`extend_schema_*` 패턴)

## v3 멀티 에이전트 토론 시스템 (온톨로지 개선)

### 7단계 루프 프로토콜
`OBSERVE → PROPOSE → DEBATE(비평+투표) → APPLY → EVALUATE → LEARN`

### 에이전트 6종 (`src/v3/agents.py`)
| 에이전트 | 역할 | 주요 스킬 |
|---|---|---|
| ProcessAnalyst | 공정 흐름/병목 | bottleneck_analysis, add_rework_link |
| QualityEngineer | FMEA/품질 | add_defect_fmea, add_quality_spec |
| MaintenanceEngineer | 설비 보전 | add_maintenance_plan |
| AutomationArchitect | 자동화/ROI | automation_upgrade, yield_improvement |
| SupplyChainAnalyst | 자재/공급망 | add_material_link |
| SafetyAuditor | 안전 위험 | safety_risk_assessment |

### 토론 프로토콜 (Moderator)
- 각 에이전트 제안 → 다른 에이전트 비평 → 전원 투표
- **신뢰도 가중 투표**: trust_score × raw_vote
- APPROVAL_THRESHOLD (2.0) 이상 → 승인, 동일 대상 중복 방지
- 한 라운드 최대 15건 적용

### 자가 학습 메커니즘
- 메트릭 개선 기여 → 신뢰도 +0.05
- 개선 미달 → 신뢰도 -0.03
- 신뢰도 범위: 0.1 ~ 2.0

### 새 에이전트/스킬 추가 방법
1. `src/v3/agents.py`에 `BaseAgent` 상속
2. `observe()`, `propose()`, `critique()`, `vote()` 구현
3. `create_agents()`에 등록
4. 필요시 `src/v3/skills.py`에 스킬 추가 후 `create_skill_registry()` 등록

## v4 자율 복구 + L4 Tier 2 모듈

### 핵심 모듈
- **CausalReasoner** (`causal.py`): 인과 그래프 역추적 RCA + FailureChain 매칭. base/causal/history/pattern 점수 합산.
- **CausalDiscoveryEngine** (`causal_discovery.py`): Granger F-test + 조건부 독립성 가지치기로 센서 데이터에서 인과 자동 발견. 7 이터레이션마다 실행. CR-DISC-* ID로 CausalRule 자동 승격.
- **EvolutionAgent** (`evolution_agent.py`): 8 전략(anomaly_threshold_tuning, causal_rule_derivation, correlation_expansion, playbook_optimization, scenario_difficulty, causal_strength_calibration, causal_discovery, preverify_threshold_tuning) fitness 추적 + 가우시안 변형 + 승격/쿨다운. 5 이터레이션마다 실행.
- **LLMOrchestrator** (`llm_orchestrator.py`): Hybrid Agentic — 복잡도 기반 rule/LLM 분기. Anthropic + OpenAI 지원. 오프라인 모드 폴백.
- **PreverifyPanel** (frontend): 시뮬레이션 게이트 + 진화하는 안전등급별 임계값 + 예측 정확도(sign_acc/MAE) 가시화.

### Anti-recurrence 정책 (`recurrence.py`)
- 시그니처: `(step_id, anomaly_type, top_cause)`
- `RECUR_DEMOTE_AT = 2`: 같은 시그니처 2회 이상 발생 시 시도된 액션 후순위
- `RECUR_ESCALATE_AT = 3`: 3회 이상 + 모든 후보 소진 시 ESCALATE 강제
- production(`learn.py`), replay(`backtest.py`), preverify(`preverify.py`) 모두 동일 헬퍼 사용

## 개발 환경 실행

```bash
./run.sh dev      # 백엔드(8080) + Next.js(3000) 동시 시작 (개발 표준)
./run.sh live     # 백엔드만 (HTML 대시보드 포함)
./run.sh v3       # 배치 하네스 v3 실행 (CLI 결과 출력)
```

**개발 시 항상 백엔드+프론트엔드를 동시에 띄워놓고 실시간 시뮬레이션이 가능한 상태를 유지한다.**

### 회귀 검증 (PR 전 필수)
```bash
python scripts/backtest.py --snapshot results/self_healing_v4_latest.json
# decision_match_rate, ECE, Brier, drift_warnings 확인
```

## 프론트엔드 아키텍처 (web/)

- **프레임워크**: Next.js 14 + TypeScript (strict) + Tailwind CSS
- **상태 관리**: useReducer + React Context (외부 라이브러리 없음)
- **실시간 연동**: WebSocket (`ws://localhost:8080/ws`) + 20+ 이벤트 타입
- **차트**: 커스텀 SVG 컴포넌트 (외부 차트 라이브러리 없음)
- **디자인**: 다크 테마, 글래스모피즘, 네온 액센트

### 핵심 파일
- `web/src/hooks/useHarnessEngine.ts` — WebSocket 연결 + 상태 리듀서 (모든 데이터 흐름의 중심)
- `web/src/hooks/reducers.ts` — 이벤트별 리듀서
- `web/src/context/EngineContext.tsx` — React Context Provider
- `web/src/types/index.ts` — 모든 TypeScript 인터페이스
- `web/src/components/process/ProcessMap.tsx` — 5 영역 공정 시각화
- `web/src/components/preverify/PreverifyPanel.tsx` — PRE-VERIFY 게이트/임계값/예측 정확도

### 프론트엔드 컴포넌트 추가 방법
1. `web/src/components/` 하위에 디렉토리·컴포넌트 파일 생성
2. `'use client'` 디렉티브 추가
3. `useEngine()` 훅으로 엔진 상태 접근
4. Tailwind CSS + `glass` 유틸리티 클래스
5. 새 WebSocket 이벤트는 `hooks/reducers.ts`에 핸들러 추가 + `types/index.ts`에 인터페이스

## 프로젝트 스킬 (`.claude/skills/`)

### `/harness-improve` — 비전 정합 개선 사이클
한 사이클 측정→분석→제안→구현→검증을 멀티 에이전트로 수행. VISION.md GAP을 자동 식별하고 단일 작은 변화를 적용.

### `/refactor-review` — 4관점 리팩토링 리뷰
code-reviewer / silent-failure-hunter / code-simplifier / type-design-analyzer 4 에이전트 병렬 spawn → 합의 우선순위 → P0 1개만 즉시 실행.

## 다크 팩토리 로드맵

현재: **L3 자율 공장 + L4 Tier 2** — `ARCHITECTURE.md` §17, `VISION.md` §6 참조.

### 미구현 / 다음 사이클 후보 (`ARCHITECTURE.md` §18)
1. **Backtest CI gate (높음)**: GitHub Actions PR 게이트 자동화
2. **Multi-step PRE-VERIFY (중간)**: 단일 액션 → 액션 시퀀스 lookahead
3. **Counterfactual replay (중간)**: "안 했다면?" 가상 yield 추정
4. **Threshold sparkline (낮음)**: 안전등급별 임계값 진화 시각화
5. **Real OPC-UA (중간)**: SimulatedBridge → asyncua.Client + Sparkplug B
6. **Transformer RUL (낮음)**: Weibull → LSTM/Transformer (라벨 데이터 확보 후)
7. **NL-to-Cypher 진단**: LLMOrchestrator scaffolding 완료, 가드레일 추가 필요

### 학술 근거
- KG-Driven Fault Diagnosis (Sensors, 2025)
- CausalTrace: Neurosymbolic Causal Analysis (arXiv, 2025)
- Causal AI for Manufacturing RCA (Databricks, 2025)
- Self-evolving agents (NAMRC 2026)
- FD-LLM (자연어 진단)
