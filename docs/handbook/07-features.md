# Ch.07 Features — 6 페이지 기능 카탈로그

← [06. Agents & Skills](./06-agents-skills.md) | [목차](./00-toc.md) | 다음 → [08. SLO · Evolution · Recurrence](./08-slo-evolution-recurrence.md)

---

이 챕터는 운영자가 브라우저에서 보는 모든 화면의 **기능 카탈로그**입니다. 페이지마다 *한 질문*과 *드릴다운 동선*을 명시.

---

## 7.1 페이지 정체성 (PageIntent)

각 페이지는 한 질문에 답합니다. 사이드바 nav 클릭 시 상단 PageIntent가 그 질문을 보여줌:

| 페이지 | 한 질문 | 핵심 |
|---|---|---|
| 🏠 **Overview** | 지금 어떻게 돌아가는가? | 시스템 전체 한눈 |
| 🛡 **Healing** | 이 incident는 누가, 어떻게 잡고 있는가? | Detect → Diagnose → Heal 풀 라이프사이클 |
| 📊 **SLO** | 어떤 약속이 깨지고 있는가? | 5 SLI · 31 step microservice · error budget |
| 🧠 **Learning** | 어제와 무엇이 달라졌는가? | 8 전략 진화 · FailureChain · 자가 보정 |
| 🖥 **Console** | 원본 데이터 그대로 보여줘 | Raw observability — 디버그 채널 |
| ⚙ **Settings** | 시스템을 어떻게 조정할까? | HITL 정책 · 단축키 · 시스템 정보 |

키보드 단축키: `g o`/`g h`/`g s`/`g l`/`g c` ([Ch.02](./02-quickstart.md)).

---

## 7.2 사이드바 (모든 페이지 공통)

좌측 240px 고정 너비. 다음 5 영역을 위→아래 배치:

1. **페이지 네비** — 6 메뉴 + 단축키 힌트
2. **Control Panel** — Sim 시작/정지/속도
3. **Sim Control (ScenarioPicker)** — 시나리오 강제 trigger
4. **Sidebar Metrics** — yield/OEE/incident count 요약
5. **Agent List** — v3 에이전트 trust bar

상단 Header는 SystemStatusPill (5초 룰 신호등): `● 모든 SLO 충족` / `⚠ N건 위반` / `🔴 주의` — 클릭 시 SLO 페이지로 이동.

---

## 7.3 페이지 1 — Overview 🏠

**진입 시 첫 화면 옵션** (Healing이 디폴트지만 "전체 한눈"이 필요하면 여기).

| 컴포넌트 | 무엇을 보여주는가 | 드릴다운 |
|---|---|---|
| **TodayHeadline** | 24h narrative — "✓ N/M 자동복구 · MTTR · 🟢 모든 SLO 충족" | 4 KPI 클릭 → Healing/SLO/Learning |
| **ActiveScenarioPanel** | 현재 활성 시나리오 + library_stats | 클릭 → Healing + scenarioId tracking |
| **MetricsBar** | yield, OEE, incident count, hitl_pending | 클릭 → 해당 페이지 |

---

## 7.4 페이지 2 — Healing 🛡 (디폴트)

**가장 큰 페이지** — 12-column grid:

```
col-span-9 (왼쪽 큰 영역)         col-span-3 (오른쪽 스택)
┌─────────────────────────────┐  ┌──────────────────┐
│ OntologyGraph (force SVG)   │  │ Detect 패널      │
│ — L3 인과 chain overlay     │  │ Heal 패널        │
└─────────────────────────────┘  │ Preverify 패널   │
                                  └──────────────────┘
```

### Healing 컴포넌트 카탈로그

| 컴포넌트 | 핵심 |
|---|---|
| **OntologyGraph** | force-directed SVG. 노드/관계 hover, CausalChain overlay |
| **IncidentFlowPanel** | 7-페이즈 swim-lane. severity 필터 + ×N recurrence 표시 |
| **SelectedIncidentCard** | 5-섹션 워크벤치 (Detect/Diagnose/PreVerify/Recover/Verify+Learn) + HITL Approve/Reject inline |
| **PreverifyPanel** | 시뮬 게이트 + 안전등급별 임계값 sparkline + 예측 정확도(sign_acc/MAE) |
| **DebatePanel** | v3 에이전트 토론 진행 상황 (해당 사이클일 때만) |
| **HitlPanel** | 대기 중 HITL incident 목록 — 카드 클릭 → SelectedIncidentCard |

### 드릴다운 동선

```
incident 발생 토스트 알림
    ↓ 클릭
Healing 페이지 + selectedIncidentId 자동 set
    ↓ SelectedIncidentCard 자동 강조
5 섹션 워크벤치 + HITL Approve/Reject inline
```

---

## 7.5 페이지 3 — SLO 📊

**SRE-style 측정 페이지**. 31 step을 *마이크로서비스*로 보고 SLO 계산.

| 컴포넌트 | 무엇 |
|---|---|
| **SLOKpiRibbon** | 5 SLI 칩 (auto_recovery_rate / p95_recovery / yield_compliance / hitl_rate / repeat_rate) + error budget gauge |
| **SLOSparklines** | SLI 시계열 + burn rate |
| **SLODefinitions** | SLI 카탈로그 + 선택된 SLI 강조 + auto-scroll |
| **SLOViolationAlert** | 현재 위반 알림 + affected_steps 클릭 → 해당 step Healing |
| **MicroservicePanel** | per-step SLI bar (31 step 가로 정렬) |
| **IncidentFlowPanel** | (Healing과 같은 컴포넌트지만 SLO에서는 SLI 위반 incident만 강조) |

