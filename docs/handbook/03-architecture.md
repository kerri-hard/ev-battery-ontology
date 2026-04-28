# Ch.03 Architecture — 시스템 토폴로지

← [02. Quick Start](./02-quickstart.md) | [목차](./00-toc.md) | 다음 → [04. Ontology](./04-ontology.md)

---

이 챕터는 [`ARCHITECTURE.md`](../../ARCHITECTURE.md)의 신규 개발자용 다이제스트입니다. 모듈 단위 정확한 라인까지는 ARCHITECTURE.md를 진실로 삼고, 본 챕터는 *전체 그림*을 빠르게 이해하기 위한 것입니다.

---

## 3.1 4-Layer 토폴로지

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend  (Next.js 14 + TypeScript + Tailwind)                  │
│  web/  — 6 pages, useReducer + Context, custom SVG charts        │
└─────────────────────────────▲────────────────────────────────────┘
                              │ WebSocket (20+ event types) + REST
┌─────────────────────────────┴────────────────────────────────────┐
│  Backend  (FastAPI + uvicorn)                                    │
│  server.py  — REST 엔드포인트 + WebSocket 브로드캐스트            │
└─────────────────────────────▲────────────────────────────────────┘
                              │ in-process call
┌─────────────────────────────┴────────────────────────────────────┐
│  Engine  (Python — 자율 복구 두뇌)                                │
│  src/v4/engine.py  + phases/* + healing/* + research/*            │
└─────────────────────────────▲────────────────────────────────────┘
                              │ Cypher (kuzu 임베디드)
┌─────────────────────────────┴────────────────────────────────────┐
│  Graph DB (Kuzu) — 온톨로지/인과/이력                              │
│  L1 도메인 + L2 확장 + L3 인과 + L4 거버넌스                       │
└──────────────────────────────────────────────────────────────────┘
```

세부 모듈 맵: [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §4.

---

## 3.2 데이터 흐름 — 1 사이클

`SelfHealingEngine.run_cycle()` 한 호출이 일으키는 일:

```
[가상 센서 56개]
    ↓ sense.py
[reading 수집 + scenario 활성화]
    ↓ detect.py (SPC + Western Electric + CUSUM/EWMA)
[Anomaly events]
    ↓ diagnose.py (causal 역추적 + LLM 보강)
[RCA top-K 후보]
    ↓ preverify.py (시뮬 게이트 + anti-recurrence)
[검증된 RecoveryAction]
    ↓ recover.py (HITL 정책 + 실 적용)
[적용 결과]
    ↓ verify.py (yield/OEE 사후 측정)
[VERIFY 결과 + 예측 정확도]
    ↓ learn.py (Incident 영속화 + L3 강화)
[온톨로지 업데이트]
    ↓ event_bus.py
[WebSocket → Frontend toast/incident card]
```

각 페이즈는 단일 `.py` 파일이며 모두 `engine.py`가 오케스트레이션. 페이즈는 자세히 [Ch.05](./05-7phase-loop.md)에서.

---

## 3.3 핵심 모듈 맵

### 백엔드 (`src/`)

```
src/
├── v3/            # 멀티 에이전트 토론 시스템 (온톨로지 자체 개선)
│   ├── agents.py    # 6 에이전트 + Moderator
│   ├── skills.py    # 14 스킬
│   ├── harness.py   # 배치 루프
│   └── engine.py    # 실시간 엔진 (WebSocket)
└── v4/            # 자율 복구 + L3-L4 (운영)
    ├── engine.py            # 7-페이즈 오케스트레이션
    ├── _engine_state.py     # snapshot 영속화 + SLO 계산
    ├── _engine_hitl.py      # HITL 정책 게이트
    ├── phases/              # SENSE/DETECT/DIAGNOSE/PREVERIFY/RECOVER/VERIFY/LEARN
    ├── healing/             # detector, rca, recovery, playbook, orchestrator
    ├── analyst/             # LLM analyst (client/cache/prompts/scoring)
    ├── research/            # 전략 탐색 시뮬레이션
    ├── recurrence.py        # anti-recurrence 단일 진실 소스
    ├── causal.py            # CausalReasoner + FailureChain 매칭
    ├── causal_discovery.py  # Granger 인과 자동 발견
    ├── correlation.py       # 상관 분석 + cross-process 조사
    ├── scenarios.py         # 20 가상 시나리오 + 가중 랜덤
    ├── sensor_simulator.py  # 56 가상 센서
    ├── advanced_detection.py # CUSUM, EWMA
    ├── llm_orchestrator.py  # Hybrid Agentic
    ├── llm_agents.py        # PredictiveAgent, NaturalLanguageDiagnoser
    ├── llm_analyst.py       # 사이클 후 분석
    ├── decision_layer.py    # L4 정책/HITL 결정
    ├── learning_layer.py    # L5 LearningRecord
    ├── evolution_agent.py   # 자가 진화 8 전략
    ├── healing_agents.py    # 회복탄력성 4 에이전트
    ├── traceability.py      # ProductionBatch ↔ Incident
    ├── weibull_rul.py       # Weibull RUL 추정
    ├── protocol_bridge.py   # OPC-UA / Sparkplug B
    ├── event_bus.py         # 사이클 이벤트 발행
    ├── backtest.py          # 회귀 가드 replay
    └── research_loop.py     # 전략 6종 + 자가 진화
```

### 프론트엔드 (`web/`)

```
web/src/
├── app/page.tsx                 # 6 view dispatch
├── types/index.ts               # 모든 TypeScript 인터페이스
├── hooks/useHarnessEngine.ts    # WebSocket + useReducer (모든 데이터 흐름의 중심)
├── hooks/reducers.ts            # 이벤트별 리듀서
├── context/EngineContext.tsx    # Provider
└── components/
    ├── layout/        # Header, Sidebar, MainContent, PageIntent
    ├── overview/      # TodayHeadline, ...
    ├── process/       # ProcessMap, AreaColumn, StepNode
    ├── graph/         # 온톨로지 force-directed SVG
    ├── issues/        # 실시간 incident
    ├── debate/        # v3 토론 패널
    ├── slo/           # SLOKpiRibbon, IncidentFlowPanel, SelectedIncidentCard
    ├── learning/      # EvolutionTimeline, FailureChainExplorer, CausalChainTracer
    ├── preverify/     # PreverifyPanel + ThresholdSparklines
    ├── autonomy/      # AutonomyPanel + RecurrencePanel
    ├── scenarios/     # ScenarioPicker, ActiveScenarioPanel
    ├── settings/      # SettingsView (HITL 정책 편집)
    └── common/        # GlassCard, Badge, NotificationCenter, severityColors
```

---

## 3.4 통신 채널

### WebSocket 이벤트 (실시간)

`server.py` → `useHarnessEngine.ts` 리듀서가 처리하는 20+ 이벤트:

| 이벤트 | 용도 |
|---|---|
| `cycle_started` / `cycle_done` | 사이클 진행 |
| `phase_started` | 페이즈 진입 (UI에서 어떤 페이즈인지 강조) |
| `incident_detected` / `incident_resolved` | DETECT/VERIFY 결과 |
| `preverify_result` | 시뮬 게이트 통과/거절 |
| `hitl_required` / `hitl_decision` | A 등급 액션 |
| `slo_violation` | SLI 임계 초과 |
| `evolution_cycle` | 진화 전략 적용 |
| `causal_discovered` | 새 CausalRule |
| `metrics_update` | yield/OEE 갱신 |

### REST 엔드포인트 (요청-응답)

| 엔드포인트 | 메서드 | 용도 |
|---|---|---|
| `/api/heal` | POST | 사이클 한 번 강제 실행 |
| `/api/snapshot` | GET | 최신 state JSON |
| `/api/active-scenarios` | GET | 활성 시나리오 + library_stats |
| `/api/scenarios/library` | GET | 20 시나리오 카탈로그 |
| `/api/scenarios/trigger` | POST | 강제 활성화 |
| `/api/hitl/policy` | GET/POST | HITL 정책 조회/갱신 |

상세는 `server.py` 참고.

---

## 3.5 영속화

세 종류의 영속 저장소:

| 저장소 | 용도 | 위치 |
|---|---|---|
| **Kuzu (임베디드 그래프 DB)** | 온톨로지, 인과, Incident | DB 경로 환경변수 |
| **JSON snapshot** | 페이즈 상태, SLI 시계열, 진화 이력 | `results/self_healing_v4_latest.json` |
| **In-memory (`_engine_state.py`)** | 실시간 ring buffer (preverify thresholds 60 iter) | 프로세스 내 |

snapshot은 [`_engine_state.py`](../../src/v4/_engine_state.py)의 `snapshot()` 메서드에 의해 매 사이클 갱신. 백테스트가 이 파일을 replay.

---

## 3.6 인터페이스 경계 (변경 시 주의)

다음 경계를 변경하려면 양쪽 모두 동기 수정 필요:

| 경계 | 백엔드 측 | 프론트엔드 측 |
|---|---|---|
| WebSocket 이벤트 | `event_bus.py` | `hooks/reducers.ts` + `types/index.ts` |
| REST 응답 형태 | `server.py` | `lib/api.ts` + 타입 |
| Snapshot JSON | `_engine_state.py:snapshot()` | `backtest.py` replay |
| HITL 정책 | `_engine_hitl.py` | `SettingsView.tsx` |
| anti-recurrence | `recurrence.py` (단일 진실) | (백엔드만) |

---

## 3.7 외부 의존성 / 통합 지점

- **Kuzu** — 임베디드, 그래프 DB
- **scipy / numpy** — Granger F-test, CUSUM, EWMA
- **Anthropic / OpenAI SDK** — LLM 보강 (선택)
- **asyncua** — OPC-UA 클라이언트 (선택, 실 PLC 연결용)
- **Sparkplug B** — Eclipse Tahu (선택)

LLM/OPC-UA 모두 *graceful fallback* — 라이브러리 없거나 서버 없으면 시뮬레이션 모드로 동작.

---

## 3.8 다음 → 그래프 스키마

이제 위에서 자주 언급된 *온톨로지 그래프* 가 정확히 어떤 노드/관계를 가지는지 [Ch.04 Ontology](./04-ontology.md)에서 봅니다.

---

← [02. Quick Start](./02-quickstart.md) | [목차](./00-toc.md) | 다음 → [04. Ontology](./04-ontology.md)
