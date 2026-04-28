# Ch.10 Glossary — 용어집

← [09. Development](./09-development.md) | [목차](./00-toc.md)

---

이 챕터는 본 프로젝트에서 등장하는 모든 약어/용어를 한 곳에 모은 사전입니다. 한국어, 영문, 약어 어느 형태로 만나도 이 글로서리에서 한 번에 정의를 확인하세요.

표기 규약:
- **굵은 영문** = 정식 용어 또는 약어
- *이탤릭* = 동의어 / 비슷한 개념
- 🔗 = 본 책 다른 챕터로 링크

---

## A

**Anti-recurrence** *반복 방지*
같은 시그니처(step + anomaly_type + cause) incident가 반복되지 않도록 시도된 액션을 후순위로 보내는 정책. `RECUR_DEMOTE_AT=2`, `RECUR_ESCALATE_AT=3`. 단일 진실: [`src/v4/recurrence.py`](../../src/v4/recurrence.py). 🔗 [Ch.08](./08-slo-evolution-recurrence.md)

**AnomalyPattern**
이상 패턴 노드. 종류: `drift`, `spike`, `oscillation`, `level_shift`, `variance_increase`. 🔗 [Ch.04](./04-ontology.md)

**Approval threshold**
v3 토론에서 신뢰도 가중 투표 합이 2.0 이상이면 제안 승인. 🔗 [Ch.06](./06-agents-skills.md)

**asyncua**
Python OPC-UA 클라이언트 라이브러리. `protocol_bridge.py:OPCUABridge`가 sync wrapper로 사용. 라이브러리 없으면 graceful fallback.

**AutoRecoveryAgent**
v4 회복탄력성 에이전트. RECOVER 페이즈에서 액션 실행 담당. `src/v4/healing_agents.py`.

**AutomationPlan**
자동화 계획 노드. ROI, payback_months 속성. v3 `automation_upgrade` 스킬이 추가.

---

## B

**Backtest** *백테스트*
스냅샷 replay로 회귀를 검증. `scripts/backtest.py` + GitHub Actions [`backtest.yml`](../../.github/workflows/backtest.yml). 🔗 [Ch.08](./08-slo-evolution-recurrence.md)

**BMS** *Battery Management System*
배터리 관리 시스템. PA-200 전장 조립의 핵심 부품. PCB 제조사: LG이노텍 (가상).

**Brier score**
확률 예측의 평균 제곱 오차. 백테스트 게이트 임계 ≤ 0.10.

**Burn rate**
SLO error budget 소진 속도. SLOSparklines에 표시.

---

## C

**CausalChainTracer**
프론트엔드 컴포넌트. L3 multi-hop 인과 chain 자동 추출. 🔗 [Ch.07](./07-features.md)

**CausalDiscoveryEngine**
Granger F-test + 조건부 독립성으로 센서 데이터에서 인과 자동 발견. 7 iter마다 실행. 발견된 규칙은 `CR-DISC-*` ID로 `CausalRule` 자동 승격. `src/v4/causal_discovery.py`.

**CausalReasoner**
인과 그래프 역추적 RCA. base/causal/history/pattern 점수 합산. `src/v4/causal.py`.

**CausalRule**
L3 인과 규칙 노드. cause_type, effect_type, strength, confirmation_count 속성. 🔗 [Ch.04](./04-ontology.md)

**CausalTrace** *인과 추적*
incident에서 root cause까지 그래프 traversal로 추적. 🔗 [Ch.05](./05-7phase-loop.md), [Ch.07](./07-features.md)

**CDT** *Causal Digital Twin*
인과 디지털 트윈. PRE-VERIFY 시뮬레이션의 이론적 근거. `simulate_action()` 구현.

**Counterfactual** *반사실*
"만약 다른 액션을 골랐다면?" 질문. `action_value = chosen_delta - baseline_delta`. 백테스트가 계산. 🔗 [Ch.08](./08-slo-evolution-recurrence.md)

**CrossProcessInvestigator**
cross-step 영향 분석 보조 진단. `src/v4/correlation.py`.

**CUSUM** *Cumulative Sum*
누적합 변화 검출. `advanced_detection.py`.

