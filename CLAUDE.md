# EV Battery Pack 제조 AIOps 플랫폼 - 개발 가이드

## 프로젝트 개요

제조공정 온톨로지 + AIOps로 **문제 감지→자동 진단→자동 복구→학습**하는 자율 제조 시스템(다크 팩토리) 플랫폼.

**비전 문서**: `VISION.md` 참조 — 다크 팩토리 방향성, 자율 복구 루프 아키텍처, 5단계 로드맵. 개발 전 반드시 읽을 것.

## 핵심 원칙

1. **자동 복구가 목적**: 대시보드가 아니라 "사람이 안 봐도 AI가 해결하는 것"이 목표
2. **온톨로지 = 공장의 두뇌**: 모든 공정 지식, 인과관계, 장애 이력은 온톨로지에 구조화
3. **에이전트 협업**: 감지→진단→복구→검증을 전문 에이전트들이 분업
4. **실패에서 성장**: 장애/오탐/잘못된 복구를 삭제하지 않고 학습 데이터로 축적
5. **점진적 자율성**: 권고(L1) → 반자율(L2) → 자동(L3) → 완전자율(L4) 순서로 승격

## 프로젝트 구조

```
ev-battery-ontology/
├── VISION.md                 # 프로젝트 비전, 아키텍처, 로드맵
├── CLAUDE.md                 # 이 파일 — 개발 가이드 (에이전트 하네스 주입용)
├── server.py                 # FastAPI 백엔드 (WebSocket + REST API, port 8080)
├── serve.py                  # 정적 대시보드 서버
├── run.sh                    # 실행 스크립트
├── requirements.txt          # Python 의존성 (kuzu, fastapi, uvicorn)
├── src/
│   ├── harness_v3.py         # 하네스 루프 v3 엔트리포인트 (배치)
│   └── v3/                   # v3 멀티 에이전트 토론 시스템
│       ├── agents.py         # 6종 전문 에이전트 + 모더레이터
│       ├── skills.py         # 14종 스킬 레지스트리
│       ├── harness.py        # 배치 하네스 루프
│       └── engine.py         # 실시간 하네스 엔진 (WebSocket 이벤트 발행)
├── web/                      # Next.js 14 + TypeScript + Tailwind CSS 프론트엔드
│   └── src/
│       ├── app/page.tsx      # 메인 대시보드 페이지
│       ├── types/index.ts    # TypeScript 타입 정의
│       ├── hooks/            # useHarnessEngine (WebSocket + useReducer)
│       ├── context/          # EngineContext (React Context)
│       └── components/       # UI 컴포넌트
│           ├── layout/       # Header, Sidebar, MainContent
│           ├── process/      # ProcessMap, AreaColumn, StepNode (공정 시각화)
│           ├── agents/       # AgentList, TrustBar
│           ├── debate/       # DebatePanel, VoteResults, ...
│           ├── metrics/      # MetricsBar, SidebarMetrics
│           ├── charts/       # SparklineChart, SVGLineChart, SVGBarChart
│           ├── controls/     # ControlPanel, PhaseIndicator
│           └── common/       # GlassCard, Badge, EventLog, ConnectionDot
├── data/
│   └── graph_data.json       # 원본 제조 데이터 (5 공정영역, 31 스텝)
├── results/                  # 하네스 루프 실행 결과 JSON
└── dashboards/               # HTML 대시보드 (독립 실행 가능)
```

## 온톨로지 스키마 (현재 v2)

### 노드 타입 (8종)
- `ProcessArea` — 공정 영역 (셀 어셈블리, 전장 조립, 냉각 시스템, 인클로저, 최합조립/검사)
- `ProcessStep` — 개별 공정 단계 (31개, yield_rate/oee/sigma_level 포함)
- `Equipment` — 설비 (mtbf_hours/mttr_hours 포함)
- `Material` — 자재 (cost/supplier/lead_time_days 포함)
- `QualitySpec` — 품질 규격 (min/max 범위)
- `DefectMode` — 결함 모드 (severity/occurrence/detection/rpn)
- `AutomationPlan` — 자동화 계획 (from→to level, 투자비, 기대 수율 향상)
- `MaintenancePlan` — 정비 계획 (전략, 주기, 비용)

