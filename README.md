# EV Battery Manufacturing — Self-Healing Factory

제조 공정 온톨로지 + AIOps로 문제를 자동 감지/진단/복구하는 다크 팩토리 플랫폼.

> 문제가 생기면 AI가 원인을 찾고, 시뮬레이션으로 미리 검증한 뒤 스스로 복구하며, 같은 장애가 재발하지 않도록 학습한다.

**현재 단계**: L3 자율 공장 + L4 Tier 2 + 운영자 워크벤치 — 자동 인과 발견·자가 진화·Multi-step PRE-VERIFY·Counterfactual replay·OPC-UA bridge stub·5-페이지 운영 도구.

📖 [VISION.md](VISION.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [CLAUDE.md](CLAUDE.md)

## 빠른 시작

```bash
pip install -r requirements.txt
cd web && npm install && cd ..

./run.sh dev    # 백엔드(:8080) + Next.js(:3000) 동시 시작
```

http://localhost:3000 에서 온톨로지 + 자율 복구 시뮬레이션 + PRE-VERIFY 게이트 확인.

## 아키텍처

```
Browser (:3000)  ←── WebSocket ──→  FastAPI (:8080)
Next.js + TypeScript                 SelfHealingEngine (v4)
                                     ├─ v3: 6 토론 에이전트 (온톨로지 개선)
                                     ├─ v4: 7-페이즈 자율 복구 루프
                                     ├─ L3: CausalReasoner + FailureChain
                                     ├─ L4 Tier 2: EvolutionAgent + LLMOrchestrator
                                     └─ Kuzu 그래프 DB
```

## 자율 복구 루프 (7 페이즈)

```
① SENSE       56 가상 센서 reading 수집 + 시나리오 활성화
② DETECT      SPC 3-σ + Western Electric + CUSUM/EWMA
③ DIAGNOSE    인과 그래프 역추적 RCA + LLM 보강 + cross-cause
④ PRE-VERIFY  액션 가상 적용 → 안전등급별 임계로 자동 거절 + anti-recurrence
⑤ RECOVER     검증된 액션 실행 + HITL 게이트 (안전등급 A는 강제)
⑥ VERIFY      사후 yield/OEE 측정, 예측 정확도 추적
⑦ LEARN       Incident 영속화, FailureChain 갱신, recurrence_tracker 갱신
```

5 이터레이션마다 EvolutionAgent (8 전략 자가 진화), 7 이터레이션마다 CausalDiscovery (Granger).

## 운영자 대시보드 (5 페이지)

| 페이지 | 한 질문 | 핵심 컴포넌트 |
|---|---|---|
| 🏠 **Overview** | "지금 어떻게 돌아가는가?" | TodayHeadline + SLOViolationAlert + ActiveScenarioPanel |
| 🛡 **Healing** | "이 incident는 누가 잡고 있나?" | Triptych (DETECT/DIAGNOSE/HEAL) + SelectedIncidentCard (HITL inline) |
| 📊 **SLO** | "어떤 약속이 깨지나?" | SLOKpiRibbon + SLOSparklines + MicroservicePanel |
| 🧠 **Learning** | "어제와 무엇이 달라졌나?" | EvolutionTimeline + CausalChainTracer + FailureChainExplorer |
| 🖥 **Console** | "원본 데이터 그대로" | EventLog (필터/검색) + IncidentAnalysis |

**전역**:
- Header SystemStatusPill — ● 안전 / ⚠ 위반 / 🔴 주의 (5초 룰)
- Sidebar Sim Control — 20 시나리오 강제 트리거 + 활성화 카운트
- NotificationCenter — Toast 알림 (HIGH/CRITICAL incident, HITL, SLO 위반)
- Drill-down — selectedIncidentId/SloKey/StepId/ScenarioId 4 axes 동기

## CI/CD

```yaml
# .github/workflows/backtest.yml — PR/main push 자동 트리거
- 10-iter sim seed
- backtest run + threshold guard:
  · decision_match >= 0.55
  · brier <= 0.10
  · ECE <= 0.30
  · drift_warnings <= 5
- 위반 시 exit 1 → CI 차단
```

## 프로젝트 구조

```
├── server.py              # FastAPI (REST + WebSocket)
├── scripts/
│   └── backtest.py        # snapshot replay 회귀 게이트
├── src/
│   ├── v3/                # 멀티 에이전트 토론 (6 에이전트, 14 스킬)
│   └── v4/                # 자율 복구 + L3-L4
│       ├── engine.py            # 7-페이즈 오케스트레이션
│       ├── phases/              # SENSE/DETECT/DIAGNOSE/PREVERIFY/RECOVER/VERIFY/LEARN/PERIODIC
│       ├── healing/             # detector, rca, recovery, playbook, orchestrator
│       ├── analyst/             # LLM 분석 + 캐싱/스코어링/폴백
│       ├── research/            # research_loop 시뮬레이션·전략 탐색
│       ├── recurrence.py        # anti-recurrence 정책 단일 진실 소스
│       ├── causal.py            # L3 CausalReasoner + FailureChain
│       ├── causal_discovery.py  # Granger 인과 자동 발견
│       ├── evolution_agent.py   # 자가 진화 (8 전략 fitness)
│       ├── llm_orchestrator.py  # Hybrid Agentic (rule/LLM 분기)
│       ├── llm_agents.py        # PredictiveAgent, NL Diagnoser
│       ├── decision_layer.py    # L4 정책/HITL
│       ├── traceability.py      # ProductionBatch ↔ Incident
│       ├── weibull_rul.py       # Weibull RUL 추정
│       ├── protocol_bridge.py   # OPC-UA / Sparkplug B 브리지 (현재 SimulatedBridge)
│       └── backtest.py          # anti-recurrence 인지 replay
├── web/                   # Next.js 14 + TypeScript + Tailwind
│   └── src/components/
│       ├── process/       # 5 공정영역 ProcessMap
│       ├── graph/         # 온톨로지 force-directed SVG
│       ├── issues/        # 실시간 이슈 패널
│       ├── preverify/     # PRE-VERIFY 시뮬 게이트 + 임계값 진화
│       ├── autonomy/      # AutonomyPanel + RecurrencePanel
│       ├── agents/        # 신뢰도 시각화
│       ├── debate/        # 토론/투표 패널
│       ├── metrics/       # 메트릭 카드
│       └── controls/      # 제어판 + PhaseIndicator
├── data/graph_data.json   # 제조 데이터 (5 공정영역, 31 스텝)
├── results/               # 사이클 결과 JSON (snapshot, evolution_state, backtest_report)
└── .claude/skills/
    ├── harness-improve/   # 비전 정합 멀티 에이전트 개선 사이클
    └── refactor-review/   # 4관점 멀티 에이전트 리팩토링 리뷰
```

## 핵심 기능

| 영역 | 기술 | 모듈 |
|---|---|---|
| 온톨로지 | Kuzu 그래프 DB, L1-L4 노드/관계 통합 | `src/v3/engine.py`, `src/v4/causal.py` |
| 이상 감지 | SPC 3-σ, Western Electric, CUSUM, EWMA | `src/v4/advanced_detection.py` |
| 인과 진단 | Causal Reasoner + FailureChain 매칭 | `src/v4/causal.py` |
| 자동 인과 발견 | Granger F-test + 조건부 독립성 | `src/v4/causal_discovery.py` |
| PRE-VERIFY | 액션 가상 적용 + 안전등급별 임계 + anti-recurrence | `src/v4/phases/preverify.py`, `src/v4/recurrence.py` |
| 자가 진화 | 8 전략 fitness 추적/변형/승격 | `src/v4/evolution_agent.py` |
| Hybrid LLM | 복잡도 기반 rule/LLM 분기 (오프라인 폴백) | `src/v4/llm_orchestrator.py` |
| HITL | 안전등급 A 강제 + 정책 진화 | `src/v4/_engine_hitl.py`, `src/v4/decision_layer.py` |
| 트레이서빌리티 | ProductionBatch ↔ Incident | `src/v4/traceability.py` |
| RUL | Weibull 분포 기반 잔여 수명 | `src/v4/weibull_rul.py` |
| 회귀 게이트 | snapshot replay + drift 분류 (policy_switch / hist_demoted / force_escalate) | `scripts/backtest.py` |

## 회귀 검증

```bash
python scripts/backtest.py --snapshot results/self_healing_v4_latest.json
```

산출 메트릭:
- `decision_match_rate` — 현재 모델 top-action vs 기록된 action 일치율
- `confidence_brier` / `confidence_ece` — 캘리브레이션 (낮을수록 좋음)
- `policy_switch_rate` / `force_escalate_rate` / `historical_demoted_rate` — anti-recurrence 인지 분류
- `drift_warnings` — 정책 일치 이후 남는 진짜 회귀 (anti-recurrence 영향 제외)

## 프로젝트 스킬

```bash
/harness-improve         # 측정→분석→제안→구현→검증 한 사이클
/harness-improve [영역]   # 특정 영역만 (preverify, recurrence, evolution 등)

/refactor-review         # 4관점 멀티 에이전트 리팩토링 리뷰
/refactor-review [영역]   # 특정 디렉토리/파일
```

## 학술 근거

- KG-Driven Fault Diagnosis (Sensors, 2025)
- CausalTrace: Neurosymbolic Causal Analysis (arXiv, 2025)
- Causal AI for Manufacturing RCA (Databricks, 2025)
- Self-evolving agents (NAMRC 2026)
- FD-LLM (자연어 진단)

## 라이센스

연구·데모 목적. 상용화 시 추가 검증 필요 (특히 OPC-UA 통합 + 안전등급 A 공정).
