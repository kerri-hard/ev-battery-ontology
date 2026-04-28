# Ch.04 Ontology — 그래프 스키마와 Cypher 패턴

← [03. Architecture](./03-architecture.md) | [목차](./00-toc.md) | 다음 → [05. 7-Phase Loop](./05-7phase-loop.md)

---

## 4.1 왜 그래프인가

전통적 RDB로는 표현하기 어려운 두 종류의 질문이 본 도메인에 자주 등장합니다:

1. **"이 incident와 인과적으로 연결된 모든 step은?"** → 다중 hop traversal
2. **"이 결함 모드와 같은 root cause를 공유하는 과거 사례는?"** → 패턴 매칭

Kuzu(임베디드 그래프 DB)는 Cypher 쿼리로 두 질문을 직접 표현 가능. 본 시스템은 이 강점을 100% 활용합니다.

---

## 4.2 4-Layer 스키마 개요

| 계층 | 무엇 | 진실 출처 |
|---|---|---|
| **L1 도메인** | 공정, 설비, 자재, 품질 | `data/graph_data.json` |
| **L2 확장** | 결함 모드, 자동화, 정비 계획 | v3 토론 결과 |
| **L3 인과** | CausalRule, FailureChain, Incident | `causal.py`, `causal_discovery.py` |
| **L4 거버넌스** | EscalationPolicy, ProductionBatch, RUL | `decision_layer.py`, `traceability.py` |

---

## 4.3 노드 타입 (전체 12종)

### L1-L2 노드 (8종)

| 노드 | 용도 | 핵심 속성 |
|---|---|---|
| `ProcessArea` | 5 공정영역 (PA-100~500) | id, name, sequence |
| `ProcessStep` | 31 공정 스텝 | id, yield_rate, oee, sigma_level, safety_level |
| `Equipment` | 설비 | id, mtbf_hours, mttr_hours |
| `Material` | 자재 | id, cost, supplier, lead_time_days |
| `QualitySpec` | 품질 규격 | id, name, target, tolerance |
| `DefectMode` | 결함 모드 (FMEA) | id, severity, occurrence, detection, rpn |
| `AutomationPlan` | 자동화 계획 | id, roi, payback_months |
| `MaintenancePlan` | 정비 계획 | id, frequency_days, kind |

### L3 노드 (4종)

| 노드 | 용도 | 핵심 속성 |
|---|---|---|
| `CausalRule` | 인과 규칙 | id, cause_type, effect_type, strength, confirmation_count |
| `AnomalyPattern` | 이상 패턴 | type (drift / spike / oscillation / level_shift / variance_increase) |
| `FailureChain` | 과거 확인된 인과 체인 | success_count, fail_count, avg_recovery_sec |
| `Incident` | 장애 이력 | id, step_id, root_cause, recovery_action, resolved, timestamp |

### L4 노드 (4종)

| 노드 | 용도 | 핵심 속성 |
|---|---|---|
| `EscalationPolicy` | HITL 정책 | min_confidence, high_risk_threshold |
| `RecoveryAction` | 적용 액션 이력 | id, kind, params, success |
| `ProductionBatch` | 추적 단위 | batch_id, lot_id, timestamp |
| `RULEstimate` | Weibull RUL | equipment_id, eta_days, confidence |

---

## 4.4 관계 (약 20종)

### 공정 흐름

| 관계 | from → to | 의미 |
|---|---|---|
| `NEXT_STEP` | ProcessStep → ProcessStep | 다음 단계 (선형 흐름) |
| `FEEDS_INTO` | ProcessStep → ProcessStep | 산출물 공급 |
| `PARALLEL_WITH` | ProcessStep → ProcessStep | 병행 가능 |
| `TRIGGERS_REWORK` | ProcessStep → ProcessStep | 재작업 경로 |

### 구조

| 관계 | from → to | 의미 |
|---|---|---|
| `BELONGS_TO` | ProcessStep → ProcessArea | 공정영역 소속 |
| `USES_EQUIPMENT` | ProcessStep → Equipment | 사용 설비 |
| `CONSUMES` | ProcessStep → Material | 소비 자재 |
| `REQUIRES_SPEC` | ProcessStep → QualitySpec | 품질 요구 |

### L2 확장

| 관계 | from → to | 의미 |
|---|---|---|
| `HAS_DEFECT` | ProcessStep → DefectMode | 가능 결함 |
| `PREVENTS` | QualitySpec → DefectMode | 방지 |
| `PLANNED_UPGRADE` | ProcessStep → AutomationPlan | 자동화 계획 |
| `HAS_MAINTENANCE` | Equipment → MaintenancePlan | 정비 계획 |
| `DEPENDS_ON` | Material → Material | 자재 의존 |
| `INSPECTS` | ProcessStep → DefectMode | 검사 대상 |