**Cypher**
Kuzu DB의 쿼리 언어. Neo4j와 호환. 🔗 [Ch.04](./04-ontology.md)

---

## D

**Dark factory** *다크 팩토리*
사람이 24시간 지키지 않아도 자율 운영되는 공장. 본 프로젝트의 비전. 🔗 [Ch.01](./01-introduction.md)

**DETECT**
7-페이즈 2번. SPC 3-sigma + Western Electric + CUSUM/EWMA로 anomaly 감지. 🔗 [Ch.05](./05-7phase-loop.md)

**DIAGNOSE**
7-페이즈 3번. RCA + LLM 보강. 🔗 [Ch.05](./05-7phase-loop.md)

**DefectMode**
결함 모드 노드 (FMEA). severity, occurrence, detection, RPN 속성.

**Decision match rate**
백테스트에서 같은 입력에 같은 결정이 나오는 비율. 임계 ≥ 0.55.

**Drift warning**
데이터 분포 변화 경고. 백테스트에서 누적. 임계 ≤ 5.

**ds-heading / ds-label / ds-body / ds-caption**
디자인 토큰 (12/10/11/9 px). 🔗 [Ch.07](./07-features.md)

---

## E

**ECE** *Expected Calibration Error*
캘리브레이션 오차. 확률 예측의 신뢰도와 실제 정확도의 차이. 백테스트 임계 ≤ 0.30.

**Equipment**
설비 노드. mtbf_hours, mttr_hours 속성.

**EMA** *Exponential Moving Average*
지수 가중 이동 평균. EvolutionAgent fitness 추적, EWMA 검출에 사용.

**EngineContext**
프론트엔드 React Context. WebSocket 상태 + sendCommand + selectIncident/setView/navigateTo. `web/src/context/EngineContext.tsx`.

**EOL test** *End-of-Line test*
PA-100 셀 어셈블리의 마지막 출하 검사 단계.

**ESCALATE**
HITL 강제. anti-recurrence가 RECUR_ESCALATE_AT 도달 시 트리거.

**EscalationPolicy**
L4 노드. min_confidence, high_risk_threshold 속성.

**EvolutionAgent**
8 전략 fitness 추적 + 가우시안 변형 + 승격/쿨다운. 5 iter마다 실행. 🔗 [Ch.08](./08-slo-evolution-recurrence.md)

**EWMA** *Exponentially Weighted Moving Average*
EWMA 차트로 변화점 검출. `advanced_detection.py`.

---

## F

**FailureChain**
과거 확인된 인과 체인. success_count, fail_count, avg_recovery_sec 속성. 매칭 시 `MATCHED_BY` 관계. 🔗 [Ch.04](./04-ontology.md)

**FailureChainExplorer**
프론트엔드 컴포넌트. anti-recurrence 시그니처 카탈로그. 🔗 [Ch.07](./07-features.md)

**FastAPI**
백엔드 프레임워크. `server.py`. WebSocket + REST.

**FD-LLM** *Fault Diagnosis LLM*
자연어 진단 학술 근거. NaturalLanguageDiagnoser 구현.

**FMEA** *Failure Mode and Effects Analysis*
결함 모드 영향 분석. RPN = severity × occurrence × detection.

**Force-directed graph**
OntologyGraph 컴포넌트가 노드 위치 자동 계산하는 알고리즘. SVG 렌더.

---

## G

**Granger F-test** *그레인저 인과*
시계열 X가 Y를 예측하는 데 도움이 되는지 검정. CausalDiscoveryEngine의 핵심.

**Glassmorphism** *글래스모피즘*
반투명 + 블러 카드 디자인. `glass` 유틸리티 클래스.

---

## H

**Healing**
프론트엔드 디폴트 페이지. Detect → Diagnose → Heal 풀 라이프사이클. 🔗 [Ch.07](./07-features.md)

**HitlPanel**
HITL 대기 incident 목록 컴포넌트.

**HITL** *Human-in-the-loop*
사람 개입 게이트. 안전등급 A 액션은 항상 HITL. 정책: [`_engine_hitl.py`](../../src/v4/_engine_hitl.py).

