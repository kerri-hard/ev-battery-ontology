# Ch.06 Agents & Skills — 협업 프로토콜

← [05. 7-Phase Loop](./05-7phase-loop.md) | [목차](./00-toc.md) | 다음 → [07. Features](./07-features.md)

---

## 6.1 두 종류의 에이전트

본 시스템에는 **두 갈래**의 에이전트가 공존합니다.

| 갈래 | 어디 | 무엇 | 트리거 |
|---|---|---|---|
| **v3 토론 에이전트** | `src/v3/agents.py` | 온톨로지 자체를 *빌드/개선* | `./run.sh v3` 또는 실시간 엔진 |
| **v4 회복탄력성 에이전트** | `src/v4/healing_agents.py` | 운영 중 *자율 복구* 분업 | 7-페이즈 루프 |

이 챕터는 두 갈래 모두 다룹니다.

---

## 6.2 v3 — 6 토론 에이전트

### 6.2.1 에이전트 명단

| 에이전트 | 역할 | 주요 스킬 |
|---|---|---|
| **ProcessAnalyst** | 공정 흐름/병목 분석 | `bottleneck_analysis`, `add_rework_link`, `cross_dependency_mapping` |
| **QualityEngineer** | FMEA/품질 사양 | `add_defect_fmea`, `add_quality_spec`, `add_inspection_link` |
| **MaintenanceEngineer** | 설비 보전 계획 | `add_maintenance_plan` |
| **AutomationArchitect** | 자동화 ROI/수율 개선 | `automation_upgrade`, `yield_improvement` |
| **SupplyChainAnalyst** | 자재/공급망 의존 | `add_material_link` |
| **SafetyAuditor** | 안전 위험 평가 | `safety_risk_assessment` |

각 에이전트는 `BaseAgent`를 상속하며 다음 4 메서드를 구현합니다:

```python
class BaseAgent:
    def observe(self, conn) -> dict        # 그래프 상태 관찰
    def propose(self, observation) -> list # 제안 생성 (Proposal 리스트)
    def critique(self, proposal) -> dict   # 다른 에이전트 제안 비평
    def vote(self, proposal) -> float      # 찬반 점수 (-1 ~ 1)
```

### 6.2.2 토론 프로토콜 (7-단계)

```
OBSERVE → PROPOSE → DEBATE(비평+투표) → APPLY → EVALUATE → LEARN
```

`Moderator`가 진행:

1. **OBSERVE**: 모든 에이전트가 현재 그래프를 쿼리해 관찰 dict 생성
2. **PROPOSE**: 각 에이전트가 자기 영역 개선안 제안 (Proposal 객체)
3. **DEBATE**: 다른 에이전트들이 비평 + 투표
4. **신뢰도 가중**: `weighted_vote = trust_score × raw_vote`
5. **APPROVAL_THRESHOLD (2.0) 이상** → 승인. 한 라운드 최대 15건
6. **APPLY**: 승인된 Proposal을 실제 스킬 호출로 그래프에 적용
7. **EVALUATE**: 메트릭 변화 측정 (yield, sigma, RPN, ...)
8. **LEARN**: 메트릭 개선 → trust +0.05, 미달 → -0.03 (range 0.1 ~ 2.0)

### 6.2.3 자가 학습 (trust score)

```python
if proposed_metric_improved:
    agent.trust_score += 0.05
else:
    agent.trust_score -= 0.03
agent.trust_score = clip(agent.trust_score, 0.1, 2.0)
```

trust_score 시계열은 프론트엔드 `AgentList` 컴포넌트의 TrustBar로 시각화됩니다.

---

## 6.3 14 스킬 카탈로그

스킬은 그래프를 *수정*하는 함수. 모두 `(conn, params, counters)` 시그니처. 등록은 `create_skill_registry()`.