### L3 인과

| 관계 | from → to | 의미 |
|---|---|---|
| `CAUSES` | CausalRule → CausalRule | 인과 chain |
| `HAS_CAUSE` | Incident → CausalRule | RCA |
| `HAS_PATTERN` | Incident → AnomalyPattern | 이상 유형 |
| `MATCHED_BY` | Incident → FailureChain | 과거 매칭 |
| `CHAIN_USES` | FailureChain → CausalRule | 체인 구성 |
| `PREDICTS` | CausalRule → DefectMode | 결함 예측 |

### L4 거버넌스

| 관계 | from → to | 의미 |
|---|---|---|
| `ESCALATES_TO` | RecoveryAction → EscalationPolicy | HITL 트리거 |
| `RESOLVED_BY` | Incident → RecoveryAction | 해결 액션 |
| `HAS_INCIDENT` | ProcessStep → Incident | 장애 이력 |
| `BATCH_INCIDENT` | ProductionBatch → Incident | 추적성 |

---

## 4.5 자주 쓰는 Cypher 패턴

### 패턴 1 — 특정 step의 가능 결함 모드

```cypher
MATCH (s:ProcessStep {id: 'PS-203'})-[:HAS_DEFECT]->(d:DefectMode)
RETURN d.id, d.name, d.rpn ORDER BY d.rpn DESC
```

### 패턴 2 — RCA: incident에서 인과 chain 역추적

```cypher
MATCH (i:Incident {id: $incident_id})-[:HAS_CAUSE]->(c1:CausalRule)
MATCH path = (c1)-[:CAUSES*1..3]->(cN:CausalRule)
RETURN path
```

### 패턴 3 — FailureChain 매칭 (과거 유사 사례)

```cypher
MATCH (i:Incident {id: $incident_id})-[:HAS_PATTERN]->(p:AnomalyPattern)
MATCH (fc:FailureChain)-[:CHAIN_USES]->(c:CausalRule)<-[:HAS_CAUSE]-(i_old:Incident)-[:HAS_PATTERN]->(p)
WHERE i_old.resolved = true
RETURN fc.id, fc.success_count, fc.avg_recovery_sec
ORDER BY fc.success_count DESC LIMIT 3
```

### 패턴 4 — 병목 step 찾기

```cypher
MATCH (s:ProcessStep)
WHERE s.yield_rate < 0.99
RETURN s.id, s.name, s.yield_rate ORDER BY s.yield_rate ASC
```

### 패턴 5 — cross-process 영향 분석

```cypher
MATCH (s1:ProcessStep {id: 'PS-203'})-[:FEEDS_INTO|TRIGGERS_REWORK*1..2]->(s2:ProcessStep)
RETURN DISTINCT s2.id, s2.name
```

---

## 4.6 스키마 확장 규칙

새 노드/관계를 추가할 때 반드시 지킬 것:

1. **이름은 의미 명확히** — `RELATED_TO` 같은 모호한 관계는 🔴 금지
2. **속성은 정량적** — 측정 가능한 값
3. **idempotent 확장** — `try ... except: pass` 패턴으로 재실행 안전
4. **VISION L1-L4 구조 준수** — 어느 계층에 속하는지 PR 설명에 명시

확장 코드 예 (`extend_schema_*` 패턴):

```python
def extend_schema_for_x(conn):
    try:
        conn.execute("CREATE NODE TABLE NewNode (id STRING, ..., PRIMARY KEY (id))")
    except Exception:
        pass  # idempotent
    try:
        conn.execute("CREATE REL TABLE NEW_REL (FROM NodeA TO NodeB)")
    except Exception:
        pass
```

---

## 4.7 Kuzu 사용 팁

- **DB 경로**는 환경변수 또는 인자로 받기. 🔴 하드코딩 금지
- **트랜잭션** — 여러 노드/관계 추가 시 `conn.execute()` 순서 주의
- **버전** — Kuzu는 빠르게 발전 중. 마이그레이션은 `extend_schema` 함수에 명시

---

## 4.8 다음 → 그래프가 살아 움직이는 7-페이즈 루프

지금까지는 *정적 스키마*. 다음 챕터는 이 그래프가 **사이클마다 어떻게 읽히고 갱신되는지**입니다.

---

← [03. Architecture](./03-architecture.md) | [목차](./00-toc.md) | 다음 → [05. 7-Phase Loop](./05-7phase-loop.md)