**Hybrid Agentic**
빠른 규칙 에이전트 + 복잡 추론 LLM 분기. VISION §9.3. `LLMOrchestrator` 구현.

---

## I

**Incident**
장애 이력 노드. id, step_id, root_cause, recovery_action, resolved, timestamp 속성. 🔗 [Ch.04](./04-ontology.md)

**IncidentFlowPanel**
7-페이즈 swim-lane 컴포넌트. Healing/SLO 양쪽에서 사용.

**Idempotent**
재실행 안전. 스키마 확장은 모두 `try ... except: pass` 패턴. VISION §9.9.

---

## K

**Kuzu**
임베디드 그래프 DB. 본 프로젝트의 단일 영속 저장소 (snapshot JSON 외).

**Knowledge Graph (KG)**
지식 그래프. KG-Driven Fault Diagnosis (Sensors 2025) 학술 근거.

---

## L

**L1 / L2 / L3 / L4 / L5**
점진적 자율성 단계 (L0-L5). 또한 온톨로지 4-layer를 지칭하기도 함 (혼동 주의):
- 자율성: L0 수동 / L1 권고 / L2 반자율 / L3 자동 / L4 완전자율 / L5 학습
- 온톨로지: L1 도메인 / L2 확장 / L3 인과 / L4 거버넌스
🔗 [Ch.01](./01-introduction.md), [Ch.04](./04-ontology.md)

**LEARN**
7-페이즈 7번. Incident 영속화 + FailureChain 강화. 🔗 [Ch.05](./05-7phase-loop.md)

**LearningRecord**
L5 노드. EvolutionAgent의 변형 시도/결과 영속화. `learning_layer.py`.

**LLM** *Large Language Model*
Anthropic Claude / OpenAI GPT. Hybrid Agentic의 *복잡 추론* 측.

**LLMOrchestrator**
복잡도 기반 rule/LLM 분기. `src/v4/llm_orchestrator.py`.

---

## M

**Markov assumption**
다음 상태가 현재 상태에만 의존. Multi-step PRE-VERIFY가 사용 (이전 액션 결과 누적 무시).

**MES** *Manufacturing Execution System*
제조 실행 시스템. 본 프로젝트는 가상이지만 실 환경에서 통합 대상.

**MicroservicePanel**
SLO 페이지 컴포넌트. 31 step을 microservice로 보고 per-step SLI bar.

**Moderator**
v3 토론 진행자. observe → propose → debate → apply → evaluate → learn 루프 진행.

**MTBF** *Mean Time Between Failures*
설비 평균 무고장 시간. `Equipment.mtbf_hours`.

**MTTR** *Mean Time To Recovery*
평균 복구 시간. `Equipment.mttr_hours`.

**Multi-step PRE-VERIFY**
액션 시퀀스(최대 3 step)를 Markov 가정으로 시뮬. cumulative_success_prob, expected_delta_total 산출. `simulate_action_sequence()`. 🔗 [Ch.05](./05-7phase-loop.md)

---

## N

**NaturalLanguageDiagnoser**
LLM 기반 자연어 진단 에이전트. `src/v4/llm_agents.py`.

**Next.js 14**
프론트엔드 프레임워크. App Router + TypeScript strict + Tailwind.

**NotificationCenter**
Toast 알림 시스템. HIGH/CRITICAL incident, HITL pending, SLO violation 자동 푸시.

---

## O

**OBSERVE**
v3 토론 1단계. 모든 에이전트가 그래프 쿼리.

**OEE** *Overall Equipment Effectiveness*
설비 종합 효율 = 가용성 × 성능 × 품질. ProcessStep 속성.

**Ontology** *온톨로지*
공정 지식의 그래프 표현. VISION §9.1 "공장의 두뇌".

**OPC-UA** *Open Platform Communications Unified Architecture*
산업 자동화 표준 프로토콜. `protocol_bridge.py:OPCUABridge`로 통합.

**Overview**
프론트엔드 페이지. 24h narrative + KPI drill-down. 🔗 [Ch.07](./07-features.md)

---

## P

**p95**
95 퍼센타일. `p95_recovery_latency` SLI에서 사용.