| 스킬 | 카테고리 | 효과 |
|---|---|---|
| `bottleneck_analysis` | 분석 | 병목 step 식별 |
| `coverage_analysis` | 분석 | 스키마 커버리지 |
| `graph_metrics` | 분석 | 노드/관계 통계 |
| `cross_dependency_mapping` | 분석 | step 간 의존 |
| `cost_benefit_analysis` | 분석 | 비용/효익 평가 |
| `add_defect_fmea` | 실행 | DefectMode 추가 + RPN |
| `add_quality_spec` | 실행 | QualitySpec + REQUIRES_SPEC |
| `add_material_link` | 실행 | Material + DEPENDS_ON |
| `automation_upgrade` | 실행 | AutomationPlan + PLANNED_UPGRADE |
| `add_maintenance_plan` | 실행 | MaintenancePlan + HAS_MAINTENANCE |
| `add_inspection_link` | 실행 | INSPECTS 관계 |
| `yield_improvement` | 실행 | yield_rate 개선 (검증된 액션) |
| `add_rework_link` | 실행 | TRIGGERS_REWORK |
| `safety_risk_assessment` | 분석 | 위험 점수 + 권고 |

새 스킬 추가 절차는 [Ch.09 Development](./09-development.md).

---

## 6.4 v4 — 4 회복탄력성 에이전트

`src/v4/healing_agents.py`에 정의된 운영 에이전트.

| 에이전트 | 7-페이즈에서 어디에 |
|---|---|
| **AnomalyDetector** | DETECT 페이즈 보조 |
| **RootCauseAnalyzer** | DIAGNOSE 페이즈 보조 |
| **AutoRecoveryAgent** | RECOVER 페이즈 (액션 실행) |
| **ResilienceOrchestrator** | 페이즈 간 협업 조정 |

이들은 v3 토론 에이전트와 달리 *서로 토론하지 않음*. 각자 7-페이즈의 단일 책임을 수행하며, ResilienceOrchestrator만 흐름을 조율.

---

## 6.5 LLM Hybrid Agentic

`src/v4/llm_orchestrator.py`의 `LLMOrchestrator`는 *복잡도*에 따라 rule-based vs LLM 분기:

```
복잡도 = anomaly_count × cross_step_count × novelty_score
↓
- LOW   → 규칙 기반 진단 (빠름, 토큰 0)
- MED   → 규칙 + LLM 보강 (양쪽 융합)
- HIGH  → LLM 우선 (자연어 진단)
```

LLM 결과는 항상 confidence cap 적용 — 환각 방지. API key 없거나 호출 실패 시 자동 오프라인 폴백.

지원 모델:
- Anthropic Claude (`anthropic` SDK)
- OpenAI (`openai` SDK)

캐시는 `analyst/cache.py`. 동일 입력 동일 응답 보장.

---

## 6.6 새 v3 에이전트 추가 (5 단계)

1. `src/v3/agents.py`에 `BaseAgent` 상속 클래스 작성
2. `observe()`, `propose()`, `critique()`, `vote()` 4 메서드 구현
3. `create_agents()` 함수에 등록
4. (필요 시) 새 스킬은 `src/v3/skills.py` + `create_skill_registry()`
5. v3 하네스 실행 후 trust_score 변동 관찰

자세한 절차/예제는 [Ch.09 Development](./09-development.md).

---

## 6.7 Anti-pattern

🔴 다음은 본 프로젝트에서 명시적으로 금지:

- **에이전트가 다중 역할 가지기** — 단일 책임 원칙 위반
- **하드코딩된 if-else 판단** — 9.8 원칙 위반. 그래프 쿼리로 표현
- **trust_score 직접 조작** — 진화 메커니즘 깨짐
- **APPROVAL_THRESHOLD 우회** — 신뢰 시스템 의의 손상
- **LLM 결과를 confidence cap 없이 적용** — 환각 위험

---

## 6.8 다음 → 사용자가 직접 보는 화면

이제 그래프, 페이즈, 에이전트가 *서버 측*에서 어떻게 협력하는지 봤으니, 다음은 **사용자가 보는 6 페이지의 기능 카탈로그**입니다.

---

← [05. 7-Phase Loop](./05-7phase-loop.md) | [목차](./00-toc.md) | 다음 → [07. Features](./07-features.md)