### 관계 타입 (14종)
- 공정 흐름: `NEXT_STEP`, `FEEDS_INTO`, `PARALLEL_WITH`, `TRIGGERS_REWORK`
- 구조: `BELONGS_TO`, `USES_EQUIPMENT`, `CONSUMES` (qty), `REQUIRES_SPEC`
- v2 확장: `HAS_DEFECT`, `PREVENTS`, `PLANNED_UPGRADE`, `HAS_MAINTENANCE`, `DEPENDS_ON` (dependency_type), `INSPECTS`

## 제조 도메인 컨텍스트

- **제품**: EV 배터리팩 (96셀 파우치, 리튬이온)
- **5대 공정영역**: 셀 어셈블리(PA-100) → 전장 조립(PA-200) → 냉각 시스템(PA-300) → 인클로저(PA-400) → 최합조립/검사(PA-500)
- **주요 병목**: 와이어 하네스 제작(PS-203, 수율 0.98), 표면 처리/코팅(PS-404, 수율 0.988)
- **핵심 자재**: 리튬이온 파우치 셀(SK On), BMS PCB(LG이노텍), 쿨링 플레이트(삼성SDI)
- **안전 등급**: A(위험-고전압/레이저), B(주의), C(일반)

## 개발시 유의사항

### 온톨로지 확장
- 새 노드/관계 추가 전 기존 타입으로 표현 가능한지 검토
- 관계명은 동사형으로 의미가 명확하게 (`RELATED_TO` 같은 모호한 관계 금지)
- 속성은 가능하면 정량적 (측정 가능한 값)
- `VISION.md`의 Layer 구조(L1~L4)에 맞춰 확장

### 하네스 루프 확장
- 반드시 측정→분석→개선→검증 사이클 준수
- 수렴 조건 명확히 정의 (v2 기준: 개선률 0.3% 이하시 종료)
- 결과는 JSON으로 기록 (results/ 디렉토리)
- 이전 버전과의 비교 메트릭 포함

### 에이전트 개발
- 단일 책임 원칙: 하나의 에이전트 = 하나의 역할
- 판단은 온톨로지 쿼리 기반 (하드코딩 금지)
- 모든 행동/결과는 온톨로지에 기록
- 판단 불가시 에스컬레이션 (상위 에이전트 또는 사람)

### 그래프 DB
- 현재: Kuzu (임베디드, 프로토타이핑)
- Cypher 쿼리 사용 (`conn.execute()`)
- DB 경로는 설정 가능하게 (하드코딩 금지)

## v3 멀티 에이전트 토론 시스템

### 7단계 루프 프로토콜
`OBSERVE → PROPOSE → DEBATE(비평+투표) → APPLY → EVALUATE → LEARN`

### 에이전트 6종 (src/v3/agents.py)
| 에이전트 | 역할 | 주요 스킬 |
|---------|------|----------|
| ProcessAnalyst | 공정 흐름/병목 분석 | bottleneck_analysis, add_rework_link |
| QualityEngineer | FMEA/품질기준 | add_defect_fmea, add_quality_spec |
| MaintenanceEngineer | 설비 보전 | add_maintenance_plan |
| AutomationArchitect | 자동화/ROI | automation_upgrade, yield_improvement |
| SupplyChainAnalyst | 자재/공급망 | add_material_link |
| SafetyAuditor | 안전 위험 평가 | safety_risk_assessment |

### 토론 프로토콜 (Moderator)
- 각 에이전트가 제안 (Proposal) → 다른 에이전트가 비평 (Critique) → 전원 투표 (Vote)
- 투표는 **신뢰도 가중** (trust_score × raw_vote)
- APPROVAL_THRESHOLD (2.0) 이상 → 승인, 동일 대상 중복 방지
- 한 라운드 최대 15건 적용

### 자가 학습 메커니즘
- 제안이 메트릭 개선에 기여 → 해당 에이전트 신뢰도 +0.05
- 개선 미달 → 신뢰도 -0.03
- 신뢰도 범위: 0.1 ~ 2.0 (투표 가중치에 직접 반영)