**PA-100 ~ PA-500**
5 ProcessArea ID. 각각 셀 어셈블리/전장/냉각/인클로저/최종조립. 🔗 [Ch.01](./01-introduction.md)

**PageIntent**
페이지 정체성 헤더. 5 페이지마다 다른 한 질문 + accent color. 🔗 [Ch.07](./07-features.md)

**Periodic phase**
7-페이즈와 별개로 주기 실행 작업. CausalDiscovery (7 iter), Evolution (5 iter). `phases/periodic.py`.

**Playbook**
RECOVER 페이즈의 액션 카탈로그. EvolutionAgent의 `playbook_optimization` 전략이 우선순위 자가 보정.

**PRE-VERIFY**
7-페이즈 4번. 액션을 가상 적용해 시뮬. anti-recurrence 정책 적용. 🔗 [Ch.05](./05-7phase-loop.md)

**PreverifyPanel**
프론트엔드 컴포넌트. 시뮬 게이트 + 안전등급별 임계 sparkline + 예측 정확도. 🔗 [Ch.07](./07-features.md)

**ProcessArea**
공정영역 노드 (5종).

**ProcessStep**
공정 스텝 노드 (31종). yield_rate, oee, sigma_level, safety_level 속성.

**ProductionBatch**
L4 노드. 트레이서빌리티 단위. `BATCH_INCIDENT` 관계.

**PS-101 ~ PS-505**
ProcessStep ID 표기. PS-203 = PA-200 영역의 3번째 step (와이어 하네스).

---

## R

**RCA** *Root Cause Analysis*
근본 원인 분석. CausalReasoner.diagnose(). 🔗 [Ch.05](./05-7phase-loop.md)

**RecoveryAction**
L4 노드. 적용된 액션 이력. `RESOLVED_BY` 관계로 Incident와 연결.

**Recurrence tracker**
시그니처별 카운터. `recurrence.py:update_tracker`.

**ResilienceOrchestrator**
v4 회복탄력성 에이전트. 페이즈 간 협업 조율.

**REST**
HTTP 요청-응답 API. `server.py`의 엔드포인트들. 🔗 [Ch.03](./03-architecture.md)

**RootCauseAnalyzer**
v4 회복탄력성 에이전트. DIAGNOSE 페이즈 보조.

**RPN** *Risk Priority Number*
FMEA의 위험 우선순위 = severity × occurrence × detection.

**RUL** *Remaining Useful Life*
잔여 유효 수명. Weibull 분포로 추정. `weibull_rul.py`.

---

## S

**Safety level** *안전등급*
A (고전압/레이저, 위험) / B (주의) / C (일반). PRE-VERIFY 임계가 등급별로 다름.

**SCN-001 ~ SCN-020**
20 시나리오 ID. severity HIGH 7 / MEDIUM 7 / LOW 6.

**SCN-DISC-***
CausalDiscoveryEngine이 자동 발견한 CausalRule ID 접두.

**ScenarioPicker**
Sim Control 컴포넌트. 시나리오 강제 trigger + 활성화 카운트 표시. 🔗 [Ch.07](./07-features.md)

**SelectedIncidentCard**
Healing 페이지 5-섹션 워크벤치. HITL Approve/Reject inline.

**SENSE**
7-페이즈 1번. 56 가상 센서 reading + 시나리오 활성화. 🔗 [Ch.05](./05-7phase-loop.md)

**Sigma level**
공정 표준편차 수준. 6-sigma 가까울수록 안정. ProcessStep 속성.

**Sign accuracy**
PRE-VERIFY 예측 부호(개선/악화)가 실측과 같은 비율.

**Sim Control**
프론트엔드 시나리오 강제 trigger 패널. 사이드바 위치.

**SLI** *Service Level Indicator*
서비스 수준 지표. 5종 정의. 🔗 [Ch.08](./08-slo-evolution-recurrence.md)

**SLO** *Service Level Objective*
서비스 수준 목표. SLI의 임계값. 5 SLI 각각 target 정의됨.

**SLOKpiRibbon**
SLO 페이지 상단 5 SLI 칩 + budget gauge.