### 5 SLI 정의 (코드 진실)

| SLI | 식 | target | higher_is_better |
|---|---|---|---|
| `auto_recovery_rate` | auto_recovered / total_incidents | 0.95 | ✓ |
| `p95_recovery_latency` | recovery_time_sec p95 | 0.05s | ✗ |
| `yield_compliance` | yield_rate ≥ 0.99 인 step 비율 | 0.95 | ✓ |
| `hitl_rate` | hitl_required / total_incidents | 0.05 | ✗ |
| `repeat_rate` | 동일 시그니처 재발 / total | 0.25 | ✗ |

진실 출처: [`src/v4/_engine_state.py:SLO_TARGETS`](../../src/v4/_engine_state.py).

---

## 7.6 페이지 4 — Learning 🧠

**자가 학습/진화 가시화** 페이지.

| 컴포넌트 | 무엇 |
|---|---|
| **EvolutionTimeline** | 8 진화 전략 fitness sparkline ([Ch.08](./08-slo-evolution-recurrence.md) 참조) |
| **FailureChainExplorer** | anti-recurrence 시그니처 카탈로그. 클릭 → Healing |
| **CausalChainTracer** | L3 multi-hop 인과 chain 자동 추출. 결함 → 원인 → 원인의 원인 traversal |
| **PreverifyPanel** | (재사용) 예측 정확도가 학습이므로 여기에도 표시 |

### CausalChainTracer 사용

특정 incident에서 시작 → 인과 chain을 따라 root cause까지 도식. 각 단계의 CausalRule.strength 가시화.

---

## 7.7 페이지 5 — Console 🖥

**Raw observability** — 디버그/검증용.

- WebSocket 이벤트 raw 로그 (스크롤)
- HITL 대기 incident 목록 (Healing보다 단순화)
- 마지막 N 사이클 cycle_done 이벤트 (timing 등)

운영자 워크벤치가 아니라 *개발자 도구*에 가까운 페이지. 정상 운영 중에는 거의 안 봄.

---

## 7.8 페이지 6 — Settings ⚙

**시스템 정책 편집**.

| 영역 | 무엇 |
|---|---|
| **HITL 정책** | 슬라이더로 `min_confidence`, `high_risk_threshold` 조정. `medium_requires_history` 체크박스. ✓ 적용 버튼 → 실시간 반영 |
| **키보드 단축키** | `g o`/`g h`/`g s`/`g l`/`g c`/`Esc`/`?` 카탈로그 |
| **시스템 정보** | 현재 healing iter, 총 incident, 자동 복구, SLO 위반 |

HITL 정책은 [`src/v4/_engine_hitl.py`](../../src/v4/_engine_hitl.py)에 있고, 슬라이더 변경 시 `cmd: 'hitl_policy_update'` WebSocket으로 전송. 즉시 다음 사이클부터 반영.

---

## 7.9 공통 UX 패턴

### Toast 알림 (NotificationCenter)

자동으로 푸시되는 알림:

| 트리거 | 색 |
|---|---|
| HIGH/CRITICAL incident | 🔴 |
| HITL pending | 🟡 |
| SLO violation | 🟠 |

8초 자동 dismiss. 최대 5건 stack. 클릭 → navigateTo로 자동 페이지 이동.

### 드릴다운 상태

다음 4 selection이 페이지 간 보존됩니다:
- `selectedIncidentId` — Healing에서 SelectedIncidentCard 강조
- `selectedSloKey` — SLO에서 SLODefinitions ring 강조
- `selectedStepId` — Healing/SLO에서 step 강조
- `selectedScenarioId` — ActiveScenarioPanel 강조

`Esc` 키로 모두 클리어.

### EmptyState / LoadingState / ErrorState

`common/StateMessages.tsx`에 표준 컴포넌트 3종. 모든 패널이 데이터 없을 때 같은 모양 빈 상태를 보여줌.

### severityColors 단일 매핑

`common/severityColors.ts`이 severity/status/phase → Tailwind 클래스 단일 매핑. 색상 일관성 보장.

---

## 7.10 디자인 토큰 (`globals.css`)

| 토큰 | 용도 |
|---|---|
| `ds-heading` | 12px bold heading |
| `ds-label` | 10px uppercase label |
| `ds-body` | 11px 본문 |
| `ds-caption` | 9px mono caption |
| `pill-success/warning/danger/info` | 상태 알약 |
| `glass` | 글래스모피즘 카드 |
| `animate-slide-in` | toast 슬라이드 인 |

---

## 7.11 다음 → 화면 뒤의 측정/학습/방지

이 6 페이지가 *어떻게* 측정값(SLI), 진화 fitness, 재발 카운터를 만들어내는지 다음 챕터에서 한꺼번에 봅니다.

---

← [06. Agents & Skills](./06-agents-skills.md) | [목차](./00-toc.md) | 다음 → [08. SLO · Evolution · Recurrence](./08-slo-evolution-recurrence.md)