### 스킬 시스템 (src/v3/skills.py)
- **SkillRegistry**: 스킬 등록/실행/추적 (호출 횟수, 성공률, 평균 임팩트)
- 분석 스킬 5종: bottleneck_analysis, coverage_analysis, graph_metrics, cost_benefit_analysis, safety_risk_assessment
- 실행 스킬 9종: add_defect_fmea, add_quality_spec, add_material_link, automation_upgrade, add_maintenance_plan, add_inspection_link, yield_improvement, add_rework_link, cross_dependency_mapping

### 새 에이전트/스킬 추가 방법
1. `src/v3/agents.py`에 `BaseAgent` 상속 클래스 추가
2. `observe()`, `propose()`, `critique()`, `vote()` 구현
3. `create_agents()` 함수에 등록
4. 필요시 `src/v3/skills.py`에 스킬 함수 추가 후 `create_skill_registry()`에 등록

## 개발 환경 실행

```bash
./run.sh dev      # 백엔드(8080) + Next.js(3000) 동시 시작
./run.sh live     # 백엔드만 (HTML 대시보드 포함)
./run.sh v3       # 배치 하네스 실행 (CLI 결과 출력)
```

**개발 시 항상 백엔드와 프론트엔드를 동시에 띄워놓고 실시간 시뮬레이션이 가능한 상태를 유지한다.**

## 프론트엔드 아키텍처 (web/)

- **프레임워크**: Next.js 14 + TypeScript (strict) + Tailwind CSS
- **상태 관리**: useReducer + React Context (외부 라이브러리 없음)
- **실시간 연동**: WebSocket (`ws://localhost:8080/ws`) + 15+ 이벤트 타입
- **차트**: 커스텀 SVG 컴포넌트 (외부 차트 라이브러리 없음)
- **디자인**: 다크 테마, 글래스모피즘, 네온 액센트

### 핵심 파일
- `web/src/hooks/useHarnessEngine.ts` — WebSocket 연결 + 상태 리듀서 (모든 데이터 흐름의 중심)
- `web/src/context/EngineContext.tsx` — React Context Provider
- `web/src/types/index.ts` — 모든 TypeScript 인터페이스
- `web/src/components/process/ProcessMap.tsx` — 5개 영역 공정 시각화

### 프론트엔드 컴포넌트 추가 방법
1. `web/src/components/` 하위에 컴포넌트 파일 생성
2. `'use client'` 디렉티브 추가
3. `useEngine()` 훅으로 엔진 상태 접근
4. Tailwind CSS + `glass` 유틸리티로 스타일링

## 다크 팩토리 로드맵 (연구 기반)

현재: **L3 (자율 공장)** — 온톨로지 L1-L2 + 자율 복구 에이전트 구현 완료. VISION.md 참조.

### 1순위: 인과 추론 계층 (L3 온톨로지)
- CausalRule, AnomalyPattern, FailureChain 노드 추가
- CAUSES, CORRELATES_WITH, PREDICTS 관계
- CausalReasoner 에이전트 (경로 기반 → 인과관계 기반 RCA 전환)
- 근거: KG-Driven Fault Diagnosis (2025), CausalTrace (2025)

### 2순위: 장애 이력 구조화
- Incident → CausalRule → AnomalyPattern 체인으로 구조화
- 동일 장애 재발 시 패턴 매칭으로 즉시 대응
- 근거: Causal AI for Manufacturing RCA (Databricks, 2025)

### 3순위: LLM Hybrid 에이전트 통합
- LLM 오케스트레이션 + 에지 경량 에이전트 (NAMRC 2026 아키텍처)
- 자연어 쿼리로 온톨로지 진단 (FD-LLM)
- PredictiveAgent: RUL 예측 + 선제적 정비

### 4순위: 디지털 트윈 + 자가 진화
- Cognitive Digital Twin 완성
- EvolutionAgent: 에이전트 전략 자체를 변형/테스트/승격
- 다공장 연합 온톨로지