**SLOSparklines**
SLI 시계열 + burn rate 컴포넌트.

**SLO_TARGETS**
[`_engine_state.py`](../../src/v4/_engine_state.py)의 5 SLI 단일 진실 출처.

**SPC** *Statistical Process Control*
통계적 공정 관리. 3-sigma + Western Electric 룰.

**Sparkplug B**
산업 IoT 메시지 표준. Eclipse Tahu 라이브러리.

**Strategy fitness**
EvolutionAgent의 전략별 EMA 점수.

**SystemStatusPill**
헤더의 5초 룰 신호등. 클릭 시 SLO 페이지로 이동.

---

## T

**Tailwind CSS**
프론트엔드 utility-first CSS. 디자인 토큰 + pill 클래스 + glass 함께 사용.

**ThresholdSparklines**
PreverifyPanel의 A/B/C 3색 시계열. 60 iter ring buffer.

**Toast**
NotificationCenter의 알림 단위. 8초 자동 dismiss.

**TodayHeadline**
Overview 페이지 24h narrative 컴포넌트.

**Trust score**
v3 에이전트 신뢰도. 0.1 ~ 2.0. 메트릭 개선 기여 시 +0.05, 미달 시 -0.03.

---

## U

**useEngine**
프론트엔드 훅. EngineContext 접근.

**useHarnessEngine**
WebSocket 연결 + useReducer. 모든 데이터 흐름의 중심. `web/src/hooks/useHarnessEngine.ts`.

---

## V

**VERIFY**
7-페이즈 6번. 사후 yield/OEE 측정 + 예측 정확도. 🔗 [Ch.05](./05-7phase-loop.md)

**ViewKey**
프론트엔드 페이지 식별자. `'overview' | 'healing' | 'slo' | 'learning' | 'console' | 'settings'`.

**VISION**
[`VISION.md`](../../VISION.md). 다크 팩토리 5단계 로드맵 + 9 설계 철학.

---

## W

**WebSocket**
실시간 양방향 통신. `ws://localhost:8080/ws`. 20+ 이벤트 타입.

**Weibull RUL**
Weibull 분포 기반 RUL 추정. `weibull_rul.py`.

**Western Electric rules**
SPC 보조 룰 (예: 9점 같은 쪽). DETECT 페이즈에서 사용.

---

## Y

**Yield rate** *수율*
정상 산출물 비율. ProcessStep 핵심 속성. yield_compliance SLI의 기반.

---

## 한국어 → 영문 인덱스

| 한국어 | 영문 |
|---|---|
| 다크 팩토리 | Dark factory |
| 자율 복구 | Self-healing |
| 인과 추적 | Causal trace |
| 그래프 데이터베이스 | Graph DB |
| 점진적 자율성 | Progressive autonomy |
| 신뢰도 가중 투표 | Trust-weighted voting |
| 안전 등급 | Safety level |
| 시그니처 | Signature |
| 반사실 | Counterfactual |
| 임계값 | Threshold |
| 사이드바 | Sidebar |
| 패널 | Panel |
| 지수 가중 이동 평균 | EMA |
| 캘리브레이션 | Calibration |
| 가중 랜덤 | Weighted random |
| 공정영역 | ProcessArea |
| 공정 스텝 | ProcessStep |
| 결함 모드 | DefectMode |
| 인과 규칙 | CausalRule |
| 장애 이력 | Incident |
| 토론 프로토콜 | Debate protocol |
| 자가 진화 | Self-evolution |
| 자가 학습 | Self-learning |
| 회귀 가드 | Regression guard |

---

## 끝맺음

이로써 본 핸드북 10 챕터를 마칩니다. 추가 질문이나 설명이 부족한 용어는 PR로 본 챕터를 확장해 주세요.

다른 진실 출처:
- [VISION.md](../../VISION.md) — 비전과 9 원칙
- [ARCHITECTURE.md](../../ARCHITECTURE.md) — 시스템 동작/모듈 맵
- [CLAUDE.md](../../CLAUDE.md) — 개발 가이드
- [README.md](../../README.md) — 빠른 시작

---

← [09. Development](./09-development.md) | [목차](./00-toc.md)
